import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from app.api.routes import router
from app.autopilot import AutopilotService
from app.manual_recommendations import ManualRecommendationService
from app.config import get_settings
from app.db import create_database, sqlite_database_file
from app.migration_runner import run_pending_migrations
from app.logging_config import configure_logging
from app.providers.registry import build_provider_registry
from app.repositories import Repositories
from app.services.jobs import JobService
from app.website_analysis import WebsiteAnalysisService
from app.wordpress_connector import WordPressConnectorService

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    started = time.perf_counter()
    settings = get_settings()
    configure_logging(settings.log_level)

    await asyncio.to_thread(run_pending_migrations, settings.database_url)
    database = create_database(settings.database_url)
    db_file = sqlite_database_file(settings.database_url)
    if db_file is not None:
        logger.info("Using SQLite database at %s", db_file)

    repositories = Repositories(database.session_factory)
    registry = build_provider_registry(settings)
    app.state.settings = settings
    job_service = JobService(settings, registry, repositories)
    app.state.job_service = job_service
    website_analysis_service = WebsiteAnalysisService(
        registry.content_generation,
        repositories,
        job_service,
        settings,
        registry.video,
    )
    app.state.website_analysis_service = website_analysis_service
    app.state.autopilot_service = AutopilotService(
        settings=settings,
        repositories=repositories,
        website_analysis=website_analysis_service,
        job_service=job_service,
    )
    app.state.manual_recommendation_service = ManualRecommendationService(
        settings=settings,
        repositories=repositories,
        openai_client=getattr(registry.content_generation, "client", None),
    )
    wordpress_connector_service = WordPressConnectorService(
        settings=settings,
        repositories=repositories,
        job_service=job_service,
    )
    job_service.wordpress_connector_service = wordpress_connector_service
    app.state.wordpress_connector_service = wordpress_connector_service
    app.state.repositories = repositories
    app.state.database = database

    logger.info("Application startup complete in %.2fs", time.perf_counter() - started)
    try:
        yield
    finally:
        await website_analysis_service.cancel_active_analyses("Application shutdown cancelled active analysis.")
        await database.close()


app = FastAPI(title="Trendplot", version="0.2.0", lifespan=lifespan)
app.include_router(router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
