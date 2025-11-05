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
    try:
        logger.info("Fetching all companies")

        # Fetch all companies from database
        companies = await database.company.find({}).to_list(length=None)

        # Serialize all companies
        companies = [serialize_company_for_json(company) for company in companies]

        logger.info(f"Found {len(companies)} companies")

        return JSONResponse(content={
            "success": True,
            "data": {
                "companies": companies,
                "count": len(companies)
            }
        })

    except Exception as e:
        logger.error(f"Failed to retrieve companies: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve companies: {str(e)}"
        )
