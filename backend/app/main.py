from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.agent1 import router as agent1_router
from app.api.routes.agent2 import router as agent2_router
from app.api.routes.agent3 import router as agent3_router
from app.api.routes.health import router as health_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(health_router, prefix=settings.api_v1_prefix)
app.include_router(agent1_router, prefix=settings.api_v1_prefix)
app.include_router(agent2_router, prefix=settings.api_v1_prefix)
app.include_router(agent3_router, prefix=settings.api_v1_prefix)
