"""
Submit endpoint for handling file submission requests from clients.
"""

import logging
from fastapi import APIRouter, HTTPException, status as http_status
from fastapi.responses import JSONResponse

from app.models.requests import SubmitRequest
from app.models.responses import SubmitSuccessResponse, SubmitErrorResponse
from app.services.submit_service import submit_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Submit"])


@router.post(
    "/submit",
    responses={
        200: {"model": SubmitSuccessResponse, "description": "Successful submission"},
        400: {"model": SubmitErrorResponse, "description": "Validation error"},
        404: {"model": SubmitErrorResponse, "description": "Transaction or document not found"},
        500: {"model": SubmitErrorResponse, "description": "Database or server error"}
    }
)
async def submit_file(request: SubmitRequest):
    """
    Submit a translated file and update transaction database.

    This endpoint receives file submission requests from clients with translated file
    information. It updates the appropriate MongoDB collection (translation_transactions
    for enterprise, user_transactions for individuals) and sends email notifications.

    **Request Body:**
    - file_name: Name of the translated file (required)
    - file_url: Google Drive URL of translated file (required)
    - user_email: User's email address (required)
    - company_name: Company name - "Ind" for individuals, else enterprise (required)
    - transaction_id: Transaction ID to update (required)

    **Responses:**
    - 200: Success with transaction details and email status
    - 400: Bad request with validation error
    - 404: Transaction or document not found
    - 500: Database or server error
    """
    logger.info(
        f"Submit request received - File: {request.file_name}, "
        f"User: {request.user_email}, Company: {request.company_name}, "
        f"Transaction ID: {request.transaction_id or 'None'}"
    )

    try:
        # Process the submission using the service
        result = await submit_service.process_submission(
            file_name=request.file_name,
            file_url=request.file_url,
            user_email=request.user_email,
            company_name=request.company_name,
            transaction_id=request.transaction_id
        )

        # Check if service returned an error
        if result.get("status") == "error":
            error_message = result.get("message", "Unknown error")

            # Determine appropriate HTTP status code based on error type
            if "not found" in error_message.lower():
                # Transaction or document not found -> 404
                logger.warning(f"Resource not found: {error_message}")
                return JSONResponse(
                    content={
                        "error": error_message,
                        "transaction_id": result.get("transaction_id")
                    },
                    status_code=http_status.HTTP_404_NOT_FOUND
                )
            else:
                # Database or other server error -> 500
                logger.error(f"Service error: {error_message}")
                return JSONResponse(
                    content={
                        "error": error_message,
                        "transaction_id": result.get("transaction_id")
                    },
                    status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        # Return enhanced success response
        response_data = {
            "status": result["status"],
            "message": result["message"],
            "transaction_id": result.get("transaction_id"),
            "document_name": result.get("document_name"),
            "translated_url": result.get("translated_url"),
            "email_sent": result.get("email_sent", False)
        }

        # Add optional fields if present
        if "translated_name" in result:
            response_data["translated_name"] = result["translated_name"]
        if "all_documents_complete" in result:
            response_data["all_documents_complete"] = result["all_documents_complete"]
        if "documents_count" in result:
            response_data["documents_count"] = result["documents_count"]
        if "email_error" in result:
            response_data["email_error"] = result["email_error"]

        logger.info(
            f"Submit request successful for {request.file_name} "
            f"(Transaction: {result.get('transaction_id')}, Email sent: {result.get('email_sent')})"
        )
        return JSONResponse(content=response_data, status_code=200)

    except ValueError as e:
        # Handle validation errors (400 Bad Request)
        logger.warning(f"Validation error in submit request: {e}")
        return JSONResponse(
            content={"error": str(e)},
            status_code=http_status.HTTP_400_BAD_REQUEST
        )

    except Exception as e:
        # Handle unexpected errors (500 Internal Server Error)
        logger.error(f"Error processing submit request: {e}", exc_info=True)
        return JSONResponse(
            content={"error": f"Internal server error: {str(e)}"},
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR
        )
