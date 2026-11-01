from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "generate_html_report", PROJECT_ROOT / "scripts" / "generate_html_report.py"
)
report = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(report)


class HtmlReportTests(unittest.TestCase):
    def test_digest_json_renders_member_visible_projection_only(self) -> None:
        digest = json.loads(
            (PROJECT_ROOT / "examples" / "digest.example.json").read_text(encoding="utf-8")
        )
        title, markdown = report.digest_json_to_markdown(digest)
        self.assertEqual(title, digest["title"])
        self.assertIn(f"### [ACTION] {digest['actions'][0]['title']}", markdown)
        self.assertIn(f"### [SIGNAL] {digest['signals'][0]['title']}", markdown)
        self.assertIn(digest["sources"][0]["url"], markdown)
        for private in ("illustrative-private-portfolio", "query-protect-margin", "memory-creator-commerce"):
            self.assertNotIn(private, markdown)

    def test_json_without_digest_shape_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "other.json"
            path.write_text(json.dumps({"title": "x", "body": "plain"}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "schema-v2 digest"):
                report.digest_json_to_markdown(json.loads(path.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
