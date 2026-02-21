"""
LinkedIn Scraper HTTP API Server.

Run on Ahmed's Mac (needs Chrome + LinkedIn session).
Rover calls this from the sandbox for deep contact enrichment.

Usage:
    python -m services.linkedin_scraper.server
    # or
    python services/linkedin_scraper/scraper.py --serve --port 8585
"""

import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Lazy imports — only loaded when server mode is used
app = None


def create_app():
    """Create and configure the FastAPI app."""
    try:
        from fastapi import FastAPI, HTTPException
        from fastapi.middleware.cors import CORSMiddleware
        from pydantic import BaseModel
    except ImportError:
        raise ImportError(
            "FastAPI not installed. Run: pip install fastapi uvicorn\n"
            "These are only needed on the machine running the scraper server."
        )

    from .scraper import LinkedInScraper

    class ScrapeRequest(BaseModel):
        url: str
        generate_summary: bool = True

    class ScrapeResponse(BaseModel):
        name: str = ""
        headline: str = ""
        location: str = ""
        about: str = ""
        experience: list = []
        education: list = []
        skills: list = []
        certifications: list = []
        summary: str = ""
        profile_url: str = ""
        scraped_at: str = ""

    # Shared scraper instance (reuses Chrome session)
    scraper_instance = None

    @asynccontextmanager
    async def lifespan(app):
        nonlocal scraper_instance
        api_key = os.getenv("ANTHROPIC_API_KEY")
        linkedin_email = os.getenv("LINKEDIN_EMAIL")
        linkedin_password = os.getenv("LINKEDIN_PASSWORD")
        user_data_dir = os.getenv("CHROME_USER_DATA_DIR")

        if not api_key:
            logger.error("ANTHROPIC_API_KEY not set")
        else:
            scraper_instance = LinkedInScraper(
                api_key=api_key,
                headless=False,
                linkedin_email=linkedin_email,
                linkedin_password=linkedin_password,
                user_data_dir=user_data_dir,
            )
            logger.info("LinkedIn scraper initialized")

        yield

        if scraper_instance:
            scraper_instance.cleanup()
            logger.info("Scraper cleaned up")

    app = FastAPI(
        title="LinkedIn Scraper API",
        description="Deep LinkedIn profile scraping for Rover Network Agent",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health():
        return {"status": "ok", "scraper_ready": scraper_instance is not None}

    @app.post("/scrape", response_model=ScrapeResponse)
    async def scrape_profile(req: ScrapeRequest):
        if not scraper_instance:
            raise HTTPException(status_code=503, detail="Scraper not initialized — check ANTHROPIC_API_KEY")

        if "linkedin.com/in/" not in req.url:
            raise HTTPException(status_code=400, detail="Invalid LinkedIn URL")

        import asyncio
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, scraper_instance.scrape_profile_to_dict, req.url)

        if not result:
            raise HTTPException(status_code=500, detail="Failed to scrape profile")

        return ScrapeResponse(**result)

    return app


def start_server(port: int = 8585):
    """Start the FastAPI server."""
    import uvicorn
    application = create_app()
    logger.info(f"Starting LinkedIn Scraper API on port {port}")
    uvicorn.run(application, host="0.0.0.0", port=port)


if __name__ == "__main__":
    start_server()
