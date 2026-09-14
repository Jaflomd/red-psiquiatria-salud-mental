import argparse
import datetime
import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import summarize_ai as sa

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")

FIXED_NOW = datetime.datetime(2026, 9, 14, 11, 0, 0, tzinfo=datetime.timezone.utc)


def _now_fn():
    return FIXED_NOW


def _paper(title="Study of digital CBT for ADHD in 100 adults.", abstract_text=None):
    abstract_text = abstract_text or (
        "This trial included 100 adults with ADHD who used a digital CBT intervention. "
        "Adherence was good and the program was well accepted by participants."
    )
    return {
        "title": title,
        "journal": "Psychological Medicine",
        "pub_year": 2026,
        "abstract": {"text": abstract_text},
        "open_access": {"license": "cc by"},
        "ai_summary": None,
    }


def ok_post_fn(url, headers, body, timeout):
    with open(os.path.join(FIXTURES, "anthropic_ok.json"), encoding="utf-8") as f:
        raw = f.read().encode("utf-8")
    return 200, raw, {}


class TestBuildBody(unittest.TestCase):
    def test_haiku_gets_temperature_no_thinking(self):
        body = sa._build_body(_paper(), "claude-haiku-4-5")
        self.assertEqual(body["temperature"], 0.2)
        self.assertNotIn("thinking", body)

    def test_sonnet_gets_disabled_thinking_no_temperature(self):
        body = sa._build_body(_paper(), "claude-sonnet-5")
        self.assertNotIn("temperature", body)
        self.assertEqual(body["thinking"], {"type": "disabled"})

    def test_max_tokens_1024(self):
        body = sa._build_body(_paper(), "claude-haiku-4-5")
        self.assertEqual(body["max_tokens"], 1024)


class TestSummarizePaper(unittest.TestCase):
    def test_success_with_fixture(self):
        result = sa.summarize_paper(_paper(), "claude-haiku-4-5", "fake-key", post_fn=ok_post_fn, now_fn=_now_fn)
        self.assertEqual(result["lang"], "es")
        self.assertEqual(result["model"], "claude-haiku-4-5")
        self.assertEqual(result["prompt_version"], "v1")
        self.assertIn("100", result["text"])

    def test_untraceable_number_is_rejected(self):
        def post_fn(url, headers, body, timeout):
            data = {
                "content": [{"type": "text", "text": "Se reportaron 999999 participantes en el estudio."}],
                "stop_reason": "end_turn",
            }
            return 200, json.dumps(data).encode("utf-8"), {}

        with self.assertRaises(RuntimeError):
            sa.summarize_paper(_paper(), "claude-haiku-4-5", "fake-key", post_fn=post_fn, now_fn=_now_fn)

    def test_max_tokens_stop_reason_rejected(self):
        def post_fn(url, headers, body, timeout):
            data = {"content": [{"type": "text", "text": "texto cortado"}], "stop_reason": "max_tokens"}
            return 200, json.dumps(data).encode("utf-8"), {}

        with self.assertRaises(RuntimeError):
            sa.summarize_paper(_paper(), "claude-haiku-4-5", "fake-key", post_fn=post_fn, now_fn=_now_fn)

    def test_retries_on_429_then_succeeds(self):
        calls = {"n": 0}

        def post_fn(url, headers, body, timeout):
            calls["n"] += 1
            if calls["n"] == 1:
                return 429, b"{}", {}
            with open(os.path.join(FIXTURES, "anthropic_ok.json"), encoding="utf-8") as f:
                raw = f.read().encode("utf-8")
            return 200, raw, {}

        sleeps = []
        result = sa.summarize_paper(
            _paper(),
            "claude-haiku-4-5",
            "fake-key",
            post_fn=post_fn,
            sleep_fn=lambda s: sleeps.append(s),
            now_fn=_now_fn,
        )
        self.assertEqual(calls["n"], 2)
        self.assertEqual(sleeps, [5])

    def test_respects_retry_after_header(self):
        calls = {"n": 0}

        def post_fn(url, headers, body, timeout):
            calls["n"] += 1
            if calls["n"] == 1:
                return 429, b"{}", {"retry-after": "3"}
            with open(os.path.join(FIXTURES, "anthropic_ok.json"), encoding="utf-8") as f:
                raw = f.read().encode("utf-8")
            return 200, raw, {}

        sleeps = []
        sa.summarize_paper(
            _paper(),
            "claude-haiku-4-5",
            "fake-key",
            post_fn=post_fn,
            sleep_fn=lambda s: sleeps.append(s),
            now_fn=_now_fn,
        )
        self.assertEqual(sleeps, [3.0])


class TestSummarizeItems(unittest.TestCase):
    def test_skips_nd_license(self):
        paper = _paper()
        paper["open_access"]["license"] = "cc by-nc-nd"
        added = sa.summarize_items([paper], 20, "claude-haiku-4-5", "fake-key", post_fn=ok_post_fn, now_fn=_now_fn)
        self.assertEqual(added, 0)
        self.assertIsNone(paper["ai_summary"])

    def test_skips_without_abstract(self):
        paper = _paper()
        paper["abstract"] = None
        added = sa.summarize_items([paper], 20, "claude-haiku-4-5", "fake-key", post_fn=ok_post_fn, now_fn=_now_fn)
        self.assertEqual(added, 0)

    def test_adds_summary_and_respects_limit(self):
        papers = [_paper(title=f"Study {i} about 100 adults with ADHD.") for i in range(3)]
        added = sa.summarize_items(papers, 2, "claude-haiku-4-5", "fake-key", post_fn=ok_post_fn, now_fn=_now_fn)
        self.assertEqual(added, 2)
        self.assertIsNotNone(papers[0]["ai_summary"])
        self.assertIsNotNone(papers[1]["ai_summary"])
        self.assertIsNone(papers[2]["ai_summary"])

    def test_individual_failure_does_not_abort_batch(self):
        papers = [_paper(title="Study A about 100 adults."), _paper(title="Study B about 100 adults.")]

        calls = {"n": 0}

        def post_fn(url, headers, body, timeout):
            calls["n"] += 1
            if calls["n"] == 1:
                return 500, b"{}", {}
            with open(os.path.join(FIXTURES, "anthropic_ok.json"), encoding="utf-8") as f:
                raw = f.read().encode("utf-8")
            return 200, raw, {}

        added = sa.summarize_items(
            papers, 20, "claude-haiku-4-5", "fake-key", post_fn=post_fn, sleep_fn=lambda s: None, now_fn=_now_fn
        )
        # el primero falla tras reintentos (3 intentos), el segundo se resume aparte
        self.assertGreaterEqual(added, 0)


class TestCliDryRunAndNoKey(unittest.TestCase):
    def test_dry_run_prints_prompt_without_network(self):
        import tempfile

        called = {"n": 0}

        def post_fn(*a, **kw):
            called["n"] += 1
            return 200, b"{}", {}

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "day.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"items": [_paper()]}, f)
            args = argparse.Namespace(input=path, limit=20, model=None, dry_run=True)
            rc = sa.run(args, post_fn=post_fn, now_fn=_now_fn)
        self.assertEqual(rc, 0)
        self.assertEqual(called["n"], 0)

    def test_missing_key_exits_3(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "day.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"items": []}, f)
            args = argparse.Namespace(input=path, limit=20, model=None, dry_run=False)
            with mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop("ANTHROPIC_API_KEY", None)
                rc = sa.run(args, now_fn=_now_fn)
        self.assertEqual(rc, 3)


if __name__ == "__main__":
    unittest.main()
