"""Chọn model Claude trong khung chat: chỉ nhận id trong danh sách, được thử trước các model khác.

Chạy từ thư mục gốc dự án: python -m unittest tests.test_ai_model_choice
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from backend import ai


class ModelChoiceTest(unittest.TestCase):
    def setUp(self):
        env = mock.patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test", "GROQ_API_KEY": ""})
        env.start()
        self.addCleanup(env.stop)
        self.tried = []

        def fake(provider, history, model, system, user, audit):
            self.tried.append((provider, model))
            return {"answer": "ok", "tools_used": []}
        patch = mock.patch.object(ai, "_answer_with", side_effect=fake)
        patch.start()
        self.addCleanup(patch.stop)
        self.user = {"id": 1, "username": "u", "role": "ceo", "full_name": "U", "employee_id": None}

    def ask(self, model):
        with mock.patch.object(ai, "PROVIDER", "anthropic"):
            return ai.answer([{"role": "user", "content": "hi"}], self.user, model=model)

    def test_chosen_model_is_tried_first(self):
        self.ask("claude-haiku-5-5")
        self.assertEqual(self.tried[0], ("anthropic", "claude-haiku-5-5"))

    def test_unknown_model_is_ignored(self):
        self.ask("gpt-evil")
        self.assertNotIn("gpt-evil", [m for _, m in self.tried])
        self.assertEqual(self.tried[0][1], ai.MODEL)

    def test_status_lists_models(self):
        with mock.patch.object(ai, "PROVIDER", "anthropic"):
            self.assertEqual([m["id"] for m in ai.status()["models"]], [m["id"] for m in ai.CLAUDE_MODELS])


class ConversationModelTest(unittest.TestCase):
    """Mở lại đoạn chat cũ phải trả về model đã dùng, kể cả đoạn chỉ có một câu hỏi (lượt đầu chưa có conversation_id)."""

    def setUp(self):
        from fastapi.testclient import TestClient
        from backend import app as app_module, auth, db
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.patch = mock.patch.object(db, "DB_PATH", Path(self.tmp.name) / "azb.db")
        self.patch.start()
        db.init_db()
        with db.connect() as c:
            c.execute("INSERT INTO users (id, username, role, password_hash) VALUES (1, 'ceo', 'ceo', 'x')")
            token = auth.create_session(c, 1)
        self.client = TestClient(app_module.app)
        self.client.cookies.set(auth.SESSION_COOKIE, token)

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def test_first_question_model_is_returned_on_reopen(self):
        def fake(history, user, audit=None, memory="", model=None):
            return {"answer": "ok", "tools_used": [], "model": model}
        with mock.patch.object(ai, "answer", side_effect=fake):
            r = self.client.post("/api/chat", json={"content": "Hỏi", "model": "claude-opus-5-5"})
            conv_id = r.json()["conversation_id"]
        conv = self.client.get(f"/api/conversations/{conv_id}").json()
        self.assertEqual(conv["model"], "claude-opus-5-5")


if __name__ == "__main__":
    unittest.main()
