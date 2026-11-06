"""The patent chapter must carry a precise, localized evaluation plan per report."""

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
FIELDS = {"focus", "academic_comparison", "industry_question", "boundary"}


class PatentReportEditorialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((ROOT / "data/patent_report_editorial.json").read_text(encoding="utf-8"))
        cls.questions = json.loads((ROOT / "data/cross_analysis.json").read_text(encoding="utf-8"))["questions"]
        cls.directions = json.loads((ROOT / "data/direction_reports/zh.json").read_text(encoding="utf-8"))

    def test_exact_report_coverage_and_scope(self):
        self.assertEqual(self.data["schema_version"], 1)
        expected = {q["question_id"]: "question" for q in self.questions}
        expected.update({key: "direction" for key in self.directions})
        self.assertEqual(len(expected), 148)
        self.assertEqual(set(self.data["reports"]), set(expected))
        for key, scope in expected.items():
            self.assertEqual(self.data["reports"][key]["scope"], scope, key)

    def test_complete_localized_substantive_guidance(self):
        for key, report in self.data["reports"].items():
            self.assertEqual(set(report["locales"]), {"zh", "en", "de"}, key)
            for locale, guidance in report["locales"].items():
                self.assertEqual(set(guidance), FIELDS, (key, locale))
                for field, value in guidance.items():
                    self.assertIsInstance(value, str)
                    self.assertGreater(len(value.strip()), 30, (key, locale, field))
                    self.assertNotIn("TODO", value)
                    self.assertNotIn("E:\\", value)
                    self.assertNotIn("C:\\", value)

    def test_each_question_has_distinct_focus_and_comparison(self):
        for locale in ("zh", "en", "de"):
            for field in ("focus", "academic_comparison", "industry_question"):
                values = [v["locales"][locale][field] for v in self.data["reports"].values()]
                self.assertEqual(len(values), len(set(values)), (locale, field))

    def test_clinical_comparisons_and_reviews_state_evidence_boundary(self):
        ids = ["P2-018", "P2-021", "P2-029", "P2-030", "P2-031", "P4-070", "P4-071", "P4-072", "P6-088", "P6-090", "P6-092", "P6-093", "P2-05", "P4-04"]
        markers = {"zh": "专利不能", "en": "patents cannot", "de": "Patente können"}
        for key in ids:
            for locale, marker in markers.items():
                boundary = self.data["reports"][key]["locales"][locale]["boundary"]
                self.assertIn(marker, boundary, (key, locale))
                self.assertTrue(any(term in boundary for term in {"zh": ("临床", "对照", "教学", "随访", "理解"), "en": ("clinical", "controlled", "follow-up", "learning", "comprehension"), "de": ("klinisch", "kontrolliert", "Nachbeobachtung", "Lernen", "Verständnis")}[locale]), (key, locale))

    def test_each_boundary_discloses_screening_and_empty_result_limits(self):
        for key, report in self.data["reports"].items():
            for locale, guidance in report["locales"].items():
                boundary = guidance["boundary"]
                markers = {"zh": ("授权", "权利要求", "未找到"), "en": ("Grant", "claims", "no scoped"), "de": ("Erteilung", "Patentansprüche", "kein passender")}[locale]
                for marker in markers:
                    self.assertIn(marker, boundary, (key, locale))


if __name__ == "__main__":
    unittest.main()
