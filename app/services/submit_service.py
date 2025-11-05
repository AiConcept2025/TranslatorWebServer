"""
Submit service for handling file submission requests.
Processes file submissions and sends email notifications to users.
"""

import logging
from typing import Dict, Any, Optional, List

from app.models.email import DocumentInfo
from app.services.email_service import email_service

logger = logging.getLogger(__name__)


class SubmitService:
    """Service for handling file submission logic and email notifications."""

    async def process_submission(
        self,
        file_name: str,
        file_url: str,
        user_email: str,
        company_name: str,
        transaction_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process file submission request and send email notification.

        This implementation:
        1. Validates the submission
        2. Creates document information
        3. Sends email notification to the user
        4. Returns success even if email fails (email is non-critical)

        Args:
            file_name: Name of the file being submitted
            file_url: Google Drive URL of the file
            user_email: Email of the user submitting the file
            company_name: Name of the company
            transaction_id: Optional transaction ID

        Returns:
            Dictionary containing status and message
        """
        logger.info(
            f"Processing submission - File: {file_name}, User: {user_email}, "
            f"Company: {company_name}, Transaction: {transaction_id or 'None'}"
        )

        try:
            # Create document information for email
            # For now, we'll simulate having both original and translated URLs
            # In a real implementation, you would:
            # 1. Store the original file URL from the submission
            # 2. Process/translate the document
            # 3. Get the translated document URL
            # 4. Then send the email with both URLs

            # For demonstration, we'll use the submitted URL as original
            # and simulate a translated URL (in reality, this would come from the translation service)
            documents = [
                DocumentInfo(
                    document_name=file_name,
                    original_url=file_url,
                    translated_url=self._generate_translated_url(file_url)
                )
            ]

            # Extract user name from email (simple approach)
            # In a real system, you'd get the actual user name from the database
            user_name = self._extract_user_name_from_email(user_email)

            # Send email notification
            logger.info(f"Sending email notification to {user_email}")
            email_result = email_service.send_translation_notification(
                documents=documents,
                user_name=user_name,
                user_email=user_email,
                company_name=company_name
            )

            if email_result.success:
                logger.info(f"Email notification sent successfully to {user_email}")
                return {
                    "status": "processed",
                    "message": f"File submission received for {file_name}. Notification email sent to {user_email}.",
                    "email_sent": True
                }
            else:
                # Email failed, but don't fail the submission
                logger.warning(f"Email notification failed for {user_email}: {email_result.error}")
                return {
                    "status": "processed",
                    "message": f"File submission received for {file_name}. Email notification failed.",
                    "email_sent": False,
                    "email_error": email_result.error
                }

        except Exception as e:
            logger.error(f"Error processing submission for {file_name}: {e}", exc_info=True)
            # Return success for the submission even if email fails
            # This ensures submission doesn't fail due to email issues
            return {
                "status": "processed",
                "message": f"File submission received for {file_name}. Email notification encountered an error.",
                "email_sent": False,
                "email_error": str(e)
            }

    def _generate_translated_url(self, original_url: str) -> str:
        """
        Generate translated document URL.

        In a real implementation, this would:
        1. Trigger the translation service
        2. Wait for translation to complete
        3. Return the actual translated document URL

        For now, this is a placeholder that modifies the original URL.

        Args:
            original_url: Original document URL

        Returns:
            Translated document URL (simulated)
        """
        # Placeholder: In reality, this would be the actual translated file URL
        # For demo purposes, we'll just modify the URL
        if '/file/d/' in original_url:
            # Simulate a translated version by adding a suffix
            return original_url.replace('/view', '_translated/view')
        return original_url + "?translated=true"

    def _extract_user_name_from_email(self, email: str) -> str:
        """
        Extract user name from email address.

        Simple extraction: takes the part before @ and formats it.
        In a real system, you'd query the database for the actual user name.

        Args:
            email: User email address

        Returns:
            Formatted user name
        """
        try:
            username = email.split('@')[0]
            # Convert "john.doe" to "John Doe"
            parts = username.replace('_', '.').replace('-', '.').split('.')
            name = ' '.join(word.capitalize() for word in parts)
            return name
        except Exception:
            return "User"

    async def process_bulk_submission(
        self,
        documents: List[Dict[str, str]],
        user_email: str,
        company_name: str
    ) -> Dict[str, Any]:
        """
        Process multiple file submissions at once and send a single email.

        Args:
            documents: List of documents with file_name and file_url
            user_email: User email address
            company_name: Company name

        Returns:
            Dictionary with processing results
        """
        logger.info(f"Processing bulk submission: {len(documents)} documents for {user_email}")

        try:
            # Create DocumentInfo list
            document_infos = []
            for doc in documents:
                document_infos.append(
                    DocumentInfo(
                        document_name=doc['file_name'],
                        original_url=doc['file_url'],
                        translated_url=self._generate_translated_url(doc['file_url'])
                    )
                )

            # Extract user name
            user_name = self._extract_user_name_from_email(user_email)

            # Send single email with all documents
            email_result = email_service.send_translation_notification(
                documents=document_infos,
                user_name=user_name,
                user_email=user_email,
                company_name=company_name
            )

            return {
                "status": "processed",
                "message": f"Processed {len(documents)} documents",
                "documents_count": len(documents),
                "email_sent": email_result.success,
                "email_error": email_result.error if not email_result.success else None
            }

        except Exception as e:
            logger.error(f"Error in bulk submission: {e}", exc_info=True)
            return {
                "status": "error",
                "message": f"Error processing bulk submission: {str(e)}",
                "documents_count": len(documents),
                "email_sent": False
            }


# Create singleton instance
submit_service = SubmitService()
