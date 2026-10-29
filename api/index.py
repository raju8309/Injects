"""
Vercel entry point for the FastAPI application.
"""
from api.main import app

# Vercel Python runtime looks for the ASGI app
handler = app

