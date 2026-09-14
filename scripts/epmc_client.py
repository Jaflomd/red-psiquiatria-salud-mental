"""Cliente HTTP para la REST API de Europe PMC.

Solo stdlib. Inyectable (`fetch_fn`, `sleep_fn`) para tests offline.
Ver 3.A A3 y enmienda 10 (orden de fallback SSL) del plan de implementación.
"""

from __future__ import annotations

import http.client
import json
import os
import re
import shutil
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
UA = "red-psm-feed/0.1 (Europe PMC client; contact via repository)"

# Contexto SSL que funcionó la última vez, cacheado a nivel de módulo
# (enmienda 10): evita reintentar el contexto por defecto en cada llamada.
_CACHED_SSL_MODE = None  # None | "default" | "cafile" | "curl"


class EpmcError(Exception):
    def __init__(self, kind, msg=""):
        self.kind = kind  # "network" | "api" | "invalid_response"
        self.msg = msg
        super().__init__(f"[{kind}] {msg}")


def _log(msg):
    print(f"[epmc_client] {msg}", file=sys.stderr)


def _default_ctx():
    return None  # urllib usa el contexto SSL por defecto del sistema


def _cafile_ctx():
    cafile = os.environ.get("EPMC_CA_FILE") or "/etc/ssl/cert.pem"
    if not os.path.exists(cafile):
        return None
    return ssl.create_default_context(cafile=cafile)


def _do_urlopen(url, timeout, ctx):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    if ctx is None:
        return urllib.request.urlopen(req, timeout=timeout)
    return urllib.request.urlopen(req, timeout=timeout, context=ctx)


def _do_curl(url, timeout):
    if not shutil.which("curl"):
        raise EpmcError("network", "sin certificados SSL utilizables e instala curl o define EPMC_CA_FILE")
    proc = subprocess.run(
        ["curl", "-sS", "--fail", "--max-time", str(timeout), "-A", UA, "-H", "Accept: application/json", url],
        capture_output=True,
    )
    if proc.returncode != 0:
        raise EpmcError(
            "network",
            f"curl falló (returncode={proc.returncode}): {proc.stderr.decode(errors='replace')[:200]}",
        )
    return proc.stdout


class _NoCafile(Exception):
    pass


