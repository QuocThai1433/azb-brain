"""Trả lời AI theo luồng: /api/chat/stream báo từng công cụ AI gọi rồi gửi kết quả cuối giống /api/chat."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from backend import ai, app as app_module, auth, db


def _events(text: str) -> list[dict]:
    return [json.loads(line[5:]) for line in text.split("\n\n") if line.startswith("data:")]


def _fake_answer(history, user, audit=None, memory=""):
    audit["progress"] and audit["progress"]("search")
    audit["progress"] and audit["progress"]("get_unit_detail")
    return {"answer": "Đây là câu trả lời", "tools_used": ["search", "get_unit_detail"]}


class ChatStreamTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.patch = mock.patch.object(db, "DB_PATH", Path(self.tmp.name) / "azb.db")
        self.patch.start()
        db.init_db()
        with db.connect() as c:
            c.execute("INSERT INTO users (id, username, role, password_hash) VALUES (1, 'ceo', 'ceo', 'x')")
            self.token = auth.create_session(c, 1)
        self.client = TestClient(app_module.app)
        self.client.cookies.set(auth.SESSION_COOKIE, self.token)

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def test_streams_tool_progress_then_done(self):
        with mock.patch.object(ai, "answer", side_effect=_fake_answer):
            r = self.client.post("/api/chat/stream", json={"content": "Phòng IT có bao nhiêu người?"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.headers["content-type"].startswith("text/event-stream"))
        events = _events(r.text)
        self.assertEqual([e["type"] for e in events], ["tool", "tool", "done"])
        self.assertEqual([e["tool"] for e in events[:2]], ["search", "get_unit_detail"])
        done = events[-1]
        self.assertEqual(done["answer"], "Đây là câu trả lời")
        self.assertIn("conversation_id", done)
        self.assertTrue(done["title"])

    def test_saves_conversation_like_plain_chat(self):
        with mock.patch.object(ai, "answer", side_effect=_fake_answer):
            self.client.post("/api/chat/stream", json={"content": "Hỏi thử"})
        with db.connect() as c:
            n = c.execute("SELECT COUNT(*) FROM chat_messages").fetchone()[0]
        self.assertEqual(n, 2)

    def test_error_is_sent_as_error_event(self):
        def boom(*a, **k):
            raise RuntimeError("hỏng")
        with mock.patch.object(ai, "answer", side_effect=boom):
            r = self.client.post("/api/chat/stream", json={"content": "x"})
        events = _events(r.text)
        self.assertEqual(events[-1]["type"], "error")
        self.assertNotIn("hỏng", events[-1]["detail"])  # không lộ lỗi nội bộ cho người dùng

    def test_requires_login(self):
        anon = TestClient(app_module.app)
        self.assertEqual(anon.post("/api/chat/stream", json={"content": "x"}).status_code, 401)


if __name__ == "__main__":
    unittest.main()
