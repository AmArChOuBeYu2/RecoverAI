import sys
import os

# Ensure root directory is in sys.path for Vercel Serverless Function imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.main import app

# Vercel Serverless Function handler
app = app
