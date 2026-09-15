"""Utilidades puras (sin red) compartidas por los scripts del pipeline.

Todas las funciones son deterministas dado su input; no hacen I/O de red.
Ver la spec del proyecto (README / plan de implementación) para el contrato
completo de cada función.
"""

from __future__ import annotations

import datetime
import html
import json
import os
import re
import sys
import unicodedata
import urllib.parse

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover - stdlib siempre trae zoneinfo en 3.12
    ZoneInfo = None


# ---------------------------------------------------------------------------
# Vocabularios controlados (3.0.2). Fuente única de verdad para todo el sitio;
# se serializan en data/daily/index.json y data/summaries.json como "labels".
# ---------------------------------------------------------------------------

TAGS = {
    "psychosis": "Psicosis y esquizofrenia",
    "depression": "Depresión",
    "anxiety": "Ansiedad",
    "symptom_networks": "Redes de síntomas",
    "suicide": "Suicidio y autolesión",
    "adhd": "TDAH",
    "bipolar": "Trastorno bipolar",
    "bpd": "Trastorno límite de la personalidad",
    "alcohol": "Alcohol",
    "substances": "Otras sustancias",
    "ptsd": "Trauma y TEPT",
    "ocd": "TOC",
    "eating": "Conducta alimentaria",
    "child_adolescent": "Niñez y adolescencia",
    "older_adults": "Adultos mayores",
    "public_mental_health": "Salud mental pública",
    "peru_latam": "Perú y América Latina",
    "medical_education": "Educación médica",
    "digital": "Salud digital",
    "psychopharmacology": "Psicofarmacología",
    "psychotherapy": "Psicoterapia",
    "neuroscience": "Neurociencia y biomarcadores",
    "epidemiology": "Epidemiología",
}
TAG_ORDER = list(TAGS.keys())

DESIGNS = {
    "protocol": "Protocolo de estudio",
    "systematic_review_meta": "Revisión sistemática y metaanálisis",
    "meta_analysis": "Metaanálisis",
    "systematic_review": "Revisión sistemática",
    "scoping_review": "Revisión de alcance",
    "rct": "Ensayo clínico aleatorizado",
    "nonrandomized_trial": "Ensayo clínico no aleatorizado",
    "cohort": "Cohorte / longitudinal",
    "case_control": "Casos y controles",
    "mixed_methods": "Métodos mixtos",
    "qualitative": "Cualitativo",
    "cross_sectional": "Transversal",
    "case_report": "Reporte / serie de casos",
    "pilot": "Piloto / factibilidad",
    "modelling": "Modelado / economía de la salud",
    "guideline": "Guía / consenso",
    "narrative_review": "Revisión narrativa",
}
DESIGN_ORDER = list(DESIGNS.keys())

LICENSE_LABELS = {
    "cc by": "CC BY",
    "cc by-nc": "CC BY-NC",
    "cc by-nc-nd": "CC BY-NC-ND",
    "cc by-nc-sa": "CC BY-NC-SA",
    "cc by-sa": "CC BY-SA",
    "cc by-nd": "CC BY-ND",
    "cc0": "CC0",
}

# Enmienda 2: restricción dura de licencia. Solo CC0 o cualquier variante de
# CC BY (incluye -nc/-nd/-sa) cuentan como "licencia abierta declarada".
LICENSE_ALLOWED_RE = re.compile(r"^cc(0| by)")

# ---------------------------------------------------------------------------
# Tipología de resúmenes v2 (empírico / conceptual). Ver contrato §C1-C3.
# ---------------------------------------------------------------------------

SUMMARY_TYPES = {"empirico": "Empírico", "conceptual": "Conceptual"}

# Sugerencia (no validación) para add_paper: study_design -> summary_type por
# defecto. Todo diseño no listado aquí sugiere "empirico".
SUMMARY_TYPE_BY_DESIGN = {
    "narrative_review": "conceptual",
    "guideline": "conceptual",
}

# Diseños observacionales: un principio empírico basado en uno de estos no
# puede usar vocabulario causal (contrato C1.5).
OBSERVATIONAL_DESIGNS = {
    "cohort", "case_control", "cross_sectional", "case_report", "qualitative",
    "mixed_methods", "modelling", "scoping_review", "narrative_review", "guideline",
}

# Tope de Fuerza del principio por study_design (solo empírico). Orden:
# muy baja < baja < moderada < alta.
STRENGTH_ORDER = {"muy baja": 0, "baja": 1, "moderada": 2, "alta": 3}
STRENGTH_CAP = {
    "rct": "alta",
    "systematic_review_meta": "alta",
    "meta_analysis": "alta",
    "systematic_review": "moderada",
    "nonrandomized_trial": "moderada",
    "cohort": "baja",
    "case_control": "baja",
    "cross_sectional": "baja",
    "pilot": "baja",
    "qualitative": "baja",
    "mixed_methods": "baja",
    "modelling": "baja",
    "scoping_review": "baja",
    "case_report": "muy baja",
    "protocol": "muy baja",
}

LIMITATION_CATEGORIES = {
    "Diseño", "Muestra", "Medición", "Análisis", "Generalización",
    "Confusión", "Conflicto de interés", "Alcance", "Otra",
}
FULL_NOTE_LIMITATION_CATEGORIES = {"Selección", "Medición", "Confusión", "Otras"}

PRINCIPLE_KEYS = ["Enunciado", "Fundamento", "Evidencia", "Fuerza", "Transferencia", "Límite", "Procedencia"]

QUICK_FACT_KEYS = {
    "empirico": [
        "Población", "Intervención o exposición", "Comparador",
        "Desenlace primario", "Efecto principal", "Certeza",
    ],
    "conceptual": [
        "Tipo", "Objeto", "Tesis", "Mecanismo central", "Para quién", "Implicación práctica",
    ],
}

# Secciones de nivel '## ', por tipo, en el orden relativo obligatorio
# (contrato C1.2). "nota_completa" solo existe para "empirico".
SECTION_HEADINGS_BY_TYPE = {
    "empirico": [
        ("en_una_frase", "En una frase"),
        ("ficha_rapida", "Ficha rápida"),
        ("pregunta", "Pregunta"),
        ("metodos", "Métodos"),
        ("hallazgos", "Hallazgos clave"),
        ("limitaciones", "Limitaciones"),
        ("principio", "El principio"),
        ("clinica", "Por qué importa para la clínica"),
        ("glosario", "Glosario"),
        ("lecturas", "Lecturas recomendadas"),
        ("nota", "Nota del curador"),
        ("nota_completa", "Nota completa"),
    ],
    "conceptual": [
        ("en_una_frase", "En una frase"),
        ("ficha_rapida", "Ficha rápida"),
        ("pregunta", "Pregunta"),
        ("argumento", "El argumento"),
        ("ideas", "Ideas clave"),
        ("limitaciones", "Limitaciones"),
        ("principio", "El principio"),
        ("clinica", "Por qué importa para la clínica"),
        ("glosario", "Glosario"),
        ("lecturas", "Lecturas recomendadas"),
        ("nota", "Nota del curador"),
    ],
}
SECTION_ORDER_BY_TYPE = {t: [i for i, _h in v] for t, v in SECTION_HEADINGS_BY_TYPE.items()}
SECTION_HEADING_LABEL = {i: h for v in SECTION_HEADINGS_BY_TYPE.values() for i, h in v}

# Encabezados obligatorios independientemente de status/study_design. El
# principio (obligatorio solo si published, salvo protocol) y la nota
# completa (obligatoria solo si published, solo empírico) se validan aparte
# en build_summaries._build_item, que sí conoce study_design.
REQUIRED_ALWAYS_BY_TYPE = {
    "empirico": {"en_una_frase", "pregunta", "metodos", "hallazgos", "limitaciones", "clinica"},
    "conceptual": {"en_una_frase", "pregunta", "argumento", "ideas", "limitaciones", "clinica"},
}
OPTIONAL_SECTION_IDS = {"ficha_rapida", "glosario", "lecturas", "nota"}

# Mapa global heading-exacto -> id. Los textos son únicos entre tipos (no hay
# colisión), así que un solo mapa sirve para detectar encabezados
# desconocidos antes de saber si están permitidos para el tipo del archivo.
HEADING_TO_ID = {}
for _t, _pairs in SECTION_HEADINGS_BY_TYPE.items():
    for _i, _h in _pairs:
        HEADING_TO_ID[_h] = _i
del _t, _pairs, _i, _h

# Las 17 subsecciones '### ' de "## Nota completa" (solo empírico), en su
# orden obligatorio (contrato C2 / Anexo).
FULL_NOTE_HEADINGS = [
    ("nc_info", "Información del estudio"),
    ("nc_intro", "Introducción en tres frases"),
    ("nc_pregunta", "Pregunta de investigación"),
    ("nc_metodo", "Método"),
    ("nc_diseno", "Diseño"),
    ("nc_unidad", "Unidad de análisis"),
    ("nc_muestra", "Muestra"),
    ("nc_muestreo", "Muestreo"),
    ("nc_procedimientos", "Procedimientos"),
    ("nc_dependientes", "Variables dependientes"),
    ("nc_independientes", "Variables independientes"),
    ("nc_analisis", "Análisis de datos"),
    ("nc_hallazgos", "Hallazgos principales"),
    ("nc_datos", "Datos por hallazgo"),
    ("nc_discusion", "Discusión"),
    ("nc_limitaciones", "Limitaciones según los autores"),
    ("nc_futuro", "Investigación futura"),
]
FULL_NOTE_ORDER = [i for i, _h in FULL_NOTE_HEADINGS]
FULL_NOTE_HEADING_TO_ID = {h: i for i, h in FULL_NOTE_HEADINGS}
FULL_NOTE_LABEL = {i: h for i, h in FULL_NOTE_HEADINGS}

# Guiones Unicode (en abstracts/títulos reales: U+2010 NO-BREAK aparece en 35 de
# 481 ítems observados) rompen las regex de detect_tags/detect_design escritas
# con "-" ASCII. Se normalizan antes de cualquier matching (hallazgo de verificación).
_UNICODE_HYPHEN_RE = re.compile("[‐‑‒–—−]")


def _normalize_hyphens(s):
    return _UNICODE_HYPHEN_RE.sub("-", s or "")


DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SLUG_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*$")
FILE_SLUG_PART_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def validate_date(s):
    """True si s es 'YYYY-MM-DD' y representa una fecha calendario válida."""
    if not isinstance(s, str) or not DATE_RE.match(s):
        return False
    try:
        datetime.date.fromisoformat(s)
    except ValueError:
        return False
    return True


def validate_slug(s):
    """True si s cumple el formato de slug de archivo (con fecha, 3.0.6/16)."""
    if not isinstance(s, str) or len(s) > 80:
        return False
    return bool(SLUG_RE.match(s))


