from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.routers import api_keys, audits, billing, geo, health, projects, public

settings = get_settings()

app = FastAPI(title="SEO Repair Kit API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(projects.router)
app.include_router(audits.router)
app.include_router(billing.router)
app.include_router(geo.router)
app.include_router(api_keys.router)
app.include_router(public.router)
