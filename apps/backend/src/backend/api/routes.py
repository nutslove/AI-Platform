"""/api/v1 配下の全ルータを束ねる。"""

from fastapi import APIRouter

from backend.api import (
    agents,
    custom_agents,
    enablements,
    execution,
    mcp_servers,
    users,
)

router = APIRouter(prefix="/api/v1")


@router.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    return {"status": "healthy"}


router.include_router(users.router)
router.include_router(agents.router)
router.include_router(mcp_servers.router)
router.include_router(enablements.router)
router.include_router(execution.router)
router.include_router(custom_agents.router)
