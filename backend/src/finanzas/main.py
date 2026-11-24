"""Punto de entrada: arma la app según la configuración (plan §1.2, §5.6)."""

from collections.abc import Sequence

from fastapi import APIRouter, Depends, FastAPI

from finanzas import __version__
from finanzas.api.deps import require_password
from finanzas.api.errors import install_error_handlers
from finanzas.api.routers import health
from finanzas.config import Settings

API_PREFIX = "/api/v1"

# Routers de recursos (cuentas, movimientos…). Todos nacen protegidos.
PROTECTED_ROUTERS: list[APIRouter] = []


def create_app(
    settings: Settings | None = None,
    protected_routers: Sequence[APIRouter] | None = None,
) -> FastAPI:
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
    install_error_handlers(app)

    # Público: solo /health.
    app.include_router(health.router, prefix=API_PREFIX)

    # Protegido: todo lo demás exige la contraseña.
    protected = APIRouter(dependencies=[Depends(require_password)])
    for router in PROTECTED_ROUTERS if protected_routers is None else protected_routers:
        protected.include_router(router)
    app.include_router(protected, prefix=API_PREFIX)
    return app


app = create_app()
