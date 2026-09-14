import json
import os
import ssl
import sys
import unittest
import urllib.error

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import epmc_client as ec

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def load_fixture(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as f:
        return json.load(f)


class TestBuildDailyQuery(unittest.TestCase):
    def test_exact_query_for_a_day(self):
        config = {
            "title_abs_terms": ['"mental health"', "psychiatr*"],
            "journals": ["JAMA Psychiatry"],
            "journal_issns": ["2215-0366"],
            "extra_clauses": ['(TITLE_ABS:Peru* AND TITLE_ABS:depress*)'],
            "exclude_pub_types": ["abstract", "editorial"],
            "date_field": "FIRST_IDATE",
        }
        q = ec.build_daily_query(config, "2026-09-13")
        expected = (
            '(((TITLE_ABS:"mental health" OR TITLE_ABS:psychiatr*) OR (JOURNAL:"JAMA Psychiatry") '
            'OR (ISSN:"2215-0366") OR (TITLE_ABS:Peru* AND TITLE_ABS:depress*))) AND OPEN_ACCESS:y '
            "AND FIRST_IDATE:[2026-09-13 TO 2026-09-13] AND NOT "
            '(PUB_TYPE:"abstract" OR PUB_TYPE:"editorial")'
        )
        self.assertEqual(q, expected)

    def test_invalid_date_degenerate_query(self):
        config = {"title_abs_terms": [], "journals": [], "exclude_pub_types": []}
        q = ec.build_daily_query(config, "not-a-date")
        self.assertIn("FIRST_IDATE", q)


class TestValidateResponse(unittest.TestCase):
    def test_err_code_raises_api(self):
        data = load_fixture("epmc_error.json")
        with self.assertRaises(ec.EpmcError) as ctx:
            ec.validate_response(data)
        self.assertEqual(ctx.exception.kind, "api")

    def test_missing_hitcount_raises_invalid(self):
        data = load_fixture("epmc_invalid_sort.json")
        with self.assertRaises(ec.EpmcError) as ctx:
            ec.validate_response(data)
        self.assertEqual(ctx.exception.kind, "invalid_response")

    def test_ok_passthrough(self):
        data = load_fixture("epmc_lookup_oa.json")
        self.assertIs(ec.validate_response(data), data)


class TestSearchAll(unittest.TestCase):
    def test_pages_with_next_cursor_mark(self):
        page1 = {
            "version": "6.9",
            "hitCount": 2,
            "nextCursorMark": "CURSOR2",
            "resultList": {"result": [{"id": "1"}]},
        }
        page2 = {
            "version": "6.9",
            "hitCount": 2,
            "nextCursorMark": "CURSOR2",  # no cambia -> fin
            "resultList": {"result": [{"id": "2"}]},
        }
        calls = {"n": 0}

        def fetch_fn(url):
            calls["n"] += 1
            return page1 if calls["n"] == 1 else page2

        results, hit_count, truncated = ec.search_all(
            "query", page_size=1, max_pages=5, fetch_fn=fetch_fn, sleep_fn=lambda s: None
        )
        self.assertEqual([r["id"] for r in results], ["1", "2"])
        self.assertEqual(hit_count, 2)
        self.assertFalse(truncated)

    def test_truncated_flag(self):
        page = {
            "version": "6.9",
            "hitCount": 1000,
            "nextCursorMark": "SAME",
            "resultList": {"result": [{"id": "1"}]},
        }

        def fetch_fn(url):
            return page

        results, hit_count, truncated = ec.search_all(
            "query", page_size=10, max_pages=2, fetch_fn=fetch_fn, sleep_fn=lambda s: None
        )
        self.assertTrue(truncated)


class TestLookup(unittest.TestCase):
    def test_doi_maps_to_doi_query(self):
        captured = {}

        def fetch_fn(url):
            captured["url"] = url
            return {"version": "6.9", "hitCount": 0, "resultList": {"result": []}}

        ec.lookup("10.1093/schbul/sbae197", fetch_fn=fetch_fn)
        self.assertIn("DOI%3A%2210.1093%2Fschbul%2Fsbae197%22", captured["url"])

    def test_pmid_maps_to_ext_id_med(self):
        captured = {}

        def fetch_fn(url):
            captured["url"] = url
            return {"version": "6.9", "hitCount": 0, "resultList": {"result": []}}

        ec.lookup("39550208", fetch_fn=fetch_fn)
        self.assertIn("EXT_ID%3A39550208%20AND%20SRC%3AMED", captured["url"])

    def test_pmcid_maps_to_pmcid_query(self):
        captured = {}

        def fetch_fn(url):
            captured["url"] = url
            return {"version": "6.9", "hitCount": 0, "resultList": {"result": []}}

        ec.lookup("pmc12809804", fetch_fn=fetch_fn)
        self.assertIn("PMCID%3APMC12809804", captured["url"])

    def test_ppr_maps_to_ext_id_ppr(self):
        captured = {}

        def fetch_fn(url):
            captured["url"] = url
            return {"version": "6.9", "hitCount": 0, "resultList": {"result": []}}

        ec.lookup("PPR1309022", fetch_fn=fetch_fn)
        self.assertIn("EXT_ID%3APPR1309022%20AND%20SRC%3APPR", captured["url"])

    def test_fixture_oa_result(self):
        data = load_fixture("epmc_lookup_oa.json")

        def fetch_fn(url):
            return data

        rec = ec.lookup("PMC12809804", fetch_fn=fetch_fn)
        self.assertEqual(rec["isOpenAccess"], "Y")
        self.assertEqual(rec["license"], "cc by-nc")

    def test_fixture_not_oa_result(self):
        data = load_fixture("epmc_lookup_not_oa.json")

        def fetch_fn(url):
            return data

        rec = ec.lookup("10.1001/jamapsychiatry.2026.2410", fetch_fn=fetch_fn)
        self.assertEqual(rec["isOpenAccess"], "N")

    def test_fixture_empty_result(self):
        data = load_fixture("epmc_lookup_empty.json")

        def fetch_fn(url):
            return data

        rec = ec.lookup("10.9999/doesnotexist12345", fetch_fn=fetch_fn)
        self.assertIsNone(rec)

    def test_unrecognized_identifier_returns_none_without_network(self):
        called = {"n": 0}

        def fetch_fn(url):
            called["n"] += 1
            return {}

        rec = ec.lookup("not-an-identifier", fetch_fn=fetch_fn)
        self.assertIsNone(rec)
        self.assertEqual(called["n"], 0)


class TestNetworkFailureAndSslFallback(unittest.TestCase):
    def test_network_failure_raises_after_retries(self):
        calls = {"n": 0}

        def fetch_fn(url):
            calls["n"] += 1
            raise urllib.error.URLError("boom")

        sleeps = []
        with self.assertRaises(ec.EpmcError) as ctx:
            ec.http_get_json("http://x", fetch_fn=fetch_fn, sleep_fn=lambda s: sleeps.append(s))
        self.assertEqual(ctx.exception.kind, "network")
        self.assertEqual(calls["n"], 3)
        self.assertEqual(sleeps, [2, 5])

    def test_ssl_cert_error_switches_context_without_sleep_or_retry_count(self):
        ec._CACHED_SSL_MODE = None
        calls = {"n": 0}

        def fetch_fn(url):
            calls["n"] += 1
            if calls["n"] == 1:
                raise urllib.error.URLError(ssl.SSLCertVerificationError("bad cert"))
            return {"version": "6.9", "hitCount": 0, "resultList": {"result": []}}

        sleeps = []
        data = ec.http_get_json("http://x", fetch_fn=fetch_fn, sleep_fn=lambda s: sleeps.append(s))
        self.assertEqual(data["hitCount"], 0)
        self.assertEqual(calls["n"], 2)
        self.assertEqual(sleeps, [])  # sin esperas: el cambio de contexto no cuenta como reintento

    def test_http_4xx_not_retried(self):
        calls = {"n": 0}

        def fetch_fn(url):
            calls["n"] += 1
            raise urllib.error.HTTPError(url, 404, "Not Found", None, None)

        sleeps = []
        with self.assertRaises(ec.EpmcError) as ctx:
            ec.http_get_json("http://x", fetch_fn=fetch_fn, sleep_fn=lambda s: sleeps.append(s))
        self.assertEqual(ctx.exception.kind, "api")
        self.assertEqual(calls["n"], 1)  # un solo intento, sin reintento
        self.assertEqual(sleeps, [])

    def test_http_5xx_is_retried(self):
        calls = {"n": 0}

        def fetch_fn(url):
            calls["n"] += 1
            raise urllib.error.HTTPError(url, 503, "Service Unavailable", None, None)

        sleeps = []
        with self.assertRaises(ec.EpmcError):
            ec.http_get_json("http://x", fetch_fn=fetch_fn, sleep_fn=lambda s: sleeps.append(s))
        self.assertEqual(calls["n"], 3)
        self.assertEqual(sleeps, [2, 5])

    def test_non_json_body_is_retried_then_raises_network_error(self):
        calls = {"n": 0}

        def fetch_fn(url):
            calls["n"] += 1
            return b"<html>Service temporarily unavailable</html>"

        sleeps = []
        with self.assertRaises(ec.EpmcError) as ctx:
            ec.http_get_json("http://x", fetch_fn=fetch_fn, sleep_fn=lambda s: sleeps.append(s))
        self.assertEqual(calls["n"], 3)
        self.assertEqual(sleeps, [2, 5])

    def test_connection_reset_is_retried(self):
        calls = {"n": 0}

        def fetch_fn(url):
            calls["n"] += 1
            raise ConnectionResetError("reset")

        sleeps = []
        with self.assertRaises(ec.EpmcError):
            ec.http_get_json("http://x", fetch_fn=fetch_fn, sleep_fn=lambda s: sleeps.append(s))
        self.assertEqual(calls["n"], 3)
        self.assertEqual(sleeps, [2, 5])


if __name__ == "__main__":
    unittest.main()
