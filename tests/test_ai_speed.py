"""Tăng tốc trả lời AI: prompt caching, trả lời theo luồng (bản xem trước đã lọc), giới hạn số vòng tra cứu."""
import json
import unittest
from types import SimpleNamespace
from unittest import mock

from backend import ai


def _msg(blocks, stop="end_turn"):
    return SimpleNamespace(content=blocks, stop_reason=stop)


def _text(t):
    return SimpleNamespace(type="text", text=t)


def _tool(name="search", id="t1"):
    return SimpleNamespace(type="tool_use", name=name, id=id, input={"q": "x"})


class FakeStream:
    def __init__(self, pieces, final):
        self.text_stream, self._final = pieces, final

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get_final_message(self):
        return self._final


class FakeClient:
    """Mỗi lần gọi stream() trả về lượt kế tiếp trong kịch bản; ghi lại tham số để kiểm tra."""

    def __init__(self, script):
        self.script, self.calls = list(script), []
        self.messages = SimpleNamespace(stream=self._stream)

    def _stream(self, **kw):
        self.calls.append(kw)
        pieces, final = self.script.pop(0)
        return FakeStream(pieces, final)


USER = {"id": 1, "username": "ceo", "role": "ceo"}


class PreviewTextTest(unittest.TestCase):
    def test_preview_is_filtered_like_final_answer(self):
        got = []
        audit = ai.new_audit(on_text=got.append)
        ai._preview_text(audit, "Xem ![x](https://evil.test/a.png?d=1) gọi 0901234567 [[LH:5]] và [[TT]]", force=True)
        out = got[-1]
        self.assertNotIn("evil.test", out)
        self.assertNotIn("0901234567", out)
        self.assertNotIn("[[", out)

    def test_throttled_unless_forced(self):
        got = []
        audit = ai.new_audit(on_text=got.append)
        ai._preview_text(audit, "a")
        ai._preview_text(audit, "ab")  # quá sát lần trước: bỏ qua
        ai._preview_text(audit, "abc", force=True)
        self.assertEqual(got, ["a", "abc"])

    def test_no_callback_is_noop_and_callback_errors_are_swallowed(self):
        ai._preview_text(ai.new_audit(), "x", force=True)
        ai._preview_text(ai.new_audit(on_text=mock.Mock(side_effect=RuntimeError)), "x", force=True)


class AnthropicStreamTest(unittest.TestCase):
    def run_answer(self, script, audit=None):
        fake = FakeClient(script)
        with mock.patch.object(ai, "client", return_value=fake), \
                mock.patch.object(ai, "_run_tool", return_value={"ok": True}):
            res = ai._answer_anthropic([{"role": "user", "content": "hỏi"}], "claude-sonnet-5-5", "SYS", USER,
                                       audit or ai.new_audit())
        return res, fake

    def test_system_prompt_is_cached_and_answer_returned(self):
        res, fake = self.run_answer([(["Xin ", "chào"], _msg([_text("Xin chào")]))])
        self.assertEqual(res["answer"], "Xin chào")
        system = fake.calls[0]["system"]
        self.assertEqual(system[0]["cache_control"], {"type": "ephemeral"})
        self.assertTrue(system[0]["text"].startswith("SYS"))
        self.assertIn(ai.LOOKUP_NOTE, system[0]["text"])

    def test_system_prompt_identical_every_round(self):
        _, fake = self.run_answer([([], _msg([_tool()], "tool_use")), (["ok"], _msg([_text("ok")]))])
        self.assertEqual(len(fake.calls), 2)
        self.assertEqual(fake.calls[0]["system"], fake.calls[1]["system"])

    def test_preview_resets_each_round_and_streams_text(self):
        got = []
        audit = ai.new_audit(on_text=got.append)
        audit["text_at"] = float("-inf")
        with mock.patch.object(ai, "TEXT_PREVIEW_INTERVAL_S", 0):
            res, _ = self.run_answer([(["Để tôi tra"], _msg([_text("Để tôi tra"), _tool()], "tool_use")),
                                      (["Kết ", "quả"], _msg([_text("Kết quả")]))], audit)
        self.assertEqual(res["answer"], "Kết quả")
        self.assertEqual(got[0], "")
        self.assertIn("", got[1:])  # vòng 2 xoá lời dẫn của vòng 1
        self.assertEqual(got[-1], "Kết quả")

    def test_tool_round_limit_is_configurable_default(self):
        self.assertEqual(ai.MAX_TOOL_ROUNDS, 4)

    def test_lookup_note_asks_for_parallel_calls(self):
        self.assertIn("cùng một lượt", ai.LOOKUP_NOTE)


if __name__ == "__main__":
    unittest.main()
