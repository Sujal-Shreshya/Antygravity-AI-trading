"""
Global pytest configuration and fixtures.
Sets test environment variables and configures clean isolation for test suites.
"""

import os

# Configure test environment before any application modules load
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["DATABASE_URL_SYNC"] = "sqlite:///:memory:"
os.environ["LIVE_TRADING"] = "false"
os.environ["JWT_SECRET"] = "test_super_secure_random_string_at_least_32_characters_long"

from backend.core.config import get_settings

# Invalidate settings cache to load test environment overrides
get_settings.cache_clear()
