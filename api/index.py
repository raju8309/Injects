"""
Vercel entry point for the FastAPI application.
"""
from api.main import app

# Vercel Python runtime looks for the ASGI app as 'app'
# This is the standard entry point for Vercel Python deployments
__all__ = ["app"]
