"""
Test Logger Utility for Server-Side Integration Tests

Provides consistent, human-readable logging for all tests that:
1. Clearly states the PURPOSE of each test
2. Shows all API requests being made (visible in server logs)
3. Displays test RESULTS in human-readable format
4. Uses visual markers for easy log scanning

Usage in tests:
    from tests.test_logger import TestLogger

    class TestMyFeature:
        async def test_something(self, http_client):
            log = TestLogger("test_something")
            log.start("Verify user creation via POST /api/users")

            log.request("POST", "/api/users", {"name": "test"})
            response = await http_client.post("/api/users", json={"name": "test"})
            log.response(response.status_code, response.json())

            assert response.status_code == 201
            log.passed("User created successfully with ID: {id}")
"""

import logging
import json
from datetime import datetime
from typing import Any, Dict, Optional

# Configure logging to output to stdout with clear formatting
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger("test_logger")


class TestLogger:
    """
    Human-readable test logger that outputs clear test purpose and results.

    All output is designed to be visible in both pytest output (-s flag)
    and server log files (via X-Test headers on HTTP requests).
    """

    def __init__(self, test_name: str):
        """
        Initialize logger for a specific test.

        Args:
            test_name: Name of the test function (e.g., "test_create_user")
        """
        self.test_name = test_name
        self.start_time = None
        self.step_count = 0

    def start(self, purpose: str):
        """
        Log test start with clear PURPOSE statement.

        Args:
            purpose: Human-readable description of what this test verifies
        """
        self.start_time = datetime.now()
        self.step_count = 0

        print("\n" + "=" * 80)
        print(f"TEST: {self.test_name}")
        print(f"PURPOSE: {purpose}")
        print(f"STARTED: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)

    def step(self, description: str):
        """
        Log a test step.

        Args:
            description: What this step does
        """
        self.step_count += 1
        print(f"\n  STEP {self.step_count}: {description}")

    def request(self, method: str, url: str, body: Optional[Dict] = None, headers: Optional[Dict] = None):
        """
        Log an HTTP request being made (visible in server logs).

        Args:
            method: HTTP method (GET, POST, PUT, DELETE, etc.)
            url: Request URL/path
            body: Request body (optional)
            headers: Request headers (optional)
        """
        print(f"\n  --> {method} {url}")
        if body:
            body_str = json.dumps(body, indent=4, default=str)
            # Truncate if too long
            if len(body_str) > 500:
                body_str = body_str[:500] + "\n... (truncated)"
            print(f"      Body: {body_str}")
        if headers:
            safe_headers = {k: v if 'auth' not in k.lower() else '***' for k, v in headers.items()}
            print(f"      Headers: {safe_headers}")

    def response(self, status_code: int, body: Any = None, duration_ms: Optional[float] = None):
        """
        Log HTTP response received.

        Args:
            status_code: HTTP status code
            body: Response body (optional)
            duration_ms: Request duration in milliseconds (optional)
        """
        status_emoji = "+" if 200 <= status_code < 300 else "!"
        duration_str = f" ({duration_ms:.0f}ms)" if duration_ms else ""

        print(f"  <-- {status_emoji} {status_code}{duration_str}")
        if body:
            body_str = json.dumps(body, indent=4, default=str) if isinstance(body, (dict, list)) else str(body)
            # Truncate if too long
            if len(body_str) > 1000:
                body_str = body_str[:1000] + "\n... (truncated)"
            print(f"      Response: {body_str}")

    def assert_check(self, description: str, passed: bool, actual: Any = None, expected: Any = None):
        """
        Log an assertion check with result.

        Args:
            description: What is being checked
            passed: Whether the assertion passed
            actual: Actual value (optional)
            expected: Expected value (optional)
        """
        status = "PASS" if passed else "FAIL"
        emoji = "[OK]" if passed else "[X]"

        print(f"  {emoji} CHECK: {description} - {status}")
        if not passed and actual is not None:
            print(f"      Expected: {expected}")
            print(f"      Actual: {actual}")

    def info(self, message: str):
        """Log informational message."""
        print(f"  [i] {message}")

    def warning(self, message: str):
        """Log warning message."""
        print(f"  [!] WARNING: {message}")

    def error(self, message: str):
        """Log error message."""
        print(f"  [X] ERROR: {message}")

    def passed(self, summary: str = ""):
        """
        Log test PASSED with summary.

        Args:
            summary: Optional summary of what was verified
        """
        duration = (datetime.now() - self.start_time).total_seconds() if self.start_time else 0

        print("\n" + "-" * 80)
        print(f"RESULT: PASSED")
        if summary:
            print(f"SUMMARY: {summary}")
        print(f"DURATION: {duration:.2f}s")
        print("-" * 80 + "\n")

    def failed(self, reason: str):
        """
        Log test FAILED with reason.

        Args:
            reason: Why the test failed
        """
        duration = (datetime.now() - self.start_time).total_seconds() if self.start_time else 0

        print("\n" + "-" * 80)
        print(f"RESULT: FAILED")
        print(f"REASON: {reason}")
        print(f"DURATION: {duration:.2f}s")
        print("-" * 80 + "\n")


def get_test_headers(test_name: str) -> Dict[str, str]:
    """
    Get HTTP headers that identify test requests in server logs.

    These headers are logged by the server, making it easy to trace
    which requests came from which tests.

    Args:
        test_name: Name of the test making the request

    Returns:
        Dict with X-Test-* headers
    """
    return {
        "X-Test-Name": test_name,
        "X-Test-Timestamp": datetime.now().isoformat(),
        "X-Request-Source": "pytest-integration"
    }


# Convenience function for quick logging
def log_test_start(test_name: str, purpose: str) -> TestLogger:
    """
    Quick start for test logging.

    Usage:
        log = log_test_start("test_create_user", "Verify POST /api/users creates a new user")
    """
    log = TestLogger(test_name)
    log.start(purpose)
    return log
