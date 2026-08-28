# AgenticArxiv/services/log_service.py
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import func

from models.db import get_sync_session
from models.orm import ChatLogRow, AgentStepRow
from models.schemas import ChatLogItem, AgentStepItem, LogSessionSummary


class LogService:
    """Synchronous log writer/reader backed by MySQL."""

    def create_chat_log(
        self,
        session_id: str,
        msg_id: str,
        role: str,
        content: str,
        model: Optional[str] = None,
        agent_type: Optional[str] = None,
        metrics: Optional[Dict[str, int]] = None,
        termination_type: Optional[str] = None,
    ) -> None:
        with get_sync_session() as db:
            task_metrics = metrics or {}
            db.add(ChatLogRow(
                session_id=session_id,
                msg_id=msg_id,
                role=role,
                content=content,
                model=model,
                agent_type=agent_type,
                total_time_ms=task_metrics.get("total_time_ms"),
                total_llm_ms=task_metrics.get("total_llm_ms"),
                total_tool_ms=task_metrics.get("total_tool_ms"),
                framework_overhead_ms=task_metrics.get("framework_overhead_ms"),
                prompt_tokens=task_metrics.get("prompt_tokens"),
                completion_tokens=task_metrics.get("completion_tokens"),
                total_tokens=task_metrics.get("total_tokens"),
                termination_type=termination_type,
                created_at=datetime.now(),
            ))
            db.commit()

    def save_agent_step(
        self,
        msg_id: str,
        step_index: int,
        thought: Optional[str] = None,
        action_name: Optional[str] = None,
        action_args: Optional[str] = None,
        observation: Optional[str] = None,
        llm_latency_ms: Optional[int] = None,
        tool_latency_ms: Optional[int] = None,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
    ) -> None:
        with get_sync_session() as db:
            db.add(AgentStepRow(
                msg_id=msg_id,
                step_index=step_index,
                thought=thought,
                action_name=action_name,
                action_args=action_args,
                observation=observation,
                llm_latency_ms=llm_latency_ms,
                tool_latency_ms=tool_latency_ms,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                created_at=datetime.now(),
            ))
            db.commit()

    def list_sessions(self, limit: int = 50, offset: int = 0) -> List[LogSessionSummary]:
        with get_sync_session() as db:
            rows = (
                db.query(
                    ChatLogRow.session_id,
                    func.count(ChatLogRow.id).label("message_count"),
                    func.max(ChatLogRow.created_at).label("last_active_at"),
                )
                .group_by(ChatLogRow.session_id)
                .order_by(func.max(ChatLogRow.created_at).desc())
                .offset(offset)
                .limit(limit)
                .all()
            )
            return [
                LogSessionSummary(
                    session_id=r.session_id,
                    message_count=r.message_count,
                    last_active_at=r.last_active_at,
                )
                for r in rows
            ]

    def list_messages(
        self, session_id: str, limit: int = 100, offset: int = 0
    ) -> List[ChatLogItem]:
        with get_sync_session() as db:
            rows = (
                db.query(ChatLogRow)
                .filter_by(session_id=session_id)
                .order_by(ChatLogRow.created_at.asc())
                .offset(offset)
                .limit(limit)
                .all()
            )
            return [
                ChatLogItem(
                    msg_id=r.msg_id,
                    session_id=r.session_id,
                    role=r.role,
                    content=r.content,
                    model=r.model,
                    agent_type=r.agent_type,
                    total_time_ms=r.total_time_ms,
                    total_llm_ms=r.total_llm_ms,
                    total_tool_ms=r.total_tool_ms,
                    framework_overhead_ms=r.framework_overhead_ms,
                    prompt_tokens=r.prompt_tokens,
                    completion_tokens=r.completion_tokens,
                    total_tokens=r.total_tokens,
                    termination_type=r.termination_type,
                    created_at=r.created_at,
                )
                for r in rows
            ]

    def get_steps(self, msg_id: str) -> List[AgentStepItem]:
        with get_sync_session() as db:
            rows = (
                db.query(AgentStepRow)
                .filter_by(msg_id=msg_id)
                .order_by(AgentStepRow.step_index.asc())
                .all()
            )
            return [
                AgentStepItem(
                    step_index=r.step_index,
                    thought=r.thought,
                    action_name=r.action_name,
                    action_args=r.action_args,
                    observation=r.observation,
                    llm_latency_ms=r.llm_latency_ms,
                    tool_latency_ms=r.tool_latency_ms,
                    prompt_tokens=r.prompt_tokens,
                    completion_tokens=r.completion_tokens,
                    created_at=r.created_at,
                )
                for r in rows
            ]


log_service = LogService()
