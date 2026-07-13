"""Agent endpoint (Stage 3.2): POST /v1/agent/recommend."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agent.loop import run_agent
from app.api.deps import get_session
from app.llm.client import LLMError, get_llm, is_enabled
from app.schemas.agent import AgentRequest, AgentResult

router = APIRouter(prefix="/v1", tags=["agent"])


@router.post("/agent/recommend", response_model=AgentResult)
def agent_recommend(req: AgentRequest, session: Session = Depends(get_session)):
    if not is_enabled():
        raise HTTPException(503, "agent requires ANTHROPIC_API_KEY")
    try:
        client = get_llm().raw()
    except LLMError as e:
        raise HTTPException(503, str(e))
    return run_agent(session, req, client=client)
