"""
Submit service for handling file submission requests.
Processes file submissions, updates database, and sends email notifications to users.
"""

import logging
from typing import Dict, Any, Optional

from app.models.email import DocumentInfo
from app.services.email_service import email_service
from app.services.transaction_update_service import transaction_update_service

logger = logging.getLogger(__name__)


class SubmitService:
    """Service for handling file submission logic and email notifications."""

    async def process_submission(
        self,
        file_name: str,
        file_url: str,
        user_email: str,
        company_name: str,
        transaction_id: str
    ) -> Dict[str, Any]:
        """
        Process file submission request with database update and email notification.

        Flow:
        1. Determine customer type (Individual vs Enterprise)
        2. Update appropriate MongoDB collection
        3. Check if all documents are complete
        4. Send email notification with all documents
        5. Return success with email status

        Args:
            file_name: Name of the translated file
            file_url: Google Drive URL of translated file
            user_email: Email of the user
            company_name: Company name ("Ind" for individuals)
            transaction_id: Transaction ID to update

        Returns:
            Dictionary containing status, message, and email info
        """
        logger.info(
            f"Processing submission - File: {file_name}, Transaction: {transaction_id}, "
            f"Company: {company_name}, Email: {user_email}"
        )

        try:
            # Step 1: Determine customer type
            is_enterprise = company_name != "Ind"
            customer_type = "enterprise" if is_enterprise else "individual"

            logger.info(f"Customer type: {customer_type}")

            # Step 2: Update database
            if is_enterprise:
                update_result = await transaction_update_service.update_enterprise_transaction(
                    transaction_id=transaction_id,
                    file_name=file_name,
                    file_url=file_url
                )
            else:
                update_result = await transaction_update_service.update_individual_transaction(
                    transaction_id=transaction_id,
                    file_name=file_name,
                    file_url=file_url
                )

            # Check if database update failed
            if not update_result.get("success"):
                logger.error(f"Database update failed: {update_result.get('error')}")
                return {
                    "status": "error",
                    "message": update_result.get("error", "Database update failed"),
                    "transaction_id": transaction_id,
                    "email_sent": False
                }

            logger.info(f"Database updated successfully for transaction {transaction_id}")

            # Step 3: Check if all documents are complete
            all_complete = await transaction_update_service.check_transaction_complete(
                transaction_id=transaction_id,
                is_enterprise=is_enterprise
            )

            # Step 4: Prepare email notification
            # Get updated transaction with all documents
            transaction = update_result.get("transaction")

            if not transaction:
                logger.warning("Transaction data not available for email")
                return {
                    "status": "success",
                    "message": f"Document updated but email not sent (transaction data unavailable)",
                    "transaction_id": transaction_id,
                    "translated_url": update_result.get("translated_url"),
                    "email_sent": False
                }

            # Build documents list for email
            documents = []
            for doc in transaction.get("documents", []):
                # Only include documents that have been translated
                if doc.get("translated_url"):
                    documents.append(
                        DocumentInfo(
                            document_name=doc.get("file_name", ""),
                            original_url=doc.get("original_url", ""),
                            translated_url=doc.get("translated_url", "")
                        )
                    )

            # Only send email if we have translated documents
            if not documents:
                logger.warning(f"No translated documents found for transaction {transaction_id}")
                return {
                    "status": "success",
                    "message": "Document updated but no translated documents available for email",
                    "transaction_id": transaction_id,
                    "email_sent": False
                }

            # Get completion counters
            completed_docs = transaction.get("completed_documents", 0)
            total_docs = transaction.get("total_documents", len(transaction.get("documents", [])))

            # Log email gate evaluation
            logger.info(
                f"EMAIL GATE EVALUATION - Transaction {transaction_id}",
                extra={
                    "transaction_id": transaction_id,
                    "file_name": file_name,
                    "completed_documents": completed_docs,
                    "total_documents": total_docs,
                    "will_send_email": completed_docs >= total_docs,
                    "documents_in_transaction": len(transaction.get("documents", [])),
                    "translated_documents_in_email": len(documents)
                }
            )

            # EMAIL GATE: Only send email if ALL documents are complete
            if completed_docs < total_docs:
                logger.info(
                    f"BLOCKING EMAIL - Transaction {transaction_id} incomplete: {completed_docs}/{total_docs} documents ready. "
                    f"Email will be sent when all are complete.",
                    extra={
                        "transaction_id": transaction_id,
                        "file_name": file_name,
                        "completed_documents": completed_docs,
                        "total_documents": total_docs,
                        "reason": f"completed_docs({completed_docs}) < total_docs({total_docs})"
                    }
                )
                return {
                    "status": "success",
                    "message": f"Document updated ({completed_docs}/{total_docs} complete). Email pending.",
                    "transaction_id": transaction_id,
                    "document_name": file_name,
                    "translated_url": update_result.get("translated_url"),
                    "translated_name": update_result.get("translated_name"),
                    "all_documents_complete": False,
                    "completed_documents": completed_docs,
                    "total_documents": total_docs,
                    "documents_count": len(documents),
                    "email_sent": False
                }

            # Extract user name from transaction or email
            user_name = self._extract_user_name(transaction, user_email)

            # Step 5: Send email notification (ONLY when ALL documents complete)
            logger.info(
                f"EMAIL GATE PASSED - All {total_docs} documents complete for transaction {transaction_id}. "
                f"Sending email notification to {user_email} with {len(documents)} document(s)",
                extra={
                    "transaction_id": transaction_id,
                    "completed_documents": completed_docs,
                    "total_documents": total_docs,
                    "documents_in_email": len(documents),
                    "user_email": user_email
                }
            )
            logger.info(f"Sending email notification to {user_email} with {len(documents)} document(s)")

            email_result = email_service.send_translation_notification(
                documents=documents,
                user_name=user_name,
                user_email=user_email,
                company_name=company_name
            )

            if email_result.success:
                logger.info(f"Email notification sent successfully to {user_email}")
                return {
                    "status": "success",
                    "message": f"All {total_docs} documents complete. Notification sent to {user_email}",
                    "transaction_id": transaction_id,
                    "document_name": file_name,
                    "translated_url": update_result.get("translated_url"),
                    "translated_name": update_result.get("translated_name"),
                    "all_documents_complete": True,
                    "completed_documents": completed_docs,
                    "total_documents": total_docs,
                    "documents_count": len(documents),
                    "email_sent": True
                }
            else:
                # Email failed, but database update succeeded
                logger.warning(f"Email notification failed: {email_result.error}")
                return {
                    "status": "success",
                    "message": f"All documents complete but email notification failed: {email_result.error}",
                    "transaction_id": transaction_id,
                    "document_name": file_name,
                    "translated_url": update_result.get("translated_url"),
                    "translated_name": update_result.get("translated_name"),
                    "all_documents_complete": True,
                    "completed_documents": completed_docs,
                    "total_documents": total_docs,
                    "documents_count": len(documents),
                    "email_sent": False,
                    "email_error": email_result.error
                }

        except Exception as e:
            logger.error(f"Error processing submission: {e}", exc_info=True)
            return {
                "status": "error",
                "message": f"Error processing submission: {str(e)}",
                "transaction_id": transaction_id,
                "email_sent": False
            }

    def _extract_user_name(self, transaction: dict, user_email: str) -> str:
        """
        Extract user name from transaction or email.

        Args:
            transaction: Transaction document
            user_email: User's email address

        Returns:
            str: User's name
        """
        # Try to get from transaction
        user_name = transaction.get("user_name")

        # Check for non-empty string (handle empty strings and whitespace)
        if user_name and user_name.strip():
            return user_name.strip()

        # Extract from user_id or email
        user_id = transaction.get("user_id", user_email)

        # Simple extraction from email
        try:
            username = user_id.split('@')[0]
            parts = username.replace('_', '.').replace('-', '.').split('.')
            name = ' '.join(word.capitalize() for word in parts)
            return name
        except Exception:
            return "User"


# Create singleton instance
submit_service = SubmitService()
