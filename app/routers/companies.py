"""
Company management router for retrieving and managing company records.
"""

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
from typing import List
import logging

from app.database.mongodb import database

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/companies",
    tags=["Companies"]
)


def serialize_company_for_json(company: dict) -> dict:
    """Convert MongoDB company to JSON-serializable dict."""
    if "_id" in company:
        company["_id"] = str(company["_id"])

    # Convert datetime fields if present
    datetime_fields = ["created_at", "updated_at"]
    for field in datetime_fields:
        if field in company and hasattr(company[field], "isoformat"):
            company[field] = company[field].isoformat()

    return company


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Successfully retrieved companies",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "data": {
                            "companies": [
                                {
                                    "_id": "690023c7eb2bceb90e274133",
                                    "company_name": "Iris Trading",
                                    "description": "Trading company",
                                    "address": {
                                        "address0": "1325 Adams Street",
                                        "address1": "",
                                        "postal_code": "07030",
                                        "state": "NJ",
                                        "city": "Hoboken",
                                        "country": "USA"
                                    },
                                    "contact_person": {
                                        "name": "Contact Name",
                                        "type": "Primary Contact"
                                    },
                                    "phone_number": ["267-987-6305"],
                                    "company_url": [],
                                    "line_of_business": "Trading",
                                    "created_at": "2025-10-28T02:00:39.873000",
                                    "updated_at": "2025-10-31T21:01:29.174000"
                                }
                            ],
                            "count": 1
                        }
                    }
                }
            }
        },
        500: {
            "description": "Internal server error"
        }
    }
)
async def get_all_companies():
    """
    Get all companies from the database.

    Returns full company objects with all fields including address, contact info, etc.
    """
    from datetime import datetime, timezone

    try:
        timestamp = datetime.now(timezone.utc).isoformat()
        logger.info(f"🔍 [{timestamp}] GET /api/v1/companies - START")
        logger.info(f"📥 Request Parameters: None (fetching all companies)")

        # Fetch all companies from database
        logger.info(f"🔄 Calling database.company.find()...")
        companies = await database.company.find({}).to_list(length=None)
        logger.info(f"🔎 Database Query Result: count={len(companies)}")

        # Serialize all companies
        logger.info(f"🔄 Serializing {len(companies)} companies...")
        companies = [serialize_company_for_json(company) for company in companies]

        if companies:
            logger.info(f"📊 Sample Company: name={companies[0].get('company_name')}, "
                       f"_id={companies[0].get('_id')}")

        logger.info(f"✅ Companies retrieved successfully: count={len(companies)}")

        response_data = {
            "success": True,
            "data": {
                "companies": companies,
                "count": len(companies)
            }
        }
        logger.info(f"📤 Response: success=True, count={len(companies)}")

        return JSONResponse(content=response_data)

    except Exception as e:
        logger.error(f"❌ Failed to retrieve companies:", exc_info=True)
        logger.error(f"   - Error: {str(e)}")
        logger.error(f"   - Error type: {type(e).__name__}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve companies: {str(e)}"
        )


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Company created successfully"},
        400: {"description": "Company already exists or invalid data"},
        500: {"description": "Internal server error"}
    }
)
async def create_company(company_data: dict):
    """
    Create a new company in the database.

    Args:
        company_data: Dictionary with company fields (company_name is required)

    Returns:
        Created company object with generated _id
    """
    from datetime import datetime, timezone

    try:
        timestamp = datetime.now(timezone.utc).isoformat()
        logger.info(f"🔍 [{timestamp}] POST /api/v1/companies - START")
        logger.info(f"📨 Request Data: {company_data}")

        # Validate required field
        if not company_data.get("company_name"):
            logger.warning("❌ Missing required field: company_name")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="company_name is required"
            )

        company_name = company_data["company_name"]

        # Check if company already exists
        logger.info(f"🔄 Checking if company already exists: {company_name}")
        existing_company = await database.company.find_one({"company_name": company_name})

        if existing_company:
            logger.warning(f"❌ Company already exists: {company_name}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Company already exists: {company_name}"
            )

        # Add timestamps
        now = datetime.now(timezone.utc)
        company_data["created_at"] = now
        company_data["updated_at"] = now

        # Insert company into database
        logger.info(f"🔄 Inserting new company: {company_name}")
        result = await database.company.insert_one(company_data)

        # Fetch created company
        created_company = await database.company.find_one({"_id": result.inserted_id})
        created_company = serialize_company_for_json(created_company)

        logger.info(f"✅ Company created successfully: {company_name}, _id={created_company.get('_id')}")
        logger.info(f"📤 Response: success=True")

        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={
                "success": True,
                "data": created_company
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to create company:", exc_info=True)
        logger.error(f"   - Error: {str(e)}")
        logger.error(f"   - Error type: {type(e).__name__}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create company: {str(e)}"
        )


@router.patch(
    "/{company_name}",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Company updated successfully"},
        404: {"description": "Company not found"},
        500: {"description": "Internal server error"}
    }
)
async def update_company(company_name: str, update_data: dict):
    """
    Update company information.

    Updates company fields in the database. Supports partial updates.

    Args:
        company_name: The name of the company to update
        update_data: Dictionary with fields to update

    Returns:
        Updated company object
    """
    from datetime import datetime, timezone

    try:
        timestamp = datetime.now(timezone.utc).isoformat()
        logger.info(f"🔍 [{timestamp}] PATCH /api/v1/companies/{company_name} - START")
        logger.info(f"📥 Request Parameters:")
        logger.info(f"   - company_name: {company_name}")
        logger.info(f"📨 Update Data: {update_data}")

        # Check if company exists
        logger.info(f"🔄 Checking if company exists...")
        existing_company = await database.company.find_one({"company_name": company_name})

        if not existing_company:
            logger.warning(f"❌ Company not found: {company_name}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Company not found: {company_name}"
            )

        logger.info(f"✅ Company found: {company_name}")

        # Remove immutable/metadata fields that should not be updated
        fields_to_remove = ["_id", "created_at"]
        for field in fields_to_remove:
            if field in update_data:
                logger.info(f"🗑️ Removing immutable field from update: {field}")
                del update_data[field]

        # Add updated_at timestamp
        update_data["updated_at"] = datetime.now(timezone.utc)

        # Update company in database
        logger.info(f"🔄 Updating company in database...")
        logger.info(f"📨 Final update data keys: {list(update_data.keys())}")
        result = await database.company.update_one(
            {"company_name": company_name},
            {"$set": update_data}
        )

        if result.modified_count == 0:
            logger.warning(f"⚠️ No changes made to company: {company_name}")
        else:
            logger.info(f"✅ Company updated: modified_count={result.modified_count}")

        # Fetch updated company
        updated_company = await database.company.find_one({"company_name": update_data.get("company_name", company_name)})
        updated_company = serialize_company_for_json(updated_company)

        logger.info(f"📤 Response: company_name={updated_company.get('company_name')}")

        return JSONResponse(content={
            "success": True,
            "data": updated_company
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to update company:", exc_info=True)
        logger.error(f"   - Error: {str(e)}")
        logger.error(f"   - Error type: {type(e).__name__}")
        logger.error(f"   - Company: {company_name}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update company: {str(e)}"
        )
