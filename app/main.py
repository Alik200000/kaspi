from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import engine, Base

# Import all models to ensure metadata registration
import app.modules.catalog.models
import app.modules.suppliers.models
import app.modules.pricing.models
import app.modules.integrations.kaspi.models
import app.modules.orders.models
import app.modules.integrations.warehouse.models
import app.modules.ai_assistant.models
import app.modules.analytics.models

# Import routers
from app.modules.auth.router import router as auth_router
from app.modules.catalog.router import router as catalog_router
from app.modules.suppliers.router import router as suppliers_router
from app.modules.integrations.kaspi.router import router as kaspi_router
from app.modules.orders.router import router as orders_router
from app.modules.tasks.router import router as tasks_router
from app.modules.notifications.router import router as notifications_router
from app.modules.integrations.warehouse.router import router as warehouse_router
from app.modules.ai_assistant.router import router as ai_router
from app.modules.analytics.router import router as analytics_router
from app.modules.pricing.advanced_router import router as advanced_pricing_router
from app.modules.logistics.router import router as logistics_router
from app.modules.integrations.multichannel.router import router as multichannel_router
from app.workers.scheduler import scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Auto-create tables on startup (both local SQLite and cloud PostgreSQL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Start periodic background automation jobs
    scheduler.start()
    yield
    # Stop background jobs and cleanup
    scheduler.stop()
    await engine.dispose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description="SaaS Platform for Supplier Aggregation and Kaspi Marketplace Automation",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount module routers under API v1
api_prefix = settings.API_V1_STR
app.include_router(auth_router, prefix=api_prefix)
app.include_router(catalog_router, prefix=api_prefix)
app.include_router(suppliers_router, prefix=api_prefix)
app.include_router(kaspi_router, prefix=api_prefix)
app.include_router(orders_router, prefix=api_prefix)
app.include_router(tasks_router, prefix=api_prefix)
app.include_router(notifications_router, prefix=api_prefix)
app.include_router(warehouse_router, prefix=api_prefix)
app.include_router(ai_router, prefix=api_prefix)
app.include_router(analytics_router, prefix=api_prefix)
app.include_router(advanced_pricing_router, prefix=api_prefix)
app.include_router(logistics_router, prefix=api_prefix)
app.include_router(multichannel_router, prefix=api_prefix)


from fastapi.responses import HTMLResponse, FileResponse
import os
from pathlib import Path

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


@app.get("/", response_class=HTMLResponse, tags=["Dashboard UI"])
@app.get("/ui", response_class=HTMLResponse, tags=["Dashboard UI"])
async def dashboard_ui():
    index_file = TEMPLATES_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return HTMLResponse("<h1>Dashboard under construction</h1>")


@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "project": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT
    }


@app.get("/api", tags=["Root"])
async def root():
    return {
        "message": f"Welcome to {settings.PROJECT_NAME}",
        "docs_url": "/docs",
        "redoc_url": "/redoc",
        "api_v1": settings.API_V1_STR
    }
