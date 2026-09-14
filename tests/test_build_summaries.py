import argparse
import datetime
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import build_summaries as bs

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
FIXED_NOW = datetime.datetime(2026, 9, 14, 11, 0, 0, tzinfo=datetime.timezone.utc)


def _now_fn():
    return FIXED_NOW


class BuildSummariesTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.src = os.path.join(self.tmp, "summaries")
        os.makedirs(self.src, exist_ok=True)
        self.out = os.path.join(self.tmp, "summaries.json")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _copy_fixture(self, fixture_name, dest_name):
        shutil.copy(os.path.join(FIXTURES, fixture_name), os.path.join(self.src, dest_name))

    def _args(self, **kw):
        defaults = dict(
            src=self.src,
            out=self.out,
            check=False,
            verify_oa=False,
            skip_invalid=False,
            include_drafts=False,
        )
        defaults.update(kw)
        return argparse.Namespace(**defaults)


class TestValidExampleIncluded(BuildSummariesTestCase):
    def test_valid_example_summary_is_built(self):
        self._copy_fixture("summary_valid.md", "2026-09-14-app-calidad-vida-bipolar.md")
        rc = bs.run(self._args(), now_fn=_now_fn)
        self.assertEqual(rc, 0)
        with open(self.out, encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["count"], 1)
        item = data["items"][0]
        self.assertEqual(item["slug"], "2026-09-14-app-calidad-vida-bipolar")
        # El fixture canónico (3.0.8/enmienda 17) tiene ai_draft: true ->
        # confidence "draft" ("indicado en el borrador", no confirmado por
        # Javier todavía), no "manual".
        self.assertEqual(item["study_design"], {"id": "pilot", "confidence": "draft"})
        self.assertIsNotNone(item["one_liner"])
        self.assertEqual(item["paper"]["open_access"]["license"], "cc by")
        self.assertTrue(item["paper"]["links"]["doi"].startswith("https://doi.org/"))

    def test_manual_confidence_when_not_ai_draft(self):
        path = os.path.join(FIXTURES, "summary_valid.md")
        with open(path, encoding="utf-8") as f:
            text = f.read()
        text = text.replace("ai_draft: true", "ai_draft: false").replace(
            'author: "Borrador de ejemplo generado con IA"', 'author: "Javier Flores"'
        )
        dest = os.path.join(self.src, "2026-09-14-app-calidad-vida-bipolar.md")
        with open(dest, "w", encoding="utf-8") as f:
            f.write(text)
        rc = bs.run(self._args(), now_fn=_now_fn)
        self.assertEqual(rc, 0)
        with open(self.out, encoding="utf-8") as f:
            data = json.load(f)
        item = data["items"][0]
        self.assertEqual(item["study_design"]["confidence"], "manual")

    def test_verify_oa_network_failure_returns_1_not_uncaught(self):
        # hallazgo de verificación: un EpmcError durante --verify-oa (red
        # caída, timeout, SSL) escapaba de run() como traceback sin capturar
        # en vez de un fallo controlado con exit 1.
        import urllib.error

        self._copy_fixture("summary_valid.md", "2026-09-14-app-calidad-vida-bipolar.md")

        def failing_fetch_fn(url):
            raise urllib.error.URLError("simulated network failure")

        rc = bs.run(
            self._args(verify_oa=True), now_fn=_now_fn, fetch_fn=failing_fetch_fn,
            sleep_fn=lambda s: None,
        )
        self.assertEqual(rc, 1)
        self.assertFalse(os.path.exists(self.out))


class TestPendingRules(BuildSummariesTestCase):
    def test_pending_in_draft_is_accepted(self):
        self._copy_fixture("summary_draft_pending.md", "2026-09-14-borrador-pendiente.md")
        rc = bs.run(self._args(include_drafts=True), now_fn=_now_fn)
        self.assertEqual(rc, 0)
        with open(self.out, encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["count"], 1)
        sec = {s["id"]: s for s in data["items"][0]["sections"]}
        self.assertTrue(sec["en_una_frase"]["pending"])

    def test_draft_without_example_excluded_by_default(self):
        self._copy_fixture("summary_draft_pending.md", "2026-09-14-borrador-pendiente.md")
        rc = bs.run(self._args(), now_fn=_now_fn)
        self.assertEqual(rc, 0)
        with open(self.out, encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["count"], 0)


