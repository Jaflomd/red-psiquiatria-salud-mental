import argparse
import datetime
import glob
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
import urllib.error
import urllib.parse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import fetch_daily as fd
import epmc_client as ec

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "scripts", "feed_config.json")

FIXED_NOW = datetime.datetime(2026, 9, 14, 11, 0, 0, tzinfo=datetime.timezone.utc)
FIXED_TODAY = datetime.date(2026, 9, 14)


def _now_fn():
    return FIXED_NOW


def _today_fn():
    return FIXED_TODAY


def _load_cfg():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def _rec(
    id_,
    pmcid=None,
    doi=None,
    title="A study about depression and anxiety.",
    license_="cc by",
    is_oa="Y",
    pub_types=None,
    abstract="Background text. Conclusions: this matters a lot.",
    journal="Journal of Affective Disorders",
    journal_abbrev="J Affect Disord",
    source="MED",
    pmid=None,
    first_index_date="2026-09-12",
    first_pub_date="2026-09-01",
    pub_year="2026",
):
    return {
        "id": id_,
        "source": source,
        "pmid": pmid or (id_ if source == "MED" else None),
        "pmcid": pmcid,
        "doi": doi,
        "title": title,
        "authorString": "Doe J, Smith A.",
        "journalInfo": {"journal": {"title": journal, "isoabbreviation": journal_abbrev}},
        "pubYear": pub_year,
        "firstPublicationDate": first_pub_date,
        "firstIndexDate": first_index_date,
        "pubTypeList": {"pubType": pub_types or ["research-article", "Journal Article"]},
        "language": "eng",
        "isOpenAccess": is_oa,
        "license": license_,
        "fullTextUrlList": {"fullTextUrl": []},
        "abstractText": abstract,
        "meshHeadingList": {"meshHeading": []},
        "keywordList": {"keyword": []},
    }


_DATE_IN_URL_RE = re.compile(r"FIRST_IDATE%3A%5B(\d{4}-\d{2}-\d{2})")


def make_fetch_fn(day_records, day_errors=None, pubmed_day_records=None, pubmed_errors=None):
    day_errors = day_errors or set()
    pubmed_day_records = pubmed_day_records if pubmed_day_records is not None else day_records
    pubmed_errors = pubmed_errors or set()

    def fetch_fn(url):
        parsed = urllib.parse.urlparse(url)
        qs = urllib.parse.parse_qs(parsed.query)

        if parsed.netloc == "eutils.ncbi.nlm.nih.gov":
            day = (qs.get("mindate") or [""])[0].replace("/", "-")
            if day in pubmed_errors:
                raise urllib.error.URLError("simulated PubMed failure")
            records = pubmed_day_records.get(day, [])
            pmids = []
            for rec in records:
                pmid = str(rec.get("pmid") or (rec.get("id") if rec.get("source") == "MED" else ""))
                if pmid.isdigit() and pmid not in pmids:
                    pmids.append(pmid)
            retmax = int((qs.get("retmax") or ["20"])[0])
            return {
                "header": {},
                "esearchresult": {
                    "count": str(len(pmids)),
                    "retmax": str(retmax),
                    "retstart": "0",
                    "idlist": pmids[:retmax],
                },
            }

        m = _DATE_IN_URL_RE.search(url)
        date = m.group(1) if m else None
        if date in day_errors:
            raise urllib.error.URLError("simulated failure")
        if date:
            records = day_records.get(date, [])
        else:
            query = (qs.get("query") or [""])[0]
            wanted_pmids = set(re.findall(r"EXT_ID:(\d+)", query))
            records = []
            for source in (day_records, pubmed_day_records):
                for source_records in source.values():
                    for rec in source_records:
                        pmid = str(rec.get("pmid") or (rec.get("id") if rec.get("source") == "MED" else ""))
                        if pmid in wanted_pmids and all(existing.get("id") != rec.get("id") for existing in records):
                            records.append(rec)
        # Eco del cursorMark recibido cuando no hay más páginas (como la API
        # real): antes devolvía siempre "END" (!= cursor inicial "*"), lo que
        # hacía a search_all pedir SIEMPRE una página de más y disparar la
        # pausa real de 0.3s entre páginas en cada test.
        cursor = (qs.get("cursorMark") or ["*"])[0]
        return {
            "version": "6.9",
            "hitCount": len(records),
            "nextCursorMark": cursor,
            "resultList": {"result": records},
        }

    return fetch_fn


class FetchDailyTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.data_dir = os.path.join(self.tmp, "data")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _args(self, **kw):
        defaults = dict(
            days=None,
            date=None,
            summarize=False,
            max_ai=20,
            model=None,
            dry_run=False,
            config=CONFIG_PATH,
            data_dir=self.data_dir,
            quiet=True,
        )
        defaults.update(kw)
        return argparse.Namespace(**defaults)

    def _day_path(self, date):
        return os.path.join(self.data_dir, "daily", f"{date}.json")


class TestNewDay(FetchDailyTestCase):
    def test_new_day_writes_file(self):
        records = {"2026-09-14": [_rec("1"), _rec("2")]}
        fetch_fn = make_fetch_fn(records)
        rc = fd.run(self._args(date="2026-09-14"), fetch_fn=fetch_fn, now_fn=_now_fn, today_fn=_today_fn)
        self.assertEqual(rc, 0)
        self.assertTrue(os.path.exists(self._day_path("2026-09-14")))
        with open(self._day_path("2026-09-14"), encoding="utf-8") as f:
            day = json.load(f)
        self.assertEqual(len(day["items"]), 2)
        self.assertEqual(day["source"]["hit_count"], 2)


class TestIdempotency(FetchDailyTestCase):
    def test_two_runs_identical_except_nothing_since_clock_fixed(self):
        records = {"2026-09-14": [_rec("1"), _rec("2")]}
        fetch_fn = make_fetch_fn(records)
        fd.run(self._args(date="2026-09-14"), fetch_fn=fetch_fn, now_fn=_now_fn, today_fn=_today_fn)
        with open(self._day_path("2026-09-14"), encoding="utf-8") as f:
            first = f.read()
        fd.run(self._args(date="2026-09-14"), fetch_fn=fetch_fn, now_fn=_now_fn, today_fn=_today_fn)
        with open(self._day_path("2026-09-14"), encoding="utf-8") as f:
            second = f.read()
        self.assertEqual(first, second)


class TestApiFailureKeepsPrevious(FetchDailyTestCase):
    def test_failure_does_not_touch_existing_file(self):
        records = {"2026-09-14": [_rec("1")]}
        fetch_fn_ok = make_fetch_fn(records)
        fd.run(self._args(date="2026-09-14"), fetch_fn=fetch_fn_ok, now_fn=_now_fn, today_fn=_today_fn)
        with open(self._day_path("2026-09-14"), encoding="utf-8") as f:
            before = f.read()

        fetch_fn_fail = make_fetch_fn(records, day_errors={"2026-09-14"})
        rc = fd.run(
            self._args(date="2026-09-14"), fetch_fn=fetch_fn_fail, now_fn=_now_fn, today_fn=_today_fn,
            sleep_fn=lambda s: None,  # el fallo simulado dispara 3 reintentos con espera real
        )
        self.assertEqual(rc, 1)
        with open(self._day_path("2026-09-14"), encoding="utf-8") as f:
            after = f.read()
        self.assertEqual(before, after)


class TestTruncatedDay(FetchDailyTestCase):
    def test_truncated_day_not_written_and_rc_is_1(self):
        # hallazgo de verificación: un día truncado (hitCount > page_size *
        # max_pages) pisaba D.json con solo el subconjunto parcial recibido,
        # "retirando" por error los ítems que ya no volvían en esa página.
        records = {"2026-09-14": [_rec("1"), _rec("2")]}
        fetch_fn_ok = make_fetch_fn(records)
        fd.run(self._args(date="2026-09-14"), fetch_fn=fetch_fn_ok, now_fn=_now_fn, today_fn=_today_fn)
        with open(self._day_path("2026-09-14"), encoding="utf-8") as f:
            before = f.read()

        cfg = _load_cfg()
        cfg["page_size"] = 1
        cfg["max_pages"] = 1  # cap = 1; hitCount real = 2 -> truncado
        cfg_path = os.path.join(self.tmp, "feed_config.json")
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f)

        rc = fd.run(
            self._args(date="2026-09-14", config=cfg_path),
            fetch_fn=fetch_fn_ok, now_fn=_now_fn, today_fn=_today_fn,
        )
        self.assertEqual(rc, 1)
        with open(self._day_path("2026-09-14"), encoding="utf-8") as f:
            after = f.read()
        self.assertEqual(before, after)


