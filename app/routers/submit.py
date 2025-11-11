"""
Submit endpoint for handling file submission requests from clients.
"""

import logging
import time
from typing import Dict, Tuple, Optional
from fastapi import APIRouter, HTTPException, status as http_status, Depends
from fastapi.responses import JSONResponse

from app.models.requests import SubmitRequest
from app.models.responses import SubmitSuccessResponse, SubmitErrorResponse
from app.services.submit_service import submit_service
from app.middleware.auth_middleware import get_current_user, get_optional_user

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Submit"])

# Webhook Deduplication Cache
# Prevents duplicate webhook processing when GoogleTranslator sends multiple requests
# for the same file translation (which was causing 7 emails for 3 documents)
# Key: (transaction_id, file_name, file_url) -> (timestamp, result)
# TTL: 300 seconds (5 minutes) - enough to handle translator retries but not too long
_webhook_cache: Dict[Tuple[str, str, str], Tuple[float, dict]] = {}
_CACHE_TTL_SECONDS = 300  # 5 minutes


def _cleanup_expired_cache_entries():
    """Remove expired entries from webhook cache (older than TTL)."""
    current_time = time.time()
    expired_keys = [
        key for key, (timestamp, _) in _webhook_cache.items()
        if current_time - timestamp > _CACHE_TTL_SECONDS
    ]
    for key in expired_keys:
        del _webhook_cache[key]
        logger.debug(f"Cleaned up expired webhook cache entry: {key[0]}:{key[1]}")


def _check_webhook_cache(transaction_id: str, file_name: str, file_url: str) -> dict | None:
    """
    Check if webhook was already processed recently.

    Args:
        transaction_id: Transaction ID
        file_name: File name
        file_url: Translated file URL

    Returns:
        Cached result if found and not expired, None otherwise
    """
    cache_key = (transaction_id, file_name, file_url)
    current_time = time.time()

    # Cleanup expired entries periodically (every 10th request)
    if len(_webhook_cache) % 10 == 0:
        _cleanup_expired_cache_entries()

    # Check if entry exists and is not expired
    if cache_key in _webhook_cache:
        timestamp, result = _webhook_cache[cache_key]
        if current_time - timestamp <= _CACHE_TTL_SECONDS:
            logger.info(
                f"🔄 WEBHOOK DEDUPLICATION - Found cached result for {file_name} "
                f"(age: {int(current_time - timestamp)}s)"
            )
            return result

    return None


def _cache_webhook_result(transaction_id: str, file_name: str, file_url: str, result: dict):
    """
    Cache webhook processing result.

    Args:
        transaction_id: Transaction ID
        file_name: File name
        file_url: Translated file URL
        result: Processing result to cache
    """
    cache_key = (transaction_id, file_name, file_url)
    _webhook_cache[cache_key] = (time.time(), result)
    logger.debug(f"Cached webhook result for {transaction_id}:{file_name}")


@router.post(
    "/submit",
    responses={
        200: {"model": SubmitSuccessResponse, "description": "Successful submission"},
        400: {"model": SubmitErrorResponse, "description": "Validation error"},
        404: {"model": SubmitErrorResponse, "description": "Transaction or document not found"},
        500: {"model": SubmitErrorResponse, "description": "Database or server error"}
    }
)
async def submit_file(
    request: SubmitRequest,
    current_user: Optional[dict] = Depends(get_optional_user)
):
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
    # Enhanced request logging with all parameters
    logger.info("=" * 80)
    logger.info("SUBMIT ENDPOINT - Incoming Request")
    logger.info("=" * 80)

    # Log authentication status
    if current_user:
        logger.info(
            f"🔐 Authenticated user: {current_user['email']} "
            f"(permission: {current_user.get('permission_level', 'user')})"
        )
    else:
        logger.info("🌐 External webhook call (no user authentication)")

    logger.info(
        f"Submit request received - File: {request.file_name}, "
        f"User: {request.user_email}, Company: {request.company_name}, "
        f"Transaction ID: {request.transaction_id or 'None'}"
    )

    # Comprehensive request parameter logging
    logger.debug(
        "INCOMING REQUEST PARAMETERS",
        extra={
            "file_name": request.file_name,
            "file_url": request.file_url,
            "transaction_id": request.transaction_id,
            "company_name": request.company_name,
            "user_email": request.user_email,
            "is_enterprise": request.company_name != "Ind",
            "customer_type": "enterprise" if request.company_name != "Ind" else "individual",
            "file_url_length": len(request.file_url),
            "request_timestamp": time.time(),
            "authenticated_user": current_user.get('email') if current_user else None,
            "authentication_method": "session_token" if current_user else "webhook_callback"
        }
    )

    # Log full request as JSON for complete debugging
    logger.debug(
        f"Full request body: {request.model_dump_json(indent=2)}"
    )

    # Check webhook deduplication cache FIRST (before any processing)
    # This prevents duplicate processing when GoogleTranslator retries
    logger.debug(
        f"Checking webhook deduplication cache for {request.transaction_id}:{request.file_name}"
    )
    cached_result = _check_webhook_cache(
        request.transaction_id,
        request.file_name,
        request.file_url
    )
    if cached_result:
        logger.info(
            f"CACHE HIT - Returning cached result for {request.file_name} "
            f"(prevented duplicate webhook processing)"
        )
        logger.debug(f"Cached result: {cached_result}")
        return JSONResponse(content=cached_result, status_code=200)

    logger.debug(f"CACHE MISS - Proceeding with request processing")

    try:
        # Process the submission using the service
        logger.info(f"Delegating to submit_service.process_submission for {request.transaction_id}")
        logger.debug(
            "Service call parameters",
            extra={
                "service": "submit_service",
                "method": "process_submission",
                "file_name": request.file_name,
                "file_url": request.file_url,
                "user_email": request.user_email,
                "company_name": request.company_name,
                "transaction_id": request.transaction_id
            }
        )

        result = await submit_service.process_submission(
            file_name=request.file_name,
            file_url=request.file_url,
            user_email=request.user_email,
            company_name=request.company_name,
            transaction_id=request.transaction_id
        )

        logger.debug(f"Service returned result with status: {result.get('status')}")
        logger.debug(f"Service result: {result}")

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
        if "completed_documents" in result:
            response_data["completed_documents"] = result["completed_documents"]
        if "total_documents" in result:
            response_data["total_documents"] = result["total_documents"]
        if "documents_count" in result:
            response_data["documents_count"] = result["documents_count"]
        if "email_error" in result:
            response_data["email_error"] = result["email_error"]

        logger.info(
            f"Submit request successful for {request.file_name} "
            f"(Transaction: {result.get('transaction_id')}, Email sent: {result.get('email_sent')})"
        )
        logger.debug(
            "Success response data",
            extra={
                "status_code": 200,
                "transaction_id": result.get('transaction_id'),
                "document_name": result.get('document_name'),
                "translated_url": result.get('translated_url'),
                "email_sent": result.get('email_sent'),
                "all_documents_complete": result.get('all_documents_complete'),
                "completed_documents": result.get('completed_documents'),
                "total_documents": result.get('total_documents')
            }
        )

        # Cache successful result to prevent duplicate webhook processing
        logger.debug(f"Caching successful result for {request.transaction_id}:{request.file_name}")
        _cache_webhook_result(request.transaction_id, request.file_name, request.file_url, response_data)

        logger.info("=" * 80)
        logger.info("SUBMIT ENDPOINT - Request Completed Successfully")
        logger.info("=" * 80)

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