def license_allowed(raw):
    """True si raw es una licencia CC abierta reconocida (enmienda 2)."""
    if not raw or not isinstance(raw, str):
        return False
    return bool(LICENSE_ALLOWED_RE.match(raw.strip().lower()))


def license_label(raw):
    if raw is None:
        return "Licencia no declarada"
    raw_l = raw.strip().lower()
    if raw_l in LICENSE_LABELS:
        return LICENSE_LABELS[raw_l]
    return raw.upper()


def lima_today():
    """Fecha de hoy en America/Lima (con fallback UTC-5 fijo)."""
    if ZoneInfo is not None:
        try:
            return datetime.datetime.now(ZoneInfo("America/Lima")).date()
        except Exception:
            pass
    tz = datetime.timezone(datetime.timedelta(hours=-5))
    return datetime.datetime.now(tz).date()


def atomic_write_json(path, obj):
    """Escritura atómica: escribe a .tmp y hace os.replace."""
    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp_path, path)


def write_json_preserving_timestamp(path, obj, field="generated_at"):
    """Como atomic_write_json, pero si el archivo ya existe y `obj` es
    idéntico salvo por `field`, conserva el valor previo de `field` en vez de
    escribir uno nuevo. Evita que una corrida sin cambios reales (p. ej.
    build_summaries.py sobre .md sin editar) produzca un diff de un solo
    timestamp y, en CI, un commit de ruido cada día (hallazgo de
    verificación, enmienda 28.6)."""
    old = None
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                old = json.load(f)
        except (OSError, json.JSONDecodeError):
            old = None
    if isinstance(old, dict) and field in old:
        old_copy = dict(old)
        new_copy = dict(obj)
        old_copy.pop(field, None)
        new_copy.pop(field, None)
        if old_copy == new_copy:
            obj = dict(obj)
            obj[field] = old[field]
    atomic_write_json(path, obj)


# ---------------------------------------------------------------------------
# strip_html / parse_abstract  (3.A A1, enmienda 14)
# ---------------------------------------------------------------------------

_WHITELIST_TAG_RE = re.compile(
    r"</?(?:i|b|em|strong|u|sup|sub|p|br|span|sc|h[1-6]|italic|bold)\b[^>]*>",
    re.IGNORECASE,
)
_SUP_RE = re.compile(r"<sup>(.*?)</sup>", re.IGNORECASE | re.DOTALL)
_SUB_RE = re.compile(r"<sub>(.*?)</sub>", re.IGNORECASE | re.DOTALL)
_WS_RE = re.compile(r"[ \t\f\v]+")
_NEWLINES_RE = re.compile(r"\n{3,}")


def strip_html(s):
    """Unescape + normaliza sup/sub + quita solo etiquetas de lista blanca."""
    if s is None:
        return ""
    s = html.unescape(s)
    s = _SUP_RE.sub(lambda m: "^" + m.group(1), s)
    s = _SUB_RE.sub(lambda m: "_" + m.group(1), s)
    s = _WHITELIST_TAG_RE.sub(" ", s)
    s = _WS_RE.sub(" ", s)
    s = re.sub(r" *\n *", "\n", s)
    s = _NEWLINES_RE.sub("\n\n", s)
    s = re.sub(r" +([,.;:!?])", r"\1", s)
    return s.strip()


_H4_SPLIT_RE = re.compile(r"<h4>(.*?)</h4>", re.IGNORECASE | re.DOTALL)


def parse_abstract(raw):
    """Construye el objeto abstract del contrato 3.0.3, o None si no hay texto."""
    if not raw or not raw.strip():
        return None
    if re.search(r"<h4>", raw, re.IGNORECASE):
        # Dividir por <h4> ANTES de aplicar strip_html a cada trozo (14).
        parts = _H4_SPLIT_RE.split(raw)
        # parts = [preamble, heading1, text1, heading2, text2, ...]
        sections = []
        preamble = parts[0].strip() if parts else ""
        if preamble:
            sections.append({"heading": None, "text": strip_html(preamble)})
        i = 1
        while i + 1 < len(parts):
            heading = strip_html(parts[i]).strip()
            text = strip_html(parts[i + 1]).strip()
            if text:
                sections.append({"heading": heading, "text": text})
            i += 2
        structured = True
    else:
        text = strip_html(raw)
        sections = [{"heading": None, "text": text}]
        structured = False
    full_text = "\n\n".join(sec["text"] for sec in sections if sec["text"])
    return {
        "lang": None,
        "structured": structured,
        "truncated": False,
        "sections": sections,
        "text": full_text,
    }


_LANG_MAP = {"eng": "en", "spa": "es", "por": "pt"}


def abstract_language(language):
    return _LANG_MAP.get((language or "").lower())


# ---------------------------------------------------------------------------
# derive_summary  (3.0.7, enmienda 15)
# ---------------------------------------------------------------------------

_CONCLUSION_PATTERNS = [
    r"^conclusions?$",
    r"^interpretation$",
    r"^conclusions? and (relevance|implications)$",
    r"^discussion and conclusions?$",
    r"^conclusiones?$",
    r"^clinical implications$",
    r"^implications$",
    r"^summary$",
    r"^discussion$",
]
_EXCLUDE_HEADING_RE = re.compile(
    r"(?i)registration|trial number|supplementary|funding|ethics and dissemination|keywords|pre-registration"
)
_EXCLUDE_SENTENCE_RE = re.compile(
    r"©|copyright|clinicaltrials\.gov|NCT\d{8}|PROSPERO|CRD\d+", re.IGNORECASE
)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def _truncate_at_sentence(text, limit=700):
    if len(text) <= limit:
        return text, False
    cut = text[:limit]
    matches = list(re.finditer(r"[.!?]", cut))
    if matches:
        end = matches[-1].end()
        return cut[:end].strip(), True
    return cut.strip(), True


def derive_summary(abstract, language=None):
    if not abstract or not abstract.get("text"):
        return None
    lang = abstract_language(language)
    sections = abstract.get("sections") or []
    # 1) Buscar heading de conclusión, en orden de prioridad de la lista (no
    #    del abstract).
    best = None
    best_priority = None
    for sec in sections:
        heading = (sec.get("heading") or "").strip().lower()
        if not heading:
            continue
        for idx, pat in enumerate(_CONCLUSION_PATTERNS):
            if re.match(pat, heading, re.IGNORECASE):
                if best_priority is None or idx < best_priority:
                    best_priority = idx
                    best = sec
                break
    if best is not None:
        text, truncated = _truncate_at_sentence(best["text"])
        return {
            "origin": "authors",
            "lang": lang,
            "section": best.get("heading"),
            "text": text,
            "truncated": truncated,
        }
    # 2) Cola del abstract, excluyendo secciones administrativas y oraciones
    #    con metadatos de registro.
    usable_sections = [
        sec
        for sec in sections
        if not _EXCLUDE_HEADING_RE.search(sec.get("heading") or "")
    ]
    tail_text = "\n\n".join(s["text"] for s in usable_sections if s.get("text"))
    if not tail_text:
        tail_text = abstract.get("text") or ""
    sentences = [s for s in _SENTENCE_SPLIT_RE.split(tail_text) if s.strip()]
    sentences = [s for s in sentences if not _EXCLUDE_SENTENCE_RE.search(s)]
    if not sentences:
        return None
    tail = " ".join(sentences[-2:])
    text, truncated = _truncate_at_sentence(tail)
    return {
        "origin": "authors",
        "lang": lang,
        "section": "abstract_tail",
        "text": text,
        "truncated": truncated,
    }


# ---------------------------------------------------------------------------
# detect_design  (3.0.2, enmienda 11)
# ---------------------------------------------------------------------------

_PASS1_RULES = [
    ("protocol", ["clinical trial protocol"]),
    ("systematic_review_meta", ["meta analysis", "systematic review"]),  # AND
    ("meta_analysis", ["meta analysis"]),
    ("systematic_review", ["systematic review"]),
    ("scoping_review", ["scoping review"]),
    ("rct", ["randomized controlled trial"]),
    ("nonrandomized_trial", ["clinical trial", "pragmatic clinical trial"]),  # OR, excl rct
    ("case_report", ["case reports", "case report"]),  # OR
    ("guideline", ["practice guideline", "consensus statement"]),  # OR
    ("narrative_review", ["review", "review article"]),  # OR, excl systematic/meta
]

_PASS2_RULES = [
    ("protocol", None),  # especial: \bprotocol\b solo en título
    ("systematic_review_meta", r"systematic review.{0,60}meta-?analys"),
    ("meta_analysis", r"\bmeta-?analys"),
    ("systematic_review", r"\bsystematic (literature )?review\b"),
    ("scoping_review", r"\bscoping review\b"),
    ("rct", r"\brandomi[sz]ed\b.{0,40}\btrial\b|\brct\b"),
    ("nonrandomized_trial", r"\b(non-?randomi[sz]ed|single-arm|open-label)\b.{0,40}\b(trial|study)\b"),
    ("cohort", r"\b(cohort|longitudinal|prospective|follow-up) stud|\bpanel (study|design)\b|\bregister-based\b"),
    ("case_control", r"\bcase-?control\b"),
    ("mixed_methods", r"\bmixed[- ]methods?\b"),
    ("qualitative", r"\bqualitative stud|\bfocus groups?\b|\bin-depth interviews?\b|\bthematic analysis\b"),
    ("cross_sectional", r"\bcross-?sectional\b|\bsurvey\b"),
    ("case_report", r"\bcase (report|series)\b"),
    ("pilot", r"\b(pilot|feasibility) (study|trial|evaluation)\b"),
    ("modelling", r"\b(modell?ing|simulation|cost-effectiveness|economic evaluation)\b"),
    ("guideline", r"\b(guideline|consensus statement)\b"),
    ("narrative_review", r"\b(narrative|mini|literature) review\b"),
]


_TITLE_SPECIFIC_REVIEW_RE = re.compile(
    r"\bsystematic (literature )?review\b|\bmeta-?analys|\bscoping review\b|\bumbrella review\b|\bprotocol\b"
)

_COHORT_PATTERN = r"\b(cohort|longitudinal|prospective|follow-up) stud|\bpanel (study|design)\b|\bregister-based\b"
# Enmienda de verificación: "Longitudinal studies are needed", "previous ...
# prospective studies" (antecedentes / trabajo futuro) no describen el diseño
# del propio artículo y no deben activar 'cohort'.
_COHORT_EXCLUDE_CONTEXT_RE = re.compile(r"\b(needed|future|previous|prior|further)\b", re.IGNORECASE)


