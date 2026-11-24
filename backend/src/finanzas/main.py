"""Punto de entrada: arma la app según la configuración (plan §1.2, §5.6)."""

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI
from sqlalchemy.orm import Session

from finanzas import __version__
from finanzas.api.deps import require_password
from finanzas.api.errors import install_error_handlers
from finanzas.api.routers import (
    accounts,
    balances,
    categories,
    health,
    merchants,
    movements,
)
from finanzas.api.schemas.errors import error_responses
from finanzas.config import Settings
from finanzas.db.base import make_engine
from finanzas.domain.dates import SystemClock
from finanzas.services.bootstrap import ensure_initial_user

API_PREFIX = "/api/v1"

# Routers de recursos (cuentas, movimientos…). Todos nacen protegidos.
PROTECTED_ROUTERS: list[APIRouter] = [
    accounts.router,
    categories.router,
    movements.router,
    balances.router,
    merchants.router,
]


def create_app(
    settings: Settings | None = None,
    protected_routers: Sequence[APIRouter] | None = None,
) -> FastAPI:
    """Fábrica de la app. Sin configuración válida, no arranca (RNF-4)."""
    settings = settings or Settings()
    is_local = settings.app_env == "local"

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """Al arrancar: conecta a la BD y siembra el usuario inicial (RF-3)."""
        engine = make_engine(settings.database_url)
        app.state.engine = engine
        with Session(engine) as session:
            app.state.owner_id = ensure_initial_user(session, SystemClock())
        yield
        engine.dispose()

    app = FastAPI(
        title="finanzas — núcleo",
        version=__version__,
        lifespan=lifespan,
        # Documentación pública solo en local; desactivada en producción.
        docs_url="/docs" if is_local else None,
        redoc_url=None,
        openapi_url="/openapi.json" if is_local else None,
    )
    app.state.settings = settings
    install_error_handlers(app)

    # Público: solo /health.
    app.include_router(health.router, prefix=API_PREFIX, responses=error_responses(500))

    # Protegido: todo lo demás exige la contraseña.
    protected = APIRouter(
        dependencies=[Depends(require_password)],
        responses=error_responses(401, 500),
    )
    for router in PROTECTED_ROUTERS if protected_routers is None else protected_routers:
        protected.include_router(router)
    app.include_router(protected, prefix=API_PREFIX)
    return app


app = create_app()
