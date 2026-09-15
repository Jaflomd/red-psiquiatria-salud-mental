"""Crea el .md de un resumen curado a partir de un identificador de Europe PMC.

Ver 3.A A6 del plan de implementación y las enmiendas 2, 4, 16, 17, 26, y el
contrato "tipología de resúmenes v2" (--type, plantillas empírico/conceptual,
OA v2 con OpenAlex).
"""

from __future__ import annotations

import argparse
import datetime
import os
import re
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import common
import epmc_client

# Todas las secciones del tipo, opcionales incluidas, en [[PENDIENTE]]. Los
# marcadores narrativos (los que --summarize puede rellenar) quedan como una
# única línea "[[PENDIENTE]]" bajo su encabezado para poder sustituirlos con
# un simple str.replace (_apply_ai_sections); el resto lleva "- [[PENDIENTE]]"
# como pista visual de que se espera una lista (nunca los toca la IA).
BODY_TEMPLATE_EMPIRICO = """## En una frase
[[PENDIENTE]]

## Ficha rápida
- [[PENDIENTE]]

## Pregunta
[[PENDIENTE]]

## Métodos
[[PENDIENTE]]

## Hallazgos clave
[[PENDIENTE]]

## Limitaciones
[[PENDIENTE]]

## El principio
- [[PENDIENTE]]

## Por qué importa para la clínica
[[PENDIENTE]]

## Glosario
- [[PENDIENTE]]

## Lecturas recomendadas
- [[PENDIENTE]]

## Nota del curador
[[PENDIENTE]]

## Nota completa

### Información del estudio
- [[PENDIENTE]]

### Introducción en tres frases
- [[PENDIENTE]]

### Pregunta de investigación
- [[PENDIENTE]]

### Método
[[PENDIENTE]]

### Diseño
- [[PENDIENTE]]

### Unidad de análisis
[[PENDIENTE]]

### Muestra
[[PENDIENTE]]

### Muestreo
[[PENDIENTE]]

### Procedimientos
- [[PENDIENTE]]

### Variables dependientes
- [[PENDIENTE]]

### Variables independientes
- [[PENDIENTE]]

### Análisis de datos
- [[PENDIENTE]]

### Hallazgos principales
[[PENDIENTE]]

### Datos por hallazgo
- [[PENDIENTE]]

### Discusión
- [[PENDIENTE]]

### Limitaciones según los autores
- [[PENDIENTE]]

### Investigación futura
- [[PENDIENTE]]
"""

BODY_TEMPLATE_CONCEPTUAL = """## En una frase
[[PENDIENTE]]

## Ficha rápida
- [[PENDIENTE]]

## Pregunta
[[PENDIENTE]]

## El argumento
[[PENDIENTE]]

## Ideas clave
[[PENDIENTE]]

## Limitaciones
[[PENDIENTE]]

## El principio
- [[PENDIENTE]]

## Por qué importa para la clínica
[[PENDIENTE]]

## Glosario
- [[PENDIENTE]]

## Lecturas recomendadas
- [[PENDIENTE]]

## Nota del curador
[[PENDIENTE]]
"""

BODY_TEMPLATE_BY_TYPE = {"empirico": BODY_TEMPLATE_EMPIRICO, "conceptual": BODY_TEMPLATE_CONCEPTUAL}

# Secciones narrativas que --summarize puede rellenar con IA, por tipo. Nunca
# incluye ficha_rapida, principio, glosario, lecturas ni nota_completa: "La
# IA de add_paper nunca inventa lecturas ni redacta el principio".
NARRATIVE_IDS_BY_TYPE = {
    "empirico": ["en_una_frase", "pregunta", "metodos", "hallazgos", "limitaciones", "clinica"],
    "conceptual": ["en_una_frase", "pregunta", "argumento", "ideas", "limitaciones", "clinica"],
}


def _log(msg):
    print(f"[add_paper] {msg}", file=sys.stderr)


def _slugify(s, max_len=60):
    s = unicodedata.normalize("NFKD", s)
    s = s.encode("ascii", "ignore").decode("ascii")
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    if len(s) > max_len:
        s = s[:max_len].rstrip("-")
    return s