def _cohort_matches(full_l):
    for m in re.finditer(_COHORT_PATTERN, full_l, re.IGNORECASE):
        # Contexto a ambos lados: "Longitudinal studies are NEEDED to..."
        # pone la palabra excluyente DESPUÉS del término de diseño.
        context = full_l[max(0, m.start() - 40) : min(len(full_l), m.end() + 40)]
        if _COHORT_EXCLUDE_CONTEXT_RE.search(context):
            continue
        return True
    return False


def detect_design(title, abstract_text, pub_types):
    norm_types = [(p or "").lower().replace("-", " ").strip() for p in (pub_types or [])]

    def has(sig):
        return any(sig in t for t in norm_types)

    has_rct = has("randomized controlled trial")
    has_syst = has("systematic review")
    has_meta = has("meta analysis")

    for design_id, sigs in _PASS1_RULES:
        if design_id == "systematic_review_meta":
            if has_meta and has_syst:
                return {"id": design_id, "confidence": "pubtype"}
            continue
        if design_id == "nonrandomized_trial":
            if (has("clinical trial") or has("pragmatic clinical trial")) and not has_rct:
                return {"id": design_id, "confidence": "pubtype"}
            continue
        if design_id == "narrative_review":
            # El pubtype genérico "Review" también lo llevan revisiones
            # sistemáticas, metaanálisis y protocolos; si el título nombra un
            # diseño más específico, se deja que el paso 2 lo detecte.
            title_names_specific = _TITLE_SPECIFIC_REVIEW_RE.search(
                _normalize_hyphens(title or "").lower()
            )
            if (has("review") or has("review article")) and not (has_syst or has_meta) and not title_names_specific:
                return {"id": design_id, "confidence": "pubtype"}
            continue
        if any(has(sig) for sig in sigs):
            return {"id": design_id, "confidence": "pubtype"}

    # Pass 2: heurística por regex. Primero solo sobre el título (un diseño
    # nombrado explícitamente en el título es más confiable que una mención
    # de contexto en el abstract, p. ej. "A Cross-Sectional Analysis of..."
    # con "prospective studies" solo en los antecedentes) (hallazgo de
    # verificación); si nada casa en el título, se busca en título+abstract.
    title_l = _normalize_hyphens((title or "")).lower()
    full_l = _normalize_hyphens((title or "") + " " + (abstract_text or "")).lower()
    if re.search(r"\bprotocol\b", title_l):
        return {"id": "protocol", "confidence": "heuristic"}
    for design_id, pattern in _PASS2_RULES:
        if design_id == "protocol" or pattern is None:
            continue
        if design_id == "cohort":
            if _cohort_matches(title_l):
                return {"id": design_id, "confidence": "heuristic"}
            continue
        if re.search(pattern, title_l, re.IGNORECASE):
            return {"id": design_id, "confidence": "heuristic"}
    for design_id, pattern in _PASS2_RULES:
        if design_id == "protocol" or pattern is None:
            continue
        if design_id == "cohort":
            if _cohort_matches(full_l):
                return {"id": design_id, "confidence": "heuristic"}
            continue
        if re.search(pattern, full_l, re.IGNORECASE):
            return {"id": design_id, "confidence": "heuristic"}
    return None


# ---------------------------------------------------------------------------
# detect_tags  (3.0.2, enmienda 12)
# ---------------------------------------------------------------------------

def detect_tags(text, config):
    text = _normalize_hyphens(text or "")
    patterns = config.get("tag_patterns", {})
    found = []
    for tag_id in TAG_ORDER:
        pat = patterns.get(tag_id)
        if not pat:
            continue
        if re.search(pat, text, re.IGNORECASE):
            found.append(tag_id)
    return found


# ---------------------------------------------------------------------------
# detect_sample_size  (3.A A1, enmienda 13)
# ---------------------------------------------------------------------------

_NUM = r"(?<![\d.,])(\d{1,3}(?:[,   ]\d{3})+|\d+)(?![\d.,]\d)"
_SAMPLE_SUBJECTS = (
    r"participants|patients|adults|adolescents|children|individuals|respondents|"
    r"women|men|students|subjects|veterans|inpatients|outpatients"
)
_SAMPLE_SUBJECTS_SHORT = r"participants|patients|adults|adolescents|children|individuals|respondents"
_SAMPLE_VERBS = (
    r"enrolled|randomi[sz]ed|included|recruited|analy[sz]ed|assessed|surveyed|interviewed"
)

_SAMPLE_PATTERNS = [
    re.compile(
        _NUM + r"\s+(?:" + _SAMPLE_SUBJECTS + r")\s+(?:were\s+)?(?:" + _SAMPLE_VERBS + r")",
        re.IGNORECASE,
    ),
    re.compile(r"\bn\s*=\s*" + _NUM, re.IGNORECASE),
    re.compile(r"\bsample of\s+" + _NUM, re.IGNORECASE),
    re.compile(_NUM + r"\s+(?:" + _SAMPLE_SUBJECTS_SHORT + r")", re.IGNORECASE),
]

_SAMPLE_SECTION_INCLUDE_RE = re.compile(r"(?i)method|participant|design|setting|sample|population")
_SAMPLE_SECTION_EXCLUDE_RE = re.compile(
    r"(?i)registration|trial number|supplementary|funding|ethics and dissemination|keywords|pre-registration"
)
_SAMPLE_EXCLUDE_SENTENCE_RE = re.compile(r"screened|excluded|declined|eligible", re.IGNORECASE)


def _clean_num(raw):
    cleaned = re.sub(r"[,   ]", "", raw)
    try:
        return int(cleaned)
    except ValueError:
        return None


def _search_sample_patterns(text):
    for pat in _SAMPLE_PATTERNS:
        m = pat.search(text)
        if m:
            val = _clean_num(m.group(1))
            if val is not None and 5 <= val <= 50_000_000:
                return val
    return None


def detect_sample_size(abstract):
    if not abstract:
        return None
    if abstract.get("structured"):
        sections = abstract.get("sections") or []
        candidate_text = "\n".join(
            sec["text"]
            for sec in sections
            if sec.get("heading")
            and _SAMPLE_SECTION_INCLUDE_RE.search(sec["heading"])
            and not _SAMPLE_SECTION_EXCLUDE_RE.search(sec["heading"])
        )
        if not candidate_text:
            return None
        val = _search_sample_patterns(candidate_text)
    else:
        text = abstract.get("text") or ""
        sentences = _SENTENCE_SPLIT_RE.split(text)
        sentences = [s for s in sentences if not _SAMPLE_EXCLUDE_SENTENCE_RE.search(s)]
        val = _search_sample_patterns(" ".join(sentences))
    if val is None:
        return None
    return {"value": val, "confidence": "heuristic"}


# ---------------------------------------------------------------------------
# normalize_record  (3.0.3)
# ---------------------------------------------------------------------------

def _first_fulltext_url(fulltext_urls, doc_style):
    preferred_sites = ("Europe_PMC", "PubMedCentral")
    ok_avail = ("Open access", "Free")
    by_site = {}
    for u in fulltext_urls or []:
        if u.get("site") == "DOI":
            continue
        if u.get("documentStyle") != doc_style:
            continue
        if u.get("availability") not in ok_avail:
            continue
        by_site.setdefault(u.get("site"), u.get("url"))
    for site in preferred_sites:
        if site in by_site:
            return by_site[site]
    return None


def normalize_record(rec, config, checked_at):
    epmc_id = str(rec.get("id") or rec.get("pmid") or "")
    source = rec.get("source") or ""
    key = f"{source}:{epmc_id}"
    pmid = rec.get("pmid")
    pmcid = rec.get("pmcid")
    doi = rec.get("doi")

    title_raw = rec.get("title") or ""
    title = strip_html(title_raw)

    journal_info = rec.get("journalInfo") or {}
    journal = (journal_info.get("journal") or {}).get("title")
    if journal:
        # Metadato espurio observado en vivo (PMC:PMC13571855): sufijo de
        # gestión editorial que no es parte del nombre de la revista.
        journal = re.sub(r"\s*:\s*Duplicate,\s*marked for deletion\s*$", "", journal, flags=re.IGNORECASE).strip()
    journal_abbrev = (journal_info.get("journal") or {}).get("isoabbreviation")

    pub_year = None
    if rec.get("pubYear"):
        try:
            pub_year = int(rec["pubYear"])
        except (TypeError, ValueError):
            pub_year = None

    pub_types = list((rec.get("pubTypeList") or {}).get("pubType") or [])
    language = rec.get("language")
    is_preprint = source == "PPR"

    license_raw = rec.get("license")
    license_norm = license_raw.strip().lower() if license_raw else None
    open_access = {
        "status": "verified",
        "license": license_norm,
        "license_label": license_label(license_norm),
        "source": "europepmc",
        "checked_at": checked_at,
    }

    fulltext_urls = (rec.get("fullTextUrlList") or {}).get("fullTextUrl") or []
    links = {
        "doi": (
            "https://doi.org/" + urllib.parse.quote(doi, safe="/:;()._-") if doi else None
        ),
        "europepmc": (
            f"https://europepmc.org/article/{source}/{epmc_id}" if source and epmc_id else None
        ),
        "fulltext_html": _first_fulltext_url(fulltext_urls, "html"),
        "pdf": _first_fulltext_url(fulltext_urls, "pdf"),
    }

    abstract = parse_abstract(rec.get("abstractText"))
    if abstract is not None:
        abstract["lang"] = abstract_language(language)
    summary = derive_summary(abstract, language)

    abstract_text = abstract["text"] if abstract else ""
    study_design = detect_design(title, abstract_text, pub_types)

    if study_design and study_design["id"] == "protocol":
        sample_size = None
    else:
        sample_size = detect_sample_size(abstract)

    mesh_list = (rec.get("meshHeadingList") or {}).get("meshHeading") or []
    mesh_major = [
        m.get("descriptorName")
        for m in mesh_list
        if m.get("majorTopic_YN") == "Y" and m.get("descriptorName")
    ]
    keywords = list((rec.get("keywordList") or {}).get("keyword") or [])

    tag_text = "\n".join([title, abstract_text, " ".join(keywords + mesh_major)])
    tags = detect_tags(tag_text, config)

    return {
        "key": key,
        "epmc_id": epmc_id,
        "source": source,
        "pmid": pmid,
        "pmcid": pmcid,
        "doi": doi,
        "title": title,
        "authors": rec.get("authorString"),
        "journal": journal,
        "journal_abbrev": journal_abbrev,
        "pub_year": pub_year,
        "first_publication_date": rec.get("firstPublicationDate"),
        "first_index_date": rec.get("firstIndexDate"),
        "pub_types": pub_types,
        "language": language,
        "is_preprint": is_preprint,
        "open_access": open_access,
        "links": links,
        "abstract": abstract,
        "summary": summary,
        "ai_summary": None,
        "study_design": study_design,
        "sample_size": sample_size,
        "tags": tags,
        "mesh_major": mesh_major,
        "keywords": keywords,
        "relevance": None,
    }