def http_get_json(url, timeout=30, fetch_fn=None, sleep_fn=None):
    """GET url -> dict JSON. Reintenta 3 veces (2s, 5s) en URLError/timeout/5xx.

    Fallback SSL: contexto por defecto -> EPMC_CA_FILE|/etc/ssl/cert.pem -> curl.
    Un SSLCertVerificationError pasa al siguiente contexto SIN esperar ni
    contar como reintento (enmienda 10). `fetch_fn`, si se da, reemplaza la
    llamada de red real en cada intento (se le puede inyectar para simular
    tanto éxitos como URLError/SSLCertVerificationError en los tests).
    """
    global _CACHED_SSL_MODE
    sleep_fn = sleep_fn or time.sleep

    def call(mode):
        if fetch_fn is not None:
            return fetch_fn(url)
        if mode == "curl":
            return _do_curl(url, timeout)
        ctx = _default_ctx() if mode == "default" else _cafile_ctx()
        if mode == "cafile" and ctx is None:
            raise _NoCafile()
        resp = _do_urlopen(url, timeout, ctx)
        status = getattr(resp, "status", 200)
        raw = resp.read()
        if status >= 500:
            raise EpmcError("network", f"HTTP {status}")
        return raw

    modes = ["default", "cafile", "curl"]
    if _CACHED_SSL_MODE in modes and fetch_fn is None:
        modes = [_CACHED_SSL_MODE] + [m for m in modes if m != _CACHED_SSL_MODE]

    mode_idx = 0
    attempt = 0
    delays = [2, 5]
    last_err = None
    while attempt < 3:
        mode = modes[min(mode_idx, len(modes) - 1)]
        try:
            raw = call(mode)
            if fetch_fn is None:
                _CACHED_SSL_MODE = mode
            if isinstance(raw, dict):
                return raw
            return json.loads(raw)
        except _NoCafile:
            mode_idx = modes.index("curl")
            continue
        except urllib.error.HTTPError as e:
            # HTTPError es subclase de URLError: sin esta rama explícita,
            # ANTES de la de URLError, un 4xx se trataba como fallo de red
            # genérico y se reintentaba 3 veces con espera, aunque la spec
            # (A3) pide no reintentar ante HTTP 4xx.
            if e.code >= 500:
                last_err = e
                attempt += 1
                if attempt < 3:
                    sleep_fn(delays[min(attempt - 1, len(delays) - 1)])
                continue
            raise EpmcError("api", f"HTTP {e.code}")
        except urllib.error.URLError as e:
            reason = getattr(e, "reason", None)
            if isinstance(reason, ssl.SSLCertVerificationError) and mode_idx < len(modes) - 1:
                mode_idx += 1
                continue
            last_err = e
            attempt += 1
            if attempt < 3:
                sleep_fn(delays[min(attempt - 1, len(delays) - 1)])
        except EpmcError as e:
            if e.kind == "api":
                # HTTP 4xx: no se reintenta (spec A3).
                raise
            last_err = e
            attempt += 1
            if attempt < 3:
                sleep_fn(delays[min(attempt - 1, len(delays) - 1)])
        except (json.JSONDecodeError, ValueError) as e:
            # Cuerpo no-JSON (p. ej. una página HTML de error 200 de un
            # proxy/CDN intermedio): tratar como fallo de red reintentable en
            # vez de dejar escapar la excepción sin capturar.
            last_err = e
            attempt += 1
            if attempt < 3:
                sleep_fn(delays[min(attempt - 1, len(delays) - 1)])
        except (OSError, http.client.HTTPException) as e:
            # Conexión reiniciada, lectura incompleta, etc.
            last_err = e
            attempt += 1
            if attempt < 3:
                sleep_fn(delays[min(attempt - 1, len(delays) - 1)])
        # TimeoutError es subclase de OSError: ya cubierto por la rama de
        # arriba (mismo tratamiento: reintentable, con espera).
    _log(f"fallo de red tras reintentos: {last_err}")
    raise EpmcError(
        "network",
        f"no se pudo contactar Europe PMC ({last_err}). Instala certificados o define EPMC_CA_FILE.",
    )


def validate_response(data):
    if "errCode" in data:
        raise EpmcError("api", data.get("errMsg", "error de la API"))
    if "hitCount" not in data:
        raise EpmcError("invalid_response", "respuesta sin hitCount (¿sort inválido?)")
    return data


def search(
    query,
    page_size=100,
    result_type="core",
    sort=None,
    cursor="*",
    timeout=30,
    fetch_fn=None,
    sleep_fn=None,
):
    params = {
        "query": query,
        "format": "json",
        "resultType": result_type,
        "pageSize": str(page_size),
        "cursorMark": cursor,
    }
    if sort:
        params["sort"] = sort
    url = BASE_URL + "?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    data = http_get_json(url, timeout=timeout, fetch_fn=fetch_fn, sleep_fn=sleep_fn)
    return validate_response(data)


def search_all(query, page_size=100, max_pages=10, sort=None, fetch_fn=None, sleep_fn=None):
    """Pagina todos los resultados. Devuelve (results, hit_count, truncated)."""
    sleep_fn = sleep_fn or time.sleep
    results = []
    cursor = "*"
    hit_count = 0
    page = 0
    while page < max_pages:
        data = search(
            query, page_size=page_size, sort=sort, cursor=cursor, fetch_fn=fetch_fn, sleep_fn=sleep_fn
        )
        hit_count = data.get("hitCount", 0)
        page_results = (data.get("resultList") or {}).get("result") or []
        results.extend(page_results)
        next_cursor = data.get("nextCursorMark")
        page += 1
        if not page_results or not next_cursor or next_cursor == cursor:
            break
        cursor = next_cursor
        if page < max_pages:
            sleep_fn(0.3)
    truncated = hit_count > page_size * max_pages
    if truncated:
        _log(f"día truncado: hitCount={hit_count} supera page_size*max_pages={page_size * max_pages}")
    return results, hit_count, truncated


