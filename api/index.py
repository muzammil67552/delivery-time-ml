"""Vercel Serverless Function Entry Point for Delivery Time Prediction API."""

import sys
import os

# Ensure the root project directory is on sys.path so modules like app, src resolve correctly
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.main import app

# Export app for Vercel ASGI runner
app = app
