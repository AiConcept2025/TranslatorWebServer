"""
Submit service for handling file submission requests.
Processes file submissions, updates database, and sends email notifications to users.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone

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
        logger.info("=" * 80)
        logger.info("SUBMIT SERVICE - Processing Submission")
        logger.info("=" * 80)
        logger.info(
            f"Processing submission - File: {file_name}, Transaction: {transaction_id}, "
            f"Company: {company_name}, Email: {user_email}"
        )
        logger.debug(
            "Submission parameters",
            extra={
                "file_name": file_name,
                "file_url": file_url,
                "user_email": user_email,
                "company_name": company_name,
                "transaction_id": transaction_id,
                "file_url_length": len(file_url)
            }
        )

        try:
            # Step 1: Determine customer type
            is_enterprise = company_name != "Ind"
            customer_type = "enterprise" if is_enterprise else "individual"

            logger.info(f"STEP 1: Customer type determination - {customer_type}")
            logger.debug(
                "Customer type details",
                extra={
                    "company_name": company_name,
                    "is_enterprise": is_enterprise,
                    "customer_type": customer_type,
                    "target_collection": "translation_transactions" if is_enterprise else "user_transactions"
                }
            )

            # Step 2: Update database
            logger.info(f"STEP 2: Database update - {customer_type} transaction")
            logger.debug(
                f"Calling transaction_update_service.{'update_enterprise_transaction' if is_enterprise else 'update_individual_transaction'}",
                extra={
                    "service": "transaction_update_service",
                    "method": "update_enterprise_transaction" if is_enterprise else "update_individual_transaction",
                    "transaction_id": transaction_id,
                    "file_name": file_name,
                    "file_url": file_url
                }
            )

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

            logger.debug(
                f"Database update result received",
                extra={
                    "success": update_result.get("success"),
                    "transaction_id": transaction_id,
                    "update_result": update_result
                }
            )

            # Check if database update failed
            if not update_result.get("success"):
                logger.error(
                    f"Database update failed: {update_result.get('error')}",
                    extra={
                        "transaction_id": transaction_id,
                        "error": update_result.get('error'),
                        "update_result": update_result
                    }
                )
                return {
                    "status": "error",
                    "message": update_result.get("error", "Database update failed"),
                    "transaction_id": transaction_id,
                    "email_sent": False
                }

            logger.info(f"Database updated successfully for transaction {transaction_id}")
            logger.debug(
                "Database update success details",
                extra={
                    "transaction_id": transaction_id,
                    "document_name": update_result.get("document_name"),
                    "translated_url": update_result.get("translated_url"),
                    "translated_name": update_result.get("translated_name")
                }
            )

            # Step 3: Check if all documents are complete
            logger.info(f"STEP 3: Checking transaction completion status")
            logger.debug(
                f"Calling transaction_update_service.check_transaction_complete",
                extra={
                    "transaction_id": transaction_id,
                    "is_enterprise": is_enterprise
                }
            )

            all_complete = await transaction_update_service.check_transaction_complete(
                transaction_id=transaction_id,
                is_enterprise=is_enterprise
            )

            logger.info(f"Transaction completion check result: {all_complete}")

            # Step 4: Prepare email notification
            logger.info(f"STEP 4: Preparing email notification data")
            # Get updated transaction with all documents
            transaction = update_result.get("transaction")

            if not transaction:
                logger.warning(
                    "Transaction data not available for email",
                    extra={
                        "transaction_id": transaction_id,
                        "update_result_keys": list(update_result.keys())
                    }
                )
                return {
                    "status": "success",
                    "message": f"Document updated but email not sent (transaction data unavailable)",
                    "transaction_id": transaction_id,
                    "translated_url": update_result.get("translated_url"),
                    "email_sent": False
                }

            logger.debug(
                "Transaction data retrieved",
                extra={
                    "transaction_id": transaction_id,
                    "transaction_keys": list(transaction.keys()),
                    "document_count": len(transaction.get("documents", []))
                }
            )

            # Build documents list for email
            logger.debug(f"Building documents list from transaction")
            documents = []
            for idx, doc in enumerate(transaction.get("documents", [])):
                logger.debug(
                    f"Processing document {idx}",
                    extra={
                        "index": idx,
                        "file_name": doc.get("file_name"),
                        "has_translated_url": bool(doc.get("translated_url")),
                        "original_url": doc.get("original_url"),
                        "translated_url": doc.get("translated_url")
                    }
                )
                # Only include documents that have been translated
                if doc.get("translated_url"):
                    documents.append(
                        DocumentInfo(
                            document_name=doc.get("file_name", ""),
                            original_url=doc.get("original_url", ""),
                            translated_url=doc.get("translated_url", "")
                        )
                    )
                    logger.debug(f"Added document {idx} to email list: {doc.get('file_name')}")
                else:
                    logger.debug(f"Skipped document {idx} (no translated_url): {doc.get('file_name')}")

            logger.info(f"Built documents list: {len(documents)} translated document(s) ready for email")

            # Only send email if we have translated documents
            if not documents:
                logger.warning(
                    f"No translated documents found for transaction {transaction_id}",
                    extra={
                        "transaction_id": transaction_id,
                        "total_documents": len(transaction.get("documents", [])),
                        "reason": "No documents with translated_url found"
                    }
                )
                return {
                    "status": "success",
                    "message": "Document updated but no translated documents available for email",
                    "transaction_id": transaction_id,
                    "email_sent": False
                }

            # Get completion counters
            completed_docs = transaction.get("completed_documents", 0)
            total_docs = transaction.get("total_documents", len(transaction.get("documents", [])))
            batch_email_sent = transaction.get("batch_email_sent", False)

            # Enhanced email gate evaluation logging
            logger.info("=" * 80)
            logger.info("EMAIL BATCHING GATE CHECK")
            logger.info("=" * 80)
            logger.info(
                f"EMAIL GATE EVALUATION - Transaction {transaction_id}",
                extra={
                    "transaction_id": transaction_id,
                    "file_name": file_name,
                    "completed_documents": completed_docs,
                    "total_documents": total_docs,
                    "all_complete": completed_docs >= total_docs,
                    "batch_email_sent": batch_email_sent,
                    "will_send_email": completed_docs >= total_docs and not batch_email_sent,
                    "documents_in_transaction": len(transaction.get("documents", [])),
                    "translated_documents_in_email": len(documents)
                }
            )
            logger.info(f"Documents complete: {completed_docs}/{total_docs}")
            logger.info(f"Email already sent: {batch_email_sent}")
            logger.info(f"Will send email: {completed_docs >= total_docs and not batch_email_sent}")

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
            logger.info(f"STEP 5: Sending email notification")
            logger.info(
                f"EMAIL GATE PASSED - All {total_docs} documents complete for transaction {transaction_id}. "
                f"Sending email notification to {user_email} with {len(documents)} document(s)",
                extra={
                    "transaction_id": transaction_id,
                    "completed_documents": completed_docs,
                    "total_documents": total_docs,
                    "documents_in_email": len(documents),
                    "user_email": user_email,
                    "user_name": user_name,
                    "company_name": company_name
                }
            )
            logger.info(f"Sending email notification to {user_email} with {len(documents)} document(s)")
            logger.debug(
                "Email notification parameters",
                extra={
                    "service": "email_service",
                    "method": "send_translation_notification",
                    "documents_count": len(documents),
                    "documents": [
                        {
                            "document_name": doc.document_name,
                            "original_url": doc.original_url,
                            "translated_url": doc.translated_url
                        }
                        for doc in documents
                    ],
                    "user_name": user_name,
                    "user_email": user_email,
                    "company_name": company_name
                }
            )

            # Extract transaction metadata for email context
            # Get transaction_id from transaction (stripe_checkout_session_id for individuals, transaction_id for enterprise)
            txn_id = transaction.get("stripe_checkout_session_id") or transaction.get("transaction_id") or transaction_id
            # Get completion timestamp as current time (when all documents are done)
            completed_at = datetime.now(timezone.utc)
            # Get total document count
            total_docs_count = len(transaction.get("documents", []))

            logger.debug(
                "Email metadata extracted",
                extra={
                    "transaction_id": txn_id,
                    "completed_at": completed_at.isoformat(),
                    "total_documents": total_docs_count
                }
            )

            # Enhanced logging: Email content preview
            logger.info("=" * 80)
            logger.info("SENDING EMAIL - Content Preview")
            logger.info("=" * 80)
            logger.info(
                "Email details",
                extra={
                    "recipient": user_email,
                    "user_name": user_name,
                    "company_name": company_name,
                    "template": "individual_template.html" if company_name == "Ind" else "enterprise_template.html",
                    "transaction_id": txn_id,
                    "documents_count": len(documents)
                }
            )
            logger.info(f"To: {user_email}")
            logger.info(f"Name: {user_name}")
            logger.info(f"Company: {company_name}")
            logger.info(f"Transaction ID: {txn_id}")
            logger.info(f"\nDocuments included in email ({len(documents)} total):")
            for idx, doc in enumerate(documents, 1):
                logger.info(f"  {idx}. {doc.document_name}")
                logger.info(f"     Original: {doc.original_url[:60]}..." if len(doc.original_url) > 60 else f"     Original: {doc.original_url}")
                logger.info(f"     Translated: {doc.translated_url[:60]}..." if doc.translated_url and len(doc.translated_url) > 60 else f"     Translated: {doc.translated_url}")

            email_result = email_service.send_translation_notification(
                documents=documents,
                user_name=user_name,
                user_email=user_email,
                company_name=company_name,
                transaction_id=txn_id,
                completed_at=completed_at,
                total_documents=total_docs_count
            )

            # Enhanced logging: Email send result
            logger.info("=" * 80)
            logger.info("EMAIL SEND RESULT")
            logger.info("=" * 80)
            logger.info(
                "Email send status",
                extra={
                    "transaction_id": txn_id,
                    "recipient": user_email,
                    "send_successful": email_result.success,
                    "error_message": email_result.error if not email_result.success else None
                }
            )
            if email_result.success:
                logger.info(f"✅ Email sent successfully to {user_email}")
            else:
                logger.error(f"❌ Email send failed: {email_result.error}")

            logger.debug(
                f"Email service returned result",
                extra={
                    "success": email_result.success,
                    "message": email_result.message,
                    "error": email_result.error,
                    "recipient": email_result.recipient
                }
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
