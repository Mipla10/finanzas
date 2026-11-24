"""GET /api/v1/health: siempre público, no expone datos (RNF-4)."""

from fastapi import APIRouter

router = APIRouter(tags=["estado"])


@router.get(
    "/health",
    summary="Comprueba que el servicio está vivo",
    response_description="El servicio está vivo.",
)
def health() -> dict[str, str]:
    """Comprueba que el servicio responde. Es público y no expone datos."""
    return {"status": "ok"}
