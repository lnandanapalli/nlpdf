import os
import sys

from slowapi import Limiter

from backend.security import get_client_ip

# Disable rate limiting when running tests to avoid 429 errors in the test suite
# We check for 'pytest' in modules because environment variables might not be set yet during import
is_test = (
    os.getenv("PYTEST_CURRENT_TEST") is not None
    or os.getenv("GITHUB_ACTIONS") == "true"
    or "pytest" in sys.modules
)
limiter = Limiter(key_func=get_client_ip, default_limits=["60/minute"], enabled=not is_test)
