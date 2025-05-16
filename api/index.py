from app import app

# This file is needed for Vercel serverless deployment
# All it does is import and expose the FastAPI app

# Handler function for serverless deployment
handler = app
