"""Compila content/summaries/*.md a data/summaries.json (schema_version 2).

Ver el contrato de implementación "tipología de resúmenes v2" (empírico /
conceptual, principio, nota completa, OA v2 con OpenAlex) y el plan original
(3.A A7, enmiendas 2, 4, 16, 19, 31).
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


def _block_text_parts(block):
    t = block["type"]
    if t == "p":
        return [block["text"]]
    if t in ("ul", "ol"):
        return list(block["items"])
    if t == "kv":
        return [kv["value"] for kv in block["items"]]
    if t == "readings":
        return [it["why"] for it in block["items"]]
    return []


def _count_words(sections):
    n = 0
    for sec in sections:
        for block in sec.get("blocks", []):
            for part in _block_text_parts(block):
                n += len(_WORD_RE.findall(part))
    return n


def _section_text(sec):
    if not sec or sec.get("pending"):
        return ""
    parts = []
    for b in sec.get("blocks", []):
        parts.extend(_block_text_parts(b))
    return " ".join(parts)


def _corpus_text(by_id, summary_type):
    """Texto contra el que se verifican las cifras de 'Evidencia' del
    principio (contrato C1.5): Hallazgos+Métodos (empírico) o
    Ideas+Argumento (conceptual)."""
    if summary_type == "empirico":
        return _section_text(by_id.get("hallazgos")) + " " + _section_text(by_id.get("metodos"))
    return _section_text(by_id.get("ideas")) + " " + _section_text(by_id.get("argumento"))


_RETRACTION_TITLE_RE = re.compile(
    r"(?i)^(correction|erratum|corrigendum|retraction|retracted|expression of concern)\b"
)


def _verify_oa_live(fm, path, fetch_fn=None, sleep_fn=None):
    """Ejecuta lookup en vivo y valida OA v2 + no-retracción. Lanza
    ValueError si falla la validación; deja pasar epmc_client.EpmcError (red
    caída, 5xx agotados, 429...) para que el llamador la trate como fallo de
    red (exit 1), no como rechazo de contenido.

    OA v2 (solo resúmenes curados, contrato §11): ruta A si Europe PMC sigue
    marcando isOpenAccess=Y con licencia CC; si no, ruta B (OpenAlex) cuando
    el .md declara paper_oa_source: europepmc+openalex.
    """
    identifier = fm.get("paper_pmcid") or fm.get("paper_doi")
    rec = epmc_client.lookup(identifier, fetch_fn=fetch_fn, sleep_fn=sleep_fn)
    if rec is None:
        raise ValueError(f"{path}: no se encontró {identifier} en Europe PMC (--verify-oa)")

    title = common.strip_html(rec.get("title") or "")
    if _RETRACTION_TITLE_RE.match(title):
        raise ValueError(f"{path}: {identifier} aparece como corrección/retractación en Europe PMC")
    cc_list = (rec.get("commentCorrectionList") or {}).get("commentCorrection") or []
    if any(cc.get("type") in ("Retraction in", "Expression of concern in") for cc in cc_list):
        raise ValueError(f"{path}: {identifier} tiene una retractación o expresión de preocupación asociada")

    license_raw = (rec.get("license") or "").strip().lower()
    oa_source = fm.get("paper_oa_source", "europepmc")
    route_a_ok = rec.get("isOpenAccess") == "Y" and common.license_allowed(license_raw)

    if route_a_ok:
        if oa_source == "europepmc+openalex":
            _log(
                f"{path}: aviso: Europe PMC ya certifica open access con licencia CC (ruta A); "
                "paper_oa_source: europepmc+openalex ya no hace falta"
            )
        return

    # Ruta A falló: o ya no es OA en Europe PMC, o la licencia declarada ahí
    # ya no es CC abierta. Solo se intenta la ruta B (OpenAlex) si la
    # licencia de Europe PMC sigue siendo CC (el gate de licencia no se
    # salta nunca) y el .md ya declara la ruta B.
    if not common.license_allowed(license_raw):
        raise ValueError(
            f"{path}: la licencia vigente de {identifier} en Europe PMC no es una CC abierta (--verify-oa)"
        )
    doi = fm.get("paper_doi")
    if oa_source != "europepmc+openalex":
        raise ValueError(
            f"{path}: Europe PMC ya no marca {identifier} como open access (isOpenAccess != 'Y'); si la "
            "licencia CC sigue vigente en la versión publicada, verifica con OpenAlex y declara "
            "paper_oa_source: europepmc+openalex"
        )
    if not doi:
        raise ValueError(f"{path}: paper_oa_source: europepmc+openalex requiere paper_doi para consultar OpenAlex")

    work = epmc_client.openalex_lookup(doi, fetch_fn=fetch_fn, sleep_fn=sleep_fn)
    if work is None:
        raise ValueError(f"{path}: {doi} no está en OpenAlex; la ruta B de OA v2 no aplica")
    ok, license_norm, reason = common.openalex_oa_verdict(work)
    if not ok:
        raise ValueError(f"{path}: OpenAlex no confirma acceso abierto con licencia CC para {doi} ({reason})")
    if license_norm != license_raw:
        raise ValueError(
            f"{path}: la licencia de OpenAlex ({license_norm!r}) no coincide con paper_license "
            f"declarado ({license_raw!r})"
        )


def _verify_readings_live(readings, status, fetch_fn=None, sleep_fn=None):
    """Verifica que cada lectura exista (Europe PMC por doi/pmid; si el doi
    no está ahí, Crossref). Lanza ValueError si status==published y alguna
    no se puede verificar; solo avisa (stderr) si status==draft. Deja pasar
    epmc_client.EpmcError (fallo de red) sin capturar."""
    for r in readings:
        ident = r.get("doi") or r.get("pmid")
        rec = epmc_client.lookup(ident, fetch_fn=fetch_fn, sleep_fn=sleep_fn)
        found = rec is not None
        if not found and r.get("doi"):
            work = epmc_client.crossref_lookup(r["doi"], fetch_fn=fetch_fn, sleep_fn=sleep_fn)
            found = work is not None
        if not found:
            msg = f"lectura no verificable (ni Europe PMC ni Crossref la reconocen): {r['citation'][:60]}"
            if status == "published":
                raise ValueError(msg)
            _log(f"aviso: {msg}")


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
    doi_url = ("https://doi.org/" + urllib.parse.quote(doi, safe="/:;()._-")) if doi else None
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
            "source": fm.get("paper_oa_source", "europepmc"),
            "checked_at": fm["paper_oa_checked"] + "T00:00:00Z",
        },
        "links": {
            "doi": doi_url,
            "europepmc": f"https://europepmc.org/article/{source}/{epmc_id}",
            "fulltext_html": (f"https://europepmc.org/articles/{pmcid}" if pmcid else doi_url),
            "pdf": (f"https://europepmc.org/articles/{pmcid}?pdf=render" if pmcid else None),
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


def _build_item(fm, body, path, filename, verify_oa=False, fetch_fn=None, sleep_fn=None):
    summary_type = fm["summary_type"]
    status = fm["status"]
    study_design = fm["study_design"]
    sections = common.parse_body(body, status, path, summary_type)
    by_id = {s["id"]: s for s in sections}

    # El principio y la nota completa son estructuralmente opcionales para
    # parse_body (no conoce study_design/status); su obligatoriedad
    # condicional se valida aquí, que sí tiene fm completo.
    principio_exempt = summary_type == "empirico" and study_design == "protocol"
    if status == "published" and not principio_exempt and "principio" not in by_id:
        raise common.SummaryFormatError(path, 1, "'## El principio' es obligatorio en status: published")
    if status == "published" and summary_type == "empirico" and "nota_completa" not in by_id:
        raise common.SummaryFormatError(
            path, 1, "'## Nota completa' es obligatoria en status: published (resumen empírico)"
        )

    ef = by_id.get("en_una_frase")
    one_liner = ef["blocks"][0]["text"] if ef and not ef["pending"] and ef["blocks"] else None

    quick_facts = None
    fr = by_id.get("ficha_rapida")
    if fr and not fr["pending"]:
        quick_facts = [{"key": it["key"], "value": it["value"]} for it in fr["blocks"][0]["items"]]

    glossary = None
    gl = by_id.get("glosario")
    if gl and not gl["pending"]:
        glossary = [{"term": it["key"], "definition": it["value"]} for it in gl["blocks"][0]["items"]]

    principle = None
    pr = by_id.get("principio")
    if pr and not pr["pending"]:
        corpus_text = _corpus_text(by_id, summary_type)
        try:
            principle = common.validate_principle(pr["blocks"][0]["items"], summary_type, study_design, corpus_text)
        except ValueError as e:
            raise common.SummaryFormatError(path, 1, str(e))

    readings = None
    lc = by_id.get("lecturas")
    if lc and not lc["pending"]:
        readings = []
        for it in lc["blocks"][0]["items"]:
            if it.get("doi"):
                url = "https://doi.org/" + urllib.parse.quote(it["doi"], safe="/:;()._-")
            else:
                url = f"https://europepmc.org/abstract/MED/{it['pmid']}"
            readings.append(
                {
                    "citation": it["citation"],
                    "doi": it.get("doi"),
                    "pmid": it.get("pmid"),
                    "url": url,
                    "why": it["why"],
                }
            )
        if verify_oa:
            try:
                _verify_readings_live(readings, status, fetch_fn=fetch_fn, sleep_fn=sleep_fn)
            except ValueError as e:
                raise common.SummaryFormatError(path, 1, str(e))

    full_note = None
    nc = by_id.get("nota_completa")
    if nc is not None:
        fn_sections = nc.get("full_note_sections", [])
        full_note = {
            "pending": nc["pending"],
            "word_count": _count_words(fn_sections) if not nc["pending"] else 0,
            "sections": fn_sections,
        }

    out_sections = [s for s in sections if s["id"] != "nota_completa"]
    word_count = _count_words(out_sections)
    reading_minutes = max(1, round(word_count / 200))
    if word_count > 1200:
        _log(f"{path}: aviso: el resumen tiene {word_count} palabras (más de 1200)")

    slug = filename[: -len(".md")]
    design_confidence = "draft" if fm.get("ai_draft") else "manual"

    return {
        "slug": slug,
        "title": fm["title"],
        "date": fm["date"],
        "updated": fm.get("updated"),
        "status": status,
        "example": fm.get("example", False),
        "ai_draft": fm.get("ai_draft", False),
        "adapted_with_ai": fm.get("adapted_with_ai", False),
        "author": fm.get("author"),
        "summary_type": summary_type,
        "tags": fm["tags"],
        "study_design": {"id": study_design, "confidence": design_confidence},
        "sample_size": (
            {"value": fm["sample_size"], "confidence": design_confidence} if fm.get("sample_size") else None
        ),
        "one_liner": one_liner,
        "principle": principle,
        "quick_facts": quick_facts,
        "glossary": glossary,
        "readings": readings,
        "sections": out_sections,
        "full_note": full_note,
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

    return _build_item(fm, body, path, filename, verify_oa=verify_oa, fetch_fn=fetch_fn, sleep_fn=sleep_fn)


def _labels():
    return {
        "tags": common.TAGS,
        "designs": common.DESIGNS,
        "summary_types": common.SUMMARY_TYPES,
        "strengths": {
            "alta": "Alta",
            "moderada": "Moderada",
            "baja": "Baja",
            "muy baja": "Muy baja",
            "argumental": "Argumental",
        },
    }


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
                    "schema_version": 2,
                    "generated_at": now_fn().strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "count": 0,
                    "items": [],
                    "labels": _labels(),
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
            "schema_version": 2,
            "generated_at": now_fn().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "count": len(valid_items),
            "items": valid_items,
            "labels": _labels(),
        },
    )
    return 0


def main(argv):
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    return run(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
