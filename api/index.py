"""
Vercel serverless function entry point.
"""
from api.main import app

# Vercel will use this as the handler
handler = app