def _identifier_query(identifier):
    ident = identifier.strip()
    if ident.lower().startswith("https://doi.org/"):
        ident = ident[len("https://doi.org/"):]
    elif ident.lower().startswith("doi:"):
        ident = ident[len("doi:"):]
    elif ident.lower().startswith("pmid:"):
        ident = ident[len("pmid:"):]
    ident = ident.strip()
    if ident.startswith("10."):
        return f'DOI:"{ident}"'
    if re.match(r"^PMC\d+$", ident, re.IGNORECASE):
        return f'PMCID:{ident.upper()}'
    if re.match(r"^PPR\d+$", ident, re.IGNORECASE):
        return f'EXT_ID:{ident.upper()} AND SRC:PPR'
    if re.match(r"^\d+$", ident):
        return f'EXT_ID:{ident} AND SRC:MED'
    return None


def lookup(identifier, fetch_fn=None, sleep_fn=None):
    query = _identifier_query(identifier)
    if query is None:
        return None
    data = search(query, page_size=3, result_type="core", fetch_fn=fetch_fn, sleep_fn=sleep_fn)
    results = (data.get("resultList") or {}).get("result") or []
    if not results:
        return None
    return results[0]


OPENALEX_BASE_URL = "https://api.openalex.org/works/doi:"
CROSSREF_BASE_URL = "https://api.crossref.org/works/"


def openalex_lookup(doi, fetch_fn=None, sleep_fn=None, timeout=30):
    """GET https://api.openalex.org/works/doi:<doi> (sin email). Devuelve el
    dict del 'work', o None si OpenAlex responde 404 (no está indexado) — un
    404 NO es un fallo de red (enmienda OA v2: "no está en OpenAlex", no
    exit 1). Cualquier otro EpmcError (5xx agotados, 429, etc.) se propaga."""
    url = OPENALEX_BASE_URL + urllib.parse.quote(doi, safe="/:;()._-")
    try:
        return http_get_json(url, timeout=timeout, fetch_fn=fetch_fn, sleep_fn=sleep_fn)
    except EpmcError as e:
        if e.kind == "api" and "404" in e.msg:
            return None
        raise


def crossref_lookup(doi, fetch_fn=None, sleep_fn=None, timeout=30):
    """GET https://api.crossref.org/works/<doi>. Devuelve el dict interno
    `message`, o None si Crossref no conoce el DOI (404)."""
    url = CROSSREF_BASE_URL + urllib.parse.quote(doi, safe="/:;()._-")
    try:
        data = http_get_json(url, timeout=timeout, fetch_fn=fetch_fn, sleep_fn=sleep_fn)
    except EpmcError as e:
        if e.kind == "api" and "404" in e.msg:
            return None
        raise
    return data.get("message")


def build_daily_query(config, day):
    from common import validate_date  # import local para evitar ciclo en tests

    if not validate_date(day):
        return f'FIRST_IDATE:[{day} TO {day}]'  # query degenerada: 0 hits, sin error

    title_abs = " OR ".join(f"TITLE_ABS:{t}" for t in config["title_abs_terms"])
    journal_clause = " OR ".join(f'JOURNAL:"{j}"' for j in config.get("journals", []))
    issn_clause = " OR ".join(f'ISSN:"{i}"' for i in config.get("journal_issns", []))
    extra_clauses = config.get("extra_clauses", [])

    group_parts = [f"({title_abs})"]
    if journal_clause:
        group_parts.append(f"({journal_clause})")
    if issn_clause:
        group_parts.append(f"({issn_clause})")
    group_parts.extend(extra_clauses)
    group = " OR ".join(group_parts)

    excl = " OR ".join(f'PUB_TYPE:"{p}"' for p in config.get("exclude_pub_types", []))
    date_field = config.get("date_field", "FIRST_IDATE")
    query = f"(({group})) AND OPEN_ACCESS:y AND {date_field}:[{day} TO {day}]"
    if excl:
        query += f" AND NOT ({excl})"
    return query
