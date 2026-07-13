from fastapi import FastAPI
from app.api.health import router as health_router
from app.api.recommendations import router as recommendations_router
from app.api.shopping_list import router as shopping_router
from app.api.substitutions import router as substitutions_router

# Create FastAPI application
app = FastAPI(
    title="NourishAI API", description="Smart Recipe Recommender API", version="0.1.0"
)

# Include routers
app.include_router(health_router)
app.include_router(recommendations_router)
app.include_router(shopping_router)
app.include_router(substitutions_router)


# Root endpoint
@app.get("/")
def root():
    """Root endpoint - API information."""
    return {"message": "Welcome to NourishAI API", "docs": "/docs", "health": "/health"}
