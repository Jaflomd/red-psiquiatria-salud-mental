"""Compila content/summaries/*.md a data/summaries.json.

Ver 3.A A7 del plan de implementación y las enmiendas 2, 4, 16, 19, 31.
"""

from __future__ import annotations

import argparse
import datetime
import glob
import json
import os
import re
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import common
import epmc_client


def _log(msg):
    print(f"[build_summaries] {msg}", file=sys.stderr)


_WORD_RE = re.compile(r"\S+")


def _count_words(sections):
    n = 0
    for sec in sections:
        for block in sec.get("blocks", []):
            if block["type"] == "p":
                n += len(_WORD_RE.findall(block["text"]))
            elif block["type"] == "ul":
                for item in block["items"]:
                    n += len(_WORD_RE.findall(item))
    return n


_RETRACTION_TITLE_RE = re.compile(
    r"(?i)^(correction|erratum|corrigendum|retraction|retracted|expression of concern)\b"
)


def _verify_oa_live(fm, path, fetch_fn=None, sleep_fn=None):
    """Ejecuta lookup en vivo y valida OA + no-retracción. Lanza ValueError si falla."""
    identifier = fm.get("paper_pmcid") or fm.get("paper_doi")
    rec = epmc_client.lookup(identifier, fetch_fn=fetch_fn, sleep_fn=sleep_fn)
    if rec is None:
        raise ValueError(f"{path}: no se encontró {identifier} en Europe PMC (--verify-oa)")
    if rec.get("isOpenAccess") != "Y":
        raise ValueError(f"{path}: Europe PMC ya no marca {identifier} como open access (--verify-oa)")
    license_raw = (rec.get("license") or "").strip().lower()
    if not common.license_allowed(license_raw):
        raise ValueError(f"{path}: la licencia vigente de {identifier} no es una CC abierta (--verify-oa)")
    title = common.strip_html(rec.get("title") or "")
    if _RETRACTION_TITLE_RE.match(title):
        raise ValueError(f"{path}: {identifier} aparece como corrección/retractación en Europe PMC")
    cc_list = (rec.get("commentCorrectionList") or {}).get("commentCorrection") or []
    if any(cc.get("type") in ("Retraction in", "Expression of concern in") for cc in cc_list):
        raise ValueError(f"{path}: {identifier} tiene una retractación o expresión de preocupación asociada")


def _build_paper(fm):
    doi = fm.get("paper_doi")
    pmcid = fm.get("paper_pmcid")
    source = fm["paper_source"]
    epmc_id = fm["paper_epmc_id"]
    license_raw = fm["paper_license"]
    # "manual" implica que Javier confirmó el dato; un borrador con
    # ai_draft:true no lo ha hecho todavía (hallazgo de verificación) — se
    # etiqueta "draft" y el frontend lo muestra como "(indicado en el
    # borrador)" en vez de "(indicado por el curador)".
    design_confidence = "draft" if fm.get("ai_draft") else "manual"
    return {
        "key": f"{source}:{epmc_id}",
        "epmc_id": epmc_id,
        "source": source,
        "pmid": fm.get("paper_pmid"),
        "pmcid": pmcid,
        "doi": doi,
        "title": fm["paper_title"],
        "authors": fm["paper_authors"],
        "journal": fm["paper_journal"],
        "journal_abbrev": fm.get("paper_journal_abbrev"),
        "pub_year": fm["paper_year"],
        "first_publication_date": fm.get("paper_pub_date"),
        "first_index_date": None,
        "pub_types": fm.get("paper_pub_types") or [],
        "language": None,
        "is_preprint": fm.get("paper_preprint", False),
        "open_access": {
            "status": "verified",
            "license": license_raw,
            "license_label": common.license_label(license_raw),
            "source": "europepmc",
            "checked_at": fm["paper_oa_checked"] + "T00:00:00Z",
        },
        "links": {
            "doi": ("https://doi.org/" + urllib.parse.quote(doi, safe="/:;()._-")) if doi else None,
            "europepmc": f"https://europepmc.org/article/{source}/{epmc_id}",
            "fulltext_html": f"https://europepmc.org/articles/{pmcid}" if pmcid else None,
            "pdf": f"https://europepmc.org/articles/{pmcid}?pdf=render" if pmcid else None,
        },
        "abstract": None,
        "summary": None,
        "ai_summary": None,
        "study_design": {"id": fm["study_design"], "confidence": design_confidence},
        "sample_size": (
            {"value": fm["sample_size"], "confidence": design_confidence} if fm.get("sample_size") else None
        ),
        "tags": fm["tags"],
        "mesh_major": [],
        "keywords": [],
        "relevance": None,
    }


