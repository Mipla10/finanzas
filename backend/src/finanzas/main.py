"""Punto de entrada: arma la app según la configuración (plan §1.2, §5.6)."""

from fastapi import FastAPI

from finanzas import __version__
from finanzas.api.routers import health
from finanzas.config import Settings

API_PREFIX = "/api/v1"


def create_app(settings: Settings | None = None) -> FastAPI:
    """Fábrica de la app. Sin configuración válida, no arranca (RNF-4)."""
    settings = settings or Settings()
    is_local = settings.app_env == "local"
    app = FastAPI(
        title="finanzas — núcleo",
        version=__version__,
        # Documentación pública solo en local; desactivada en producción.
        docs_url="/docs" if is_local else None,
        redoc_url=None,
        openapi_url="/openapi.json" if is_local else None,
    )
    app.state.settings = settings
    app.include_router(health.router, prefix=API_PREFIX)
    return app


app = create_app()
