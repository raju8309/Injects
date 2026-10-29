"""
Vercel entry point for the FastAPI application.
"""
from api.main import app

# Vercel Python runtime looks for the ASGI app as 'app'
__all__ = ["app"]
