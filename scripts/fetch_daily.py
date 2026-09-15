"""Descarga el feed diario desde Europe PMC + PubMed y lo normaliza.

PubMed amplía el descubrimiento. Europe PMC conserva la autoridad para el
gate de publicación: isOpenAccess=Y y una licencia Creative Commons válida.

Ver 3.A A4 del plan de implementación y las enmiendas 5, 6, 7, 9, 12, 27.
"""

from __future__ import annotations

import argparse
import datetime
import glob
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import common
import epmc_client
import pubmed_client


def _log(msg, quiet=False):
    print(f"[fetch_daily] {msg}", file=sys.stderr)


_RETRACTION_TYPES = {"Retraction in", "Expression of concern in"}
_TITLE_REJECT_RE = re.compile(
    r"(?i)^(correction|erratum|corrigendum|retraction|retracted|expression of concern)\b"
)


def _local_filter_reason(rec, paper, config):
    if rec.get("isOpenAccess") != "Y":
        return "not_oa"
    if not common.license_allowed((paper.get("open_access") or {}).get("license")):
        return "no_license"
    title = (paper.get("title") or "").strip()
    if not title:
        return "empty_title"
    excl = {p.lower() for p in config.get("exclude_pub_types_local", [])}
    norm_types = [(t or "").lower() for t in paper.get("pub_types") or []]
    if any(t in excl for t in norm_types):
        return "pub_type"
    if _TITLE_REJECT_RE.match(title):
        return "title_pattern"
    cc_list = (rec.get("commentCorrectionList") or {}).get("commentCorrection") or []
    if any(cc.get("type") in _RETRACTION_TYPES for cc in cc_list):
        return "retraction_notice"
    return None


