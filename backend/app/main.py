from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.agent import router as agent_router
from app.api.config import router as config_router
from app.api.cuisines import router as cuisines_router
from app.api.health import router as health_router
from app.api.ingredients import router as ingredients_router
from app.api.orchestrate import router as orchestrate_router
from app.api.pantry import router as pantry_router
from app.api.profile import router as profile_router
from app.api.recipes import router as recipes_router
from app.api.recommendations import router as recommendations_router
from app.api.shopping_list import router as shopping_router
from app.api.substitutions import router as substitutions_router
from app.api.traces import router as traces_router
from app.core.config import settings

# Create FastAPI application
app = FastAPI(
    title="NourishAI API", description="Smart Recipe Recommender API", version="0.1.0"
)

# CORS for the Next.js frontend (Stage 5). Bearer tokens, not cookies, so
# allow_credentials stays False and the token header is explicitly allowed.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type", "X-User-Key"],
    expose_headers=["X-Cache"],
)

# Include routers
app.include_router(health_router)
app.include_router(recommendations_router)
app.include_router(recipes_router)
app.include_router(shopping_router)
app.include_router(substitutions_router)
app.include_router(agent_router)
app.include_router(profile_router)
app.include_router(orchestrate_router)
app.include_router(traces_router)
app.include_router(ingredients_router)
app.include_router(cuisines_router)
app.include_router(pantry_router)
app.include_router(config_router)


# Root endpoint
@app.get("/")
def root():
    """Root endpoint - API information."""
    return {"message": "Welcome to NourishAI API", "docs": "/docs", "health": "/health"}
