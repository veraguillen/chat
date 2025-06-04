from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.get_version()  # Updated to use the new method
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import and add routers
from app.api import router
app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "run:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=True
    )