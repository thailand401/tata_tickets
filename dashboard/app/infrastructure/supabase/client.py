"""Supabase client factories (service-role for backend, anon for auth flows)."""

from __future__ import annotations

from functools import lru_cache

from supabase import Client, create_client

from app.core.exceptions import AppError
from app.core.settings import get_settings


@lru_cache
def get_service_client() -> Client:
    """Client using the service_role key. Bypasses RLS — backend use only."""
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_key:
        raise AppError("Supabase URL / service key not configured")
    return create_client(settings.supabase_url, settings.supabase_service_key)


@lru_cache
def get_anon_client() -> Client:
    """Client using the anon key. Used for auth (login/refresh) flows."""
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_anon_key:
        raise AppError("Supabase URL / anon key not configured")
    return create_client(settings.supabase_url, settings.supabase_anon_key)
