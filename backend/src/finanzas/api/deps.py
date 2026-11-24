"""Dependencias compartidas de la API (plan §1.2)."""

import hmac

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from finanzas.config import Settings

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
            detail="Falta la contraseña o es incorrecta.",
            headers={"WWW-Authenticate": "Bearer"},
        )
