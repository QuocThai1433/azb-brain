"""Công tắc engine đọc scan (AZB_OCR_ENGINE=claude|gemini): mặc định Claude, nhánh Gemini ghi chi phí, dự phòng về Claude.

Chạy từ thư mục gốc dự án: python -m unittest tests.test_ocr_engine
Không gọi API thật: mọi lần gọi Claude/Gemini đều được thay bằng hàm giả.
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from backend import ai, db, documents
from tests.test_ai_cost import DbCase


def _make_pdf(path: Path, pages: int) -> None:
    import pymupdf
    doc = pymupdf.open()
    for i in range(pages):
        doc.new_page().insert_text((72, 72), f"Trang {i + 1}")
    doc.save(path)
    doc.close()


def _env(**kw):
    return mock.patch.dict("os.environ", {k: v for k, v in kw.items()}, clear=False)


class EngineSwitchTest(unittest.TestCase):
    def test_default_is_claude_and_unknown_value_falls_back_to_claude(self):
        with mock.patch.dict("os.environ", {}, clear=False) as env:
            env.pop("AZB_OCR_ENGINE", None)
            self.assertEqual(documents._ocr_engine(), "claude")
        with _env(AZB_OCR_ENGINE="gpt"):
            self.assertEqual(documents._ocr_engine(), "claude")
        with _env(AZB_OCR_ENGINE=" Gemini "):
            self.assertEqual(documents._ocr_engine(), "gemini")

    def test_claude_engine_never_touches_gemini(self):
        with _env(AZB_OCR_ENGINE="claude"), \
                mock.patch.object(documents, "_ocr_pdf_with_claude", return_value=(["c"], "")) as claude, \
                mock.patch.object(documents, "_ocr_pdf_with_gemini") as gemini:
            self.assertEqual(documents._ocr_pdf_with_ai(Path("a.pdf")), (["c"], ""))
        claude.assert_called_once()
        gemini.assert_not_called()

    def test_gemini_engine_marks_note(self):
        with _env(AZB_OCR_ENGINE="gemini"), \
                mock.patch.object(documents, "_ocr_pdf_with_gemini", return_value=(["g"], "")), \
                mock.patch.object(documents, "_ocr_pdf_with_claude") as claude:
            parts, note = documents._ocr_pdf_with_ai(Path("a.pdf"))
        self.assertEqual(parts, ["g"])
        self.assertIn("Gemini", note)
        claude.assert_not_called()

    def test_gemini_failure_raises_when_fallback_off(self):
        with _env(AZB_OCR_ENGINE="gemini", AZB_OCR_FALLBACK="0"), \
                mock.patch.object(documents, "_ocr_pdf_with_gemini", side_effect=RuntimeError("401")), \
                mock.patch.object(documents, "_ocr_pdf_with_claude") as claude:
            with self.assertRaises(RuntimeError):
                documents._ocr_pdf_with_ai(Path("a.pdf"))
        claude.assert_not_called()

    def test_gemini_failure_falls_back_to_claude_when_enabled(self):
        with _env(AZB_OCR_ENGINE="gemini", AZB_OCR_FALLBACK="1"), \
                mock.patch.object(documents, "_ocr_pdf_with_gemini", side_effect=RuntimeError("401")), \
                mock.patch.object(documents, "_ocr_pdf_with_claude", return_value=(["c"], "")):
            parts, note = documents._ocr_pdf_with_ai(Path("a.pdf"))
        self.assertEqual(parts, ["c"])
        self.assertIn("Claude", note)


class GeminiPdfTest(unittest.TestCase):
    def test_splits_into_chunks_and_logs_cost_per_chunk(self):
        with tempfile.TemporaryDirectory() as tmp, _env(AZB_PRICE_GEMINI="1,2"):
            pdf = Path(tmp) / "a.pdf"
            _make_pdf(pdf, documents.OCR_PAGES_PER_CALL + 1)
            with mock.patch.object(documents, "_gemini_read", return_value=("chữ", 100, 50, "STOP")) as read, \
                    mock.patch.object(ai, "log_cost") as log:
                parts, note = documents._ocr_pdf_with_gemini(pdf)
        self.assertEqual(parts, ["chữ", "chữ"])
        self.assertEqual(note, "")
        self.assertEqual(read.call_count, 2)
        self.assertIn(f"Cụm này bắt đầu từ trang {documents.OCR_PAGES_PER_CALL + 1}", read.call_args_list[1].args[2])
        self.assertEqual(log.call_count, 2)
        kind, _model, tok_in, tok_out, cost, label = log.call_args_list[0].args
        self.assertEqual((kind, tok_in, tok_out), ("ocr_pdf", 100, 50))
        self.assertAlmostEqual(cost, (100 * 1 + 50 * 2) / 1_000_000)
        self.assertIn("a.pdf", label)

    def test_truncated_output_is_noted(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "a.pdf"
            _make_pdf(pdf, 2)
            with mock.patch.object(documents, "_gemini_read", return_value=("x", 1, 1, "MAX_TOKENS")), \
                    mock.patch.object(ai, "log_cost"):
                _, note = documents._ocr_pdf_with_gemini(pdf)
        self.assertIn("thiếu", note)

    def test_missing_gemini_key_is_a_clear_error(self):
        with mock.patch.object(ai, "has_gemini", return_value=False):
            with self.assertRaises(RuntimeError) as cm:
                documents._gemini_read(b"x", "application/pdf", "p")
        self.assertIn("GEMINI_API_KEY", str(cm.exception))


class GeminiImageTest(unittest.TestCase):
    def test_image_uses_gemini_and_logs_cost(self):
        with tempfile.TemporaryDirectory() as tmp, _env(AZB_OCR_ENGINE="gemini"):
            img = Path(tmp) / "a.png"
            img.write_bytes(b"\x89PNG fake")
            with mock.patch.object(documents, "_gemini_read", return_value=("chữ trong ảnh", 10, 5, "STOP")) as read, \
                    mock.patch.object(documents, "_read_image_with_claude") as claude, \
                    mock.patch.object(ai, "log_cost") as log:
                self.assertEqual(documents._read_image(img), "chữ trong ảnh")
        self.assertEqual(read.call_args.args[1], "image/png")
        claude.assert_not_called()
        self.assertEqual(log.call_args.args[0], "ocr_image")

    def test_image_falls_back_to_claude_when_enabled(self):
        with tempfile.TemporaryDirectory() as tmp, _env(AZB_OCR_ENGINE="gemini", AZB_OCR_FALLBACK="1"):
            img = Path(tmp) / "a.png"
            img.write_bytes(b"\x89PNG fake")
            with mock.patch.object(documents, "_gemini_read", side_effect=RuntimeError("503")), \
                    mock.patch.object(documents, "_read_image_with_claude", return_value="từ claude"):
                self.assertEqual(documents._read_image(img), "từ claude")


class LogCostTest(DbCase):
    def test_writes_row_for_file_owner_and_never_raises(self):
        token = ai.usage_user.set(7)
        try:
            ai.log_cost("ocr_pdf", "gemini-x", 100, 50, 0.002, "a.pdf (trang 1-2)")
        finally:
            ai.usage_user.reset(token)
        with db.connect() as c:
            r = c.execute("SELECT kind, model, input_tokens, output_tokens, cost_usd, user_id FROM ai_usage_log").fetchone()
        self.assertEqual(tuple(r), ("ocr_pdf", "gemini-x", 100, 50, 0.002, 7))
        with mock.patch.object(ai, "connect", side_effect=RuntimeError("db hỏng")):
            ai.log_cost("ocr_pdf", "gemini-x", 1, 1, 0.0)  # lỗi ghi log không được làm hỏng việc đang làm


if __name__ == "__main__":
    unittest.main()