# ---------------------------------------------------------------------------
# relevance  (3.A A1, enmienda 9: dos pasadas, sin circularidad)
# ---------------------------------------------------------------------------

_STRONG_DESIGNS = {"rct", "systematic_review_meta", "meta_analysis", "systematic_review", "cohort"}

# Etiquetas que realmente nombran un cuadro clínico psiquiátrico. Las demás
# ("epidemiology", "neuroscience", "public_mental_health", "digital", …) casan
# con vocabulario genérico ("prevalence", "biomarker", "app") que aparece en
# papers claramente fuera de tema (hallazgo de verificación: ~8% del feed).
_CORE_CLINICAL_TAGS = {
    "psychosis", "depression", "anxiety", "suicide", "adhd", "bipolar", "bpd",
    "alcohol", "substances", "ptsd", "ocd", "eating", "symptom_networks",
}
_GENERIC_TAGS_NEED_CLINICAL = {"epidemiology", "neuroscience", "public_mental_health", "digital"}


def _count_distinct_mentions(pattern, text, merge_gap=15):
    """Cuenta apariciones de `pattern` en `text`, fusionando coincidencias muy
    cercanas (p. ej. "post-traumatic stress disorder (PTSD)" casa dos veces —
    la frase completa y la sigla — pero es UNA sola mención, no dos)."""
    spans = [m.span() for m in re.finditer(pattern, text, re.IGNORECASE)]
    if not spans:
        return 0
    spans.sort()
    count = 1
    prev_end = spans[0][1]
    for start, end in spans[1:]:
        if start - prev_end > merge_gap:
            count += 1
        prev_end = max(prev_end, end)
    return count


def _has_strong_clinical_signal(paper, config):
    """True si algún tag clínico está respaldado por el título/keywords/MeSH,
    o aparece ≥2 veces (menciones distintas) en el abstract — no solo una
    mención incidental, como en MED:42729609 (anestesia; PTSD mencionado una
    vez como posible consecuencia)."""
    tags = paper.get("tags") or []
    clinical_tags = [t for t in tags if t in _CORE_CLINICAL_TAGS]
    if not clinical_tags:
        return False
    patterns = config.get("tag_patterns", {})
    title = paper.get("title") or ""
    kw_mesh = " ".join((paper.get("keywords") or []) + (paper.get("mesh_major") or []))
    abstract_text = (paper.get("abstract") or {}).get("text") or ""
    for tag_id in clinical_tags:
        pat = patterns.get(tag_id)
        if not pat:
            continue
        if re.search(pat, title, re.IGNORECASE) or re.search(pat, kw_mesh, re.IGNORECASE):
            return True
        if _count_distinct_mentions(pat, abstract_text) >= 2:
            return True
    return False


def _base_score(paper, config):
    score = 0
    signals = []
    core_abbrevs = {a.lower() for a in config.get("core_journal_abbrevs", [])}
    journal_abbrev = (paper.get("journal_abbrev") or "").lower()
    if journal_abbrev and journal_abbrev in core_abbrevs:
        score += 3
        signals.append("core_journal")
    mesh_set = set(paper.get("mesh_major") or [])
    if mesh_set & set(config.get("mesh_psychiatry", [])):
        score += 2
        signals.append("mesh_major")
    has_clinical = _has_strong_clinical_signal(paper, config)
    tags = paper.get("tags") or []
    scored_tags = [t for t in tags if has_clinical or t not in _GENERIC_TAGS_NEED_CLINICAL]
    n_tags = len(scored_tags)
    if n_tags:
        add = min(3, n_tags)
        score += add
        signals.append(f"tags:{add}")
    design = paper.get("study_design") or {}
    if design.get("id") in _STRONG_DESIGNS and not paper.get("is_preprint"):
        score += 1
        signals.append("strong_design")
    if not has_clinical:
        score -= 4
        signals.append("weak_topic")
    return score, signals


def apply_relevance(items, config):
    """Calcula relevance para todos los items in-place (mismo día)."""
    soft_cap = config.get("journal_soft_cap", 8)
    base = {}
    for p in items:
        score, signals = _base_score(p, config)
        base[p["key"]] = (score, list(signals))

    groups = {}
    for p in items:
        j = (p.get("journal_abbrev") or p.get("journal") or "").lower()
        groups.setdefault(j, []).append(p)

    final_score = {}
    final_signals = {}
    for j, group in groups.items():
        group_sorted = sorted(group, key=lambda p: (-base[p["key"]][0], p["key"]))
        for idx, p in enumerate(group_sorted):
            score, signals = base[p["key"]]
            if idx >= soft_cap:
                score -= 2
                signals = signals + ["journal_overflow"]
            final_score[p["key"]] = score
            final_signals[p["key"]] = signals

    for p in items:
        p["relevance"] = {"score": final_score[p["key"]], "signals": final_signals[p["key"]]}

    items.sort(key=lambda p: (-p["relevance"]["score"], p.get("journal") or "", p.get("title") or "", p["key"]))


# ---------------------------------------------------------------------------
# Frontmatter parser (3.0.8, enmienda 17)
# ---------------------------------------------------------------------------

class SummaryFormatError(Exception):
    def __init__(self, path, line, msg):
        self.path = path
        self.line = line
        self.msg = msg
        super().__init__(f"{path}:{line}: {msg}")


# tipo: "str" | "int" | "bool" | "list" | "date"
FRONTMATTER_SCHEMA = {
    "title": ("str", True),
    "date": ("date", True),
    "status": ("str", True),
    "tags": ("list", True),
    "study_design": ("str", True),
    "summary_type": ("str", True),
    "adapted_with_ai": ("bool", False),
    "paper_access_type": ("str", False),
    "paper_oa_source": ("str", False),
    "paper_title": ("str", True),
    "paper_authors": ("str", True),
    "paper_journal": ("str", True),
    "paper_year": ("int", True),
    "paper_source": ("str", True),
    "paper_epmc_id": ("str", True),
    "paper_license": ("str", True),
    "paper_oa_verified": ("bool", True),
    "paper_oa_checked": ("date", True),
    "paper_pmcid": ("str", False),
    "paper_doi": ("str", False),
    "paper_pmid": ("str", False),
    "paper_journal_abbrev": ("str", False),
    "paper_pub_date": ("date", False),
    "paper_pub_types": ("list", False),
    "paper_preprint": ("bool", False),
    "updated": ("date", False),
    "example": ("bool", False),
    "ai_draft": ("bool", False),
    "author": ("str", False),
    "sample_size": ("int", False),
}

FRONTMATTER_DEFAULTS = {
    "paper_journal_abbrev": None,
    "paper_pub_date": None,
    "paper_pub_types": [],
    "paper_preprint": False,
    "updated": None,
    "example": False,
    "ai_draft": False,
    "adapted_with_ai": False,
    "paper_access_type": "open_access",
    "paper_oa_source": "europepmc",
    "author": "Red de Investigación",
    "sample_size": None,
    "paper_pmcid": None,
    "paper_doi": None,
    "paper_pmid": None,
}

_KEY_RE = re.compile(r"^([a-z][a-z0-9_]*):[ \t]*(.*)$")
_INT_RE = re.compile(r"^-?\d+$")


def _tokenize_list(raw, path, lineno):
    """Tokeniza '[a, "b, c", d]' respetando comillas dobles."""
    inner = raw[1:-1]
    tokens = []
    buf = []
    in_quotes = False
    i = 0
    while i < len(inner):
        c = inner[i]
        if c == '"' and not in_quotes:
            in_quotes = True
            buf.append(c)
        elif c == '"' and in_quotes:
            # ¿escapada?
            if buf and buf[-1] == "\\":
                buf.append(c)
            else:
                in_quotes = False
                buf.append(c)
        elif c == "," and not in_quotes:
            tokens.append("".join(buf).strip())
            buf = []
        else:
            buf.append(c)
        i += 1
    last = "".join(buf).strip()
    if last or tokens:
        tokens.append(last)
    result = []
    for tok in tokens:
        tok = tok.strip()
        if not tok:
            continue
        if len(tok) >= 2 and tok[0] == '"' and tok[-1] == '"':
            tok = tok[1:-1].replace('\\"', '"').replace("\\\\", "\\")
        result.append(tok)
    return result


def _parse_scalar(raw, key, path, lineno):
    """Devuelve (valor_python, tipo_detectado)."""
    v = raw.strip()
    if v.startswith("[") and v.endswith("]"):
        return _tokenize_list(v, path, lineno), "list"
    if len(v) >= 2 and v[0] == '"' and v[-1] == '"':
        s = v[1:-1].replace('\\"', '"').replace("\\\\", "\\")
        return s, "str"
    if v in ("true", "false"):
        return v == "true", "bool"
    if v == "" or v == "null":
        return None, "none"
    if _INT_RE.match(v):
        return int(v), "int"
    return v, "str"


