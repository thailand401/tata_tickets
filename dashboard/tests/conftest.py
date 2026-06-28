"""Test configuration and shared fixtures."""

from __future__ import annotations

import os

# Provide a deterministic JWT secret for security tests before app import.
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-secret-key")
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test-service-key")
os.environ.setdefault("SUPABASE_ANON_KEY", "test-anon-key")