class TestCrossDayDedup(FetchDailyTestCase):
    def test_item_from_earlier_day_not_duplicated(self):
        os.makedirs(os.path.join(self.data_dir, "daily"), exist_ok=True)
        old_item_rec = _rec("1", pmcid="PMC1000001")
        # Simula que el día 09-12 ya tiene este item (día "más antiguo").
        old_day = {
            "schema_version": 1,
            "date": "2026-09-12",
            "timezone": "America/Lima",
            "fetched_at": "2026-09-13T00:00:00Z",
            "source": {
                "name": "Europe PMC",
                "endpoint": ec.BASE_URL,
                "date_field": "FIRST_IDATE",
                "query": "x",
                "hit_count": 1,
                "accepted": 1,
                "query_version": "test",
            },
            "items": [
                __import__("common").normalize_record(
                    old_item_rec, _load_cfg(), "2026-09-13T00:00:00Z"
                )
            ],
        }
        with open(self._day_path("2026-09-12"), "w", encoding="utf-8") as f:
            json.dump(old_day, f)

        # El mismo pmcid reaparece en la consulta fresca del 09-13 (backfill).
        records = {"2026-09-13": [_rec("999", pmcid="PMC1000001")]}
        fetch_fn = make_fetch_fn(records)
        rc = fd.run(self._args(date="2026-09-13"), fetch_fn=fetch_fn, now_fn=_now_fn, today_fn=_today_fn)
        self.assertEqual(rc, 0)
        with open(self._day_path("2026-09-13"), encoding="utf-8") as f:
            new_day = json.load(f)
        self.assertEqual(len(new_day["items"]), 0)


class TestAiSummaryCarryover(FetchDailyTestCase):
    def test_preserved_when_abstract_unchanged(self):
        os.makedirs(os.path.join(self.data_dir, "daily"), exist_ok=True)
        cfg = _load_cfg()
        rec = _rec("1", abstract="Same abstract text throughout.")
        paper = __import__("common").normalize_record(rec, cfg, "2026-09-13T00:00:00Z")
        paper["ai_summary"] = {
            "text": "resumen previo",
            "lang": "es",
            "model": "claude-haiku-4-5",
            "generated_at": "2026-09-13T00:00:00Z",
            "prompt_version": "v1",
        }
        old_day = {
            "schema_version": 1,
            "date": "2026-09-14",
            "timezone": "America/Lima",
            "fetched_at": "2026-09-13T00:00:00Z",
            "source": {
                "name": "Europe PMC",
                "endpoint": ec.BASE_URL,
                "date_field": "FIRST_IDATE",
                "query": "x",
                "hit_count": 1,
                "accepted": 1,
                "query_version": "test",
            },
            "items": [paper],
        }
        with open(self._day_path("2026-09-14"), "w", encoding="utf-8") as f:
            json.dump(old_day, f)

        records = {"2026-09-14": [rec]}
        fetch_fn = make_fetch_fn(records)
        fd.run(self._args(date="2026-09-14"), fetch_fn=fetch_fn, now_fn=_now_fn, today_fn=_today_fn)
        with open(self._day_path("2026-09-14"), encoding="utf-8") as f:
            new_day = json.load(f)
        self.assertEqual(new_day["items"][0]["ai_summary"]["text"], "resumen previo")

    def test_dropped_when_abstract_changed(self):
        os.makedirs(os.path.join(self.data_dir, "daily"), exist_ok=True)
        cfg = _load_cfg()
        rec = _rec("1", abstract="Original abstract text.")
        paper = __import__("common").normalize_record(rec, cfg, "2026-09-13T00:00:00Z")
        paper["ai_summary"] = {
            "text": "resumen previo",
            "lang": "es",
            "model": "claude-haiku-4-5",
            "generated_at": "2026-09-13T00:00:00Z",
            "prompt_version": "v1",
        }
        old_day = {
            "schema_version": 1,
            "date": "2026-09-14",
            "timezone": "America/Lima",
            "fetched_at": "2026-09-13T00:00:00Z",
            "source": {
                "name": "Europe PMC",
                "endpoint": ec.BASE_URL,
                "date_field": "FIRST_IDATE",
                "query": "x",
                "hit_count": 1,
                "accepted": 1,
                "query_version": "test",
            },
            "items": [paper],
        }
        with open(self._day_path("2026-09-14"), "w", encoding="utf-8") as f:
            json.dump(old_day, f)

        rec_changed = _rec("1", abstract="A completely different abstract now.")
        records = {"2026-09-14": [rec_changed]}
        fetch_fn = make_fetch_fn(records)
        fd.run(self._args(date="2026-09-14"), fetch_fn=fetch_fn, now_fn=_now_fn, today_fn=_today_fn)
        with open(self._day_path("2026-09-14"), encoding="utf-8") as f:
            new_day = json.load(f)
        self.assertIsNone(new_day["items"][0]["ai_summary"])


