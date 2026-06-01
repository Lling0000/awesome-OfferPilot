from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from offerpilot.db import init_db
from offerpilot.routes import api, web

PACKAGE_DIR = Path(__file__).resolve().parent


def create_app() -> FastAPI:
    init_db()
    app = FastAPI(
        title="OfferPilot",
        description="Evidence-backed job search tracking and interview preparation.",
        version="0.1.0",
    )
    app.mount("/static", StaticFiles(directory=PACKAGE_DIR / "static"), name="static")
    app.include_router(api.router, prefix="/api")
    app.include_router(web.router)
    return app
