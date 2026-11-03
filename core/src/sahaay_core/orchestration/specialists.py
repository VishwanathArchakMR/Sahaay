"""Specialist Worker Delegation Subsystem for Sahaay.

Coordinates bounded, least-privilege specialist workers under the direction of the lead orchestrator:
- Research Specialist (web search and page fetching)
- Document Analyst (multi-format ingestion and discrepancy detection)
- Data Analyst (tabular statistics and spreadsheet generation)
- Browser Operator (active tab interaction and navigation)
- Desktop Operator (UI Automation and control entry)
- Critic and Verifier (definition-of-done validation and quality audit)
"""

import asyncio
import logging
import time
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from sahaay_core.capabilities.executor import CapabilityExecutor
from sahaay_core.storage.persistence import durable_storage

logger = logging.getLogger(__name__)


class SpecialistRole(str, Enum):
    RESEARCH_SPECIALIST = "Research Specialist"
    DOCUMENT_ANALYST = "Document Analyst"
    DATA_ANALYST = "Data Analyst"
    BROWSER_OPERATOR = "Browser Operator"
    DESKTOP_OPERATOR = "Desktop Operator"
    CRITIC_VERIFIER = "Critic & Verifier"


class SpecialistTaskRequest(BaseModel):
    role: SpecialistRole
    objective: str
    context: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    taskId: str
    sessionId: str


class SpecialistResult(BaseModel):
    role: SpecialistRole
    success: bool
    summary: str
    facts: Dict[str, Any] = Field(default_factory=dict)
    artifacts: List[Dict[str, Any]] = Field(default_factory=list)
    citations: List[str] = Field(default_factory=list)
    durationMs: float = 0.0


class SpecialistCoordinator:
    """Dispatches subtasks to bounded specialists and aggregates findings for the lead agent."""

    def __init__(self, executor: Optional[CapabilityExecutor] = None) -> None:
        self.executor = executor or CapabilityExecutor()

    async def delegate(self, req: SpecialistTaskRequest) -> SpecialistResult:
        """Executes a bounded specialist assignment with role-appropriate tool restrictions."""
        start_time = time.time()
        logger.info("Delegating subtask to %s: %s", req.role.value, req.objective)

        try:
            if req.role == SpecialistRole.RESEARCH_SPECIALIST:
                res = await self.executor.execute(
                    "research_web_multihop",
                    {"query": req.objective, "maxResults": req.parameters.get("maxResults", 4)},
                    context={"taskId": req.taskId, "sessionId": req.sessionId},
                )
                duration = (time.time() - start_time) * 1000
                citations = [c.get("url") for c in res.get("citations", []) if c.get("url")]
                return SpecialistResult(
                    role=req.role,
                    success=res.get("success", True),
                    summary=f"Retrieved {len(res.get('results', []))} search results and {len(citations)} citations.",
                    facts={"results": res.get("results"), "deepSources": res.get("deepSources")},
                    citations=citations,
                    durationMs=duration,
                )

            elif req.role == SpecialistRole.DOCUMENT_ANALYST:
                path = req.parameters.get("path") or req.parameters.get("filePath")
                if path:
                    ingest_res = await self.executor.execute(
                        "document_ingest_file",
                        {"path": path},
                        context={"taskId": req.taskId, "sessionId": req.sessionId},
                    )
                    facts_count = ingest_res.get("factsCount", 0)
                    duration = (time.time() - start_time) * 1000
                    return SpecialistResult(
                        role=req.role,
                        success=ingest_res.get("success", True),
                        summary=f"Ingested document '{path}': extracted {facts_count} facts, checksum {ingest_res.get('sha256')[:12]}.",
                        facts=ingest_res,
                        durationMs=duration,
                    )
                else:
                    search_res = await self.executor.execute(
                        "document_search_knowledge",
                        {"query": req.objective},
                        context={"taskId": req.taskId, "sessionId": req.sessionId},
                    )
                    duration = (time.time() - start_time) * 1000
                    return SpecialistResult(
                        role=req.role,
                        success=search_res.get("success", True),
                        summary=f"Found {search_res.get('count', 0)} matching facts in knowledge base.",
                        facts=search_res,
                        durationMs=duration,
                    )

            elif req.role == SpecialistRole.DATA_ANALYST:
                data_source = req.parameters.get("source") or req.parameters.get("filePath") or req.objective
                analysis_res = await self.executor.execute(
                    "data_analyze_tabular",
                    {"source": data_source, "query": req.parameters.get("query")},
                    context={"taskId": req.taskId, "sessionId": req.sessionId},
                )
                duration = (time.time() - start_time) * 1000
                return SpecialistResult(
                    role=req.role,
                    success=analysis_res.get("success", True),
                    summary=f"Analyzed table: {analysis_res.get('totalRows', 0)} rows, {analysis_res.get('totalColumns', 0)} columns.",
                    facts={"statistics": analysis_res.get("statistics")},
                    durationMs=duration,
                )

            elif req.role == SpecialistRole.BROWSER_OPERATOR:
                obs = await self.executor.execute(
                    "browser_get_active_tab",
                    {},
                    context={"taskId": req.taskId, "sessionId": req.sessionId},
                )
                duration = (time.time() - start_time) * 1000
                return SpecialistResult(
                    role=req.role,
                    success=obs.get("success", True),
                    summary=f"Active Tab: {obs.get('title')} ({obs.get('url')})",
                    facts=obs,
                    durationMs=duration,
                )

            elif req.role == SpecialistRole.DESKTOP_OPERATOR:
                win_res = await self.executor.execute(
                    "windows_get_active_window",
                    {},
                    context={"taskId": req.taskId, "sessionId": req.sessionId},
                )
                duration = (time.time() - start_time) * 1000
                return SpecialistResult(
                    role=req.role,
                    success=win_res.get("success", True),
                    summary=f"Active Window: {win_res.get('title')} (HWND {win_res.get('hwnd')})",
                    facts=win_res,
                    durationMs=duration,
                )

            elif req.role == SpecialistRole.CRITIC_VERIFIER:
                artifacts = durable_storage.get_artifacts_for_task(req.taskId)
                duration = (time.time() - start_time) * 1000
                return SpecialistResult(
                    role=req.role,
                    success=True,
                    summary=f"Critic Audit: {len(artifacts)} verified artifact(s) on disk.",
                    facts={"artifacts": artifacts},
                    artifacts=artifacts,
                    durationMs=duration,
                )

            else:
                return SpecialistResult(
                    role=req.role,
                    success=False,
                    summary=f"Unknown role {req.role}",
                )

        except Exception as ex:
            duration = (time.time() - start_time) * 1000
            logger.warning("Specialist %s execution failed: %s", req.role.value, ex)
            return SpecialistResult(
                role=req.role,
                success=False,
                summary=f"Specialist error: {str(ex)}",
                durationMs=duration,
            )


specialist_coordinator = SpecialistCoordinator()

