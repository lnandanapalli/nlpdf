"""Shared rate limiter instance for the application."""

from slowapi import Limiter

from backend.security import get_client_ip

limiter = Limiter(key_func=get_client_ip, default_limits=["60/minute"])
