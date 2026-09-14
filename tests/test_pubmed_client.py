import os
import sys
import unittest
import urllib.parse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import pubmed_client as pc


class TestBuildDailyQuery(unittest.TestCase):
    def test_maps_scope_and_exclusions_to_pubmed_fields(self):
        config = {
            "pubmed_title_abs_terms": ['"mental health"', "psychiatry"],
            "journals": ["World Psychiatry"],
            "journal_issns": ["1723-8617"],
            "pubmed_extra_clauses": ["Peru[Title/Abstract]"],
            "pubmed_exclude_pub_types": ["Editorial", "Letter"],
        }
        query = pc.build_daily_query(config)
        self.assertIn('"mental health"[Title/Abstract]', query)
        self.assertIn('"World Psychiatry"[Journal]', query)
        self.assertIn('"1723-8617"[ISSN]', query)
        self.assertIn('"Editorial"[Publication Type]', query)
        self.assertIn("Peru[Title/Abstract]", query)


class TestValidateResponse(unittest.TestCase):
    def test_valid_response_returns_numeric_ids_and_count(self):
        ids, count = pc.validate_response(
            {
                "esearchresult": {
                    "count": "3",
                    "idlist": ["123", "bad", "456"],
                    "errorlist": {"phrasesnotfound": [], "fieldsnotfound": []},
                }
            }
        )
        self.assertEqual(ids, ["123", "456"])
        self.assertEqual(count, 3)

    def test_missing_esearchresult_is_invalid(self):
        with self.assertRaises(pc.PubmedError) as ctx:
            pc.validate_response({"header": {}})
        self.assertEqual(ctx.exception.kind, "invalid_response")

    def test_api_error_is_exposed(self):
        with self.assertRaises(pc.PubmedError) as ctx:
            pc.validate_response(
                {"esearchresult": {"count": "0", "idlist": [], "errorlist": {"phrasesnotfound": ["x"]}}}
            )
        self.assertEqual(ctx.exception.kind, "api")


class TestSearchDaily(unittest.TestCase):
    def test_uses_entry_date_and_expected_eutils_parameters(self):
        captured = {}

        def fetch_fn(url):
            captured["url"] = url
            return {"esearchresult": {"count": "2", "idlist": ["123", "456"]}}

        config = {
            "pubmed_title_abs_terms": ["psychiatry"],
            "pubmed_date_type": "edat",
            "pubmed_retmax": 5000,
        }
        ids, count, truncated, query = pc.search_daily(config, "2026-09-13", fetch_fn=fetch_fn)
        params = urllib.parse.parse_qs(urllib.parse.urlparse(captured["url"]).query)
        self.assertEqual(ids, ["123", "456"])
        self.assertEqual(count, 2)
        self.assertFalse(truncated)
        self.assertEqual(params["db"], ["pubmed"])
        self.assertEqual(params["datetype"], ["edat"])
        self.assertEqual(params["mindate"], ["2026/09/13"])
        self.assertEqual(params["maxdate"], ["2026/09/13"])
        self.assertEqual(params["retmode"], ["json"])
        self.assertEqual(params["term"], [query])

    def test_reports_truncation_when_count_exceeds_retmax(self):
        def fetch_fn(url):
            return {"esearchresult": {"count": "3", "idlist": ["1", "2"]}}

        config = {"pubmed_title_abs_terms": ["psychiatry"], "pubmed_retmax": 2}
        ids, count, truncated, _query = pc.search_daily(config, "2026-09-13", fetch_fn=fetch_fn)
        self.assertEqual(ids, ["1", "2"])
        self.assertEqual(count, 3)
        self.assertTrue(truncated)

    def test_invalid_date_does_not_call_network(self):
        called = {"n": 0}

        def fetch_fn(url):
            called["n"] += 1
            return {}

        with self.assertRaises(pc.PubmedError) as ctx:
            pc.search_daily({}, "not-a-date", fetch_fn=fetch_fn)
        self.assertEqual(ctx.exception.kind, "invalid_request")
        self.assertEqual(called["n"], 0)


if __name__ == "__main__":
    unittest.main()