def parse_frontmatter(text, path):
    # Preprocesamiento (enmienda 17).
    text = text.lstrip("﻿")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = unicodedata.normalize("NFC", text)
    lines = text.split("\n")

    if not lines or lines[0].strip() != "---":
        raise SummaryFormatError(path, 1, "el archivo debe empezar con una línea '---'")

    end_idx = None
    for i in range(1, len(lines)):
        if lines[i] == "---":
            end_idx = i
            break
    if end_idx is None:
        raise SummaryFormatError(path, 1, "no se encontró la línea '---' de cierre del frontmatter")

    data = {}
    seen = set()
    for i in range(1, end_idx):
        lineno = i + 1
        raw_line = lines[i]
        stripped = raw_line.strip()
        if stripped == "" or stripped.startswith("#"):
            continue
        m = _KEY_RE.match(raw_line)
        if not m:
            raise SummaryFormatError(
                path, lineno, "línea de frontmatter inválida; se esperaba 'clave: valor'"
            )
        key, raw_value = m.group(1), m.group(2)
        if key == "slug":
            raise SummaryFormatError(
                path, lineno, "slug se deriva del nombre de archivo; no debe estar en el frontmatter"
            )
        if key in seen:
            raise SummaryFormatError(path, lineno, f"clave duplicada: {key}")
        seen.add(key)
        if key not in FRONTMATTER_SCHEMA:
            raise SummaryFormatError(path, lineno, f"clave desconocida: {key}")
        value, detected = _parse_scalar(raw_value, key, path, lineno)
        expected, _required = FRONTMATTER_SCHEMA[key]
        if detected == "none":
            value = None
        elif expected == "list":
            if detected != "list":
                raise SummaryFormatError(path, lineno, f"{key}: se esperaba una lista '[a, b]'")
        elif expected == "bool":
            if detected != "bool":
                raise SummaryFormatError(path, lineno, f"{key}: se esperaba true/false")
        elif expected == "int":
            if detected != "int":
                raise SummaryFormatError(path, lineno, f"{key}: se esperaba un entero")
        elif expected in ("str", "date"):
            if detected == "int" and key in ("paper_epmc_id", "paper_pmid"):
                value = str(value)
            elif detected == "int":
                raise SummaryFormatError(
                    path, lineno, f"{key}: se esperaba texto; usa comillas dobles"
                )
            elif detected == "list":
                raise SummaryFormatError(path, lineno, f"{key}: se esperaba texto, no una lista")
        data[key] = value

    # Defaults.
    for k, default in FRONTMATTER_DEFAULTS.items():
        if k not in data:
            data[k] = default

    # Obligatoriedad.
    for key, (_typ, required) in FRONTMATTER_SCHEMA.items():
        if required and data.get(key) is None:
            raise SummaryFormatError(path, end_idx + 1, f"falta la clave obligatoria: {key}")

    if not data.get("paper_pmcid") and not data.get("paper_doi"):
        raise SummaryFormatError(
            path, end_idx + 1, "se requiere al menos uno de paper_pmcid o paper_doi"
        )
    if data.get("paper_pmcid") and not re.match(r"^PMC\d+$", data["paper_pmcid"]):
        raise SummaryFormatError(path, end_idx + 1, "paper_pmcid inválido: debe ser 'PMC<dígitos>'")
    if data.get("paper_doi") and not re.match(r"^10\.\S+$", data["paper_doi"]):
        raise SummaryFormatError(path, end_idx + 1, "paper_doi inválido: debe empezar con '10.'")
    if data.get("paper_pmid") and not re.match(r"^\d+$", data["paper_pmid"]):
        raise SummaryFormatError(path, end_idx + 1, "paper_pmid inválido: solo dígitos")

    title = data.get("title") or ""
    if not (10 <= len(title) <= 200):
        raise SummaryFormatError(path, end_idx + 1, "title debe tener entre 10 y 200 caracteres")
    if not validate_date(data.get("date")):
        raise SummaryFormatError(path, end_idx + 1, "date inválida: se esperaba YYYY-MM-DD")
    if data.get("status") not in ("draft", "published"):
        raise SummaryFormatError(path, end_idx + 1, "status debe ser draft o published")
    tags = data.get("tags") or []
    if not (1 <= len(tags) <= 6):
        raise SummaryFormatError(path, end_idx + 1, "tags debe tener entre 1 y 6 elementos")
    for t in tags:
        if t not in TAGS:
            raise SummaryFormatError(path, end_idx + 1, f"tag desconocido: {t}")
    if data.get("study_design") not in DESIGNS:
        raise SummaryFormatError(path, end_idx + 1, f"study_design desconocido: {data.get('study_design')}")
    if data.get("summary_type") not in SUMMARY_TYPES:
        raise SummaryFormatError(path, end_idx + 1, f"summary_type desconocido: {data.get('summary_type')!r}")
    if data.get("summary_type") == "empirico" and data.get("study_design") in ("narrative_review", "guideline"):
        raise SummaryFormatError(
            path, end_idx + 1, "un resumen empírico exige un diseño con datos (study_design no puede ser "
            "narrative_review ni guideline)"
        )
    if data.get("paper_access_type") not in ("open_access", "free_to_read"):
        raise SummaryFormatError(
            path, end_idx + 1, f"paper_access_type inválido: {data.get('paper_access_type')!r}"
        )
    if data.get("paper_oa_source") not in ("europepmc", "europepmc+openalex", "publisher"):
        raise SummaryFormatError(
            path, end_idx + 1, f"paper_oa_source inválido: {data.get('paper_oa_source')!r}"
        )
    if data.get("status") == "published" and data.get("ai_draft") is True and data.get("adapted_with_ai") is True:
        raise SummaryFormatError(
            path, end_idx + 1,
            "ai_draft y adapted_with_ai no pueden ser ambos true en un resumen published "
            "(ai_draft: la IA redactó el texto; adapted_with_ai: el autor humano lo escribió y la IA "
            "solo lo adaptó al formato; son excluyentes)",
        )
    paper_title = data.get("paper_title") or ""
    if not paper_title or re.search(r"<[a-zA-Z]", paper_title):
        raise SummaryFormatError(path, end_idx + 1, "paper_title vacío o contiene HTML")
    py = data.get("paper_year")
    if py is None or not (1900 <= py <= 2100):
        raise SummaryFormatError(path, end_idx + 1, "paper_year debe estar entre 1900 y 2100")
    access_type = data.get("paper_access_type")
    if access_type == "open_access":
        if data.get("paper_oa_verified") is not True:
            raise SummaryFormatError(
                path,
                end_idx + 1,
                "Rechazado: paper_oa_verified debe ser true para paper_access_type: open_access.",
            )
        if data.get("paper_oa_source") == "publisher":
            raise SummaryFormatError(
                path, end_idx + 1, "paper_oa_source: publisher solo es válido para free_to_read"
            )
        if not license_allowed(data.get("paper_license")):
            raise SummaryFormatError(
                path,
                end_idx + 1,
                f"Rechazado: paper_license '{data.get('paper_license')}' no es una licencia CC abierta "
                "reconocida (se requiere cc0 o cc by*).",
            )
    else:
        if data.get("paper_oa_verified") is not False:
            raise SummaryFormatError(
                path, end_idx + 1,
                "paper_access_type: free_to_read requiere paper_oa_verified: false para no presentarlo como OA",
            )
        if data.get("paper_oa_source") != "publisher":
            raise SummaryFormatError(
                path, end_idx + 1,
                "paper_access_type: free_to_read requiere paper_oa_source: publisher",
            )
        if (data.get("paper_license") or "").strip().lower() != "not verified":
            raise SummaryFormatError(
                path, end_idx + 1,
                'paper_access_type: free_to_read requiere paper_license: "not verified"',
            )
        if not data.get("paper_doi"):
            raise SummaryFormatError(
                path, end_idx + 1, "paper_access_type: free_to_read requiere paper_doi"
            )
        if data.get("paper_preprint"):
            raise SummaryFormatError(
                path, end_idx + 1, "paper_access_type: free_to_read no admite preprints sin licencia abierta"
            )
    if not validate_date(data.get("paper_oa_checked")):
        raise SummaryFormatError(path, end_idx + 1, "paper_oa_checked inválida: se esperaba YYYY-MM-DD")
    if data.get("paper_pub_date") is not None and not validate_date(data["paper_pub_date"]):
        raise SummaryFormatError(path, end_idx + 1, "paper_pub_date inválida: se esperaba YYYY-MM-DD")
    if data.get("updated") is not None and not validate_date(data["updated"]):
        raise SummaryFormatError(path, end_idx + 1, "updated inválida: se esperaba YYYY-MM-DD")
    ss = data.get("sample_size")
    if ss is not None and ss <= 0:
        raise SummaryFormatError(path, end_idx + 1, "sample_size debe ser > 0")
    if data.get("status") == "published":
        if not data.get("author") or data["author"] == FRONTMATTER_DEFAULTS["author"]:
            raise SummaryFormatError(
                path, end_idx + 1, "status: published requiere un author explícito (no el default)"
            )

    body = "\n".join(lines[end_idx + 1 :])
    return data, body


# ---------------------------------------------------------------------------
# Cuerpo markdown (3.0.8, enmienda 18)
# ---------------------------------------------------------------------------

_EMPHASIS_RE = re.compile(r"(?<![\w*])(\*\*|\*|__|_)(?=\S)(.+?)(?<=\S)\1(?![\w*])")
_BACKTICK_RE = re.compile(r"`([^`]*)`")
_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]*)\)")
_RAW_HTML_RE = re.compile(r"<(?=[A-Za-z/!])")


def inline_to_plain(s):
    prev = None
    while prev != s:
        prev = s
        s = _EMPHASIS_RE.sub(r"\2", s)
    s = _BACKTICK_RE.sub(r"\1", s)

    def _link_repl(m):
        txt, url = m.group(1), m.group(2)
        if url.startswith("http://") or url.startswith("https://"):
            return f"{txt} ({url})"
        return txt

    s = _LINK_RE.sub(_link_repl, s)
    if _RAW_HTML_RE.search(s):
        raise ValueError("HTML no permitido")
    return s


def _split_paragraphs(content_lines, start_line):
    """Divide en párrafos por líneas en blanco; cada párrafo lleva su línea
    inicial (1-indexada, relativa al cuerpo del archivo)."""
    paras = []
    cur = []
    cur_start = None
    for i, line in enumerate(content_lines):
        lineno = start_line + i
        if line.strip() == "":
            if cur:
                paras.append((cur, cur_start))
                cur = []
                cur_start = None
        else:
            if cur_start is None:
                cur_start = lineno
            cur.append(line)
    if cur:
        paras.append((cur, cur_start))
    return paras


_LIST_ITEM_RE = re.compile(r"^(-|\*) ")
_OL_ITEM_RE = re.compile(r"^\d+\. ")


def _inline_or_error(s, path, lineno):
    try:
        return inline_to_plain(s)
    except ValueError as e:
        raise SummaryFormatError(path, lineno, str(e) or "HTML no permitido")