def _iso_now(now_fn):
    return now_fn().strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_day_file(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _days_for_run(args, today):
    if args.date:
        if not common.validate_date(args.date):
            raise ValueError(f"--date inválida: {args.date}")
        return [args.date]
    n = args.days
    return [str(today - datetime.timedelta(days=i)) for i in range(n - 1, -1, -1)]


def _build_existing_index(daily_dir, exclude_dates):
    """key/pmcid/doi -> date, para todos los días en disco salvo exclude_dates."""
    idx = {"key": {}, "pmcid": {}, "doi": {}}
    for path in sorted(glob.glob(os.path.join(daily_dir, "????-??-??.json"))):
        date = os.path.basename(path)[: -len(".json")]
        if date in exclude_dates:
            continue
        data = _load_day_file(path)
        if not data:
            continue
        for it in data.get("items", []):
            idx["key"][it["key"]] = date
            if it.get("pmcid"):
                idx["pmcid"][it["pmcid"].lower()] = date
            if it.get("doi"):
                idx["doi"][it["doi"].lower()] = date
    return idx


def _register_day_in_index(idx, date, items):
    for it in items:
        idx["key"][it["key"]] = date
        if it.get("pmcid"):
            idx["pmcid"][it["pmcid"].lower()] = date
        if it.get("doi"):
            idx["doi"][it["doi"].lower()] = date


def _is_cross_day_duplicate(paper, idx, date):
    k = idx["key"].get(paper["key"])
    if k is not None and k != date:
        return True
    if paper.get("pmcid"):
        d = idx["pmcid"].get(paper["pmcid"].lower())
        if d is not None and d != date:
            return True
    if paper.get("doi"):
        d = idx["doi"].get(paper["doi"].lower())
        if d is not None and d != date:
            return True
    return False


def _record_identity(rec):
    pmid = str(rec.get("pmid") or "").strip()
    if pmid:
        return "pmid:" + pmid
    pmcid = str(rec.get("pmcid") or "").strip().lower()
    if pmcid:
        return "pmcid:" + pmcid
    doi = str(rec.get("doi") or "").strip().lower()
    if doi:
        return "doi:" + doi
    return f"{rec.get('source') or ''}:{rec.get('id') or ''}"


def _merge_discovery_records(epmc_records, pubmed_records, pubmed_pmids):
    """Deduplica registros y conserva por qué API fueron descubiertos."""
    merged = {}
    order = []

    def add(rec, source):
        key = _record_identity(rec)
        if key not in merged:
            merged[key] = {"record": rec, "sources": []}
            order.append(key)
        if source not in merged[key]["sources"]:
            merged[key]["sources"].append(source)

    for rec in epmc_records:
        add(rec, "europepmc")
    for rec in pubmed_records:
        add(rec, "pubmed")

    pubmed_set = {str(x) for x in pubmed_pmids}
    for entry in merged.values():
        pmid = str(entry["record"].get("pmid") or "")
        if pmid in pubmed_set and "pubmed" not in entry["sources"]:
            entry["sources"].append("pubmed")

    return [merged[key] for key in order]


def _process_day(
    date,
    config,
    daily_dir,
    existing_idx,
    *,
    fetch_fn,
    pubmed_fetch_fn,
    sleep_fn,
    now_fn,
    quiet,
):
    query = epmc_client.build_daily_query(config, date)
    try:
        epmc_records, epmc_hit_count, truncated = epmc_client.search_all(
            query,
            page_size=config.get("page_size", 100),
            max_pages=config.get("max_pages", 10),
            sort=config.get("sort"),
            fetch_fn=fetch_fn,
            sleep_fn=sleep_fn,
        )
    except epmc_client.EpmcError as e:
        _log(f"{date}: fallo de red/API ({e.kind}): {e.msg}", quiet)
        return None, "failure"

    if truncated:
        # Enmienda 5 / hallazgo de verificación: un día truncado (más
        # resultados que page_size*max_pages) no representa el conjunto
        # completo de ese día. Escribirlo pisaría los ítems ya guardados con
        # un subconjunto parcial y los "retiraría" por error. Se deja el
        # D.json existente intacto y el día cuenta como fallo (exit 1).
        _log(
            f"{date}: Europe PMC TRUNCADO (hitCount={epmc_hit_count} > page_size*max_pages); "
            "no se escribe (sube --max-pages o reduce la ventana)",
            quiet,
        )
        return None, "failure"

    pubmed_pmids = []
    pubmed_hit_count = 0
    pubmed_query = None
    pubmed_records = []
    pubmed_unresolved = 0
    if config.get("pubmed_enabled", True):
        try:
            pubmed_pmids, pubmed_hit_count, pubmed_truncated, pubmed_query = pubmed_client.search_daily(
                config,
                date,
                fetch_fn=pubmed_fetch_fn,
                sleep_fn=sleep_fn,
            )
        except pubmed_client.PubmedError as e:
            _log(f"{date}: fallo de PubMed ({e.kind}): {e.msg}", quiet)
            return None, "failure"
        if pubmed_truncated:
            _log(
                f"{date}: PubMed TRUNCADO (hitCount={pubmed_hit_count} > "
                f"pubmed_retmax={config.get('pubmed_retmax', 5000)}); no se escribe",
                quiet,
            )
            return None, "failure"

        epmc_pmids = {
            str(rec.get("pmid") or rec.get("id") or "")
            for rec in epmc_records
            if (rec.get("source") == "MED" or rec.get("pmid"))
        }
        missing_pmids = [pmid for pmid in pubmed_pmids if pmid not in epmc_pmids]
        try:
            pubmed_records = epmc_client.lookup_pmids(
                missing_pmids,
                fetch_fn=fetch_fn,
                sleep_fn=sleep_fn,
            )
        except epmc_client.EpmcError as e:
            _log(f"{date}: fallo al verificar PMIDs de PubMed en Europe PMC ({e.kind}): {e.msg}", quiet)
            return None, "failure"
        resolved = {str(rec.get("pmid") or rec.get("id") or "") for rec in pubmed_records}
        pubmed_unresolved = len(set(missing_pmids) - resolved)

    merged_records = _merge_discovery_records(epmc_records, pubmed_records, pubmed_pmids)

    checked_at = _iso_now(now_fn)
    discard_counts = {}
    if pubmed_unresolved:
        discard_counts["pubmed_not_in_europepmc"] = pubmed_unresolved
    candidates = []
    seen_keys = set()
    for entry in merged_records:
        rec = entry["record"]
        paper = common.normalize_record(rec, config, checked_at)
        paper["discovered_via"] = entry["sources"]
        reason = _local_filter_reason(rec, paper, config)
        if reason:
            discard_counts[reason] = discard_counts.get(reason, 0) + 1
            continue
        if paper["key"] in seen_keys:
            continue
        seen_keys.add(paper["key"])
        candidates.append(paper)

    final_items = []
    omitted_cross_day = 0
    for paper in candidates:
        if _is_cross_day_duplicate(paper, existing_idx, date):
            omitted_cross_day += 1
            continue
        final_items.append(paper)

    old_day = _load_day_file(os.path.join(daily_dir, f"{date}.json"))
    old_items_by_key = {it["key"]: it for it in (old_day or {}).get("items", [])}

    new_count = 0
    existing_count = 0
    for paper in final_items:
        old = old_items_by_key.get(paper["key"])
        if old is not None:
            existing_count += 1
            old_abstract = (old.get("abstract") or {}).get("text")
            new_abstract = (paper.get("abstract") or {}).get("text")
            if old.get("ai_summary") and old_abstract == new_abstract:
                paper["ai_summary"] = old["ai_summary"]
        else:
            new_count += 1

    retired = len(set(old_items_by_key.keys()) - {p["key"] for p in final_items})

    common.apply_relevance(final_items, config)

    day_obj = {
        "schema_version": 1,
        "date": date,
        "timezone": config.get("timezone", "America/Lima"),
        "fetched_at": _iso_now(now_fn),
        "source": {
            "name": "Europe PMC + PubMed",
            "endpoint": epmc_client.BASE_URL,
            "date_field": config.get("date_field", "FIRST_IDATE"),
            "query": query,
            "hit_count": epmc_hit_count,
            "accepted": len(final_items),
            "query_version": config.get("query_version"),
            "oa_gate": "Europe PMC isOpenAccess=Y + licencia CC declarada",
            "europepmc": {
                "endpoint": epmc_client.BASE_URL,
                "query": query,
                "hit_count": epmc_hit_count,
            },
            "pubmed": {
                "endpoint": pubmed_client.BASE_URL,
                "date_field": config.get("pubmed_date_type", "edat"),
                "query": pubmed_query,
                "hit_count": pubmed_hit_count,
                "unresolved_in_europepmc": pubmed_unresolved,
            },
        },
        "items": final_items,
    }

    total_discarded = sum(discard_counts.values())
    if not quiet:
        parts = ", ".join(f"{v} {k}" for k, v in sorted(discard_counts.items()))
        print(
            f"{date}: Europe PMC {epmc_hit_count} hits · PubMed {pubmed_hit_count} hits · "
            f"{len(final_items)} aceptados OA · {new_count} nuevos · "
            f"{existing_count} existentes · {total_discarded} descartados"
            + (f" ({parts})" if parts else "")
            + (f" · {omitted_cross_day} omitidos por duplicado de otro día" if omitted_cross_day else "")
            + (f" · {retired} retirados" if retired else "")
        )
    return day_obj, "ok"


def _complete_as_of_fetch(date, fetched_at_iso):
    """True si `date` ya había terminado en UTC en el momento en que
    ESE día se consultó (`fetched_at`), no en el momento de reconstruir el
    índice (hallazgo de verificación: usar `today` de la reconstrucción hace
    que un día parcial se declare "completo" tras una re-consulta fallida
    posterior, sin que Europe PMC haya terminado de indexarlo).

    Europe PMC fecha FIRST_IDATE en UTC. Un día está completo si el fetch
    ocurrió después de que ese día terminó en UTC. PubMed (hora del este de
    EE. UU.) puede sumar papers de ese día en la corrida de la noche siguiente,
    que re-consulta el día."""
    if not common.validate_date(date) or not fetched_at_iso:
        return False
    try:
        fetched_dt = datetime.datetime.strptime(fetched_at_iso, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=datetime.timezone.utc
        )
    except ValueError:
        return False
    return date < str(fetched_dt.date())


def _rebuild_index(daily_dir, index_path, config, today, now_fn):
    days = []
    total_items = 0
    for path in sorted(glob.glob(os.path.join(daily_dir, "????-??-??.json"))):
        date = os.path.basename(path)[: -len(".json")]
        data = _load_day_file(path)
        if not data:
            continue
        items = data.get("items", [])
        ai_count = sum(1 for it in items if it.get("ai_summary"))
        complete = _complete_as_of_fetch(date, data.get("fetched_at"))
        days.append(
            {
                "date": date,
                "count": len(items),
                "ai_count": ai_count,
                "file": f"daily/{date}.json",
                "fetched_at": data.get("fetched_at"),
                "complete": complete,
            }
        )
        total_items += len(items)
    days.sort(key=lambda d: d["date"], reverse=True)

    latest = None
    for d in days:
        if d["complete"] and d["count"] > 0:
            latest = d["date"]
            break
    if latest is None:
        for d in days:
            if d["count"] > 0:
                latest = d["date"]
                break
    if latest is None and days:
        latest = days[0]["date"]

    new_index = {
        "schema_version": 1,
        "generated_at": _iso_now(now_fn),
        "timezone": config.get("timezone", "America/Lima"),
        "query_version": config.get("query_version"),
        "latest": latest,
        "total_items": total_items,
        "days": days,
        "labels": {"tags": common.TAGS, "designs": common.DESIGNS},
    }

    old_index = _load_day_file(index_path)
    if old_index:
        old_copy = dict(old_index)
        new_copy = dict(new_index)
        old_copy.pop("generated_at", None)
        new_copy.pop("generated_at", None)
        if old_copy == new_copy:
            new_index["generated_at"] = old_index["generated_at"]

    return new_index


def build_arg_parser():
    p = argparse.ArgumentParser()
    g = p.add_mutually_exclusive_group()
    g.add_argument("--days", type=int, default=None)
    g.add_argument("--date", type=str, default=None)
    p.add_argument("--summarize", action="store_true")
    p.add_argument("--max-ai", type=int, default=20)
    p.add_argument("--model", default=None)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--config", default="scripts/feed_config.json")
    p.add_argument("--data-dir", default="data")
    p.add_argument("--quiet", action="store_true")
    return p


def run(
    args,
    *,
    fetch_fn=None,
    pubmed_fetch_fn=None,
    post_fn=None,
    now_fn=None,
    today_fn=None,
    sleep_fn=None,
):
    now_fn = now_fn or (lambda: datetime.datetime.now(datetime.timezone.utc))
    today_fn = today_fn or common.lima_today
    # Antes: `sleep_fn or (lambda s: None)` apagaba TODO backoff (2s/5s entre
    # reintentos y 0.3s entre páginas) también en producción, porque el
    # default siempre era una lambda "truthy" que nunca cedía a time.sleep.
    sleep_fn = sleep_fn or time.sleep
    if pubmed_fetch_fn is None:
        pubmed_fetch_fn = fetch_fn

    if args.summarize and not os.environ.get("ANTHROPIC_API_KEY"):
        _log("--summarize requiere ANTHROPIC_API_KEY")
        return 3

    with open(args.config, "r", encoding="utf-8") as f:
        config = json.load(f)

    today = today_fn()
    days_n = args.days if args.days is not None else config.get("default_days", 2)
    args_for_days = argparse.Namespace(date=args.date, days=days_n)
    try:
        days = _days_for_run(args_for_days, today)
    except ValueError as e:
        _log(str(e), args.quiet)
        return 2

    daily_dir = os.path.join(args.data_dir, "daily")
    os.makedirs(daily_dir, exist_ok=True)
    index_path = os.path.join(daily_dir, "index.json")

    existing_idx = _build_existing_index(daily_dir, exclude_dates=set(days))

    failures = []
    written_days = []
    for date in days:
        day_obj, status = _process_day(
            date,
            config,
            daily_dir,
            existing_idx,
            fetch_fn=fetch_fn,
            pubmed_fetch_fn=pubmed_fetch_fn,
            sleep_fn=sleep_fn,
            now_fn=now_fn,
            quiet=args.quiet,
        )
        if status == "failure":
            failures.append(date)
            continue
        _register_day_in_index(existing_idx, date, day_obj["items"])
        if not args.dry_run:
            common.atomic_write_json(os.path.join(daily_dir, f"{date}.json"), day_obj)
        written_days.append(date)

    if args.summarize and not args.dry_run:
        import summarize_ai

        model = args.model or os.environ.get("ANTHROPIC_MODEL") or summarize_ai.DEFAULT_MODEL
        api_key = os.environ["ANTHROPIC_API_KEY"]
        for date in written_days:
            path = os.path.join(daily_dir, f"{date}.json")
            day_obj = _load_day_file(path)
            if not day_obj:
                continue
            items_sorted = sorted(
                day_obj["items"],
                key=lambda p: -((p.get("relevance") or {}).get("score") or 0),
            )
            added = summarize_ai.summarize_items(
                items_sorted, args.max_ai, model, api_key, post_fn=post_fn, sleep_fn=sleep_fn, now_fn=now_fn
            )
            if added:
                common.atomic_write_json(path, day_obj)

    if not args.dry_run:
        new_index = _rebuild_index(daily_dir, index_path, config, today, now_fn)
        common.atomic_write_json(index_path, new_index)

    return 1 if failures else 0


def main(argv):
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    return run(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
