"""用于覆盖 test_resume_agent_session_service.py 对应的回归测试。"""

import sys
import unittest
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.infra.database import Base  # noqa: E402
from app.models import Resume, User  # noqa: E402
from app.runtime.permissions import ConfirmationSessionManager  # noqa: E402
from app.services.agent import (  # noqa: E402
    ResumeAgentConfirmationConflict,
    ResumeAgentSessionNotFound,
    ResumeAgentSessionService,
)
from app.state.store import AgentSessionStore  # noqa: E402


class ResumeAgentSessionServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        """用于准备测试前置状态。"""
        engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(bind=engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        self.db = self.SessionLocal()
        self.store = AgentSessionStore(self.db)
        self.confirmations = ConfirmationSessionManager()
        self.service = ResumeAgentSessionService(
            self.store,
            confirmation_sessions=self.confirmations,
        )

        user = User(email="session-service@example.com", hashed_password="hashed")
        other_user = User(email="other-session-service@example.com", hashed_password="hashed")
        self.db.add_all([user, other_user])
        self.db.commit()
        self.db.refresh(user)
        self.db.refresh(other_user)
        self.user = user
        self.other_user = other_user

        resume = Resume(title="测试简历", content={}, owner_id=user.id)
        self.db.add(resume)
        self.db.commit()
        self.db.refresh(resume)
        self.resume = resume

    def tearDown(self):
        """用于清理测试后置状态。"""
        self.db.close()

    def _create_waiting_session(
        self,
        session_id: str = "session_1",
        call_id: str = "call_1",
    ) -> None:
        """用于创建waiting会话。"""
        self.store.create_session(
            session_id=session_id,
            user_id=self.user.id,
            resume_id=self.resume.id,
            task_type="resume_optimization",
        )
        self.store.update_status(session_id, "waiting_confirmation", current_step=call_id)
        self.store.append_event(
            session_id=session_id,
            event_type="tool_call_previewed",
            source="resume_agent",
            payload={
                "call_id": call_id,
                "tool_name": "优化简介",
                "diff_summary": "改前 A 改后 B",
            },
        )

    async def test_confirm_tool_dispatches_to_active_queue(self):
        """用于验证confirmtooldispatchestoactivequeue。"""
        self._create_waiting_session()
        queue = self.confirmations.create("session_1")

        result = await self.service.confirm_tool(
            session_id="session_1",
            call_id="call_1",
            confirmed=False,
            user_id=self.user.id,
        )

        self.assertEqual(result.to_response(), {"ok": True})
        self.assertFalse(queue.get_nowait())
        self.assertEqual(self.store.get_session("session_1").status, "running")

    async def test_confirm_tool_dispatches_feedback_to_active_queue(self):
        """用于验证confirmtool把用户反馈传入活动队列。"""
        self._create_waiting_session()
        queue = self.confirmations.create("session_1")

        result = await self.service.confirm_tool(
            session_id="session_1",
            call_id="call_1",
            confirmed=False,
            user_id=self.user.id,
            feedback="补充量化结果，不要只写高并发",
        )

        self.assertEqual(result.to_response(), {"ok": True})
        self.assertEqual(
            queue.get_nowait(),
            {
                "confirmed": False,
                "feedback": "补充量化结果，不要只写高并发",
            },
        )
        self.assertEqual(self.store.get_session("session_1").status, "running")

    async def test_confirm_tool_records_resumable_result_without_queue(self):
        """用于验证confirmtoolrecordsresumable结果withoutqueue。"""
        self._create_waiting_session()

        result = await self.service.confirm_tool(
            session_id="session_1",
            call_id="call_1",
            confirmed=True,
            user_id=self.user.id,
        )

        self.assertFalse(result.ok)
        self.assertTrue(result.resumable)
        self.assertEqual(self.store.get_session("session_1").status, "paused")
        latest = self.store.get_latest_event("session_1")
        self.assertEqual(latest.event_type, "tool_call_confirmed")
        self.assertFalse(latest.payload["active_stream"])

    async def test_confirm_tool_persists_feedback_without_queue(self):
        """用于验证confirmtool断流时持久化用户反馈。"""
        self._create_waiting_session()

        result = await self.service.confirm_tool(
            session_id="session_1",
            call_id="call_1",
            confirmed=False,
            user_id=self.user.id,
            feedback="不要编造新数据",
        )

        self.assertFalse(result.ok)
        latest = self.store.get_latest_event("session_1")
        self.assertEqual(latest.event_type, "tool_call_rejected")
        self.assertEqual(latest.payload["feedback"], "不要编造新数据")

    async def test_confirm_tool_treats_processed_status_as_duplicate(self):
        """用于验证confirmtooltreatsprocessed状态asduplicate。"""
        self._create_waiting_session()
        self.store.update_status("session_1", "running", clear_current_step=True)

        result = await self.service.confirm_tool(
            session_id="session_1",
            call_id="call_1",
            confirmed=True,
            user_id=self.user.id,
        )

        self.assertEqual(
            result.to_response(),
            {"ok": True, "duplicate": True, "message": "该工具确认已处理"},
        )

    async def test_confirm_tool_rejects_mismatched_call_id(self):
        """用于验证confirmtoolrejectsmismatchedcallid。"""
        self._create_waiting_session(call_id="call_real")

        with self.assertRaises(ResumeAgentConfirmationConflict):
            await self.service.confirm_tool(
                session_id="session_1",
                call_id="call_wrong",
                confirmed=True,
                user_id=self.user.id,
            )

    async def test_confirm_tool_rejects_other_user(self):
        """用于验证confirmtoolrejectsother用户。"""
        self._create_waiting_session()

        with self.assertRaises(ResumeAgentSessionNotFound):
            await self.service.confirm_tool(
                session_id="session_1",
                call_id="call_1",
                confirmed=True,
                user_id=self.other_user.id,
            )


if __name__ == "__main__":
    unittest.main()
