"""Cliente mínimo para PubMed ESearch (NCBI E-utilities).

PubMed se usa solo como fuente complementaria de descubrimiento. La decisión
de publicar sigue dependiendo de Europe PMC: isOpenAccess=Y y una licencia CC
declarada. Solo stdlib; la función HTTP es inyectable para pruebas offline.
"""

from __future__ import annotations

import os
import urllib.parse

import common
import epmc_client


BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
TOOL = "red_psm_feed"


class PubmedError(Exception):
    def __init__(self, kind, msg=""):
        self.kind = kind
        self.msg = msg
        super().__init__(f"[{kind}] {msg}")


def build_daily_query(config):
    """Traduce el alcance editorial a sintaxis de búsqueda de PubMed."""
    terms = config.get("pubmed_title_abs_terms") or config.get("title_abs_terms", [])
    title_abs = " OR ".join(f"{term}[Title/Abstract]" for term in terms)
    journals = " OR ".join(f'"{name}"[Journal]' for name in config.get("journals", []))
    issns = " OR ".join(f'"{issn}"[ISSN]' for issn in config.get("journal_issns", []))

    group_parts = []
    if title_abs:
        group_parts.append(f"({title_abs})")
    if journals:
        group_parts.append(f"({journals})")
    if issns:
        group_parts.append(f"({issns})")
    group_parts.extend(config.get("pubmed_extra_clauses", []))
    group = " OR ".join(group_parts) or "psychiatry[MeSH Terms]"

    excluded = config.get("pubmed_exclude_pub_types") or config.get("exclude_pub_types", [])
    excl = " OR ".join(f'"{name}"[Publication Type]' for name in excluded)
    query = f"({group})"
    if excl:
        query += f" NOT ({excl})"
    return query


def validate_response(data):
    result = data.get("esearchresult") if isinstance(data, dict) else None
    if not isinstance(result, dict):
        raise PubmedError("invalid_response", "respuesta sin esearchresult")
    errors = result.get("errorlist")
    if isinstance(errors, dict):
        errors = {key: value for key, value in errors.items() if value}
    if errors:
        raise PubmedError("api", str(errors))
    try:
        count = int(result.get("count", 0))
    except (TypeError, ValueError) as e:
        raise PubmedError("invalid_response", "count inválido") from e
    ids = [str(x) for x in (result.get("idlist") or []) if str(x).isdigit()]
    return ids, count


def search_daily(config, day, *, fetch_fn=None, sleep_fn=None, timeout=30):
    """Devuelve (pmids, hit_count, truncated, query) para un día de EDAT."""
    if not common.validate_date(day):
        raise PubmedError("invalid_request", f"fecha inválida: {day}")

    query = build_daily_query(config)
    retmax = int(config.get("pubmed_retmax", 5000))
    params = {
        "db": "pubmed",
        "term": query,
        "datetype": config.get("pubmed_date_type", "edat"),
        "mindate": day.replace("-", "/"),
        "maxdate": day.replace("-", "/"),
        "retmax": str(retmax),
        "retmode": "json",
        "sort": "pub_date",
        "tool": TOOL,
    }
    email = os.environ.get("NCBI_EMAIL")
    api_key = os.environ.get("NCBI_API_KEY")
    if email:
        params["email"] = email
    if api_key:
        params["api_key"] = api_key
    url = BASE_URL + "?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)

    try:
        data = epmc_client.http_get_json(
            url, timeout=timeout, fetch_fn=fetch_fn, sleep_fn=sleep_fn
        )
    except epmc_client.EpmcError as e:
        msg = e.msg.replace("Europe PMC", "PubMed")
        raise PubmedError(e.kind, msg) from e

    ids, count = validate_response(data)
    return ids, count, count > retmax, query
