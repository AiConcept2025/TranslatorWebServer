"""
Simplified Payment API endpoints - No sessions, just customer email lookup.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, Dict, Any
import logging
import stripe

# Stripe error classes - explicit imports required for SDK 13.2.0+
try:
    from stripe.error import (
        CardError, InvalidRequestError, AuthenticationError,
        APIConnectionError, StripeError
    )
except ImportError:
    from stripe._error import (
        CardError, InvalidRequestError, AuthenticationError,
        APIConnectionError, StripeError
    )

from app.services.google_drive_service import google_drive_service
from app.services.pricing_service import pricing_service
from app.services.payment_creation_service import payment_creation_service
from app.utils.amount_converter import AmountConverter
from app.config import settings

# Configure Stripe API key
stripe.api_key = settings.stripe_secret_key

router = APIRouter(prefix="/api/payment", tags=["Payments"])

class PaymentMetadata(BaseModel):
    """Payment metadata from Square/Stripe."""
    status: Optional[str] = None
    cardBrand: Optional[str] = Field(None, alias='card_brand')
    last4: Optional[str] = None
    receiptNumber: Optional[str] = Field(None, alias='receipt_number')
    created: Optional[str] = None
    simulated: Optional[bool] = None
    customer_email: Optional[EmailStr] = None
    stripe_checkout_session_id: Optional[str] = None

    model_config = {'populate_by_name': True}

class PaymentSuccessRequest(BaseModel):
    """Payment success webhook - accepts all client fields."""
    # Can be at root or in metadata
    customer_email: Optional[EmailStr] = Field(None, alias='customerEmail')

    # Payment ID (required)
    payment_intent_id: Optional[str] = Field(None, alias='paymentIntentId')

    # Square transaction ID (for user payments)
    stripe_checkout_session_id: Optional[str] = None

    # File IDs from upload response (eliminates need for Drive search)
    file_ids: Optional[list[str]] = Field(
        None,
        alias='fileIds',
        description="File IDs from upload response - enables direct lookup instead of search"
    )

    # Payment details
    amount: Optional[float] = None
    currency: Optional[str] = "USD"
    payment_method: Optional[str] = Field(None, alias='paymentMethod')

    # Additional fields
    metadata: Optional[PaymentMetadata] = None
    timestamp: Optional[str] = None

    model_config = {'populate_by_name': True}

    def get_customer_email(self) -> str:
        """Extract customer email from root or metadata."""
        if self.customer_email:
            return self.customer_email
        if self.metadata and self.metadata.customer_email:
            return self.metadata.customer_email
        raise ValueError("customer_email not found in request or metadata")

    def get_payment_intent_id(self) -> str:
        """Get payment intent ID."""
        if not self.payment_intent_id:
            raise ValueError("payment_intent_id is required")
        return self.payment_intent_id

async def process_payment_files_background(
    customer_email: str,
    payment_intent_id: str,
    amount: Optional[float],
    currency: Optional[str],
    payment_metadata: Optional[PaymentMetadata] = None,
    transaction_id: Optional[str] = None,
    file_ids: Optional[list[str]] = None,
    webhook_event_id: Optional[str] = None
):
    """
    Background task to move files from Temp to Inbox and persist payment data.
    Runs asynchronously without blocking HTTP response.

    Args:
        transaction_id: Pre-generated transaction ID from payment handler (if available)
        file_ids: File IDs from upload response (enables direct lookup, eliminates Drive search)
        webhook_event_id: Stripe webhook event ID (if triggered by webhook)
    """
    import time
    task_start = time.time()

    try:
        print("\n" + "=" * 80)
        print("🔄 BACKGROUND TASK STARTED")
        print("=" * 80)
        print(f"⏱️  Started at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📋 Task Details:")
        print(f"   Customer: {customer_email}")
        print(f"   Payment ID: {payment_intent_id}")
        print(f"   Amount: ${amount} {currency}")
        if webhook_event_id:
            print(f"   Source: Webhook (event_id: {webhook_event_id})")
        else:
            print(f"   Source: Client Notification (fallback)")
        print("=" * 80)

        # Step 0: Create or update payment using centralized service (idempotent)
        print(f"\n💾 Step 0: Creating payment record (idempotent)...")
        persist_start = time.time()

        try:
            # Use centralized payment creation service
            result = await payment_creation_service.create_or_update_payment(
                payment_intent_id=payment_intent_id,
                amount_cents=AmountConverter.dollars_to_cents(amount or 0.0),
                currency=currency or "usd",
                customer_email=customer_email,
                webhook_event_id=webhook_event_id,
                metadata={}
            )

            persist_time = (time.time() - persist_start) * 1000
            print(f"⏱️  Payment persistence completed in {persist_time:.2f}ms")

            if not result["created"]:
                # Payment already existed - duplicate webhook
                print(f"⚠️  Payment {payment_intent_id} already processed (duplicate webhook)")
                print(f"✅ Returning early - payment ID: {result['payment'].get('_id')}")
                logging.info(f"[PAYMENT] Duplicate payment webhook ignored: {payment_intent_id}")
                return  # Exit early, don't reprocess

            payment_id = str(result["payment"]["_id"])
            print(f"✅ Payment record created with ID: {payment_id}")
            logging.info(f"[PAYMENT] New payment created: {payment_intent_id}")

        except Exception as e:
            persist_time = (time.time() - persist_start) * 1000
            print(f"⏱️  Payment persistence attempted in {persist_time:.2f}ms")
            print(f"⚠️  Failed to persist payment: {str(e)}")
            logging.warning(f"Failed to persist payment {payment_intent_id}: {e}")

        # Get files - use direct lookup if file_ids provided, otherwise search
        print(f"\n🔍 Step 2: Locating files for customer...")
        find_start = time.time()

        if file_ids:
            # OPTIMIZED: Direct file ID lookup (no search)
            print(f"   Using direct file ID lookup ({len(file_ids)} files)")
            files_to_move = []
            for i, file_id in enumerate(file_ids, 1):
                try:
                    file_info = await google_drive_service.get_file_by_id(file_id)
                    files_to_move.append(file_info)
                    print(f"   ✓ {i}/{len(file_ids)}: {file_info.get('filename')} (ID: {file_id[:20]}...)")
                except Exception as e:
                    logging.warning(f"Failed to fetch file {file_id}: {e}")
                    print(f"   ✗ {i}/{len(file_ids)}: Failed to fetch {file_id[:20]}... - {str(e)}")
        else:
            # FALLBACK: Search by email (legacy, finds all files - may include old uploads)
            print(f"   ⚠️  No file_ids provided - falling back to Drive search (may find old files)")
            files_to_move = await google_drive_service.find_files_by_customer_email(
                customer_email=customer_email,
                status="awaiting_payment"
            )

        find_time = (time.time() - find_start) * 1000
        print(f"⏱️  File lookup completed in {find_time:.2f}ms")

        if not files_to_move:
            print(f"⚠️  No files found for {customer_email}")
            total_time = (time.time() - task_start) * 1000
            print(f"⏱️  BACKGROUND TASK TOTAL TIME: {total_time:.2f}ms")
            print("=" * 80 + "\n")
            return

        print(f"\n✅ Located {len(files_to_move)} files to process")

        # Create translation transaction record
        print(f"\n💾 Step 2.5: Creating translation transaction record...")
        transaction_start = time.time()

        try:
            from app.services.translation_transaction_service import create_translation_transaction
            from app.utils.transaction_id_generator import generate_translation_transaction_id
            from datetime import datetime, timezone

            # Use pre-generated transaction_id or generate new one
            if not transaction_id:
                transaction_id = generate_translation_transaction_id()
                print(f"✅ Generated new transaction ID: {transaction_id}")
            else:
                print(f"✅ Using pre-generated transaction ID: {transaction_id}")

            # Build documents array from files_to_move
            documents = []
            for file_info in files_to_move:
                doc = {
                    "file_name": file_info.get('filename'),
                    "file_size": file_info.get('size', 0),
                    "original_url": file_info.get('google_drive_url'),
                    "translated_url": None,
                    "translated_name": None,
                    "status": "uploaded",
                    "uploaded_at": datetime.fromisoformat(file_info.get('upload_timestamp').replace('Z', '+00:00')) if file_info.get('upload_timestamp') else datetime.now(timezone.utc),
                    "translated_at": None,
                    "processing_started_at": None,
                    "processing_duration": None
                }
                documents.append(doc)

            # Calculate pricing using pricing service (individual user, default mode)
            total_units = sum(file_info.get('page_count', 1) for file_info in files_to_move)
            total_price_decimal = pricing_service.calculate_price(total_units, "individual", "default")
            total_price = float(total_price_decimal)
            # Back-calculate price per unit for database storage
            price_per_unit = total_price / total_units if total_units > 0 else 0

            # Extract languages from first file (all files should have same languages)
            source_language = files_to_move[0].get('source_language', 'en')
            target_language = files_to_move[0].get('target_language', 'fr')

            # Create transaction
            mongo_id = await create_translation_transaction(
                transaction_id=transaction_id,
                user_id=customer_email,
                documents=documents,
                source_language=source_language,
                target_language=target_language,
                units_count=total_units,
                price_per_unit=price_per_unit,
                total_price=total_price,
                status="pending_confirmation",  # Payment received, awaiting user confirmation
                company_name=None,  # Individual users don't have companies
                subscription_id=None,
                unit_type="page"
            )

            transaction_time = (time.time() - transaction_start) * 1000

            if mongo_id:
                print(f"⏱️  Transaction creation completed in {transaction_time:.2f}ms")
                print(f"✅ Translation transaction created:")
                print(f"   transaction_id: {transaction_id}")
                print(f"   MongoDB _id: {mongo_id}")
                print(f"   Documents: {len(documents)}")
                print(f"   Total units: {total_units} pages")
                print(f"   Total price: ${total_price}")
                print(f"   Languages: {source_language} → {target_language}")
            else:
                print(f"⏱️  Transaction creation attempted in {transaction_time:.2f}ms")
                print(f"⚠️  Failed to create transaction record (mongo_id is None)")
                transaction_id = None  # Reset if creation failed

        except Exception as e:
            transaction_time = (time.time() - transaction_start) * 1000
            print(f"⏱️  Transaction creation attempted in {transaction_time:.2f}ms")
            print(f"⚠️  Error creating transaction: {str(e)}")
            logging.warning(f"Failed to create translation transaction for {customer_email}: {e}")
            transaction_id = None  # Reset on error

        # DO NOT move files - let confirm endpoint handle it
        print(f"\n📁 Step 3: Files remain in Temp (awaiting user confirmation)")
        print(f"   Files ready for confirmation: {len(files_to_move)}")
        for i, file_info in enumerate(files_to_move, 1):
            print(f"      {i}. {file_info.get('filename')} (ID: {file_info.get('file_id')[:20]}...)")
        print(f"   ⚠️  Files will be moved when user clicks 'Confirm' button")
        print(f"   ⚠️  Confirm endpoint will: update metadata → move to Inbox")

        total_time = (time.time() - task_start) * 1000
        print(f"\n✅ PAYMENT WEBHOOK COMPLETE (Files not moved yet)")
        print(f"⏱️  TOTAL TASK TIME: {total_time:.2f}ms")
        print(f"   - Payment persistence: {persist_time:.2f}ms")
        print(f"   - File search: {find_time:.2f}ms")
        if transaction_id:
            print(f"   - Transaction creation: Completed")
        print(f"   - File movement: SKIPPED (done by confirm endpoint)")
        print("=" * 80 + "\n")

        logging.info(f"Payment webhook completed for {customer_email}: {len(files_to_move)} files ready for confirmation (not moved yet)")

    except Exception as e:
        total_time = (time.time() - task_start) * 1000
        print(f"\n❌ BACKGROUND TASK ERROR")
        print(f"⏱️  Failed after: {total_time:.2f}ms")
        print(f"💥 Error type: {type(e).__name__}")
        print(f"💥 Error message: {str(e)}")
        print("=" * 80 + "\n")
        logging.error(f"Background file processing error for {customer_email}: {e}", exc_info=True)


class CreatePaymentIntentRequest(BaseModel):
    """Request model for creating a Stripe payment intent."""
    amount: int = Field(..., description="Amount in cents (e.g., 5000 = $50.00)", gt=0)
    currency: str = Field(default="usd", description="Currency code (ISO 4217)")
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional metadata (email, file_ids, etc.)"
    )


@router.post("/create-intent")
async def create_payment_intent(request: CreatePaymentIntentRequest):
    """
    Create Stripe payment intent.

    Args:
        amount: Amount in cents (e.g., 5000 = $50.00)
        currency: Currency code (default: usd)
        metadata: Optional metadata (email, file_ids, etc.)

    Returns:
        {
            "clientSecret": "pi_xxx_secret_yyy",
            "paymentIntentId": "pi_xxx"
        }

    Raises:
        HTTPException: 400 if Stripe API error occurs
    """
    print("\n" + "=" * 80)
    print("💳 CREATE PAYMENT INTENT REQUEST")
    print("=" * 80)
    print(f"Amount: ${AmountConverter.cents_to_dollars(request.amount):.2f} ({request.amount} cents)")
    print(f"Currency: {request.currency.upper()}")
    if request.metadata:
        print(f"Metadata: {request.metadata}")
    print("=" * 80)

    try:
        # TEST MODE: Return mock payment intent without calling Stripe API
        if settings.is_test_mode():
            import uuid
            mock_intent_id = f"pi_test_{uuid.uuid4().hex[:24]}"
            mock_client_secret = f"{mock_intent_id}_secret_{uuid.uuid4().hex[:16]}"

            print(f"\n✅ TEST MODE: Mock payment intent created")
            print(f"   Payment Intent ID: {mock_intent_id}")
            print(f"   Client Secret: {mock_client_secret[:20]}...")
            print(f"   Amount: ${AmountConverter.cents_to_dollars(request.amount):.2f} {request.currency.upper()}")
            print("=" * 80 + "\n")

            logging.info(
                f"TEST MODE: Mock payment intent created: {mock_intent_id} "
                f"for ${AmountConverter.cents_to_dollars(request.amount):.2f} {request.currency.upper()}"
            )

            return JSONResponse(
                content={
                    "clientSecret": mock_client_secret,
                    "paymentIntentId": mock_intent_id
                },
                status_code=200
            )

        # PRODUCTION MODE: Create real Stripe payment intent
        intent = stripe.PaymentIntent.create(
            amount=request.amount,
            currency=request.currency,
            metadata=request.metadata or {},
            automatic_payment_methods={"enabled": True}
        )

        print(f"\n✅ Payment intent created successfully")
        print(f"   Payment Intent ID: {intent.id}")
        print(f"   Client Secret: {intent.client_secret[:20]}...")
        print(f"   Amount: ${AmountConverter.cents_to_dollars(intent.amount):.2f} {intent.currency.upper()}")
        print("=" * 80 + "\n")

        logging.info(
            f"Payment intent created: {intent.id} "
            f"for ${AmountConverter.cents_to_dollars(intent.amount):.2f} {intent.currency.upper()}"
        )

        return JSONResponse(
            content={
                "clientSecret": intent.client_secret,
                "paymentIntentId": intent.id
            },
            status_code=200
        )

    except CardError as e:
        # Card was declined
        error_msg = str(e.user_message) if hasattr(e, 'user_message') else str(e)
        print(f"\n❌ Card error: {error_msg}")
        print("=" * 80 + "\n")
        logging.error(f"Stripe card error: {error_msg}")
        raise HTTPException(status_code=400, detail=error_msg)

    except InvalidRequestError as e:
        # Invalid parameters
        error_msg = str(e)
        print(f"\n❌ Invalid request error: {error_msg}")
        print("=" * 80 + "\n")
        logging.error(f"Stripe invalid request: {error_msg}")
        raise HTTPException(status_code=400, detail=error_msg)

    except AuthenticationError as e:
        # Authentication with Stripe API failed
        error_msg = "Authentication with payment provider failed"
        print(f"\n❌ Authentication error: {str(e)}")
        print("=" * 80 + "\n")
        logging.error(f"Stripe authentication error: {e}")
        raise HTTPException(status_code=500, detail=error_msg)

    except APIConnectionError as e:
        # Network communication failed
        error_msg = "Payment provider connection failed"
        print(f"\n❌ API connection error: {str(e)}")
        print("=" * 80 + "\n")
        logging.error(f"Stripe API connection error: {e}")
        raise HTTPException(status_code=503, detail=error_msg)

    except StripeError as e:
        # Generic Stripe error
        error_msg = str(e)
        print(f"\n❌ Stripe error: {error_msg}")
        print("=" * 80 + "\n")
        logging.error(f"Stripe error: {error_msg}")
        raise HTTPException(status_code=400, detail=error_msg)

    except Exception as e:
        # Unexpected error
        error_msg = "An unexpected error occurred while creating payment intent"
        print(f"\n❌ Unexpected error: {str(e)}")
        print(f"   Type: {type(e).__name__}")
        print("=" * 80 + "\n")
        logging.error(f"Unexpected error in create_payment_intent: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=error_msg)


@router.post("/success")
async def handle_payment_success(
    request: PaymentSuccessRequest,
    background_tasks: BackgroundTasks
):
    """
    INSTANT payment success webhook - returns immediately.
    Files are moved in background (non-blocking).
    """
    import time
    start_time = time.time()

    print("\n" + "=" * 80)
    print("⚡ INSTANT PAYMENT SUCCESS WEBHOOK")
    print("=" * 80)
    print(f"⏱️  Request received at: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        # Log raw request data
        print("\n📥 RAW REQUEST DATA:")
        print(f"   payment_intent_id (snake_case): {request.payment_intent_id}")
        print(f"   customer_email (root): {request.customer_email}")
        print(f"   amount: {request.amount}")
        print(f"   currency: {request.currency}")
        print(f"   payment_method: {request.payment_method}")
        print(f"   timestamp: {request.timestamp}")

        if request.metadata:
            print(f"\n📋 METADATA:")
            print(f"   status: {request.metadata.status}")
            print(f"   cardBrand: {request.metadata.cardBrand}")
            print(f"   last4: {request.metadata.last4}")
            print(f"   receiptNumber: {request.metadata.receiptNumber}")
            print(f"   created: {request.metadata.created}")
            print(f"   simulated: {request.metadata.simulated}")
            print(f"   customer_email (metadata): {request.metadata.customer_email}")

        # Extract required fields (FAST - no I/O)
        parse_start = time.time()
        customer_email = request.get_customer_email()
        payment_intent_id = request.get_payment_intent_id()
        parse_time = (time.time() - parse_start) * 1000

        print(f"\n✅ EXTRACTED FIELDS (took {parse_time:.2f}ms):")
        print(f"   Customer: {customer_email}")
        print(f"   Payment ID: {payment_intent_id}")
        print(f"   Amount: ${request.amount} {request.currency}")
        print(f"   Payment Method: {request.payment_method}")

        # CHECK: Has webhook already processed this payment?
        # Webhook sets webhook_processing=True to claim payment processing
        check_webhook_start = time.time()
        from app.database.mongodb import database
        existing_payment = await database.payments.find_one({
            "stripe_payment_intent_id": payment_intent_id
        })

        if existing_payment and existing_payment.get("webhook_processing"):
            check_webhook_time = (time.time() - check_webhook_start) * 1000
            total_time = (time.time() - start_time) * 1000

            logging.info(
                f"[CLIENT_NOTIFICATION] Payment {payment_intent_id} already "
                f"processed by webhook (webhook_processing=True), skipping"
            )

            print(f"\n⚠️  WEBHOOK ALREADY PROCESSED THIS PAYMENT")
            print(f"   Payment ID: {payment_intent_id}")
            print(f"   Webhook processing flag: True")
            print(f"   Skipping client-side processing")
            print(f"⏱️  Webhook check time: {check_webhook_time:.2f}ms")
            print(f"⏱️  TOTAL TIME: {total_time:.2f}ms")
            print("=" * 80 + "\n")

            return JSONResponse(content={
                "success": True,
                "message": "Payment already processed by webhook",
                "data": {
                    "customer_email": customer_email,
                    "payment_intent_id": payment_intent_id,
                    "status": "already_processed",
                    "processed_by": "webhook",
                    "processing_time_ms": round(total_time, 2)
                }
            })

        check_webhook_time = (time.time() - check_webhook_start) * 1000
        print(f"\n✅ WEBHOOK CHECK: Payment not yet processed by webhook")
        print(f"   Proceeding with client-side processing (webhook fallback)")
        print(f"⏱️  Webhook check time: {check_webhook_time:.2f}ms")

        # Create translation transaction (synchronously, returns transaction_id)
        print(f"\n💾 Creating translation transaction...")
        transaction_create_start = time.time()
        transaction_id = None

        try:
            from app.utils.transaction_id_generator import generate_translation_transaction_id
            transaction_id = generate_translation_transaction_id()
            print(f"✅ Transaction ID generated: {transaction_id}")
        except Exception as e:
            print(f"⚠️  Failed to generate transaction ID: {str(e)}")
            logging.warning(f"Failed to generate transaction ID: {e}")

        transaction_create_time = (time.time() - transaction_create_start) * 1000

        # Schedule background file processing (pass transaction_id and file_ids)
        task_schedule_start = time.time()
        background_tasks.add_task(
            process_payment_files_background,
            customer_email=customer_email,
            payment_intent_id=payment_intent_id,
            amount=request.amount,
            currency=request.currency,
            payment_metadata=request.metadata,
            transaction_id=transaction_id,  # Pass pre-generated transaction_id
            file_ids=request.file_ids  # Pass file IDs for direct lookup (eliminates search)
        )
        task_schedule_time = (time.time() - task_schedule_start) * 1000

        total_time = (time.time() - start_time) * 1000
        print(f"\n⚡ INSTANT RESPONSE - Background task scheduled (took {task_schedule_time:.2f}ms)")
        print(f"⏱️  Transaction ID generation: {transaction_create_time:.2f}ms")
        print(f"⏱️  TOTAL PROCESSING TIME: {total_time:.2f}ms")
        print("=" * 80 + "\n")

        # Return IMMEDIATELY (< 100ms) with transaction_id
        response_data = {
            "success": True,
            "message": "Payment confirmed. Files are being processed in the background.",
            "data": {
                "customer_email": customer_email,
                "payment_intent_id": payment_intent_id,
                "status": "processing",
                "processing_time_ms": round(total_time, 2)
            }
        }

        # Add transaction_id to response if created successfully
        if transaction_id:
            response_data["data"]["transaction_id"] = transaction_id
            print(f"📤 Returning transaction_id: {transaction_id}")

        return JSONResponse(content=response_data)

    except ValueError as e:
        print(f"❌ VALIDATION ERROR: {e}")
        print("=" * 80 + "\n")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {e}")
        print("=" * 80 + "\n")
        logging.error(f"Payment success error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def process_user_payment_files_background(
    customer_email: str,
    stripe_checkout_session_id: str,
    amount: Optional[float] = None,
    currency: Optional[str] = None,
    payment_metadata: Optional[PaymentMetadata] = None
):
    """
    Background task to move user transaction files from Temp to Inbox and persist payment data.
    Updates user_transactions collection status to "completed".
    Runs asynchronously without blocking HTTP response.

    Args:
        customer_email: User email address
        stripe_checkout_session_id: Square payment transaction ID
        amount: Payment amount in dollars
        currency: Currency code (default: USD)
        payment_metadata: Additional payment metadata from Square
    """
    import time
    from app.utils.user_transaction_helper import (
        get_user_transaction,
        update_user_transaction_status
    )

    task_start = time.time()

    try:
        print("\n" + "=" * 80)
        print("🔄 USER PAYMENT BACKGROUND TASK STARTED")
        print("=" * 80)
        print(f"⏱️  Started at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📋 Task Details:")
        print(f"   Customer: {customer_email}")
        print(f"   Square Transaction ID: {stripe_checkout_session_id}")
        print("=" * 80)

        # Step 0: Create or update payment using centralized service (idempotent)
        print(f"\n💾 Step 0: Creating payment record (idempotent)...")
        persist_start = time.time()

        try:
            # Use centralized payment creation service
            result = await payment_creation_service.create_or_update_payment(
                payment_intent_id=stripe_checkout_session_id,
                amount_cents=AmountConverter.dollars_to_cents(amount or 0.0),
                currency=currency or "usd",
                customer_email=customer_email,
                metadata={}
            )

            persist_time = (time.time() - persist_start) * 1000
            print(f"⏱️  Payment persistence completed in {persist_time:.2f}ms")

            if not result["created"]:
                # Payment already existed - duplicate webhook
                print(f"⚠️  Payment {stripe_checkout_session_id} already processed (duplicate)")
                logging.info(f"[PAYMENT] Duplicate user payment ignored: {stripe_checkout_session_id}")
                # Continue processing for user payments (user transaction still needs to be completed)

            payment_id = str(result["payment"]["_id"])
            print(f"✅ Payment record created/found with ID: {payment_id}")

        except Exception as e:
            persist_time = (time.time() - persist_start) * 1000
            print(f"⏱️  Payment persistence attempted in {persist_time:.2f}ms")
            print(f"⚠️  Failed to persist payment: {str(e)}")
            logging.warning(f"Failed to persist user payment {stripe_checkout_session_id}: {e}")

        # Step 1: Get transaction from user_transactions collection
        print(f"\n🔍 Step 1: Fetching user transaction...")
        fetch_start = time.time()
        transaction = await get_user_transaction(stripe_checkout_session_id)
        fetch_time = (time.time() - fetch_start) * 1000
        print(f"⏱️  Transaction fetch completed in {fetch_time:.2f}ms")

        if not transaction:
            print(f"⚠️  Transaction not found: {stripe_checkout_session_id}")
            total_time = (time.time() - task_start) * 1000
            print(f"⏱️  BACKGROUND TASK TOTAL TIME: {total_time:.2f}ms")
            print("=" * 80 + "\n")
            logging.warning(
                f"User payment background task: Transaction not found - {stripe_checkout_session_id}"
            )
            return

        print(f"✅ Transaction found:")
        print(f"   User: {transaction.get('user_name')} ({transaction.get('user_email')})")
        print(f"   Document: {transaction.get('document_url')}")
        print(f"   Status: {transaction.get('status')}")
        print(f"   Total Cost: ${transaction.get('total_cost')}")

        # Step 2: Extract file_id from document_url
        print(f"\n📁 Step 2: Extracting file information...")
        document_url = transaction.get('document_url', '')

        # Extract file_id from Google Drive URL
        # Format: https://drive.google.com/file/d/{FILE_ID}/view or similar
        file_id = None
        if '/file/d/' in document_url:
            parts = document_url.split('/file/d/')
            if len(parts) > 1:
                file_id = parts[1].split('/')[0]

        if not file_id:
            error_msg = f"Could not extract file_id from document_url: {document_url}"
            print(f"❌ {error_msg}")
            await update_user_transaction_status(
                stripe_checkout_session_id=stripe_checkout_session_id,
                new_status="failed",
                error_message=error_msg
            )
            total_time = (time.time() - task_start) * 1000
            print(f"⏱️  BACKGROUND TASK TOTAL TIME: {total_time:.2f}ms")
            print("=" * 80 + "\n")
            logging.error(f"User payment background task: {error_msg}")
            return

        print(f"✅ Extracted file_id: {file_id[:20]}...")

        # Step 3: Move file from Temp to Inbox
        print(f"\n📂 Step 3: Moving file from Temp to Inbox...")
        move_start = time.time()

        try:
            result = await google_drive_service.move_files_to_inbox_on_payment_success(
                customer_email=customer_email,
                file_ids=[file_id]
            )
            move_time = (time.time() - move_start) * 1000
            print(f"⏱️  File move completed in {move_time:.2f}ms")
            print(f"✅ Moved: {result['moved_successfully']}/{result['total_files']} files")
            print(f"📂 Inbox folder ID: {result.get('inbox_folder_id', 'N/A')}")

            if result['moved_successfully'] == 0:
                error_msg = "File move failed - no files moved successfully"
                if result.get('failed_files'):
                    error_details = result['failed_files'][0].get('error', 'Unknown error')
                    error_msg = f"File move failed: {error_details}"

                print(f"❌ {error_msg}")
                await update_user_transaction_status(
                    stripe_checkout_session_id=stripe_checkout_session_id,
                    new_status="failed",
                    error_message=error_msg
                )
                total_time = (time.time() - task_start) * 1000
                print(f"⏱️  BACKGROUND TASK TOTAL TIME: {total_time:.2f}ms")
                print("=" * 80 + "\n")
                logging.error(f"User payment background task: {error_msg}")
                return

        except Exception as move_error:
            error_msg = f"Google Drive move error: {str(move_error)}"
            print(f"❌ {error_msg}")
            await update_user_transaction_status(
                stripe_checkout_session_id=stripe_checkout_session_id,
                new_status="failed",
                error_message=error_msg
            )
            total_time = (time.time() - task_start) * 1000
            print(f"⏱️  BACKGROUND TASK TOTAL TIME: {total_time:.2f}ms")
            print("=" * 80 + "\n")
            logging.error(f"User payment background task: {error_msg}", exc_info=True)
            return

        # Step 4: Update transaction status to "completed"
        print(f"\n🔄 Step 4: Updating transaction status to 'completed'...")
        update_start = time.time()

        success = await update_user_transaction_status(
            stripe_checkout_session_id=stripe_checkout_session_id,
            new_status="completed"
        )

        update_time = (time.time() - update_start) * 1000
        print(f"⏱️  Status update completed in {update_time:.2f}ms")

        if success:
            print(f"✅ Transaction status updated to 'completed'")
        else:
            print(f"⚠️  Failed to update transaction status (transaction may not exist)")

        # Step 5: Update file status in Google Drive metadata
        print(f"\n🔄 Step 5: Updating file status in Google Drive metadata...")
        status_start = time.time()

        try:
            await google_drive_service.update_file_status(
                file_id=file_id,
                new_status="payment_confirmed",
                payment_intent_id=stripe_checkout_session_id
            )
            status_time = (time.time() - status_start) * 1000
            print(f"⏱️  File status update completed in {status_time:.2f}ms")
            print(f"✅ File status updated to 'payment_confirmed'")
        except Exception as status_error:
            print(f"⚠️  Failed to update file status: {str(status_error)[:60]}")
            logging.warning(
                f"User payment: Failed to update file status for {file_id}: {status_error}"
            )

        total_time = (time.time() - task_start) * 1000
        print(f"\n✅ USER PAYMENT BACKGROUND TASK COMPLETE")
        print(f"⏱️  TOTAL TASK TIME: {total_time:.2f}ms")
        print(f"   - Transaction fetch: {fetch_time:.2f}ms")
        print(f"   - File move: {move_time:.2f}ms")
        print(f"   - Status update: {update_time:.2f}ms")
        print("=" * 80 + "\n")

        logging.info(
            f"User payment background task completed for {customer_email}: "
            f"transaction {stripe_checkout_session_id} processed in {total_time:.2f}ms"
        )

    except Exception as e:
        total_time = (time.time() - task_start) * 1000
        print(f"\n❌ USER PAYMENT BACKGROUND TASK ERROR")
        print(f"⏱️  Failed after: {total_time:.2f}ms")
        print(f"💥 Error type: {type(e).__name__}")
        print(f"💥 Error message: {str(e)}")
        print("=" * 80 + "\n")

        # Attempt to mark transaction as failed
        try:
            from app.utils.user_transaction_helper import update_user_transaction_status
            await update_user_transaction_status(
                stripe_checkout_session_id=stripe_checkout_session_id,
                new_status="failed",
                error_message=str(e)
            )
        except Exception as update_error:
            logging.error(
                f"Failed to update transaction status after error: {update_error}"
            )

        logging.error(
            f"User payment background task error for {customer_email}: {e}",
            exc_info=True
        )


@router.post("/user-success")
async def handle_user_payment_success(
    request: PaymentSuccessRequest,
    background_tasks: BackgroundTasks
):
    """
    INSTANT user payment success webhook for individual users.
    Returns immediately, processes user transaction files in background.

    Updates user_transactions collection and moves files from Temp to Inbox.

    Expected request format:
    {
        "customerEmail": "user@example.com",
        "stripe_checkout_session_id": "txn_abc123",  // Can be in root or metadata
        "amount": 10.00,
        "currency": "USD",
        "paymentMethod": "square",
        "metadata": {
            "stripe_checkout_session_id": "txn_abc123"  // Alternative location
        }
    }
    """
    import time
    start_time = time.time()

    print("\n" + "=" * 80)
    print("⚡ INSTANT USER PAYMENT SUCCESS WEBHOOK")
    print("=" * 80)
    print(f"⏱️  Request received at: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        # Log raw request data
        print("\n📥 RAW REQUEST DATA:")
        print(f"   customer_email (root): {request.customer_email}")
        print(f"   payment_intent_id: {request.payment_intent_id}")
        print(f"   amount: {request.amount}")
        print(f"   currency: {request.currency}")
        print(f"   payment_method: {request.payment_method}")
        print(f"   timestamp: {request.timestamp}")

        # Extract stripe_checkout_session_id from request or metadata
        stripe_checkout_session_id = None

        # Try to get from root level first (check if request has stripe_checkout_session_id attribute)
        if hasattr(request, 'stripe_checkout_session_id') and getattr(request, 'stripe_checkout_session_id'):
            stripe_checkout_session_id = getattr(request, 'stripe_checkout_session_id')
            print(f"   stripe_checkout_session_id (root): {stripe_checkout_session_id}")

        # Try metadata next
        if not stripe_checkout_session_id and request.metadata:
            print(f"\n📋 METADATA:")
            print(f"   status: {request.metadata.status}")
            print(f"   cardBrand: {request.metadata.cardBrand}")
            print(f"   last4: {request.metadata.last4}")
            print(f"   receiptNumber: {request.metadata.receiptNumber}")
            print(f"   created: {request.metadata.created}")
            print(f"   simulated: {request.metadata.simulated}")
            print(f"   customer_email (metadata): {request.metadata.customer_email}")

            # Check for stripe_checkout_session_id in metadata
            if hasattr(request.metadata, 'stripe_checkout_session_id'):
                stripe_checkout_session_id = getattr(request.metadata, 'stripe_checkout_session_id')
                print(f"   stripe_checkout_session_id (metadata): {stripe_checkout_session_id}")

        # Validate stripe_checkout_session_id
        if not stripe_checkout_session_id:
            error_msg = "stripe_checkout_session_id not found in request or metadata"
            print(f"❌ VALIDATION ERROR: {error_msg}")
            print("=" * 80 + "\n")
            raise HTTPException(status_code=400, detail=error_msg)

        # Extract customer email (FAST - no I/O)
        parse_start = time.time()
        customer_email = request.get_customer_email()
        parse_time = (time.time() - parse_start) * 1000

        print(f"\n✅ EXTRACTED FIELDS (took {parse_time:.2f}ms):")
        print(f"   Customer: {customer_email}")
        print(f"   Square Transaction ID: {stripe_checkout_session_id}")
        print(f"   Amount: ${request.amount} {request.currency}")
        print(f"   Payment Method: {request.payment_method}")

        # CHECK: Has webhook already processed this payment?
        # For user payments, check user_transactions collection
        check_webhook_start = time.time()
        from app.database.mongodb import database
        existing_transaction = await database.user_transactions.find_one({
            "stripe_checkout_session_id": stripe_checkout_session_id
        })

        if existing_transaction and existing_transaction.get("webhook_processing"):
            check_webhook_time = (time.time() - check_webhook_start) * 1000
            total_time = (time.time() - start_time) * 1000

            logging.info(
                f"[CLIENT_NOTIFICATION] User payment {stripe_checkout_session_id} already "
                f"processed by webhook (webhook_processing=True), skipping"
            )

            print(f"\n⚠️  WEBHOOK ALREADY PROCESSED THIS USER PAYMENT")
            print(f"   Transaction ID: {stripe_checkout_session_id}")
            print(f"   Webhook processing flag: True")
            print(f"   Skipping client-side processing")
            print(f"⏱️  Webhook check time: {check_webhook_time:.2f}ms")
            print(f"⏱️  TOTAL TIME: {total_time:.2f}ms")
            print("=" * 80 + "\n")

            return JSONResponse(content={
                "success": True,
                "message": "User payment already processed by webhook",
                "data": {
                    "customer_email": customer_email,
                    "stripe_checkout_session_id": stripe_checkout_session_id,
                    "status": "already_processed",
                    "processed_by": "webhook",
                    "processing_time_ms": round(total_time, 2)
                }
            })

        check_webhook_time = (time.time() - check_webhook_start) * 1000
        print(f"\n✅ WEBHOOK CHECK: User payment not yet processed by webhook")
        print(f"   Proceeding with client-side processing (webhook fallback)")
        print(f"⏱️  Webhook check time: {check_webhook_time:.2f}ms")

        # Schedule background file processing for user transaction
        task_schedule_start = time.time()
        background_tasks.add_task(
            process_user_payment_files_background,
            customer_email=customer_email,
            stripe_checkout_session_id=stripe_checkout_session_id,
            amount=request.amount,
            currency=request.currency,
            payment_metadata=request.metadata
        )
        task_schedule_time = (time.time() - task_schedule_start) * 1000

        total_time = (time.time() - start_time) * 1000
        print(f"\n⚡ INSTANT RESPONSE - User payment background task scheduled (took {task_schedule_time:.2f}ms)")
        print(f"⏱️  TOTAL PROCESSING TIME: {total_time:.2f}ms")
        print("=" * 80 + "\n")

        # Return IMMEDIATELY (< 100ms)
        return JSONResponse(
            content={
                "success": True,
                "message": "Payment confirmed. Files are being processed in the background.",
                "data": {
                    "customer_email": customer_email,
                    "stripe_checkout_session_id": stripe_checkout_session_id,
                    "status": "processing",
                    "processing_time_ms": round(total_time, 2)
                }
            }
        )

    except ValueError as e:
        print(f"❌ VALIDATION ERROR: {e}")
        print("=" * 80 + "\n")
        raise HTTPException(status_code=400, detail=str(e))

    except HTTPException:
        # Re-raise HTTP exceptions without wrapping
        raise

    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {e}")
        print("=" * 80 + "\n")
        logging.error(f"User payment success error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/failure")
async def handle_payment_failure(customer_email: EmailStr, payment_intent_id: str):
    """
    SIMPLIFIED PAYMENT FAILURE HANDLER:
    1. Find all files for customer with status "awaiting_payment"
    2. Delete files from Temp folder
    """
    print(f"❌ PAYMENT FAILED for {customer_email}: {payment_intent_id}")
    
    try:
        # Find files for customer
        files_to_delete = await google_drive_service.find_files_by_customer_email(
            customer_email=customer_email,
            status="awaiting_payment"
        )
        
        if not files_to_delete:
            return JSONResponse(
                content={
                    "success": True,
                    "message": f"Payment failed but no pending files found for {customer_email}",
                    "data": {
                        "customer_email": customer_email,
                        "payment_intent_id": payment_intent_id,
                        "files_deleted": 0
                    }
                }
            )
        
        # Delete files
        file_ids = [file_info.get('file_id') for file_info in files_to_delete]
        result = await google_drive_service.delete_files_on_payment_failure(
            customer_email=customer_email,
            file_ids=file_ids
        )
        
        print(f"Payment failure cleanup: {result['deleted_successfully']}/{result['total_files']} files deleted")
        
        return JSONResponse(
            content={
                "success": True,
                "message": f"Payment failed. {result['deleted_successfully']} files deleted from Temp folder.",
                "data": {
                    "customer_email": customer_email,
                    "payment_intent_id": payment_intent_id,
                    "total_files": result['total_files'],
                    "deleted_successfully": result['deleted_successfully'],
                    "workflow": "simplified_no_sessions"
                }
            }
        )
        
    except Exception as e:
        logging.error(f"Payment failure cleanup error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clean up files: {str(e)}"
        )