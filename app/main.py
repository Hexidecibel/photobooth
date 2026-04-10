from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import api

app = FastAPI(
    title="photobooth",
    description="we are going to take pibooth and upgrade the hell out of it. and make it into a modern product that runs great on new raspberry pis. i have a photo booth we can use to test! ",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api.router, prefix="/api")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Welcome to photobooth"}