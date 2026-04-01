"""
DubKaro Backend — FastAPI Application
Run: uvicorn main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import CORS_ORIGINS, API_HOST, API_PORT, DEBUG

from routers import upload, process, status, download, api_keys

app = FastAPI(
    title="DubKaro API",
    description="AI-Powered Video Dubbing — Indian + Foreign Languages",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers (NO auth router — Flutter handles it)
app.include_router(upload.router)
app.include_router(process.router)
app.include_router(status.router)
app.include_router(download.router)
app.include_router(api_keys.router)


@app.get("/")
def root():
    return {
        "app": "DubKaro",
        "version": "2.0.0",
        "status": "running",
        "docs": "/docs",
        "features": [
            "Multi-speaker detection",
            "30+ languages (Indian + Foreign)",
            "Voice cloning per speaker",
            "API key system with token limits",
        ],
    }


@app.get("/health")
def health_check():
    import torch
    return {
        "status": "healthy",
        "gpu_available": torch.cuda.is_available(),
        "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=API_HOST, port=API_PORT, reload=DEBUG)