def _quote(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _fmt_value(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, list):
        return "[" + ", ".join(_quote(x) for x in v) + "]"
    if v is None:
        return ""
    return _quote(str(v))


_FRONTMATTER_KEY_ORDER = [
    "title",
    "date",
    "status",
    "example",
    "ai_draft",
    "adapted_with_ai",
    "author",
    "tags",
    "study_design",
    "summary_type",
    "sample_size",
    "paper_access_type",
    "paper_title",
    "paper_authors",
    "paper_journal",
    "paper_journal_abbrev",
    "paper_year",
    "paper_pub_date",
    "paper_source",
    "paper_epmc_id",
    "paper_pmid",
    "paper_pmcid",
    "paper_doi",
    "paper_license",
    "paper_pub_types",
    "paper_preprint",
    "paper_oa_verified",
    "paper_oa_source",
    "paper_oa_checked",
    "updated",
]


def _render_frontmatter(fm):
    lines = ["---"]
    for key in _FRONTMATTER_KEY_ORDER:
        if key not in fm or fm[key] is None:
            continue
        lines.append(f"{key}: {_fmt_value(fm[key])}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def _reject_not_oa(rec, identifier):
    urls = (rec.get("fullTextUrlList") or {}).get("fullTextUrl") or []
    url_lines = "\n".join(
        f"  - site={u.get('site')} availability={u.get('availability')}" for u in urls
    )
    _log(
        f"Rechazado: Europe PMC no lo marca como open access (isOpenAccess="
        f"{rec.get('isOpenAccess')}), y no se pudo confirmar por la ruta B (OpenAlex). 'Free' o "
        f"'gratis para leer' no es open access con licencia. Este sitio solo publica resúmenes de "
        f"artículos OA verificados.\n"
        f"título: {rec.get('title')}\n"
        f"source: {rec.get('source')}\n"
        f"license: {rec.get('license')}\n"
        f"fullTextUrlList:\n{url_lines}"
    )


def _has_free_fulltext(rec):
    urls = (rec.get("fullTextUrlList") or {}).get("fullTextUrl") or []
    return any(
        (u.get("availability") or "").strip().lower() in ("free", "open access")
        and bool(u.get("url"))
        for u in urls
    )


def _apply_ai_sections(template, ai_sections):
    """Sustituye, para cada sección narrativa que la IA devolvió, el
    '[[PENDIENTE]]' bajo su encabezado por el texto generado. Las secciones
    no devueltas (o no narrativas) quedan intactas."""
    body = template
    for section_id, text in ai_sections.items():
        heading = common.SECTION_HEADING_LABEL.get(section_id)
        if not heading:
            continue
        old = f"## {heading}\n[[PENDIENTE]]"
        new = f"## {heading}\n{text}"
        if old in body:
            body = body.replace(old, new, 1)
    return body


def _ai_draft_sections(rec, model, api_key, summary_type, post_fn=None, sleep_fn=None):
    """Genera un borrador de las secciones narrativas (según `summary_type`)
    vía IA. Nunca se ejecuta sin API key. Devuelve {section_id: texto} o None
    si falla o la respuesta no trae todas las secciones esperadas."""
    import summarize_ai

    title = common.strip_html(rec.get("title") or "")
    abstract = common.parse_abstract(rec.get("abstractText"))
    abstract_text = abstract["text"] if abstract else ""
    narrative_ids = NARRATIVE_IDS_BY_TYPE[summary_type]
    headings = [common.SECTION_HEADING_LABEL[i] for i in narrative_ids]
    prompt = (
        "Redacta un borrador en español latinoamericano de estas secciones, cada una empezando "
        "exactamente con '## <encabezado>' en su propia línea, en este orden: "
        + ", ".join(headings)
        + ". En las secciones de lista ('Hallazgos clave'/'Ideas clave' y 'Limitaciones') usa líneas "
        "'- item'; en 'Limitaciones' cada ítem debe empezar con una categoría y ': ' (Diseño, Muestra, "
        "Medición, Análisis, Generalización, Confusión, Conflicto de interés, Alcance u Otra). Usa solo "
        "la información del resumen recibido, sin inventar cifras ni conclusiones. No redactes 'El "
        "principio' ni 'Lecturas recomendadas': no los pidas ni los incluyas.\n\n"
        f"Título: {title}\n\nResumen original (inglés):\n{abstract_text}"
    )
    headers = {
        "content-type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": summarize_ai.ANTHROPIC_VERSION,
    }
    body = summarize_ai._build_body_for_prompt(prompt, model, "Eres asistente editorial de un psiquiatra investigador.")
    post_fn = post_fn or summarize_ai._default_post_fn
    status, raw, _headers = post_fn(summarize_ai.API_URL, headers, body, 60)
    if status != 200:
        return None
    import json as _json

    data = _json.loads(raw)
    if data.get("stop_reason") != "end_turn":
        return None
    text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")

    parts = re.split(r"^## (.+)$", text, flags=re.MULTILINE)
    sections = {}
    i = 1
    while i + 1 < len(parts):
        heading = parts[i].strip()
        body_text = parts[i + 1].strip()
        section_id = common.HEADING_TO_ID.get(heading)
        if section_id in narrative_ids:
            sections[section_id] = body_text
        i += 2
    if len(sections) < len(narrative_ids):
        return None
    return sections


def build_arg_parser():
    p = argparse.ArgumentParser()
    p.add_argument("identifier")
    p.add_argument("--slug", default=None)
    p.add_argument("--title", default=None)
    p.add_argument("--tags", default=None)
    p.add_argument("--design", default=None)
    p.add_argument(
        "--type", dest="type", default=None, choices=sorted(common.SUMMARY_TYPES),
        help="summary_type; por defecto se sugiere a partir de --design/study_design detectado",
    )
    p.add_argument("--sample-size", type=int, default=None)
    p.add_argument(
        "--free-to-read",
        action="store_true",
        help=(
            "permite crear una reseña curada de una versión publicada accesible gratis pero sin "
            "licencia CC verificada; nunca se usa para el feed diario"
        ),
    )
    p.add_argument("--date", default=None)
    p.add_argument("--out-dir", default="content/summaries")
    p.add_argument("--force", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--summarize", action="store_true")
    p.add_argument("--model", default=None)
    p.add_argument("--config", default="scripts/feed_config.json")
    return p


def run(args, *, fetch_fn=None, post_fn=None, today_fn=None, sleep_fn=None):
    today_fn = today_fn or common.lima_today

    api_key = None
    if args.summarize:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            _log("--summarize requiere ANTHROPIC_API_KEY")
            return 3

    try:
        rec = epmc_client.lookup(args.identifier, fetch_fn=fetch_fn)
    except epmc_client.EpmcError as e:
        _log(f"fallo de red/API: {e.msg}")
        return 1

    if rec is None:
        _log(f"No encontrado en Europe PMC: {args.identifier}")
        return 2

    license_raw = (rec.get("license") or "").strip().lower() or None
    paper_access_type = "open_access"
    paper_oa_source = "europepmc"
    route_a_ok = rec.get("isOpenAccess") == "Y" and common.license_allowed(license_raw)
    if not route_a_ok:
        if args.free_to_read:
            if license_raw and not common.license_allowed(license_raw):
                _log(
                    f"Rechazado: Europe PMC declara una licencia cerrada explícita para "
                    f"{args.identifier} (license={rec.get('license')!r})."
                )
                return 2
            if not _has_free_fulltext(rec):
                _log(
                    f"Rechazado: {args.identifier} no tiene un enlace de texto completo gratuito "
                    "verificable en Europe PMC."
                )
                return 2
            paper_access_type = "free_to_read"
            paper_oa_source = "publisher"
            license_raw = "not verified"
            _log(
                "Aceptado como reseña free_to_read: el texto completo es accesible gratuitamente, "
                "pero no se afirmará que es open access ni que tiene licencia de reutilización."
            )
        else:
            if license_raw and not common.license_allowed(license_raw):
                # Una licencia cerrada explícita en Europe PMC no se sobreescribe
                # con otra fuente. La ruta B solo completa metadatos ausentes o
                # confirma el OA cuando isOpenAccess todavía no está actualizado.
                _log(
                    f"Rechazado: Europe PMC declara una licencia no abierta para {args.identifier} "
                    f"(license={rec.get('license')!r})."
                )
                return 2
            doi_for_oa = rec.get("doi")
            if not doi_for_oa:
                _reject_not_oa(rec, args.identifier)
                return 2
            try:
                work = epmc_client.openalex_lookup(doi_for_oa, fetch_fn=fetch_fn, sleep_fn=sleep_fn)
            except epmc_client.EpmcError as e:
                _log(f"fallo de red/API consultando OpenAlex (ruta B de OA v2): {e.msg}")
                return 1
            if work is None:
                _reject_not_oa(rec, args.identifier)
                return 2
            ok, license_norm, reason = common.openalex_oa_verdict(work)
            if not ok or (license_raw and license_norm != license_raw):
                _log(
                    f"Rechazado: Europe PMC no marca isOpenAccess=Y para {args.identifier} y OpenAlex no "
                    f"confirma acceso abierto con licencia CC de la versión publicada "
                    f"({reason or 'licencia distinta a la declarada por Europe PMC'})."
                )
                return 2
            license_raw = license_norm
            paper_oa_source = "europepmc+openalex"
            _log(
                "Europe PMC no completa el gate OA, pero OpenAlex confirma acceso abierto y licencia CC "
                "de la versión publicada; se acepta con "
                "paper_oa_source: europepmc+openalex"
            )

    import json

    with open(args.config, "r", encoding="utf-8") as f:
        config = json.load(f)

    paper_title = common.strip_html(rec.get("title") or "")
    title = args.title or paper_title
    if not args.title and len(title) > 200:
        # build_summaries exige title <= 200 caracteres; paper_title (el
        # título original completo) no se toca, solo el título editable que
        # Javier va a reescribir de todos modos.
        title = title[:200].rsplit(" ", 1)[0].rstrip(" ,;:.-")
        _log(f"título original > 200 caracteres; se truncó 'title' a: {title!r} (usa --title para fijarlo)")
    is_preprint = rec.get("source") == "PPR"

    date = args.date or str(today_fn())
    if not common.validate_date(date):
        _log(f"--date inválida: {date}")
        return 2

    descriptive = args.slug or _slugify(args.title or paper_title)
    if not re.match(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", descriptive):
        _log(f"slug inválido: {descriptive}")
        return 2
    full_slug = f"{date}-{descriptive}"
    if not common.validate_slug(full_slug):
        _log(f"slug resultante inválido: {full_slug}")
        return 2

    out_path = os.path.join(args.out_dir, f"{full_slug}.md")
    if os.path.exists(out_path) and not args.force:
        _log(f"el archivo ya existe: {out_path} (usa --force para sobrescribir)")
        return 4

    abstract = common.parse_abstract(rec.get("abstractText"))
    abstract_text = abstract["text"] if abstract else ""
    pub_types = list((rec.get("pubTypeList") or {}).get("pubType") or [])

    if args.tags:
        tags = [t.strip() for t in args.tags.split(",") if t.strip()]
        unknown = [t for t in tags if t not in common.TAGS]
        if unknown:
            _log(f"--tags contiene id(s) desconocido(s): {', '.join(unknown)}")
            return 2
        if not (1 <= len(tags) <= 6):
            _log(f"--tags debe tener entre 1 y 6 elementos (recibidos: {len(tags)})")
            return 2
    else:
        mesh_list = (rec.get("meshHeadingList") or {}).get("meshHeading") or []
        mesh_major = [m.get("descriptorName") for m in mesh_list if m.get("majorTopic_YN") == "Y"]
        keywords = list((rec.get("keywordList") or {}).get("keyword") or [])
        tag_text = "\n".join([paper_title, abstract_text, " ".join(keywords + (mesh_major or []))])
        tags = common.detect_tags(tag_text, config)
        if not tags:
            _log("sin coincidencias de etiquetas automáticas; se usa 'public_mental_health'")
            tags = ["public_mental_health"]
        elif len(tags) > 6:
            # build_summaries exige 1-6 tags; detect_tags devuelve en orden
            # canónico, así que recortar conserva las más prioritarias.
            _log(f"detect_tags encontró {len(tags)} etiquetas; se recorta a las primeras 6")
            tags = tags[:6]

    if args.design:
        if args.design not in common.DESIGNS:
            _log(f"--design desconocido: {args.design}")
            return 2
        design_id = args.design
    else:
        detected = common.detect_design(paper_title, abstract_text, pub_types)
        if detected:
            design_id = detected["id"]
        else:
            _log("sin diseño detectado automáticamente; se usa 'cross_sectional'")
            design_id = "cross_sectional"

    suggested_type = common.SUMMARY_TYPE_BY_DESIGN.get(design_id, "empirico")
    _log(
        f"summary_type sugerido: {suggested_type} (por study_design={design_id}); "
        "cámbialo con --type o en el frontmatter"
    )
    summary_type = args.type or suggested_type

    if args.sample_size is not None and args.sample_size <= 0:
        _log(f"--sample-size debe ser > 0 (recibido: {args.sample_size})")
        return 2

    journal_info = rec.get("journalInfo") or {}
    journal = (journal_info.get("journal") or {}).get("title")
    journal_abbrev = (journal_info.get("journal") or {}).get("isoabbreviation")
    if not journal:
        # Los preprints (source PPR) no traen journalInfo; paper_journal es
        # obligatorio en build_summaries. bookOrReportDetails.publisher trae
        # el servidor de preprints (medRxiv, bioRxiv...) cuando existe.
        publisher = (rec.get("bookOrReportDetails") or {}).get("publisher")
        journal = publisher or f"Preprint ({rec.get('source') or '?'})"
    pub_year = None
    if rec.get("pubYear"):
        try:
            pub_year = int(rec["pubYear"])
        except (TypeError, ValueError):
            pub_year = None

    fm = {
        "title": title,
        "date": date,
        "status": "draft",
        "example": False,
        "ai_draft": bool(args.summarize),
        "adapted_with_ai": False,
        "author": "Red de Investigación",
        "tags": tags,
        "study_design": design_id,
        "summary_type": summary_type,
        "sample_size": args.sample_size,
        "paper_access_type": paper_access_type,
        "paper_title": paper_title,
        "paper_authors": rec.get("authorString"),
        "paper_journal": journal,
        "paper_journal_abbrev": journal_abbrev,
        "paper_year": pub_year,
        "paper_pub_date": rec.get("firstPublicationDate"),
        "paper_source": rec.get("source"),
        "paper_epmc_id": str(rec.get("id") or rec.get("pmid") or ""),
        "paper_pmid": rec.get("pmid"),
        "paper_pmcid": rec.get("pmcid"),
        "paper_doi": rec.get("doi"),
        "paper_license": license_raw,
        "paper_pub_types": pub_types,
        "paper_preprint": is_preprint,
        "paper_oa_verified": paper_access_type == "open_access",
        "paper_oa_source": paper_oa_source,
        "paper_oa_checked": str(today_fn()),
        "updated": None,
    }

    body = BODY_TEMPLATE_BY_TYPE[summary_type]
    if args.summarize:
        model = args.model or os.environ.get("ANTHROPIC_MODEL") or "claude-haiku-4-5"
        try:
            ai_sections = _ai_draft_sections(rec, model, api_key, summary_type, post_fn=post_fn, sleep_fn=sleep_fn)
        except Exception as e:  # noqa: BLE001 - cualquier fallo cae a la plantilla, nunca aborta
            _log(f"fallo generando el borrador IA ({e}); se usa la plantilla con [[PENDIENTE]]")
            ai_sections = None
        if ai_sections:
            body = _apply_ai_sections(body, ai_sections)
        else:
            _log("no se pudo generar el borrador IA; se usa la plantilla con [[PENDIENTE]]")

    content = _render_frontmatter(fm) + "\n" + body

    # Autovalidación: el .md generado debe poder parsearse con las mismas
    # reglas que build_summaries usará después. Antes, un md inválido (más de
    # 6 tags, título > 200, journal faltante en un preprint...) solo se
    # descubría al correr build_summaries, y ahí bloqueaba TODO el batch
    # (hallazgo de verificación).
    try:
        fm_check, body_check = common.parse_frontmatter(content, out_path)
        common.parse_body(body_check, fm_check["status"], out_path, fm_check["summary_type"])
    except common.SummaryFormatError as e:
        _log(f"el .md generado no pasa su propia validación: {e}")
        return 2

    if args.dry_run:
        print(content)
        return 0

    os.makedirs(args.out_dir, exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print(f"Creado {out_path}")
    return 0


def main(argv):
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    return run(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
