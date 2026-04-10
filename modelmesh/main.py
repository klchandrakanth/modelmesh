from fastapi import FastAPI
from modelmesh.api.v1.chat import router as chat_router
from modelmesh.api.v1.models import router as models_router

def create_app() -> FastAPI:
    app = FastAPI(title="ModelMesh", version="0.1.0")
    app.include_router(chat_router)
    app.include_router(models_router)
    return app

app = create_app()
