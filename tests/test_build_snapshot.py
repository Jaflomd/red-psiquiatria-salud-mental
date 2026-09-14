import argparse
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import build_snapshot as bsnap

INDEX_HTML = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Red de Investigación de Psiquiatría y Salud Mental</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Newsreader&display=swap" rel="stylesheet">
<link rel="stylesheet" href="assets/styles.css">
</head>
<body>
<!-- snapshot:start -->
<div id="app">
  <header class="site-header">Cabecera</header>
  <main id="main"></main>
  <footer class="site-footer">Pie</footer>
</div>
<!-- snapshot:end -->
<script src="assets/app.js"></script>
</body>
</html>
"""

STYLES_CSS = ":root { --bg: #fff; }\nbody { background: var(--bg); }\n"
APP_JS = "(function(){ 'use strict'; console.log('app'); })();\n"


class BuildSnapshotTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.tmp, "assets"), exist_ok=True)
        os.makedirs(os.path.join(self.tmp, "content"), exist_ok=True)
        os.makedirs(os.path.join(self.tmp, "data", "daily"), exist_ok=True)
        with open(os.path.join(self.tmp, "index.html"), "w", encoding="utf-8") as f:
            f.write(INDEX_HTML)
        with open(os.path.join(self.tmp, "assets", "styles.css"), "w", encoding="utf-8") as f:
            f.write(STYLES_CSS)
        with open(os.path.join(self.tmp, "assets", "app.js"), "w", encoding="utf-8") as f:
            f.write(APP_JS)
        with open(os.path.join(self.tmp, "data", "summaries.json"), "w", encoding="utf-8") as f:
            json.dump({"schema_version": 1, "count": 0, "items": []}, f)

        self.out = os.path.join(self.tmp, "dist", "snapshot.html")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_index(self, days):
        with open(os.path.join(self.tmp, "data", "daily", "index.json"), "w", encoding="utf-8") as f:
            json.dump(
                {
                    "schema_version": 1,
                    "generated_at": "2026-09-14T11:00:00Z",
                    "timezone": "America/Lima",
                    "query_version": "test",
                    "latest": days[0]["date"] if days else None,
                    "total_items": sum(d["count"] for d in days),
                    "days": days,
                },
                f,
            )

    def _write_day(self, date, n_items, title_with_script_tag=False):
        items = []
        for i in range(n_items):
            title = f"Item {i}"
            if title_with_script_tag and i == 0:
                title = "Weird </script><!-- title"
            items.append(
                {
                    "key": f"MED:{date}-{i}",
                    "title": title,
                    "abstract": {
                        "lang": "en",
                        "structured": True,
                        "truncated": False,
                        "sections": [{"heading": "Background", "text": "x"}],
                        "text": ("Sentence one. " * 200),
                    },
                }
            )
        with open(os.path.join(self.tmp, "data", "daily", f"{date}.json"), "w", encoding="utf-8") as f:
            json.dump(
                {
                    "schema_version": 1,
                    "date": date,
                    "timezone": "America/Lima",
                    "fetched_at": "2026-09-14T11:00:00Z",
                    "source": {
                        "name": "Europe PMC",
                        "endpoint": "x",
                        "date_field": "FIRST_IDATE",
                        "query": "x",
                        "hit_count": n_items,
                        "accepted": n_items,
                        "query_version": "test",
                    },
                    "items": items,
                },
                f,
            )

    def _args(self, **kw):
        defaults = dict(days=3, max_items=40, abstract_chars=700, out=self.out, root=self.tmp)
        defaults.update(kw)
        return argparse.Namespace(**defaults)


class TestBasicSnapshot(BuildSnapshotTestCase):
    def test_starts_with_title_no_doctype(self):
        self._write_index([{"date": "2026-09-14", "count": 2, "ai_count": 0, "file": "daily/2026-09-14.json", "fetched_at": "x", "complete": True}])
        self._write_day("2026-09-14", 2)
        rc = bsnap.run(self._args())
        self.assertEqual(rc, 0)
        with open(self.out, encoding="utf-8") as f:
            content = f.read()
        self.assertTrue(content.startswith("<title>"))
        self.assertNotIn("<!doctype", content.lower())
        self.assertIn('<div id="app">', content)

    def test_font_link_extracted_correctly(self):
        self._write_index([{"date": "2026-09-14", "count": 0, "ai_count": 0, "file": "daily/2026-09-14.json", "fetched_at": "x", "complete": True}])
        self._write_day("2026-09-14", 0)
        bsnap.run(self._args())
        with open(self.out, encoding="utf-8") as f:
            content = f.read()
        self.assertIn('href="https://fonts.googleapis.com/css2?family=Newsreader&display=swap" rel="stylesheet"', content)
        # No debe confundir el <link rel="preconnect"> con la hoja de estilos.
        self.assertNotIn('<link href="https://fonts.googleapis.com" rel="stylesheet">', content)

    def test_no_script_close_or_html_comment_inside_json(self):
        self._write_index([{"date": "2026-09-14", "count": 1, "ai_count": 0, "file": "daily/2026-09-14.json", "fetched_at": "x", "complete": True}])
        self._write_day("2026-09-14", 1, title_with_script_tag=True)
        bsnap.run(self._args())
        with open(self.out, encoding="utf-8") as f:
            content = f.read()
        # Extraer el bloque JSON embebido del día y confirmar round-trip.
        marker = 'id="data-daily-2026-09-14">'
        start = content.index(marker) + len(marker)
        end = content.index("</script>", start)
        raw_json = content[start:end]
        self.assertNotIn("</script", raw_json)
        data = json.loads(raw_json)
        self.assertEqual(data["items"][0]["title"], "Weird </script><!-- title")


class TestMissingRequiredFile(BuildSnapshotTestCase):
    def test_missing_app_js_exits_2(self):
        os.remove(os.path.join(self.tmp, "assets", "app.js"))
        self._write_index([])
        rc = bsnap.run(self._args())
        self.assertEqual(rc, 2)


class TestCompaction(BuildSnapshotTestCase):
    def test_max_items_and_embedded_count(self):
        self._write_index(
            [{"date": "2026-09-14", "count": 50, "ai_count": 0, "file": "daily/2026-09-14.json", "fetched_at": "x", "complete": True}]
        )
        self._write_day("2026-09-14", 50)
        rc = bsnap.run(self._args(max_items=40))
        self.assertEqual(rc, 0)
        with open(self.out, encoding="utf-8") as f:
            content = f.read()
        marker = 'id="data-daily-2026-09-14">'
        start = content.index(marker) + len(marker)
        end = content.index("</script>", start)
        day_data = json.loads(content[start:end])
        self.assertEqual(len(day_data["items"]), 40)
        self.assertEqual(day_data["embedded_count"], 40)

        marker2 = 'id="data-daily-index">'
        start2 = content.index(marker2) + len(marker2)
        end2 = content.index("</script>", start2)
        index_data = json.loads(content[start2:end2])
        self.assertEqual(index_data["days"][0]["embedded_count"], 40)
        self.assertEqual(index_data["days"][0]["count"], 50)

    def test_abstract_truncated_at_sentence_boundary(self):
        self._write_index(
            [{"date": "2026-09-14", "count": 1, "ai_count": 0, "file": "daily/2026-09-14.json", "fetched_at": "x", "complete": True}]
        )
        self._write_day("2026-09-14", 1)
        bsnap.run(self._args(abstract_chars=50))
        with open(self.out, encoding="utf-8") as f:
            content = f.read()
        marker = 'id="data-daily-2026-09-14">'
        start = content.index(marker) + len(marker)
        end = content.index("</script>", start)
        day_data = json.loads(content[start:end])
        item = day_data["items"][0]
        self.assertLessEqual(len(item["abstract"]["text"]), 60)
        self.assertTrue(item["abstract"]["truncated"])
        self.assertEqual(item["abstract"]["sections"], [])


class TestLatestAlwaysEmbedded(BuildSnapshotTestCase):
    def test_latest_added_even_if_outside_days_window(self):
        days = [
            {"date": "2026-09-14", "count": 0, "ai_count": 0, "file": "daily/2026-09-14.json", "fetched_at": "x", "complete": False},
            {"date": "2026-09-13", "count": 5, "ai_count": 0, "file": "daily/2026-09-13.json", "fetched_at": "x", "complete": True},
            {"date": "2026-09-12", "count": 5, "ai_count": 0, "file": "daily/2026-09-12.json", "fetched_at": "x", "complete": True},
            {"date": "2026-09-11", "count": 5, "ai_count": 0, "file": "daily/2026-09-11.json", "fetched_at": "x", "complete": True},
        ]
        with open(os.path.join(self.tmp, "data", "daily", "index.json"), "w", encoding="utf-8") as f:
            json.dump(
                {
                    "schema_version": 1,
                    "generated_at": "x",
                    "timezone": "America/Lima",
                    "query_version": "test",
                    "latest": "2026-09-11",  # fuera de la ventana de --days 2
                    "total_items": 15,
                    "days": days,
                },
                f,
            )
        for d in days:
            self._write_day(d["date"], d["count"])
        rc = bsnap.run(self._args(days=2))
        self.assertEqual(rc, 0)
        with open(self.out, encoding="utf-8") as f:
            content = f.read()
        self.assertIn('id="data-daily-2026-09-11"', content)


if __name__ == "__main__":
    unittest.main()
