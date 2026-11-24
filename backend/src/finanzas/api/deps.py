"""Dependencias compartidas de la API (plan §1.2)."""

import hmac
import uuid

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from finanzas.config import Settings
from finanzas.domain.messages import render

# auto_error=False: los errores los damos nosotros, en español.
# Además, HTTPBearer añade el botón «Authorize» en /docs.
_bearer = HTTPBearer(
    auto_error=False,
    description="Contraseña única de la app (APP_PASSWORD).",
)


def require_password(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),  # noqa: B008
) -> None:
    """Exige «Authorization: Bearer <APP_PASSWORD>» (RNF-4, plan §5.6)."""
    settings: Settings = request.app.state.settings
    expected = settings.app_password.get_secret_value().encode("utf-8")
    given = credentials.credentials.encode("utf-8") if credentials else b""
    # Comparación en tiempo constante: no revela cuántos caracteres acertaste.
    if not hmac.compare_digest(given, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=render("unauthorized"),
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_owner_id(request: Request) -> uuid.UUID:
    """Dueño de los datos de la petición (plan §5.4).

    Hasta la spec 004 es el único usuario, sembrado al arrancar. Los servicios
    siempre reciben owner_id; los tests de aislamiento lo sustituyen.
    """
    owner_id: uuid.UUID = request.app.state.owner_id
    return owner_id