class TestRejections(BuildSummariesTestCase):
    def test_not_oa_verified_false_rejected(self):
        self._copy_fixture("summary_invalid_not_oa.md", "2026-09-14-no-oa.md")
        rc = bs.run(self._args(), now_fn=_now_fn)
        self.assertEqual(rc, 2)
        self.assertFalse(os.path.exists(self.out))

    def test_bad_license_rejected(self):
        path = os.path.join(FIXTURES, "summary_valid.md")
        with open(path, encoding="utf-8") as f:
            text = f.read()
        text = text.replace('paper_license: "cc by"', 'paper_license: "all rights reserved"')
        dest = os.path.join(self.src, "2026-09-14-app-calidad-vida-bipolar.md")
        with open(dest, "w", encoding="utf-8") as f:
            f.write(text)
        rc = bs.run(self._args(), now_fn=_now_fn)
        self.assertEqual(rc, 2)

    def test_html_in_body_rejected(self):
        path = os.path.join(FIXTURES, "summary_valid.md")
        with open(path, encoding="utf-8") as f:
            text = f.read()
        text = text.replace(
            "## Pregunta\n", "## Pregunta\nEsto <b>no</b> debe permitirse.\n\n## Pregunta original\n"
        )
        # Insertamos HTML crudo dentro de la sección Pregunta (mantiene encabezados válidos).
        text = text.replace(
            "¿Es factible y aceptable usar la app PolarUs",
            "<script>alert(1)</script> ¿Es factible y aceptable usar la app PolarUs",
        )
        dest = os.path.join(self.src, "2026-09-14-app-calidad-vida-bipolar.md")
        with open(dest, "w", encoding="utf-8") as f:
            f.write(text)
        rc = bs.run(self._args(), now_fn=_now_fn)
        self.assertEqual(rc, 2)

    def test_missing_heading_rejected(self):
        path = os.path.join(FIXTURES, "summary_valid.md")
        with open(path, encoding="utf-8") as f:
            text = f.read()
        text = text.replace("## Limitaciones\n", "## Sección Rara\n")
        dest = os.path.join(self.src, "2026-09-14-app-calidad-vida-bipolar.md")
        with open(dest, "w", encoding="utf-8") as f:
            f.write(text)
        rc = bs.run(self._args(), now_fn=_now_fn)
        self.assertEqual(rc, 2)

    def test_one_liner_too_long_rejected(self):
        path = os.path.join(FIXTURES, "summary_valid.md")
        with open(path, encoding="utf-8") as f:
            text = f.read()
        long_line = "X" * 301
        text = text.replace(
            "Una aplicación móvil para el automonitoreo del trastorno bipolar fue evaluada en un piloto de factibilidad.",
            long_line,
        )
        dest = os.path.join(self.src, "2026-09-14-app-calidad-vida-bipolar.md")
        with open(dest, "w", encoding="utf-8") as f:
            f.write(text)
        rc = bs.run(self._args(), now_fn=_now_fn)
        self.assertEqual(rc, 2)

    def test_mixed_list_paragraph_rejected(self):
        path = os.path.join(FIXTURES, "summary_valid.md")
        with open(path, encoding="utf-8") as f:
            text = f.read()
        text = text.replace(
            "- Los participantes pudieron usar la aplicación para el automonitoreo.\n",
            "- Los participantes pudieron usar la aplicación para el automonitoreo.\ntexto plano suelto\n",
        )
        dest = os.path.join(self.src, "2026-09-14-app-calidad-vida-bipolar.md")
        with open(dest, "w", encoding="utf-8") as f:
            f.write(text)
        rc = bs.run(self._args(), now_fn=_now_fn)
        self.assertEqual(rc, 2)


class TestCheckAndSkipInvalid(BuildSummariesTestCase):
    def test_check_does_not_write(self):
        self._copy_fixture("summary_valid.md", "2026-09-14-app-calidad-vida-bipolar.md")
        rc = bs.run(self._args(check=True), now_fn=_now_fn)
        self.assertEqual(rc, 0)
        self.assertFalse(os.path.exists(self.out))

    def test_skip_invalid_writes_valid_only(self):
        self._copy_fixture("summary_valid.md", "2026-09-14-app-calidad-vida-bipolar.md")
        self._copy_fixture("summary_invalid_not_oa.md", "2026-09-14-no-oa.md")
        rc = bs.run(self._args(skip_invalid=True), now_fn=_now_fn)
        self.assertEqual(rc, 0)
        with open(self.out, encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["count"], 1)


class TestEmptyDir(BuildSummariesTestCase):
    def test_no_files_writes_empty(self):
        rc = bs.run(self._args(), now_fn=_now_fn)
        self.assertEqual(rc, 0)
        with open(self.out, encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data, {**data, "count": 0, "items": []})


if __name__ == "__main__":
    unittest.main()