class TestRetiredItems(FetchDailyTestCase):
    def test_item_gone_from_fresh_query_is_removed(self):
        os.makedirs(os.path.join(self.data_dir, "daily"), exist_ok=True)
        cfg = _load_cfg()
        rec1 = _rec("1")
        paper1 = __import__("common").normalize_record(rec1, cfg, "2026-09-13T00:00:00Z")
        old_day = {
            "schema_version": 1,
            "date": "2026-09-14",
            "timezone": "America/Lima",
            "fetched_at": "2026-09-13T00:00:00Z",
            "source": {
                "name": "Europe PMC",
                "endpoint": ec.BASE_URL,
                "date_field": "FIRST_IDATE",
                "query": "x",
                "hit_count": 1,
                "accepted": 1,
                "query_version": "test",
            },
            "items": [paper1],
        }
        with open(self._day_path("2026-09-14"), "w", encoding="utf-8") as f:
            json.dump(old_day, f)

        # La consulta fresca ya no trae el item "1" (p. ej. fue retractado).
        records = {"2026-09-14": [_rec("2")]}
        fetch_fn = make_fetch_fn(records)
        fd.run(self._args(date="2026-09-14"), fetch_fn=fetch_fn, now_fn=_now_fn, today_fn=_today_fn)
        with open(self._day_path("2026-09-14"), encoding="utf-8") as f:
            new_day = json.load(f)
        keys = {it["key"] for it in new_day["items"]}
        self.assertNotIn("MED:1", keys)
        self.assertIn("MED:2", keys)


class TestIndexRebuild(FetchDailyTestCase):
    def test_index_sorted_descending_with_complete_flag(self):
        records = {
            "2026-09-12": [_rec("1")],
            "2026-09-13": [_rec("2")],
            "2026-09-14": [_rec("3")],
        }
        fetch_fn = make_fetch_fn(records)
        rc = fd.run(self._args(days=3), fetch_fn=fetch_fn, now_fn=_now_fn, today_fn=_today_fn)
        self.assertEqual(rc, 0)
        with open(os.path.join(self.data_dir, "daily", "index.json"), encoding="utf-8") as f:
            index = json.load(f)
        dates = [d["date"] for d in index["days"]]
        self.assertEqual(dates, sorted(dates, reverse=True))
        by_date = {d["date"]: d for d in index["days"]}
        self.assertTrue(by_date["2026-09-12"]["complete"])
        self.assertTrue(by_date["2026-09-13"]["complete"])
        self.assertFalse(by_date["2026-09-14"]["complete"])
        # latest = primer día completo con count>0 -> 2026-09-13
        self.assertEqual(index["latest"], "2026-09-13")

    def test_complete_derived_from_fetched_at_not_rebuild_time(self):
        # hallazgo de verificación: si un día parcial (09-14) se reconsulta
        # sin éxito un día después (09-15), el índice se reconstruye igual
        # (para reflejar 'failures') pero el 09-14 NO debe volverse "completo"
        # solo porque el reloj de la reconstrucción ya es 09-15: sigue siendo
        # el mismo fetched_at parcial de las 11:00 UTC del 09-14.
        records = {"2026-09-14": [_rec("1")]}
        fetch_fn_ok = make_fetch_fn(records)
        fd.run(self._args(date="2026-09-14"), fetch_fn=fetch_fn_ok, now_fn=_now_fn, today_fn=_today_fn)
        with open(os.path.join(self.data_dir, "daily", "index.json"), encoding="utf-8") as f:
            index_before = json.load(f)
        self.assertFalse({d["date"]: d for d in index_before["days"]}["2026-09-14"]["complete"])

        later_now = datetime.datetime(2026, 9, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)
        later_today = datetime.date(2026, 9, 15)
        fetch_fn_fail = make_fetch_fn(records, day_errors={"2026-09-14"})
        rc = fd.run(
            self._args(date="2026-09-14"), fetch_fn=fetch_fn_fail,
            now_fn=lambda: later_now, today_fn=lambda: later_today,
            sleep_fn=lambda s: None,
        )
        self.assertEqual(rc, 1)  # falló, pero el índice se reconstruye igual
        with open(os.path.join(self.data_dir, "daily", "index.json"), encoding="utf-8") as f:
            index_after = json.load(f)
        self.assertFalse({d["date"]: d for d in index_after["days"]}["2026-09-14"]["complete"])


