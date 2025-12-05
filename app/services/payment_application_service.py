"""
Payment application service for applying payments to invoices.

This service links payments to invoices, updates payment tracking,
and manages invoice status transitions.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any
from bson import ObjectId

from app.database.mongodb import database

logger = logging.getLogger(__name__)

# Module load marker
logger.warning("🔄 PAYMENT_APPLICATION_SERVICE MODULE LOADED - v1.0")


class PaymentApplicationError(Exception):
    """Base payment application error."""
    pass


class PaymentApplicationService:
    """Service for applying payments to invoices."""

    def _calculate_invoice_status(self, total_amount: float, amount_paid: float) -> str:
        """
        Calculate invoice status based on payment amounts.

        Args:
            total_amount: Total invoice amount
            amount_paid: Amount paid so far

        Returns:
            Invoice status: 'sent', 'partially_paid', or 'paid'
        """
        if amount_paid <= 0:
            return "sent"
        elif amount_paid >= total_amount:
            return "paid"
        else:
            return "partially_paid"

    async def apply_payment_to_invoice(
        self,
        payment_id: str,
        invoice_id: str
    ) -> Dict[str, Any]:
        """
        Apply a payment to an invoice.

        This updates:
        1. invoice.amount_paid += payment.amount
        2. invoice.status (sent → partially_paid → paid)
        3. payment.invoice_id = invoice_id
        4. invoice.payment_applications with payment record

        Args:
            payment_id: Payment ObjectId
            invoice_id: Invoice ObjectId

        Returns:
            dict: Updated invoice document

        Raises:
            PaymentApplicationError: If application fails
        """
        logger.info(f"[PAYMENT_APP] Applying payment {payment_id} to invoice {invoice_id}")

        # Step 1: Fetch payment
        try:
            payment = await database.payments.find_one({"_id": ObjectId(payment_id)})
            if not payment:
                raise PaymentApplicationError(f"Payment not found: {payment_id}")
        except Exception as e:
            logger.error(f"[PAYMENT_APP] Error fetching payment: {e}")
            raise PaymentApplicationError(f"Failed to fetch payment: {str(e)}")

        logger.info(f"[PAYMENT_APP] Payment found: ${payment.get('amount', 0) / 100:.2f}")

        # Step 2: Check if payment is already applied to an invoice
        existing_invoice_id = payment.get("invoice_id")
        if existing_invoice_id:
            logger.warning(f"[PAYMENT_APP] Payment {payment_id} already applied to invoice {existing_invoice_id}")
            raise PaymentApplicationError(f"Payment already applied to invoice {existing_invoice_id}")

        # Step 3: Check if payment is completed
        payment_status = payment.get("payment_status", "")
        if payment_status not in ["COMPLETED", "APPROVED"]:
            raise PaymentApplicationError(f"Payment status must be COMPLETED or APPROVED, got: {payment_status}")

        # Step 4: Fetch invoice
        try:
            invoice = await database.invoices.find_one({"_id": ObjectId(invoice_id)})
            if not invoice:
                raise PaymentApplicationError(f"Invoice not found: {invoice_id}")
        except Exception as e:
            logger.error(f"[PAYMENT_APP] Error fetching invoice: {e}")
            raise PaymentApplicationError(f"Failed to fetch invoice: {str(e)}")

        logger.info(f"[PAYMENT_APP] Invoice found: {invoice.get('invoice_number')}")

        # Step 5: Calculate new amount_paid
        payment_amount_cents = payment.get("amount", 0)
        payment_amount_dollars = payment_amount_cents / 100.0

        current_amount_paid = invoice.get("amount_paid", 0.0)
        new_amount_paid = current_amount_paid + payment_amount_dollars

        total_amount = invoice.get("total_amount", 0.0)
        logger.info(f"[PAYMENT_APP] Amount paid: ${current_amount_paid:.2f} + ${payment_amount_dollars:.2f} = ${new_amount_paid:.2f} / ${total_amount:.2f}")

        # Step 6: Calculate new invoice status
        new_status = self._calculate_invoice_status(total_amount, new_amount_paid)
        logger.info(f"[PAYMENT_APP] Status transition: {invoice.get('status')} → {new_status}")

        # Step 7: Create payment application record
        now = datetime.now(timezone.utc)
        payment_application = {
            "payment_id": payment_id,
            "stripe_payment_intent_id": payment.get("stripe_payment_intent_id"),
            "amount": payment_amount_dollars,
            "applied_at": now,
            "user_email": payment.get("user_email")
        }

        # Step 8: Update invoice
        try:
            payment_applications = invoice.get("payment_applications", [])
            payment_applications.append(payment_application)

            updated_invoice = await database.invoices.find_one_and_update(
                {"_id": ObjectId(invoice_id)},
                {
                    "$set": {
                        "amount_paid": new_amount_paid,
                        "status": new_status,
                        "payment_applications": payment_applications,
                        "updated_at": now
                    }
                },
                return_document=True  # Return updated document
            )

            if not updated_invoice:
                raise PaymentApplicationError("Failed to update invoice")

            logger.info(f"[PAYMENT_APP] Invoice updated: amount_paid=${new_amount_paid:.2f}, status={new_status}")

        except Exception as e:
            logger.error(f"[PAYMENT_APP] Error updating invoice: {e}")
            raise PaymentApplicationError(f"Failed to update invoice: {str(e)}")

        # Step 9: Update payment with invoice linkage
        try:
            subscription_id = invoice.get("subscription_id")

            await database.payments.update_one(
                {"_id": ObjectId(payment_id)},
                {
                    "$set": {
                        "invoice_id": invoice_id,
                        "subscription_id": subscription_id,
                        "updated_at": now
                    }
                }
            )

            logger.info(f"[PAYMENT_APP] Payment updated: linked to invoice {invoice_id}")

        except Exception as e:
            logger.error(f"[PAYMENT_APP] Error updating payment: {e}")
            # Don't raise - invoice was already updated, payment link is secondary
            logger.warning(f"[PAYMENT_APP] Payment not linked but invoice was updated successfully")

        logger.info(f"[PAYMENT_APP] Payment application completed successfully")

        return updated_invoice

    async def get_invoice_payments(self, invoice_id: str) -> list[Dict[str, Any]]:
        """
        Get all payments applied to an invoice.

        Args:
            invoice_id: Invoice ObjectId

        Returns:
            List of payment documents linked to this invoice

        Raises:
            PaymentApplicationError: If fetch fails
        """
        logger.info(f"[PAYMENT_APP] Fetching payments for invoice {invoice_id}")

        try:
            payments = await database.payments.find({"invoice_id": invoice_id}).to_list(length=100)
            logger.info(f"[PAYMENT_APP] Found {len(payments)} payments for invoice {invoice_id}")
            return payments
        except Exception as e:
            logger.error(f"[PAYMENT_APP] Error fetching payments: {e}")
            raise PaymentApplicationError(f"Failed to fetch payments: {str(e)}")

    async def unapply_payment_from_invoice(
        self,
        payment_id: str,
        invoice_id: str
    ) -> Dict[str, Any]:
        """
        Remove a payment application from an invoice (for corrections/refunds).

        This reverses the apply_payment_to_invoice operation.

        Args:
            payment_id: Payment ObjectId
            invoice_id: Invoice ObjectId

        Returns:
            dict: Updated invoice document

        Raises:
            PaymentApplicationError: If unapply fails
        """
        logger.info(f"[PAYMENT_APP] Unapplying payment {payment_id} from invoice {invoice_id}")

        # Step 1: Fetch payment
        try:
            payment = await database.payments.find_one({"_id": ObjectId(payment_id)})
            if not payment:
                raise PaymentApplicationError(f"Payment not found: {payment_id}")
        except Exception as e:
            logger.error(f"[PAYMENT_APP] Error fetching payment: {e}")
            raise PaymentApplicationError(f"Failed to fetch payment: {str(e)}")

        # Step 2: Verify payment is linked to this invoice
        if payment.get("invoice_id") != invoice_id:
            raise PaymentApplicationError(f"Payment {payment_id} is not linked to invoice {invoice_id}")

        # Step 3: Fetch invoice
        try:
            invoice = await database.invoices.find_one({"_id": ObjectId(invoice_id)})
            if not invoice:
                raise PaymentApplicationError(f"Invoice not found: {invoice_id}")
        except Exception as e:
            logger.error(f"[PAYMENT_APP] Error fetching invoice: {e}")
            raise PaymentApplicationError(f"Failed to fetch invoice: {str(e)}")

        # Step 4: Calculate new amount_paid
        payment_amount_cents = payment.get("amount", 0)
        payment_amount_dollars = payment_amount_cents / 100.0

        current_amount_paid = invoice.get("amount_paid", 0.0)
        new_amount_paid = max(0.0, current_amount_paid - payment_amount_dollars)

        total_amount = invoice.get("total_amount", 0.0)
        logger.info(f"[PAYMENT_APP] Amount paid: ${current_amount_paid:.2f} - ${payment_amount_dollars:.2f} = ${new_amount_paid:.2f} / ${total_amount:.2f}")

        # Step 5: Calculate new invoice status
        new_status = self._calculate_invoice_status(total_amount, new_amount_paid)
        logger.info(f"[PAYMENT_APP] Status transition: {invoice.get('status')} → {new_status}")

        # Step 6: Remove payment application record
        now = datetime.now(timezone.utc)
        payment_applications = invoice.get("payment_applications", [])
        payment_applications = [
            app for app in payment_applications
            if app.get("payment_id") != payment_id
        ]

        # Step 7: Update invoice
        try:
            updated_invoice = await database.invoices.find_one_and_update(
                {"_id": ObjectId(invoice_id)},
                {
                    "$set": {
                        "amount_paid": new_amount_paid,
                        "status": new_status,
                        "payment_applications": payment_applications,
                        "updated_at": now
                    }
                },
                return_document=True
            )

            if not updated_invoice:
                raise PaymentApplicationError("Failed to update invoice")

            logger.info(f"[PAYMENT_APP] Invoice updated: amount_paid=${new_amount_paid:.2f}, status={new_status}")

        except Exception as e:
            logger.error(f"[PAYMENT_APP] Error updating invoice: {e}")
            raise PaymentApplicationError(f"Failed to update invoice: {str(e)}")

        # Step 8: Update payment to remove invoice linkage
        try:
            await database.payments.update_one(
                {"_id": ObjectId(payment_id)},
                {
                    "$set": {
                        "invoice_id": None,
                        "subscription_id": None,
                        "updated_at": now
                    }
                }
            )

            logger.info(f"[PAYMENT_APP] Payment updated: unlinked from invoice {invoice_id}")

        except Exception as e:
            logger.error(f"[PAYMENT_APP] Error updating payment: {e}")
            logger.warning(f"[PAYMENT_APP] Payment not unlinked but invoice was updated successfully")

        logger.info(f"[PAYMENT_APP] Payment unapplication completed successfully")

        return updated_invoice


# Singleton instance
payment_application_service = PaymentApplicationService()
