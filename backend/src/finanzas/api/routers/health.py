"""GET /api/v1/health: siempre público, no expone datos (RNF-4)."""

from fastapi import APIRouter

router = APIRouter(tags=["estado"])


@router.get("/health", summary="Comprueba que el servicio está vivo")
def health() -> dict[str, str]:
    return {"status": "ok"}