class TestDryRun(FetchDailyTestCase):
    def test_dry_run_writes_nothing(self):
        records = {"2026-09-14": [_rec("1")]}
        fetch_fn = make_fetch_fn(records)
        rc = fd.run(
            self._args(date="2026-09-14", dry_run=True),
            fetch_fn=fetch_fn,
            now_fn=_now_fn,
            today_fn=_today_fn,
        )
        self.assertEqual(rc, 0)
        self.assertEqual(glob.glob(os.path.join(self.data_dir, "**", "*.json"), recursive=True), [])


class TestLocalFilters(FetchDailyTestCase):
    def test_correction_and_no_license_and_not_oa_discarded(self):
        records = {
            "2026-09-14": [
                _rec("1", title="Correction: something was wrong."),
                _rec("2", license_=None),
                _rec("3", is_oa="N"),
                _rec("4"),  # el único válido
            ]
        }
        fetch_fn = make_fetch_fn(records)
        rc = fd.run(self._args(date="2026-09-14"), fetch_fn=fetch_fn, now_fn=_now_fn, today_fn=_today_fn)
        self.assertEqual(rc, 0)
        with open(self._day_path("2026-09-14"), encoding="utf-8") as f:
            day = json.load(f)
        self.assertEqual(len(day["items"]), 1)
        self.assertEqual(day["items"][0]["key"], "MED:4")


class TestPubMedDiscovery(FetchDailyTestCase):
    def test_pubmed_only_record_is_resolved_in_epmc_and_accepted_if_oa(self):
        epmc_records = {"2026-09-14": [_rec("1")]}
        pubmed_records = {"2026-09-14": [_rec("1"), _rec("2", license_="cc by-nc")]}
        fetch_fn = make_fetch_fn(epmc_records, pubmed_day_records=pubmed_records)

        rc = fd.run(
            self._args(date="2026-09-14"),
            fetch_fn=fetch_fn,
            now_fn=_now_fn,
            today_fn=_today_fn,
        )
        self.assertEqual(rc, 0)
        with open(self._day_path("2026-09-14"), encoding="utf-8") as f:
            day = json.load(f)

        by_key = {item["key"]: item for item in day["items"]}
        self.assertEqual(set(by_key), {"MED:1", "MED:2"})
        self.assertEqual(by_key["MED:1"]["discovered_via"], ["europepmc", "pubmed"])
        self.assertEqual(by_key["MED:2"]["discovered_via"], ["pubmed"])
        self.assertEqual(day["source"]["name"], "Europe PMC + PubMed")
        self.assertEqual(day["source"]["oa_gate"], "Europe PMC isOpenAccess=Y + licencia CC declarada")
        self.assertEqual(day["source"]["pubmed"]["hit_count"], 2)

    def test_pubmed_only_record_without_oa_or_cc_license_is_rejected(self):
        epmc_records = {"2026-09-14": []}
        pubmed_records = {
            "2026-09-14": [
                _rec("2", is_oa="N"),
                _rec("3", license_=None),
                _rec("4", license_="cc by"),
            ]
        }
        fetch_fn = make_fetch_fn(epmc_records, pubmed_day_records=pubmed_records)

        rc = fd.run(
            self._args(date="2026-09-14"),
            fetch_fn=fetch_fn,
            now_fn=_now_fn,
            today_fn=_today_fn,
        )
        self.assertEqual(rc, 0)
        with open(self._day_path("2026-09-14"), encoding="utf-8") as f:
            day = json.load(f)
        self.assertEqual([item["key"] for item in day["items"]], ["MED:4"])

    def test_pubmed_failure_keeps_previous_day_untouched(self):
        records = {"2026-09-14": [_rec("1")]}
        fetch_fn_ok = make_fetch_fn(records)
        fd.run(
            self._args(date="2026-09-14"),
            fetch_fn=fetch_fn_ok,
            now_fn=_now_fn,
            today_fn=_today_fn,
        )
        with open(self._day_path("2026-09-14"), encoding="utf-8") as f:
            before = f.read()

        fetch_fn_fail = make_fetch_fn(records, pubmed_errors={"2026-09-14"})
        rc = fd.run(
            self._args(date="2026-09-14"),
            fetch_fn=fetch_fn_fail,
            now_fn=_now_fn,
            today_fn=_today_fn,
            sleep_fn=lambda s: None,
        )
        self.assertEqual(rc, 1)
        with open(self._day_path("2026-09-14"), encoding="utf-8") as f:
            after = f.read()
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
