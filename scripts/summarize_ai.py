"""Generación OPCIONAL de resúmenes en español con la API de Anthropic.

Camino nunca ejecutado en este prototipo (no hay ANTHROPIC_API_KEY en el
entorno). Solo stdlib: POST manual a /v1/messages con urllib. Ver 3.A A5 y
enmienda 26 (familias de modelo, stop_reason, post-chequeo de cifras).
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.request

DEFAULT_MODEL = "claude-haiku-4-5"
API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
PROMPT_VERSION = "v1"

SYSTEM_PROMPT = (
    "Eres asistente de un psiquiatra investigador. Resume en español latinoamericano, "
    "en 3 o 4 oraciones y máximo 90 palabras, el artículo cuyo título y resumen recibes. "
    "Usa solo la información del texto recibido: no inventes cifras, autores ni "
    "conclusiones; si el resumen no da un dato, no lo menciones. Escribe con tus propias "
    "palabras, sin citar textualmente más de 10 palabras seguidas. Sin viñetas, sin "
    "encabezados, sin comillas. Empieza por el hallazgo principal, no por 'Este estudio'."
)


def _log(msg):
    print(f"[summarize_ai] {msg}", file=sys.stderr)


def _user_prompt(paper):
    abstract_text = ((paper.get("abstract") or {}).get("text")) or ""
    return (
        f"Título: {paper.get('title', '')}\n\n"
        f"Revista: {paper.get('journal', '')} ({paper.get('pub_year', '')})\n\n"
        f"Resumen original (inglés):\n{abstract_text}"
    )


# Modelos donde thinking:{type:"disabled"} funciona (ver skill claude-api):
# Sonnet 5 y Opus 4.7/4.8 lo aceptan. Fable 5/5.1 y Mythos lo RECHAZAN con
# 400 (piensan siempre); Opus 5 lo acepta solo hasta effort "high" pero tiene
# fallas conocidas con thinking desactivado. Para esos casos (y cualquier
# modelo futuro no listado, p. ej. si ANTHROPIC_MODEL apunta al planner de
# Javier) se omite el parámetro por completo: corre en su modo adaptativo
# por defecto, que siempre es válido (hallazgo de verificación).
_THINKING_DISABLED_OK_RE = re.compile(r"^claude-sonnet-5$|^claude-opus-4-[78]")


def _build_body_for_prompt(prompt, model, system):
    body = {
        "model": model,
        "max_tokens": 1024,
        "system": system,
        "messages": [{"role": "user", "content": prompt}],
    }
    if model.startswith("claude-haiku-4-5"):
        body["temperature"] = 0.2
    elif _THINKING_DISABLED_OK_RE.match(model):
        body["thinking"] = {"type": "disabled"}
    # Fable/Mythos/Opus 5/otros: ni temperature ni thinking -> modo por
    # defecto del modelo (adaptativo), aceptado siempre.
    return body


def _build_body(paper, model):
    return _build_body_for_prompt(_user_prompt(paper), model, SYSTEM_PROMPT)


_NUM_RE = re.compile(r"\d+(?:[.,]\d+)?")


def _numbers_traceable(text, title, abstract_text):
    haystack = (title + " " + abstract_text).replace(",", ".")
    haystack_nums = set(_NUM_RE.findall(haystack))
    for m in _NUM_RE.finditer(text):
        tok = m.group(0).replace(",", ".")
        if tok not in haystack_nums:
            return False, tok
    return True, None


def _cafile_ctx():
    cafile = os.environ.get("EPMC_CA_FILE") or "/etc/ssl/cert.pem"
    if not os.path.exists(cafile):
        return None
    return ssl.create_default_context(cafile=cafile)


def _lower_headers(headers_obj):
    """dict(headers.items()) pierde la insensibilidad a mayúsculas de
    HTTPMessage: 'Retry-After' ya no lo encuentra un .get('retry-after')
    (hallazgo de verificación). Se normaliza a minúsculas al vuelo."""
    if not headers_obj:
        return {}
    return {k.lower(): v for k, v in headers_obj.items()}


def _default_post_fn(url, headers, body, timeout):
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST"
    )
    try:
        try:
            resp = urllib.request.urlopen(req, timeout=timeout)
        except urllib.error.URLError as e:
            # El contexto SSL por defecto falla en macOS sin certificados de
            # sistema instalados (mismo síntoma que epmc_client); se
            # reintenta una vez con la cadena de certificados de
            # EPMC_CA_FILE|/etc/ssl/cert.pem antes de rendirse.
            if not isinstance(getattr(e, "reason", None), ssl.SSLCertVerificationError):
                raise
            ctx = _cafile_ctx()
            if ctx is None:
                raise
            resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
        status = getattr(resp, "status", 200)
        raw = resp.read()
        return status, raw, _lower_headers(resp.headers)
    except urllib.error.HTTPError as e:
        raw = e.read()
        return e.code, raw, _lower_headers(e.headers)


def summarize_paper(paper, model, api_key, timeout=60, post_fn=None, sleep_fn=None, now_fn=None):
    post_fn = post_fn or _default_post_fn
    sleep_fn = sleep_fn or time.sleep
    now_fn = now_fn or (lambda: datetime.datetime.now(datetime.timezone.utc))

    headers = {
        "content-type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_VERSION,
    }
    body = _build_body(paper, model)

    delays = [5, 15]
    attempt = 0
    last_status = None
    last_body_preview = ""
    while attempt < 3:
        try:
            status, raw, resp_headers = post_fn(API_URL, headers, body, timeout)
        except (OSError, TimeoutError) as e:
            # Conexión caída, timeout, etc.: reintentable, igual que un 5xx
            # (antes solo se reintentaban códigos HTTP, nunca errores de
            # conexión — hallazgo de verificación).
            attempt += 1
            last_status = None
            last_body_preview = str(e)
            if attempt < 3:
                sleep_fn(delays[min(attempt - 1, len(delays) - 1)])
                continue
            break
        if status == 200:
            data = json.loads(raw)
            stop_reason = data.get("stop_reason")
            if stop_reason != "end_turn":
                raise RuntimeError(f"stop_reason no aceptable: {stop_reason}")
            text = "".join(
                block.get("text", "")
                for block in data.get("content", [])
                if block.get("type") == "text"
            ).strip()
            title = paper.get("title") or ""
            abstract_text = ((paper.get("abstract") or {}).get("text")) or ""
            ok, bad_tok = _numbers_traceable(text, title, abstract_text)
            if not ok:
                raise RuntimeError(f"cifra no trazable: {bad_tok}")
            return {
                "text": text,
                "lang": "es",
                "model": model,
                "generated_at": now_fn().strftime("%Y-%m-%dT%H:%M:%SZ"),
                "prompt_version": PROMPT_VERSION,
            }
        last_status = status
        last_body_preview = raw.decode("utf-8", errors="replace")[:200]
        if status in (429, 529) or status >= 500:
            attempt += 1
            if attempt >= 3:
                break
            retry_after = resp_headers.get("retry-after") if resp_headers else None
            if retry_after:
                try:
                    wait = min(60, float(retry_after))
                except ValueError:
                    wait = delays[min(attempt - 1, len(delays) - 1)]
            else:
                wait = delays[min(attempt - 1, len(delays) - 1)]
            sleep_fn(wait)
            continue
        break
    raise RuntimeError(f"HTTP {last_status}: {last_body_preview}")


def summarize_items(items, limit, model, api_key, post_fn=None, sleep_fn=None, now_fn=None):
    added = 0
    count = 0
    for paper in items:
        if count >= limit:
            break
        if paper.get("ai_summary"):
            continue
        if not paper.get("abstract") or not paper["abstract"].get("text"):
            continue
        license_raw = (paper.get("open_access") or {}).get("license") or ""
        if "-nd" in license_raw:
            _log(f"omitido (licencia -nd, no derivados): {paper.get('key')}")
            continue
        count += 1
        try:
            ai_summary = summarize_paper(
                paper, model, api_key, post_fn=post_fn, sleep_fn=sleep_fn, now_fn=now_fn
            )
            paper["ai_summary"] = ai_summary
            added += 1
        except Exception as e:  # noqa: BLE001 - fallo individual, no debe abortar el lote
            _log(f"fallo al resumir {paper.get('key')}: {e}")
    return added


def _resolve_model(args):
    if args.model:
        return args.model
    env_model = os.environ.get("ANTHROPIC_MODEL")
    if env_model:
        return env_model
    return DEFAULT_MODEL


def build_arg_parser():
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--model", default=None)
    p.add_argument("--dry-run", action="store_true")
    return p


def run(args, *, post_fn=None, sleep_fn=None, now_fn=None):
    model = _resolve_model(args)

    if args.dry_run:
        with open(args.input, "r", encoding="utf-8") as f:
            day = json.load(f)
        items = day.get("items", [])
        if items:
            print(_user_prompt(items[0]))
        else:
            print("(día sin items)")
        return 0

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        _log("falta ANTHROPIC_API_KEY")
        return 3

    with open(args.input, "r", encoding="utf-8") as f:
        day = json.load(f)
    items = day.get("items", [])
    added = summarize_items(
        items, args.limit, model, api_key, post_fn=post_fn, sleep_fn=sleep_fn, now_fn=now_fn
    )
    from common import atomic_write_json

    atomic_write_json(args.input, day)
    _log(f"{added} resúmenes IA añadidos de {min(args.limit, len(items))} intentados")
    if added == 0 and len(items) > 0:
        return 1
    return 0


def main(argv):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    return run(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
