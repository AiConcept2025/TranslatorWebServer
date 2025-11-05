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
        400: {"model": SubmitErrorResponse, "description": "Bad request"},
        500: {"model": SubmitErrorResponse, "description": "Server error"}
    }
)
async def submit_file(request: SubmitRequest):
    """
    Submit a file for processing.

    This endpoint receives file submission requests from clients with file information
    and user details.

    **Request Body:**
    - file_name: Name of the file (required)
    - file_url: Google Drive shareable URL (required)
    - user_email: User's email address (required)
    - company_name: Company name (required)
    - transaction_id: Optional transaction ID

    **Responses:**
    - 200: Success with status and message
    - 400: Bad request with error message
    - 500: Server error with error message
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

        # Return success response
        response_data = {
            "status": result["status"],
            "message": result["message"]
        }

        logger.info(f"Submit request successful for {request.file_name}")
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
