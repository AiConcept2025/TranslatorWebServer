"""
Email testing and diagnostic endpoints.
"""

import logging
from typing import Optional
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr

from app.services.email_service import email_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/test-email", tags=["Email Testing"])


class EmailTestRequest(BaseModel):
    """Request model for sending test email."""
    to_email: EmailStr
    subject: str = "Test Email"
    body_text: str = "This is a test email."
    debug: bool = False


@router.get("/diagnostics")
async def email_diagnostics():
    """
    Run comprehensive email service diagnostics.

    Returns configuration checks and Yahoo SMTP-specific validation.
    """
    logger.info("Running email service diagnostics...")

    # Run Yahoo configuration checks
    issues = email_service.diagnose_yahoo_account()

    # Test basic connection
    connection_test = email_service.test_connection()

    return JSONResponse(content={
        "success": True,
        "data": {
            "configuration_issues": issues,
            "connection_test": connection_test,
            "smtp_config": {
                "host": email_service.smtp_host,
                "port": email_service.smtp_port,
                "username": email_service.smtp_username,
                "email_from": email_service.email_from,
                "tls_enabled": email_service.smtp_use_tls,
                "ssl_enabled": email_service.smtp_use_ssl
            }
        }
    })


@router.post("/minimal-smtp")
async def test_minimal_smtp(to_email: EmailStr = Query(..., description="Recipient email address")):
    """
    Send ultra-minimal test email to diagnose SMTP protocol-level issues.

    This test bypasses all complex message building and sends the simplest
    possible email to identify where the 550 error occurs in the SMTP conversation.

    Returns:
    - Which SMTP commands succeeded (connection, auth, send)
    - Exact SMTP command that failed
    - Full SMTP protocol trace (in logs)
    """
    logger.info(f"Running minimal SMTP test to {to_email}...")

    results = email_service.test_minimal_smtp(to_email=str(to_email))

    return JSONResponse(content={
        "success": results.get("send_ok", False),
        "data": results,
        "message": "Check server logs for full SMTP protocol trace"
    })


@router.post("/email-message-api")
async def test_email_message_api(to_email: EmailStr = Query(..., description="Recipient email address")):
    """
    Test with Python's newer EmailMessage API instead of MIME.

    Some SMTP servers behave differently with different message APIs.
    This test tries both send_message() and lower-level sendmail().
    """
    logger.info(f"Testing EmailMessage API to {to_email}...")

    results = email_service.test_with_email_message(to_email=str(to_email))

    return JSONResponse(content={
        "success": results.get("email_message_api", False) or results.get("sendmail_api", False),
        "data": results,
        "message": "Check server logs for full test output"
    })


@router.post("/send-test-email")
async def send_test_email(request: EmailTestRequest):
    """
    Send a test email with optional SMTP debug mode.

    When debug=true, enables full SMTP protocol tracing and diagnostic logging.
    """
    from app.models.email import EmailRequest

    logger.info(f"Sending test email to {request.to_email} (debug={request.debug})...")

    # Create email request
    email_request = EmailRequest(
        to_email=request.to_email,
        to_name="Test Recipient",
        subject=request.subject,
        body_text=request.body_text,
        body_html=f"<html><body><p>{request.body_text}</p></body></html>"
    )

    # Send with debug mode if requested
    result = email_service.send_email(email_request, debug=request.debug)

    return JSONResponse(content={
        "success": result.success,
        "message": result.message,
        "error": result.error,
        "recipient": result.recipient,
        "sent_at": result.sent_at,
        "debug_note": "Check server logs for full SMTP trace" if request.debug else None
    })


@router.get("/full-diagnostic-suite")
async def full_diagnostic_suite(to_email: EmailStr = Query("danishevsky@gmail.com")):
    """
    Run all email diagnostic tests in sequence.

    This endpoint runs:
    1. Configuration validation
    2. Connection test
    3. Minimal SMTP test
    4. EmailMessage API test

    WARNING: This will attempt to send 2 test emails.
    """
    logger.info("=" * 80)
    logger.info("RUNNING FULL EMAIL DIAGNOSTIC SUITE")
    logger.info("=" * 80)

    results = {}

    # 1. Configuration check
    logger.info("\n[1/4] Configuration diagnostics...")
    issues = email_service.diagnose_yahoo_account()
    results["configuration"] = {
        "issues_found": len(issues),
        "issues": issues
    }

    # 2. Connection test
    logger.info("\n[2/4] Testing SMTP connection...")
    connection_test = email_service.test_connection()
    results["connection"] = connection_test

    # 3. Minimal SMTP test
    logger.info("\n[3/4] Testing minimal SMTP send...")
    minimal_test = email_service.test_minimal_smtp(to_email=str(to_email))
    results["minimal_smtp"] = minimal_test

    # 4. EmailMessage API test
    logger.info("\n[4/4] Testing EmailMessage API...")
    api_test = email_service.test_with_email_message(to_email=str(to_email))
    results["email_message_api"] = api_test

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("DIAGNOSTIC SUITE COMPLETE")
    logger.info("=" * 80)
    logger.info(f"Configuration issues: {len(issues)}")
    logger.info(f"Connection successful: {connection_test.get('success', False)}")
    logger.info(f"Minimal SMTP successful: {minimal_test.get('send_ok', False)}")
    logger.info(f"EmailMessage API successful: {api_test.get('email_message_api', False)}")
    logger.info("=" * 80)

    overall_success = (
        len(issues) == 0 and
        connection_test.get('success', False) and
        (minimal_test.get('send_ok', False) or api_test.get('email_message_api', False))
    )

    return JSONResponse(content={
        "success": overall_success,
        "data": results,
        "summary": {
            "configuration_issues": len(issues),
            "connection_ok": connection_test.get('success', False),
            "can_send_email": minimal_test.get('send_ok', False) or api_test.get('email_message_api', False),
            "recommendation": _get_recommendation(results)
        }
    })


def _get_recommendation(results: dict) -> str:
    """Generate recommendation based on diagnostic results."""
    config_issues = results.get("configuration", {}).get("issues", [])
    connection_ok = results.get("connection", {}).get("success", False)
    smtp_send_ok = results.get("minimal_smtp", {}).get("send_ok", False)

    if config_issues:
        return f"Fix configuration issues: {', '.join(config_issues)}"

    if not connection_ok:
        return "Cannot connect to SMTP server. Check host, port, and credentials."

    if not smtp_send_ok:
        error = results.get("minimal_smtp", {}).get("error", "Unknown error")
        failed_cmd = results.get("minimal_smtp", {}).get("smtp_command_that_failed", "Unknown")

        if "Recipients refused" in error or failed_cmd == "RCPT TO":
            return "Yahoo is rejecting the recipient email address via SMTP API. This is a Yahoo policy restriction. Consider using SendGrid or AWS SES instead."

        if "550" in error:
            return "Yahoo SMTP returning 550 'Mailbox unavailable'. This typically means Yahoo is blocking sends to this recipient via SMTP API, even though webmail works. Consider switching to a transactional email service (SendGrid, AWS SES, Mailgun)."

        return f"SMTP send failed at {failed_cmd} command: {error}"

    return "All tests passed! Email service is working correctly."