def _warn(msg):
    print(f"[common] {msg}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Bloques de lista de bajo nivel: ul ('- texto'), ol ('1. texto') y kv
# ('- Clave: valor', que es un ul reinterpretado). Contrato C1.3.
# ---------------------------------------------------------------------------


def _parse_ul_items(para_lines, path, para_start):
    if not para_lines or not _LIST_ITEM_RE.match(para_lines[0]):
        raise SummaryFormatError(path, para_start, "se esperaba una lista de ítems '- texto'")
    has_plain = any(not (_LIST_ITEM_RE.match(l) or l.startswith("  ")) for l in para_lines)
    if has_plain:
        raise SummaryFormatError(
            path, para_start,
            "los ítems de lista deben empezar con '- '; para continuar un ítem, indenta con 2 espacios",
        )
    items = []
    for j, l in enumerate(para_lines):
        lineno = para_start + j
        if _LIST_ITEM_RE.match(l):
            items.append(_inline_or_error(l[2:].strip(), path, lineno))
        else:
            if items:
                items[-1] = items[-1] + " " + _inline_or_error(l.strip(), path, lineno)
    return items


def _parse_ol_items(para_lines, path, para_start):
    if not para_lines or not _OL_ITEM_RE.match(para_lines[0]):
        raise SummaryFormatError(path, para_start, "se esperaba una lista numerada '1. texto'")
    has_plain = any(not (_OL_ITEM_RE.match(l) or l.startswith("  ")) for l in para_lines)
    if has_plain:
        raise SummaryFormatError(
            path, para_start,
            "los ítems de lista numerada deben empezar con '1. '; para continuar, indenta con 2 espacios",
        )
    items = []
    for j, l in enumerate(para_lines):
        lineno = para_start + j
        if _OL_ITEM_RE.match(l):
            text = _OL_ITEM_RE.sub("", l, count=1).strip()
            items.append(_inline_or_error(text, path, lineno))
        else:
            if items:
                items[-1] = items[-1] + " " + _inline_or_error(l.strip(), path, lineno)
    return items


def parse_kv_block(para_lines, path, para_start):
    """Parsea un párrafo de ítems '- Clave: valor' (continuación indentada 2
    espacios) a una lista de {"key","value"}. La separación es en el PRIMER
    ': ' (dos puntos + espacio), después de inline_to_plain. Lanza
    SummaryFormatError si un ítem no tiene esa forma, o si la clave está
    vacía, excede 60 caracteres, o el valor queda vacío."""
    texts = _parse_ul_items(para_lines, path, para_start)
    items = []
    for text in texts:
        if ": " not in text:
            raise SummaryFormatError(path, para_start, f"se esperaba '- Clave: valor': '{text[:60]}'")
        key, value = text.split(": ", 1)
        key = key.strip()
        value = value.strip()
        if not key or len(key) > 60 or ":" in key:
            raise SummaryFormatError(path, para_start, f"clave de '- Clave: valor' inválida: '{key}'")
        if not value:
            raise SummaryFormatError(path, para_start, f"valor vacío para la clave: {key}")
        items.append({"key": key, "value": value})
    return items


# ---------------------------------------------------------------------------
# Validadores puros (sin red) reutilizados por el parser y por build_summaries.
# ---------------------------------------------------------------------------

_QUOTE_RE = re.compile(r'"([^"\n]+)"|“([^”\n]+)”|«([^»\n]+)»')


def find_long_quotes(text):
    """Devuelve [(n_palabras, fragmento), ...] por cada cita textual (entre
    comillas rectas, tipográficas '“”' o angulares '«»') con 15 palabras
    o más (política del sitio: las citas deben tener menos de 15)."""
    violations = []
    for m in _QUOTE_RE.finditer(text or ""):
        frag = next(g for g in m.groups() if g is not None)
        n = len(frag.split())
        if n >= 15:
            violations.append((n, frag))
    return violations


def validate_limitations(items, categories):
    """Lanza ValueError si algún ítem no tiene el prefijo '<Categoría>: ' con
    Categoría en `categories` (contrato C1.7 / C2 nc_limitaciones)."""
    for it in items:
        if ": " not in it:
            raise ValueError(f"limitación sin categoría (se esperaba '<Categoría>: texto'): '{it[:50]}'")
        cat = it.split(": ", 1)[0]
        if cat not in categories:
            raise ValueError(f"categoría de limitación no reconocida: '{cat}' (ítem: '{it[:50]}')")


_READING_DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$")
_READING_PMID_RE = re.compile(r"^\d+$")


def parse_readings_item(text):
    """Parsea '<cita> · doi:<DOI>|PMID:<dígitos> · <por qué leerla>' (contrato
    C1.6, separador ' · ' = espacio + punto medio U+00B7 + espacio). Devuelve
    {"citation","doi","pmid","why"}. Lanza ValueError si el formato no coincide."""
    parts = text.split(" · ")
    if len(parts) != 3:
        raise ValueError(
            "se esperaban 3 partes separadas por ' · ' (espacio, punto medio, espacio): "
            "cita · doi:<DOI>|PMID:<dígitos> · por qué leerla"
        )
    citation, ident, why = (p.strip() for p in parts)
    if not citation:
        raise ValueError("la cita no puede estar vacía")
    if not why:
        raise ValueError("la justificación ('por qué leerla') no puede estar vacía")
    doi = None
    pmid = None
    if ident.startswith("doi:"):
        doi = ident[len("doi:"):].strip()
        if not _READING_DOI_RE.match(doi):
            raise ValueError(f"doi inválido: '{doi}'")
    elif ident.startswith("PMID:"):
        pmid = ident[len("PMID:"):].strip()
        if not _READING_PMID_RE.match(pmid):
            raise ValueError(f"PMID inválido: '{pmid}'")
    else:
        raise ValueError("el identificador debe ser 'doi:<DOI>' o 'PMID:<dígitos>'")
    return {"citation": citation, "doi": doi, "pmid": pmid, "why": why}


_PRINCIPLE_FORBIDDEN_RE = re.compile(
    r"\b(siempre|nunca|todos|todas|todo|demuestran?|deben?|deber[ií]an?|hay que|"
    r"se recomienda|recomendamos)\b",
    re.IGNORECASE,
)
_PRINCIPLE_CAUSAL_RE = re.compile(r"\b(causan?|provocan?|producen?)\b", re.IGNORECASE)
_PRINCIPLE_DIGIT_RE = re.compile(r"\d")
_PRINCIPLE_EVIDENCE_NUM_RE = re.compile(r"\d+[.,]\d+|\d{2,}")
_PRINCIPLE_TRANSFER_VALUES = {"clínica", "investigación", "formación"}
_PRINCIPLE_STRENGTHS = {"alta", "moderada", "baja", "muy baja", "argumental"}


def validate_principle(kv_items, summary_type, study_design, corpus_text):
    """Valida el contenido semántico de 'El principio' (contrato C1.5).
    `kv_items`: lista de {"key","value"}. `corpus_text`: concatenación de
    Hallazgos+Métodos (empírico) o Ideas+Argumento (conceptual), para
    verificar que cada cifra de 'Evidencia' aparece en el cuerpo. Lanza
    ValueError; si es válido, devuelve el dict listo para el JSON."""
    keys = [it["key"] for it in kv_items]
    if keys != PRINCIPLE_KEYS:
        raise ValueError(f"El principio debe tener exactamente estas 7 claves en orden: {', '.join(PRINCIPLE_KEYS)}")
    values = {it["key"]: it["value"] for it in kv_items}
    statement = values["Enunciado"]
    if len(statement.split()) > 30:
        raise ValueError("Enunciado debe tener 30 palabras o menos")
    if _PRINCIPLE_DIGIT_RE.search(statement):
        raise ValueError("Enunciado no debe contener cifras")
    if _PRINCIPLE_FORBIDDEN_RE.search(statement):
        raise ValueError("Enunciado contiene una palabra prohibida (siempre/nunca/todos/debe/recomendamos...)")
    if summary_type == "empirico" and study_design in OBSERVATIONAL_DESIGNS and _PRINCIPLE_CAUSAL_RE.search(statement):
        raise ValueError("Enunciado no puede afirmar causalidad desde un diseño observacional")
    if statement.strip().endswith("?"):
        raise ValueError("Enunciado no debe terminar en '?'")

    strength = values["Fuerza"].strip()
    if strength not in _PRINCIPLE_STRENGTHS:
        raise ValueError(f"Fuerza inválida: '{strength}'")
    if summary_type == "conceptual":
        if strength != "argumental":
            raise ValueError("un resumen conceptual exige Fuerza: argumental")
    else:
        if strength == "argumental":
            raise ValueError("un resumen empírico no puede tener Fuerza: argumental")
        cap = STRENGTH_CAP.get(study_design)
        if cap is not None and STRENGTH_ORDER[strength] > STRENGTH_ORDER[cap]:
            raise ValueError(f"Fuerza '{strength}' supera el tope para study_design={study_design} ('{cap}')")

    transfer = [t.strip() for t in values["Transferencia"].split(",") if t.strip()]
    if not transfer or any(t not in _PRINCIPLE_TRANSFER_VALUES for t in transfer):
        raise ValueError("Transferencia debe ser un subconjunto de 'clínica, investigación, formación'")

    limit = values["Límite"]
    if len(limit.split()) < 5:
        raise ValueError("Límite debe tener al menos 5 palabras")

    provenance = values["Procedencia"].strip()
    if provenance not in ("autores", "curador"):
        raise ValueError("Procedencia debe ser 'autores' o 'curador'")

    evidence = values["Evidencia"]
    for num in _PRINCIPLE_EVIDENCE_NUM_RE.findall(evidence):
        if num not in (corpus_text or ""):
            raise ValueError(f"cifra del principio ausente del cuerpo (Hallazgos/Métodos o Ideas/Argumento): '{num}'")

    return {
        "statement": statement,
        "rationale": values["Fundamento"],
        "evidence": evidence,
        "strength": strength,
        "transfer": transfer,
        "limit": limit,
        "provenance": provenance,
    }


def normalize_openalex_license(raw):
    """'cc-by-nc' -> 'cc by-nc' (OpenAlex separa con guion; el resto del sitio
    usa espacio tras 'cc'). Sin cambios para licencias sin ese prefijo (p. ej.
    'cc0')."""
    if not raw:
        return raw
    raw = raw.strip().lower()
    if raw.startswith("cc-"):
        return "cc " + raw[3:]
    return raw


def openalex_oa_verdict(work):
    """work: dict de la respuesta de OpenAlex GET /works/doi:<doi>. Devuelve
    (ok, license_norm, reason): ok=True solo si open_access.is_oa es True,
    best_oa_location.version es 'publishedVersion' y la licencia normalizada
    es una CC abierta reconocida (contrato: ruta B de OA v2)."""
    if not isinstance(work, dict):
        return False, None, "respuesta de OpenAlex inválida"
    oa = work.get("open_access") or {}
    if oa.get("is_oa") is not True:
        return False, None, "OpenAlex no marca open_access.is_oa=true"
    best = work.get("best_oa_location") or {}
    if best.get("version") != "publishedVersion":
        return False, None, f"best_oa_location.version no es 'publishedVersion' ({best.get('version')!r})"
    license_raw = best.get("license")
    license_norm = normalize_openalex_license(license_raw)
    if not license_allowed(license_norm):
        return False, license_norm, f"licencia de OpenAlex no reconocida como CC abierta: {license_raw!r}"
    return True, license_norm, None


# ---------------------------------------------------------------------------
# Prohibiciones globales del cuerpo (contrato C1.3): HTML crudo (ya lo hace
# inline_to_plain por bloque), tablas markdown, blockquotes, imágenes, emojis.
# ---------------------------------------------------------------------------

_TABLE_OR_QUOTE_RE = re.compile(r"^\s*[|>]", re.M)
_IMAGE_RE = re.compile(r"!\[")
_EMOJI_RE = re.compile(r"[\U0001F300-\U0001FAFF☀-➿]")


def _lineno_at(body, pos):
    return body[:pos].count("\n") + 1


def _check_forbidden_markup(body, path):
    m = _TABLE_OR_QUOTE_RE.search(body)
    if m:
        raise SummaryFormatError(
            path, _lineno_at(body, m.start()),
            "no se permiten tablas markdown ('|') ni blockquotes ('>') en el cuerpo",
        )
    m = _IMAGE_RE.search(body)
    if m:
        raise SummaryFormatError(path, _lineno_at(body, m.start()), "no se permiten imágenes en el cuerpo")
    m = _EMOJI_RE.search(body)
    if m:
        raise SummaryFormatError(path, _lineno_at(body, m.start()), "no se permiten emojis en el cuerpo")


def _forbid_h3(content_lines, path, start_line, context=""):
    for i, l in enumerate(content_lines):
        if l.startswith("### "):
            raise SummaryFormatError(
                path, start_line + i,
                f"'### ' solo está permitido dentro de '## Nota completa' (encontrado en '{context}')",
            )


# ---------------------------------------------------------------------------
# Parsers por sección (contrato C1.2). Cada uno recibe el contenido crudo de
# una sección '## ' (ya descartado el caso [[PENDIENTE]]) y devuelve su
# lista de bloques.
# ---------------------------------------------------------------------------


def _parse_one_p(content_lines, path, start_line, max_chars=None):
    paras = _split_paragraphs(content_lines, start_line)
    if len(paras) != 1:
        raise SummaryFormatError(path, start_line, "se esperaba exactamente un párrafo")
    para_lines, para_start = paras[0]
    if any(_LIST_ITEM_RE.match(l) or _OL_ITEM_RE.match(l) for l in para_lines):
        raise SummaryFormatError(path, para_start, "se esperaba un párrafo, no una lista")
    text = _inline_or_error(" ".join(l.strip() for l in para_lines), path, para_start)
    if max_chars is not None and len(text) > max_chars:
        raise SummaryFormatError(path, para_start, f"el párrafo debe tener {max_chars} caracteres o menos")
    return [{"type": "p", "text": text}]


def _parse_p_only(content_lines, path, start_line, min_p=1, max_p=None):
    paras = _split_paragraphs(content_lines, start_line)
    if len(paras) < min_p or (max_p is not None and len(paras) > max_p):
        raise SummaryFormatError(path, start_line, f"se esperaban entre {min_p} y {max_p or '∞'} párrafos")
    blocks = []
    for para_lines, para_start in paras:
        if any(_LIST_ITEM_RE.match(l) or _OL_ITEM_RE.match(l) for l in para_lines):
            raise SummaryFormatError(path, para_start, "se esperaba un párrafo, no una lista")
        text = " ".join(l.strip() for l in para_lines)
        blocks.append({"type": "p", "text": _inline_or_error(text, path, para_start)})
    return blocks


def _parse_ul_only(content_lines, path, start_line, min_n, max_n):
    paras = _split_paragraphs(content_lines, start_line)
    if len(paras) != 1:
        raise SummaryFormatError(path, start_line, "se esperaba exactamente una lista")
    para_lines, para_start = paras[0]
    items = _parse_ul_items(para_lines, path, para_start)
    if not (min_n <= len(items) <= max_n):
        raise SummaryFormatError(path, para_start, f"la lista debe tener entre {min_n} y {max_n} ítems")
    return [{"type": "ul", "items": items}]


def _parse_ul_categorized(content_lines, path, start_line, min_n, max_n, categories):
    blocks = _parse_ul_only(content_lines, path, start_line, min_n, max_n)
    try:
        validate_limitations(blocks[0]["items"], categories)
    except ValueError as e:
        raise SummaryFormatError(path, start_line, str(e))
    return blocks


def _parse_p_and_ul(content_lines, path, start_line, min_p=1):
    paras = _split_paragraphs(content_lines, start_line)
    if not paras:
        raise SummaryFormatError(path, start_line, "sección vacía")
    blocks = []
    n_p = 0
    for para_lines, para_start in paras:
        if _OL_ITEM_RE.match(para_lines[0]):
            raise SummaryFormatError(path, para_start, "lista numerada solo para secuencias reales")
        if _LIST_ITEM_RE.match(para_lines[0]):
            blocks.append({"type": "ul", "items": _parse_ul_items(para_lines, path, para_start)})
        else:
            if any(_LIST_ITEM_RE.match(l) or _OL_ITEM_RE.match(l) for l in para_lines):
                raise SummaryFormatError(path, para_start, "un párrafo no puede mezclar texto plano con ítems de lista")
            text = " ".join(l.strip() for l in para_lines)
            blocks.append({"type": "p", "text": _inline_or_error(text, path, para_start)})
            n_p += 1
    if n_p < min_p:
        raise SummaryFormatError(path, start_line, f"se esperaba al menos {min_p} párrafo(s)")
    return blocks


def _parse_argument(content_lines, path, start_line):
    paras = _split_paragraphs(content_lines, start_line)
    if not paras:
        raise SummaryFormatError(path, start_line, "sección vacía")
    blocks = []
    seen_ol = False
    n_p = 0
    for para_lines, para_start in paras:
        if _OL_ITEM_RE.match(para_lines[0]):
            if seen_ol:
                raise SummaryFormatError(path, para_start, "como máximo una lista numerada en 'El argumento'")
            items = _parse_ol_items(para_lines, path, para_start)
            if not (2 <= len(items) <= 6):
                raise SummaryFormatError(path, para_start, "la lista numerada de 'El argumento' debe tener entre 2 y 6 pasos")
            blocks.append({"type": "ol", "items": items})
            seen_ol = True
        elif _LIST_ITEM_RE.match(para_lines[0]):
            raise SummaryFormatError(
                path, para_start, "'El argumento' no admite listas con '-'; solo párrafos y una lista numerada"
            )
        else:
            if seen_ol:
                raise SummaryFormatError(path, para_start, "en 'El argumento' la lista numerada debe ir al final")
            text = " ".join(l.strip() for l in para_lines)
            blocks.append({"type": "p", "text": _inline_or_error(text, path, para_start)})
            n_p += 1
    if n_p < 1:
        raise SummaryFormatError(path, start_line, "'El argumento' exige al menos un párrafo")
    return blocks


def _parse_clinica(content_lines, path, start_line, max_ul):
    paras = _split_paragraphs(content_lines, start_line)
    if not paras:
        raise SummaryFormatError(path, start_line, "sección vacía")
    blocks = []
    seen_ul = False
    n_p = 0
    for para_lines, para_start in paras:
        if _OL_ITEM_RE.match(para_lines[0]):
            raise SummaryFormatError(path, para_start, "lista numerada solo para secuencias reales")
        if _LIST_ITEM_RE.match(para_lines[0]):
            if seen_ul:
                raise SummaryFormatError(
                    path, para_start, "como máximo una lista de aplicaciones en 'Por qué importa para la clínica'"
                )
            items = _parse_ul_items(para_lines, path, para_start)
            if len(items) > max_ul:
                raise SummaryFormatError(path, para_start, f"máximo {max_ul} aplicaciones en esta sección")
            for it in items:
                if "Límite:" not in it:
                    raise SummaryFormatError(path, para_start, f"cada aplicación debe contener 'Límite:': '{it[:40]}'")
            blocks.append({"type": "ul", "items": items})
            seen_ul = True
        else:
            text = " ".join(l.strip() for l in para_lines)
            blocks.append({"type": "p", "text": _inline_or_error(text, path, para_start)})
            n_p += 1
    if n_p < 1:
        raise SummaryFormatError(path, start_line, "se esperaba al menos un párrafo interpretativo")
    return blocks


def _parse_kv_exact(content_lines, path, start_line, expected_keys):
    paras = _split_paragraphs(content_lines, start_line)
    if len(paras) != 1:
        raise SummaryFormatError(path, start_line, "se esperaba exactamente una lista '- Clave: valor'")
    para_lines, para_start = paras[0]
    items = parse_kv_block(para_lines, path, para_start)
    keys = [it["key"] for it in items]
    if keys != expected_keys:
        raise SummaryFormatError(
            path, para_start, "se esperaban estas claves, en este orden exacto: " + ", ".join(expected_keys)
        )
    return [{"type": "kv", "items": items}]


def _parse_kv_free(content_lines, path, start_line, min_n, max_n):
    paras = _split_paragraphs(content_lines, start_line)
    if len(paras) != 1:
        raise SummaryFormatError(path, start_line, "se esperaba exactamente una lista '- Clave: valor'")
    para_lines, para_start = paras[0]
    items = parse_kv_block(para_lines, path, para_start)
    if not (min_n <= len(items) <= max_n):
        raise SummaryFormatError(path, para_start, f"se esperaban entre {min_n} y {max_n} entradas")
    return [{"type": "kv", "items": items}]


def _parse_readings(content_lines, path, start_line, min_n, max_n):
    paras = _split_paragraphs(content_lines, start_line)
    if len(paras) != 1:
        raise SummaryFormatError(path, start_line, "se esperaba exactamente una lista de lecturas")
    para_lines, para_start = paras[0]
    texts = _parse_ul_items(para_lines, path, para_start)
    if not (min_n <= len(texts) <= max_n):
        raise SummaryFormatError(path, para_start, f"'Lecturas recomendadas' debe tener entre {min_n} y {max_n} ítems")
    items = []
    for text in texts:
        try:
            items.append(parse_readings_item(text))
        except ValueError as e:
            raise SummaryFormatError(path, para_start, f"lectura mal formada: {e}")
    return [{"type": "readings", "items": items}]


def _parse_section_by_kind(section_id, content_lines, status, path, start_line, summary_type):
    joined = "\n".join(content_lines)
    if "[[PENDIENTE]]" in joined:
        if status != "draft":
            raise SummaryFormatError(
                path, start_line, f"sección '{section_id}': [[PENDIENTE]] solo permitido con status: draft"
            )
        return [], True

    if section_id == "en_una_frase":
        return _parse_one_p(content_lines, path, start_line, max_chars=300), False
    if section_id == "ficha_rapida":
        return _parse_kv_exact(content_lines, path, start_line, QUICK_FACT_KEYS[summary_type]), False
    if section_id == "pregunta":
        return _parse_p_only(content_lines, path, start_line, min_p=1, max_p=2), False
    if section_id == "metodos":
        return _parse_p_and_ul(content_lines, path, start_line, min_p=1), False
    if section_id == "argumento":
        return _parse_argument(content_lines, path, start_line), False
    if section_id == "hallazgos":
        return _parse_ul_only(content_lines, path, start_line, min_n=2, max_n=6), False
    if section_id == "ideas":
        return _parse_ul_only(content_lines, path, start_line, min_n=2, max_n=4), False
    if section_id == "limitaciones":
        return _parse_ul_categorized(content_lines, path, start_line, 1, 6, LIMITATION_CATEGORIES), False
    if section_id == "principio":
        return _parse_kv_exact(content_lines, path, start_line, PRINCIPLE_KEYS), False
    if section_id == "clinica":
        max_ul = 4 if summary_type == "empirico" else 3
        return _parse_clinica(content_lines, path, start_line, max_ul), False
    if section_id == "glosario":
        return _parse_kv_free(content_lines, path, start_line, min_n=3, max_n=10), False
    if section_id == "lecturas":
        return _parse_readings(content_lines, path, start_line, min_n=1, max_n=5), False
    if section_id == "nota":
        return _parse_p_only(content_lines, path, start_line, min_p=1, max_p=None), False
    raise AssertionError(f"sección sin parser registrado: {section_id}")


# ---------------------------------------------------------------------------
# Nota completa (contrato C2): 17 subsecciones '### ', solo para 'empirico'.
# ---------------------------------------------------------------------------

_FULL_NOTE_KV_KEYS = {
    "nc_info": ["Título", "Autor principal", "Correo de correspondencia", "Año", "Revista", "Palabras clave", "País"],
    "nc_intro": ["Problema", "Literatura previa", "Vacío"],
    "nc_pregunta": ["Primaria", "Secundarias"],
    "nc_diseno": ["Diseño", "Checklist declarado"],
    "nc_analisis": ["Univariado", "Bivariado", "Multivariado", "Supuestos", "Software"],
    "nc_discusion": ["Qué significa", "Por qué ocurre", "Contexto amplio"],
}


def _parse_full_note_subsection(nc_id, content_lines, status, path, start_line):
    joined = "\n".join(content_lines)
    if "[[PENDIENTE]]" in joined:
        if status != "draft":
            raise SummaryFormatError(
                path, start_line,
                f"Nota completa, subsección '{nc_id}': [[PENDIENTE]] solo permitido con status: draft",
            )
        return [], True

    if "mailto:" in joined.lower():
        raise SummaryFormatError(path, start_line, "no se permite 'mailto:' en la nota completa")

    if nc_id in _FULL_NOTE_KV_KEYS:
        return _parse_kv_exact(content_lines, path, start_line, _FULL_NOTE_KV_KEYS[nc_id]), False
    if nc_id in ("nc_metodo", "nc_unidad", "nc_muestra", "nc_muestreo"):
        return _parse_one_p(content_lines, path, start_line), False
    if nc_id == "nc_procedimientos":
        paras = _split_paragraphs(content_lines, start_line)
        if len(paras) != 1:
            raise SummaryFormatError(path, start_line, "'Procedimientos' exige exactamente una lista numerada")
        para_lines, para_start = paras[0]
        items = _parse_ol_items(para_lines, path, para_start)
        if len(items) < 3:
            raise SummaryFormatError(path, para_start, "'Procedimientos' exige al menos 3 pasos")
        return [{"type": "ol", "items": items}], False
    if nc_id in ("nc_dependientes", "nc_independientes"):
        paras = _split_paragraphs(content_lines, start_line)
        if len(paras) != 1:
            raise SummaryFormatError(
                path, start_line, f"'{nc_id}' exige exactamente una lista '- Variable: descripción'"
            )
        para_lines, para_start = paras[0]
        items = parse_kv_block(para_lines, path, para_start)
        if not items:
            raise SummaryFormatError(path, para_start, f"'{nc_id}' exige al menos una variable")
        return [{"type": "kv", "items": items}], False
    if nc_id == "nc_hallazgos":
        blocks = _parse_one_p(content_lines, path, start_line)
        text = blocks[0]["text"]
        if not text.startswith("Aquí se realizó "):
            raise SummaryFormatError(path, start_line, "'Hallazgos principales' debe empezar con 'Aquí se realizó '")
        if "Los hallazgos principales son: 1)" not in text:
            raise SummaryFormatError(
                path, start_line,
                "'Hallazgos principales' debe contener 'Los hallazgos principales son: 1)' con la enumeración",
            )
        return blocks, False
    if nc_id == "nc_datos":
        paras = _split_paragraphs(content_lines, start_line)
        if len(paras) != 1:
            raise SummaryFormatError(path, start_line, "'Datos por hallazgo' exige exactamente una lista numerada")
        para_lines, para_start = paras[0]
        items = _parse_ol_items(para_lines, path, para_start)
        if not items:
            raise SummaryFormatError(path, para_start, "'Datos por hallazgo' exige al menos un ítem")
        return [{"type": "ol", "items": items}], False
    if nc_id == "nc_limitaciones":
        blocks = _parse_ul_only(content_lines, path, start_line, min_n=1, max_n=50)
        try:
            validate_limitations(blocks[0]["items"], FULL_NOTE_LIMITATION_CATEGORIES)
        except ValueError as e:
            raise SummaryFormatError(path, start_line, str(e))
        return blocks, False
    if nc_id == "nc_futuro":
        return _parse_ul_only(content_lines, path, start_line, min_n=1, max_n=50), False
    raise AssertionError(f"subsección de Nota completa sin parser registrado: {nc_id}")


def _parse_full_note(content_lines, status, path, start_line):
    joined = "\n".join(content_lines)
    has_h3 = any(l.startswith("### ") for l in content_lines)
    if "[[PENDIENTE]]" in joined and not has_h3:
        if status != "draft":
            raise SummaryFormatError(path, start_line, "Nota completa: [[PENDIENTE]] solo permitido con status: draft")
        return {"pending": True, "sections": []}

    sub_positions = [i for i, l in enumerate(content_lines) if l.startswith("### ")]
    if not sub_positions:
        raise SummaryFormatError(path, start_line, "Nota completa: faltan las 17 subsecciones '### '")

    pre = content_lines[: sub_positions[0]]
    if any(l.strip() for l in pre):
        raise SummaryFormatError(path, start_line, "Nota completa: no puede haber contenido antes de la primera '### '")

    found = []
    subs = []
    for idx, pos in enumerate(sub_positions):
        heading_text = content_lines[pos][4:].strip()
        nc_id = FULL_NOTE_HEADING_TO_ID.get(heading_text)
        if nc_id is None:
            raise SummaryFormatError(path, start_line + pos, f"subsección desconocida en Nota completa: '### {heading_text}'")
        found.append(nc_id)
        end = sub_positions[idx + 1] if idx + 1 < len(sub_positions) else len(content_lines)
        subs.append((nc_id, heading_text, content_lines[pos + 1 : end], start_line + pos + 1))

    if len(set(found)) != len(found) or found != FULL_NOTE_ORDER:
        raise SummaryFormatError(
            path, start_line,
            "'Nota completa' exige exactamente estas 17 subsecciones, en este orden: "
            + ", ".join(f"### {h}" for _i, h in FULL_NOTE_HEADINGS),
        )

    sections_out = []
    for nc_id, heading_text, sub_lines, sub_start in subs:
        blocks, pending = _parse_full_note_subsection(nc_id, sub_lines, status, path, sub_start)
        sections_out.append({"id": nc_id, "heading": heading_text, "pending": pending, "blocks": blocks})

    by_id = {s["id"]: s for s in sections_out}
    hallazgos_sec = by_id.get("nc_hallazgos")
    datos_sec = by_id.get("nc_datos")
    if hallazgos_sec and datos_sec and not hallazgos_sec["pending"] and not datos_sec["pending"]:
        hp_text = hallazgos_sec["blocks"][0]["text"] if hallazgos_sec["blocks"] else ""
        n_h = len(re.findall(r"\d\)", hp_text))
        n_d = len(datos_sec["blocks"][0]["items"]) if datos_sec["blocks"] else 0
        if n_h != n_d:
            raise SummaryFormatError(
                path, start_line,
                f"'Datos por hallazgo' tiene {n_d} ítems para {n_h} hallazgos enumerados en 'Hallazgos principales'",
            )

    return {"pending": False, "sections": sections_out}


# ---------------------------------------------------------------------------
# parse_body: orquestador (contrato C1.2/C1.3/C2).
# ---------------------------------------------------------------------------


def parse_body(body, status, path, summary_type):
    if summary_type not in SECTION_ORDER_BY_TYPE:
        raise SummaryFormatError(path, 1, f"summary_type desconocido: {summary_type!r}")

    _check_forbidden_markup(body, path)

    quote_violations = find_long_quotes(body)
    if quote_violations:
        n, frag = quote_violations[0]
        msg = f"cita textual de {n} palabras (la política del sitio exige menos de 15): «{frag[:60]}»"
        if status == "published":
            raise SummaryFormatError(path, 1, msg)
        _warn(f"{path}: aviso: {msg}")

    plan_ids = SECTION_ORDER_BY_TYPE[summary_type]
    plan_index = {sid: i for i, sid in enumerate(plan_ids)}

    lines = body.split("\n")
    heading_positions = [i for i, line in enumerate(lines) if line.startswith("## ")]

    found_ids = []
    blocks_by_heading_idx = []
    for idx, pos in enumerate(heading_positions):
        heading_text = lines[pos][3:].strip()
        section_id = HEADING_TO_ID.get(heading_text)
        if section_id is None:
            raise SummaryFormatError(path, pos + 1, f"encabezado desconocido: '## {heading_text}'")
        if section_id not in plan_index:
            raise SummaryFormatError(
                path, pos + 1, f"'## {heading_text}' no está permitida para summary_type: {summary_type}"
            )
        found_ids.append(section_id)
        end = heading_positions[idx + 1] if idx + 1 < len(heading_positions) else len(lines)
        # pos+2: primera línea de contenido, 1-indexada, relativa al cuerpo
        # (después de "## <encabezado>" en la línea pos+1).
        blocks_by_heading_idx.append((section_id, heading_text, lines[pos + 1 : end], pos + 2))

    if len(set(found_ids)) != len(found_ids):
        raise SummaryFormatError(path, 1, "hay encabezados '## ' repetidos")

    indices = [plan_index[i] for i in found_ids]
    if indices != sorted(indices):
        raise SummaryFormatError(
            path, 1,
            "los encabezados '## ' deben aparecer en este orden: "
            + ", ".join(f"## {h}" for _sid, h in SECTION_HEADINGS_BY_TYPE[summary_type]),
        )

    missing = [i for i in REQUIRED_ALWAYS_BY_TYPE[summary_type] if i not in found_ids]
    if missing:
        label = dict(SECTION_HEADINGS_BY_TYPE[summary_type])
        raise SummaryFormatError(
            path, 1, "faltan encabezados obligatorios: " + ", ".join(f"## {label[i]}" for i in missing)
        )

    sections = []
    for section_id, heading_text, content_lines, start_line in blocks_by_heading_idx:
        if section_id == "nota_completa":
            full_note = _parse_full_note(content_lines, status, path, start_line)
            sections.append(
                {
                    "id": section_id,
                    "heading": heading_text,
                    "pending": full_note["pending"],
                    "blocks": [],
                    "full_note_sections": full_note["sections"],
                }
            )
            continue
        _forbid_h3(content_lines, path, start_line, context=heading_text)
        blocks, pending = _parse_section_by_kind(section_id, content_lines, status, path, start_line, summary_type)
        sections.append({"id": section_id, "heading": heading_text, "pending": pending, "blocks": blocks})
    return sections
