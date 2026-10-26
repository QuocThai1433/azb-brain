"""Script so sánh đọc scan Claude/Gemini: ước tính, so văn bản, báo lỗi từng bên, chạy thử không gọi API."""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from backend import ocr_compare


def _make_pdf(path: Path, pages: int) -> None:
    import pymupdf
    doc = pymupdf.open()
    for i in range(pages):
        doc.new_page().insert_text((72, 72), f"Trang {i + 1}")
    doc.save(path)
    doc.close()


class CompareTextsTest(unittest.TestCase):
    def test_identical_text_scores_full(self):
        d = ocr_compare.compare_texts("Quy trình duyệt 12.500.000 đồng", "Quy trình duyệt 12.500.000 đồng")
        self.assertEqual(d["word_f1"], 1.0)
        self.assertEqual(d["only_a"], [])
        self.assertEqual(d["only_b"], [])

    def test_page_markers_are_ignored(self):
        d = ocr_compare.compare_texts("--- Trang 1 ---\nabc 5", "abc 5")
        self.assertEqual(d["word_f1"], 1.0)
        self.assertEqual(d["numbers_a"], 1)

    def test_differing_numbers_are_listed_per_side(self):
        d = ocr_compare.compare_texts("hạn mức 500.000 ngày 12", "hạn mức 600.000 ngày 12")
        self.assertEqual(d["only_a"], ["500.000"])
        self.assertEqual(d["only_b"], ["600.000"])
        self.assertLess(d["word_f1"], 1.0)

    def test_empty_sides(self):
        self.assertEqual(ocr_compare.compare_texts("", "")["word_f1"], 1.0)
        self.assertEqual(ocr_compare.compare_texts("abc", "")["word_f1"], 0.0)


class PartsAndEstimateTest(unittest.TestCase):
    def test_pdf_split_by_ocr_chunk_and_estimate_scales_with_pages(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "a.pdf"
            _make_pdf(pdf, ocr_compare.OCR_PAGES_PER_CALL + 1)
            parts = ocr_compare.load_parts(pdf)
            self.assertEqual([p["pages"] for p in parts], [ocr_compare.OCR_PAGES_PER_CALL, 1])
            self.assertEqual(parts[1]["start"], ocr_compare.OCR_PAGES_PER_CALL + 1)
            est = ocr_compare.estimate(parts, (3.0, 15.0))
            self.assertEqual(est["pages"], ocr_compare.OCR_PAGES_PER_CALL + 1)
            self.assertGreater(est["claude_usd"], est["gemini_usd"])  # Sonnet đắt hơn Flash theo giá đã biết

    def test_image_is_single_part_and_other_types_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            img = Path(tmp) / "a.png"
            img.write_bytes(b"\x89PNG fake")
            self.assertEqual(len(ocr_compare.load_parts(img)), 1)
            doc = Path(tmp) / "a.docx"
            doc.write_bytes(b"x")
            with self.assertRaises(ValueError):
                ocr_compare.load_parts(doc)

    def test_gemini_price_env_override_and_bad_value_falls_back(self):
        with mock.patch.dict("os.environ", {"AZB_PRICE_GEMINI": "1.5,9"}):
            self.assertEqual(ocr_compare.gemini_price(), (1.5, 9.0))
        with mock.patch.dict("os.environ", {"AZB_PRICE_GEMINI": "abc"}):
            self.assertEqual(ocr_compare.gemini_price(), (0.50, 3.00))


class CompareFileTest(unittest.TestCase):
    def _ok(self, text, cost):
        return lambda parts: {"model": "m", "text": text, "cost_usd": cost, "in_tokens": 1, "out_tokens": 1,
                              "seconds": 0.1, "notes": []}

    def test_one_side_failing_keeps_the_other(self):
        def boom(parts):
            raise RuntimeError("429 hết hạn mức")
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "a.pdf"
            _make_pdf(pdf, 1)
            out = Path(tmp) / "out"
            res = ocr_compare.compare_file(pdf, claude_fn=self._ok("abc 1", 0.01), gemini_fn=boom, out_dir=out)
            self.assertIn("429", res["gemini"]["error"])
            self.assertNotIn("diff", res)
            self.assertTrue((out / "a.claude.md").exists())
            self.assertFalse((out / "a.gemini.md").exists())
            self.assertIn("LỖI", ocr_compare.format_report([res]))

    def test_both_sides_produce_diff_and_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "a.pdf"
            _make_pdf(pdf, 1)
            res = ocr_compare.compare_file(pdf, claude_fn=self._ok("tổng 100", 0.02), gemini_fn=self._ok("tổng 160", 0.005),
                                           out_dir=Path(tmp) / "out")
            self.assertEqual(res["diff"]["only_a"], ["100"])
            report = ocr_compare.format_report([res])
            self.assertIn("$0.0200", report)
            self.assertIn("$0.0050", report)
            self.assertIn("Tổng chi phí", report)
            self.assertIn("160", report)


class CliTest(unittest.TestCase):
    def test_dry_run_never_calls_api(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "a.pdf"
            _make_pdf(pdf, 2)
            buf = io.StringIO()
            with mock.patch.object(ocr_compare, "run_claude") as c, mock.patch.object(ocr_compare, "run_gemini") as g, \
                    contextlib.redirect_stdout(buf):
                code = ocr_compare.main([str(pdf)])
            self.assertEqual(code, 0)
            c.assert_not_called()
            g.assert_not_called()
            self.assertIn("2 trang", buf.getvalue())
            self.assertIn("chưa gọi API", buf.getvalue())

    def test_missing_file_and_too_many_files_are_refused(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(ocr_compare.main(["khong_ton_tai.pdf"]), 2)
            self.assertEqual(ocr_compare.main([f"f{i}.pdf" for i in range(ocr_compare.MAX_FILES + 1)]), 2)


if __name__ == "__main__":
    unittest.main()
