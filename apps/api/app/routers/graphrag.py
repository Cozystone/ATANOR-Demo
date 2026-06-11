from pydantic import BaseModel
from fastapi import APIRouter

from app.services.alpha_services import alpha_service

router = APIRouter(prefix="/api/graphrag", tags=["graphrag"])


class GraphRAGQuery(BaseModel):
    query: str


@router.post("/query")
def query_graphrag(request: GraphRAGQuery) -> dict:
    return alpha_service.query_graphrag(request.query)


@router.get("/status")
def graphrag_status() -> dict:
    return alpha_service.graphrag_status()
