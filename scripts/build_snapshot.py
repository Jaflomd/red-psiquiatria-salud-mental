"""Genera dist/snapshot.html: el sitio con los datos embebidos, sin fetch.

Ver 3.A A8 del plan de implementación y las enmiendas 20, 21.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import common

FONT_LINK_RE = re.compile(
    r'<link\b(?=[^>]*\brel="stylesheet")[^>]*\bhref="(https://fonts\.googleapis\.com/css2\?[^"]+)"[^>]*>'
)
SNAPSHOT_BLOCK_RE = re.compile(
    r"<!-- snapshot:start -->(.*?)<!-- snapshot:end -->", re.DOTALL
)

_SENTENCE_END_RE = re.compile(r"[.!?]")


def _log(msg):
    print(f"[build_snapshot] {msg}", file=sys.stderr)


def _truncate_text(text, limit):
    if text is None or len(text) <= limit:
        return text, False
    cut = text[:limit]
    matches = list(_SENTENCE_END_RE.finditer(cut))
    if matches:
        end = matches[-1].end()
        return cut[:end].strip(), True
    return cut.strip(), True


def _embed_json(obj):
    s = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    return s.replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def _script_json_tag(elem_id, obj):
    return f'<script type="application/json" id="{elem_id}">{_embed_json(obj)}</script>'


def _compact_day(day_obj, max_items, abstract_chars):
    day = copy.deepcopy(day_obj)
    items = day.get("items", [])
    original_count = len(items)
    compacted_items = items[: max_items if max_items > 0 else len(items)]
    for it in compacted_items:
        abstract = it.get("abstract")
        if abstract:
            abstract["sections"] = []
            text, truncated = _truncate_text(abstract.get("text"), abstract_chars)
            abstract["text"] = text
            if truncated:
                abstract["truncated"] = True
    day["items"] = compacted_items
    day["embedded_count"] = len(compacted_items)
    day["_original_count"] = original_count
    return day


def build_arg_parser():
    p = argparse.ArgumentParser()
    p.add_argument("--days", type=int, default=3)
    p.add_argument("--max-items", type=int, default=40)
    p.add_argument("--abstract-chars", type=int, default=700)
    p.add_argument("--out", default="dist/snapshot.html")
    p.add_argument("--root", default=".")
    return p


def run(args):
    root = args.root
    index_html_path = os.path.join(root, "index.html")
    styles_path = os.path.join(root, "assets", "styles.css")
    app_js_path = os.path.join(root, "assets", "app.js")
    site_json_path = os.path.join(root, "content", "site.json")
    summaries_path = os.path.join(root, "data", "summaries.json")
    daily_index_path = os.path.join(root, "data", "daily", "index.json")
    daily_dir = os.path.join(root, "data", "daily")

    required = [index_html_path, styles_path, app_js_path, summaries_path, daily_index_path]
    for p in required:
        if not os.path.exists(p):
            _log(f"falta archivo obligatorio: {p}")
            return 2

    with open(index_html_path, "r", encoding="utf-8") as f:
        index_html = f.read()
    with open(styles_path, "r", encoding="utf-8") as f:
        styles_css = f.read()
    with open(app_js_path, "r", encoding="utf-8") as f:
        app_js = f.read()

    if re.search(r"</style", styles_css, re.IGNORECASE):
        _log("styles.css contiene '</style'; abortando")
        return 2
    if re.search(r"</script|<!--", app_js, re.IGNORECASE):
        _log("app.js contiene '</script' o '<!--'; abortando")
        return 2

    font_match = FONT_LINK_RE.search(index_html)
    if not font_match:
        _log("no se encontró el <link rel=\"stylesheet\"> de fonts.googleapis.com en index.html")
        return 2
    font_href = font_match.group(1)

    snap_match = SNAPSHOT_BLOCK_RE.search(index_html)
    if not snap_match:
        _log("no se encontraron los marcadores snapshot:start/snapshot:end en index.html")
        return 2
    snapshot_block = snap_match.group(1)

    site_data = None
    if os.path.exists(site_json_path):
        with open(site_json_path, "r", encoding="utf-8") as f:
            site_data = json.load(f)

    with open(summaries_path, "r", encoding="utf-8") as f:
        summaries_data = json.load(f)
    with open(daily_index_path, "r", encoding="utf-8") as f:
        daily_index = json.load(f)

    all_days = daily_index.get("days", [])
    selected = list(all_days[: args.days])
    selected_dates = {d["date"] for d in selected}
    latest = daily_index.get("latest")
    if latest and latest not in selected_dates:
        for d in all_days:
            if d["date"] == latest:
                selected.append(d)
                selected_dates.add(latest)
                break

    compacted_index = copy.deepcopy(daily_index)
    embedded_days_entries = []
    for d in selected:
        entry = copy.deepcopy(d)
        # count original se mantiene; embedded_count aparte.
        embedded_days_entries.append(entry)
    compacted_index["days"] = embedded_days_entries

    day_tags = []
    for d in selected:
        date = d["date"]
        day_path = os.path.join(daily_dir, f"{date}.json")
        if not os.path.exists(day_path):
            continue
        with open(day_path, "r", encoding="utf-8") as f:
            day_obj = json.load(f)
        compacted_day = _compact_day(day_obj, args.max_items, args.abstract_chars)
        for entry in compacted_index["days"]:
            if entry["date"] == date:
                entry["embedded_count"] = compacted_day["embedded_count"]
        compacted_day.pop("_original_count", None)
        day_tags.append(_script_json_tag(f"data-daily-{date}", compacted_day))

    parts = [
        "<title>Red de Investigación de Psiquiatría y Salud Mental</title>",
        '<link rel="preconnect" href="https://fonts.googleapis.com">',
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>',
        f'<link href="{font_href}" rel="stylesheet">',
        f"<style>{styles_css}</style>",
        snapshot_block,
    ]
    if site_data is not None:
        parts.append(_script_json_tag("data-site", site_data))
    parts.append(_script_json_tag("data-summaries", summaries_data))
    parts.append(_script_json_tag("data-daily-index", compacted_index))
    parts.extend(day_tags)
    parts.append(f"<script>{app_js}</script>")

    output = "\n".join(parts) + "\n"

    out_dir = os.path.dirname(args.out) or "."
    os.makedirs(out_dir, exist_ok=True)
    tmp_path = args.out + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(output)
    os.replace(tmp_path, args.out)

    size_kb = len(output.encode("utf-8")) / 1024
    print(f"[build_snapshot] {args.out}: {size_kb:.1f} KB", file=sys.stderr)
    if size_kb > 1500:
        _log(f"aviso: snapshot supera 1500 KB ({size_kb:.1f} KB)")
    return 0


def main(argv):
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    return run(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
