"""用于覆盖简历 Agent SSE cursor 行为。"""

import json
import asyncio
import sys
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.infra.database import Base  # noqa: E402
from app.entrypoints.http.resume_agent import (  # noqa: E402
    ChatRequest,
    chat_with_resume_stream,
    format_sse_event,
    parse_sse_event_id,
)
from app.models import Resume, User  # noqa: E402
from app.services.agent.resume_agent_stream_service import (  # noqa: E402
    ResumeAgentStreamInput,
    ResumeAgentStreamService,
)
from app.state.store import AgentSessionStore  # noqa: E402


class FakeResumeAgent:
    async def optimize_stream(
        self,
        user_message: str,
        resume_content: dict[str, Any],
        conversation_history: list[dict[str, str]],
        confirmation_queue: asyncio.Queue | None,
        allowed_sections: set[str],
        event_callback=None,
        user_id: int | None = None,
        resume_id: int | None = None,
    ):
        """用于输出一条最小可持久化的流事件。"""
        del (
            user_message,
            resume_content,
            conversation_history,
            confirmation_queue,
            allowed_sections,
            event_callback,
            user_id,
            resume_id,
        )
        yield {"content": "已开始优化"}


class ResumeAgentSseCursorTests(unittest.TestCase):
    def test_format_sse_event_includes_id_and_data(self):
        """用于验证SSE事件同时包含id和data。"""
        payload = {"session_id": "session_1", "content": "你好"}

        rendered = format_sse_event(payload, event_id="session_1:2")

        self.assertEqual(
            rendered,
            f"id: session_1:2\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n",
        )

    def test_parse_sse_event_id_extracts_session_and_sequence(self):
        """用于验证LastEventID可还原session和sequence。"""
        parsed = parse_sse_event_id("session_1:42")

        self.assertEqual(parsed, ("session_1", 42))

    def test_parse_sse_event_id_rejects_invalid_value(self):
        """用于验证非法LastEventID不会触发回放。"""
        self.assertIsNone(parse_sse_event_id("not-a-cursor"))


class ResumeAgentSseStreamServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        """用于准备流式服务测试数据。"""
        engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(bind=engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        self.db = self.SessionLocal()

        user = User(email="sse-cursor@example.com", hashed_password="hashed")
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        self.user = user

        resume = Resume(title="SSE 简历", content={"projects": []}, owner_id=user.id)
        self.db.add(resume)
        self.db.commit()
        self.db.refresh(resume)
        self.resume = resume

    def tearDown(self):
        """用于清理流式服务测试数据。"""
        self.db.close()

    async def test_stream_events_are_persisted_with_event_ids(self):
        """用于验证stream事件带eventid并可从日志回放。"""
        service = ResumeAgentStreamService(self.db)
        request = ResumeAgentStreamInput(
            message="优化项目",
            resume_id=self.resume.id,
            user_id=self.user.id,
            request_id="req_sse_cursor",
            client_request_id="ai_client_sse_123",
        )

        with patch(
            "app.services.agent.resume_agent_stream_service.ResumeAgent",
            return_value=FakeResumeAgent(),
        ):
            events = [event async for event in service.stream_events(request)]

        event_ids = [event.get("event_id") for event in events]
        self.assertTrue(all(isinstance(event_id, str) for event_id in event_ids))

        session_id = events[0]["session_id"]
        store = AgentSessionStore(self.db)
        stored = store.list_stream_events(session_id, after_sequence=0)

        self.assertEqual(len(stored), len(events))
        self.assertEqual(stored[0].payload["session_id"], session_id)
        self.assertEqual(
            stored[0].payload["log_context"]["client_request_id"],
            "ai_client_sse_123",
        )
        self.assertEqual(stored[1].payload["content"], "已开始优化")

    def test_replay_stream_events_returns_payloads_after_cursor(self):
        """用于验证服务可按cursor回放公开stream事件。"""
        store = AgentSessionStore(self.db)
        session = store.create_session(
            session_id="replay_session",
            user_id=self.user.id,
            resume_id=self.resume.id,
            task_type="resume_optimization",
        )
        first = store.append_stream_event(
            session_id=session.id,
            payload={"session_id": session.id},
        )
        second = store.append_stream_event(
            session_id=session.id,
            payload={"content": "断线后补发"},
        )
        service = ResumeAgentStreamService(self.db)

        replayed = service.replay_stream_events(
            session_id=session.id,
            user_id=self.user.id,
            after_sequence=first.sequence,
        )

        self.assertEqual(replayed, [{"content": "断线后补发", "event_id": f"{session.id}:{second.sequence}"}])

    async def test_http_stream_replays_events_after_last_event_id(self):
        """用于验证HTTP流可根据LastEventID回放。"""
        store = AgentSessionStore(self.db)
        session = store.create_session(
            session_id="http_replay_session",
            user_id=self.user.id,
            resume_id=self.resume.id,
            task_type="resume_optimization",
        )
        first = store.append_stream_event(
            session_id=session.id,
            payload={"session_id": session.id},
        )
        second = store.append_stream_event(
            session_id=session.id,
            payload={"content": "补发内容"},
        )
        request = MagicMock()
        request.state.request_id = "req_http_replay"
        request.headers = {"last-event-id": f"{session.id}:{first.sequence}"}

        response = await chat_with_resume_stream(
            request=request,
            chat_request=ChatRequest(message="优化", resume_id=self.resume.id),
            current_user={"id": self.user.id},
            db=self.db,
        )
        chunks = [chunk async for chunk in response.body_iterator]

        rendered_parts = []
        for chunk in chunks:
            if isinstance(chunk, bytes):
                rendered_parts.append(chunk.decode())
            elif isinstance(chunk, memoryview):
                rendered_parts.append(chunk.tobytes().decode())
            else:
                rendered_parts.append(str(chunk))
        rendered = "".join(rendered_parts)
        self.assertIn(f"id: {session.id}:{second.sequence}", rendered)
        self.assertIn('"content": "补发内容"', rendered)


if __name__ == "__main__":
    unittest.main()
