import argparse
import datetime
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import add_paper as ap

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "scripts", "feed_config.json")
FIXED_TODAY = datetime.date(2026, 9, 14)


def _today_fn():
    return FIXED_TODAY


def load_fixture_rec(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as f:
        data = json.load(f)
    return data["resultList"]["result"][0]


def make_fetch_fn(rec):
    def fetch_fn(url):
        return {"version": "6.9", "hitCount": 1, "resultList": {"result": [rec]}}

    return fetch_fn


class AddPaperTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.out_dir = os.path.join(self.tmp, "summaries")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _args(self, identifier, **kw):
        defaults = dict(
            identifier=identifier,
            slug=None,
            title=None,
            tags=None,
            design=None,
            sample_size=None,
            date=None,
            out_dir=self.out_dir,
            force=False,
            dry_run=False,
            summarize=False,
            model=None,
            config=CONFIG_PATH,
        )
        defaults.update(kw)
        return argparse.Namespace(**defaults)


class TestOaAccepted(AddPaperTestCase):
    def test_oa_fixture_accepted_and_written(self):
        rec = load_fixture_rec("epmc_lookup_oa.json")
        rc = ap.run(self._args("PMC12809804"), fetch_fn=make_fetch_fn(rec), today_fn=_today_fn)
        self.assertEqual(rc, 0)
        files = os.listdir(self.out_dir)
        self.assertEqual(len(files), 1)
        with open(os.path.join(self.out_dir, files[0]), encoding="utf-8") as f:
            content = f.read()
        self.assertIn('paper_license: "cc by-nc"', content)
        self.assertIn('paper_oa_verified: true', content)
        self.assertIn("[[PENDIENTE]]", content)

    def test_dry_run_prints_and_does_not_write(self):
        rec = load_fixture_rec("epmc_lookup_oa.json")
        rc = ap.run(
            self._args("PMC12809804", dry_run=True), fetch_fn=make_fetch_fn(rec), today_fn=_today_fn
        )
        self.assertEqual(rc, 0)
        self.assertFalse(os.path.exists(self.out_dir))


class TestNotOaRejected(AddPaperTestCase):
    def test_not_oa_fixture_rejected(self):
        rec = load_fixture_rec("epmc_lookup_not_oa.json")
        rc = ap.run(self._args("10.1001/jamapsychiatry.2026.2410"), fetch_fn=make_fetch_fn(rec), today_fn=_today_fn)
        self.assertEqual(rc, 2)
        self.assertFalse(os.path.exists(self.out_dir))


class TestPreprintNotOaRejected(AddPaperTestCase):
    def test_preprint_without_oa_license_rejected(self):
        rec = load_fixture_rec("epmc_lookup_preprint.json")
        rc = ap.run(self._args("PPR1309022"), fetch_fn=make_fetch_fn(rec), today_fn=_today_fn)
        # isOpenAccess=N para este preprint -> rechazado igual que cualquier no-OA.
        self.assertEqual(rc, 2)


class TestEmptyLookup(AddPaperTestCase):
    def test_not_found_returns_2(self):
        def fetch_fn(url):
            return {"version": "6.9", "hitCount": 0, "resultList": {"result": []}}

        rc = ap.run(self._args("10.9999/doesnotexist"), fetch_fn=fetch_fn, today_fn=_today_fn)
        self.assertEqual(rc, 2)


class TestForceAndExists(AddPaperTestCase):
    def test_existing_file_without_force_exits_4(self):
        rec = load_fixture_rec("epmc_lookup_oa.json")
        fetch_fn = make_fetch_fn(rec)
        rc1 = ap.run(self._args("PMC12809804"), fetch_fn=fetch_fn, today_fn=_today_fn)
        self.assertEqual(rc1, 0)
        rc2 = ap.run(self._args("PMC12809804"), fetch_fn=fetch_fn, today_fn=_today_fn)
        self.assertEqual(rc2, 4)

    def test_force_overwrites(self):
        rec = load_fixture_rec("epmc_lookup_oa.json")
        fetch_fn = make_fetch_fn(rec)
        ap.run(self._args("PMC12809804"), fetch_fn=fetch_fn, today_fn=_today_fn)
        rc = ap.run(self._args("PMC12809804", force=True), fetch_fn=fetch_fn, today_fn=_today_fn)
        self.assertEqual(rc, 0)


class TestSummarizeWithoutKey(AddPaperTestCase):
    def test_summarize_without_api_key_exits_3_before_network(self):
        called = {"n": 0}

        def fetch_fn(url):
            called["n"] += 1
            return {"version": "6.9", "hitCount": 0, "resultList": {"result": []}}

        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ANTHROPIC_API_KEY", None)
            rc = ap.run(self._args("PMC12809804", summarize=True), fetch_fn=fetch_fn, today_fn=_today_fn)
        self.assertEqual(rc, 3)
        self.assertEqual(called["n"], 0)


class TestDetectedTagsAndDesign(AddPaperTestCase):
    def test_tags_and_design_detected_when_not_given(self):
        rec = load_fixture_rec("epmc_lookup_oa.json")  # RCT, ADHD/digital/CBT paper
        rc = ap.run(self._args("PMC12809804"), fetch_fn=make_fetch_fn(rec), today_fn=_today_fn)
        self.assertEqual(rc, 0)
        files = os.listdir(self.out_dir)
        with open(os.path.join(self.out_dir, files[0]), encoding="utf-8") as f:
            content = f.read()
        self.assertIn("tags: [", content)
        self.assertIn("study_design:", content)


if __name__ == "__main__":
    unittest.main()
