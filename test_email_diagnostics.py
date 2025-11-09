#!/usr/bin/env python3
"""
Quick test script to run email diagnostics locally without starting the server.
"""

import sys
import os
import asyncio

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from app.services.email_service import email_service


def print_section(title: str):
    """Print formatted section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


async def main():
    """Run all email diagnostic tests."""
    print_section("EMAIL SMTP DIAGNOSTIC SUITE")
    print("Testing Yahoo SMTP configuration and connectivity...")

    # 1. Configuration diagnostics
    print_section("1. Configuration Diagnostics")
    issues = email_service.diagnose_yahoo_account()
    if issues:
        print(f"\n❌ Found {len(issues)} configuration issue(s):")
        for i, issue in enumerate(issues, 1):
            print(f"   {i}. {issue}")
    else:
        print("\n✅ All configuration checks passed!")

    # 2. Connection test
    print_section("2. Connection Test")
    connection_result = email_service.test_connection()
    if connection_result["success"]:
        print("\n✅ SMTP connection and authentication successful!")
        print(f"   Host: {connection_result['details']['host']}:{connection_result['details']['port']}")
        print(f"   Username: {connection_result['details']['username']}")
        print(f"   TLS: {connection_result['details']['tls']}")
    else:
        print(f"\n❌ Connection failed: {connection_result.get('error', 'Unknown error')}")
        return

    # 3. Minimal SMTP test (the critical one)
    print_section("3. Minimal SMTP Send Test (CRITICAL)")
    print("Sending ultra-minimal test email with full SMTP debug trace...")
    print("This will show the exact SMTP command where the 550 error occurs.\n")

    to_email = input("Enter recipient email [danishevsky@gmail.com]: ").strip()
    if not to_email:
        to_email = "danishevsky@gmail.com"

    smtp_result = email_service.test_minimal_smtp(to_email=to_email)

    print("\n" + "-" * 80)
    print("MINIMAL SMTP TEST RESULTS:")
    print("-" * 80)
    print(f"  Connection:     {'✅' if smtp_result['connection_ok'] else '❌'}")
    print(f"  Authentication: {'✅' if smtp_result['auth_ok'] else '❌'}")
    print(f"  Send Email:     {'✅' if smtp_result['send_ok'] else '❌'}")

    if not smtp_result['send_ok']:
        print(f"\n❌ SMTP send failed!")
        print(f"   Failed at command: {smtp_result['smtp_command_that_failed']}")
        print(f"   Error: {smtp_result['error']}")

        # Provide specific guidance based on failure
        if smtp_result['smtp_command_that_failed'] == "RCPT TO":
            print("\n⚠️  DIAGNOSIS:")
            print("   Yahoo SMTP is rejecting the RECIPIENT email address.")
            print("   This means Yahoo's SMTP API has stricter policies than webmail.")
            print("\n   RECOMMENDED SOLUTIONS:")
            print("   1. Test with different recipient domain")
            print("   2. Switch to transactional email service (SendGrid, AWS SES)")
            print("   3. Add recipient to Yahoo contacts, then retry")
        elif smtp_result['smtp_command_that_failed'] == "DATA":
            print("\n⚠️  DIAGNOSIS:")
            print("   Yahoo accepted the recipient but rejected message content.")
            print("\n   RECOMMENDED SOLUTIONS:")
            print("   1. Ensure Date and Message-ID headers are present")
            print("   2. Simplify message content (remove HTML/links)")
            print("   3. Test with plain text only")
    else:
        print("\n✅ Minimal SMTP test PASSED!")
        print("   Yahoo SMTP successfully sent email to recipient.")

    # 4. EmailMessage API test
    print_section("4. EmailMessage API Test")
    print("Testing with alternative Python email API...\n")

    api_result = email_service.test_with_email_message(to_email=to_email)

    print("\n" + "-" * 80)
    print("EmailMessage API TEST RESULTS:")
    print("-" * 80)
    print(f"  send_message(): {'✅' if api_result['email_message_api'] else '❌'}")
    print(f"  sendmail():     {'✅' if api_result['sendmail_api'] else '❌'}")

    if api_result['error']:
        print(f"\n   Error: {api_result['error']}")

    # Summary and recommendations
    print_section("SUMMARY AND RECOMMENDATIONS")

    if issues:
        print("\n🔧 CONFIGURATION ISSUES DETECTED:")
        print("   Fix these configuration problems first:")
        for i, issue in enumerate(issues, 1):
            print(f"   {i}. {issue}")
        print("\n   See EMAIL_SMTP_DIAGNOSTICS.md for detailed fix instructions.")
        return

    if not connection_result["success"]:
        print("\n❌ SMTP CONNECTION FAILED:")
        print("   Cannot connect to Yahoo SMTP server.")
        print("   Check host, port, credentials, and network connectivity.")
        return

    if smtp_result['send_ok'] or api_result['email_message_api']:
        print("\n✅ EMAIL SERVICE IS WORKING!")
        print("   All tests passed. You can send emails successfully.")
        print("\n   Next steps:")
        print("   1. Test translation notification email")
        print("   2. Monitor for 550 errors in production")
        print("   3. Consider switching to SendGrid for better reliability")
    else:
        print("\n❌ YAHOO SMTP POLICY RESTRICTION DETECTED:")
        print("   Authentication works, but Yahoo is blocking email sends.")
        print(f"   Failed at: {smtp_result['smtp_command_that_failed']}")
        print("\n   ROOT CAUSE:")
        print("   Yahoo SMTP API has stricter policies than webmail.")
        print("   This is a Yahoo limitation, not a code issue.")
        print("\n   RECOMMENDED SOLUTION:")
        print("   Switch to a transactional email service:")
        print("   • SendGrid (100 emails/day free)")
        print("   • AWS SES ($0.10 per 1000 emails)")
        print("   • Mailgun (5,000 emails/month free)")
        print("   • Postmark (100 emails/month free)")
        print("\n   See EMAIL_SMTP_DIAGNOSTICS.md for setup instructions.")

    print("\n" + "=" * 80)
    print("  For detailed SMTP protocol trace, check the logs above")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