def _build_item(fm, body, path, filename):
    sections = common.parse_body(body, fm["status"], path)
    by_id = {s["id"]: s for s in sections}
    ef = by_id.get("en_una_frase")
    one_liner = None
    if ef and not ef["pending"]:
        if len(ef["blocks"]) != 1 or ef["blocks"][0]["type"] != "p":
            raise common.SummaryFormatError(
                path, 1, "'En una frase' debe ser exactamente un párrafo"
            )
        text = ef["blocks"][0]["text"]
        if len(text) > 300:
            raise common.SummaryFormatError(
                path, 1, "'En una frase' debe tener 300 caracteres o menos"
            )
        one_liner = text

    word_count = _count_words(sections)
    reading_minutes = max(1, round(word_count / 200))
    slug = filename[: -len(".md")]
    design_confidence = "draft" if fm.get("ai_draft") else "manual"

    return {
        "slug": slug,
        "title": fm["title"],
        "date": fm["date"],
        "updated": fm.get("updated"),
        "status": fm["status"],
        "example": fm.get("example", False),
        "ai_draft": fm.get("ai_draft", False),
        "author": fm.get("author"),
        "tags": fm["tags"],
        "study_design": {"id": fm["study_design"], "confidence": design_confidence},
        "sample_size": (
            {"value": fm["sample_size"], "confidence": design_confidence} if fm.get("sample_size") else None
        ),
        "one_liner": one_liner,
        "sections": sections,
        "word_count": word_count,
        "reading_minutes": reading_minutes,
        "source_file": f"content/summaries/{filename}",
        "paper": _build_paper(fm),
    }


def _process_file(path, verify_oa, fetch_fn, sleep_fn=None):
    filename = os.path.basename(path)
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    fm, body = common.parse_frontmatter(text, path)

    expected_slug_part = filename[: -len(".md")]
    if not common.validate_slug(expected_slug_part):
        raise common.SummaryFormatError(
            path, 1, f"nombre de archivo inválido como slug: {expected_slug_part}"
        )
    date_in_name = expected_slug_part[:10]
    if date_in_name != fm["date"]:
        raise common.SummaryFormatError(
            path, 1, f"la fecha del nombre de archivo ({date_in_name}) no coincide con date: {fm['date']}"
        )

    if verify_oa:
        try:
            _verify_oa_live(fm, path, fetch_fn=fetch_fn, sleep_fn=sleep_fn)
        except ValueError as e:
            raise common.SummaryFormatError(path, 1, str(e))

    return _build_item(fm, body, path, filename)


def build_arg_parser():
    p = argparse.ArgumentParser()
    p.add_argument("--src", default="content/summaries")
    p.add_argument("--out", default="data/summaries.json")
    p.add_argument("--check", action="store_true")
    p.add_argument("--verify-oa", action="store_true")
    p.add_argument("--skip-invalid", action="store_true")
    p.add_argument("--include-drafts", action="store_true")
    return p


def run(args, *, fetch_fn=None, now_fn=None, sleep_fn=None):
    now_fn = now_fn or (lambda: datetime.datetime.now(datetime.timezone.utc))
    paths = sorted(glob.glob(os.path.join(args.src, "*.md")))

    if not paths:
        _log("no se encontraron archivos .md en " + args.src)
        if not args.check:
            common.atomic_write_json(
                args.out,
                {
                    "schema_version": 1,
                    "generated_at": now_fn().strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "count": 0,
                    "items": [],
                    "labels": {"tags": common.TAGS, "designs": common.DESIGNS},
                },
            )
        return 0

    valid_items = []
    errors = []
    excluded_drafts = 0
    for path in paths:
        try:
            item = _process_file(path, args.verify_oa, fetch_fn, sleep_fn=sleep_fn)
        except common.SummaryFormatError as e:
            errors.append(str(e))
            continue
        except epmc_client.EpmcError as e:
            # --verify-oa hace red en vivo; antes un fallo de red/API
            # (timeout, 5xx, SSL) escapaba como traceback no capturado en vez
            # de un fallo controlado (hallazgo de verificación).
            _log(f"{path}: fallo de red/API en --verify-oa ({e.kind}): {e.msg}")
            return 1
        if item["status"] == "draft" and not item["example"] and not args.include_drafts:
            excluded_drafts += 1
            continue
        valid_items.append(item)

    for e in errors:
        print(e, file=sys.stderr)

    if errors and not args.skip_invalid:
        _log(f"{len(errors)} archivo(s) con errores; no se escribió {args.out}")
        return 2

    if excluded_drafts:
        _log(f"{excluded_drafts} borrador(es) sin 'example: true' excluidos (usa --include-drafts)")

    # date desc, luego slug asc dentro del mismo date (sort estable en dos pasadas).
    valid_items.sort(key=lambda it: it["slug"])
    valid_items.sort(key=lambda it: it["date"], reverse=True)

    if args.check:
        if errors:
            return 2
        _log(f"{len(valid_items)} resumen(es) válidos ({len(errors)} con errores)")
        return 0

    common.write_json_preserving_timestamp(
        args.out,
        {
            "schema_version": 1,
            "generated_at": now_fn().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "count": len(valid_items),
            "items": valid_items,
            "labels": {"tags": common.TAGS, "designs": common.DESIGNS},
        },
    )
    return 0


def main(argv):
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    return run(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
