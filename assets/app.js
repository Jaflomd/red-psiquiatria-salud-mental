/* ============================================================
   Red de Investigación de Psiquiatría y Salud Mental — app.js
   Sin dependencias, sin build. IIFE clásica.
   ============================================================ */
(function () {
  "use strict";

  /* ---------------- Vocabularios (orden canónico) ---------------- */
  var TAG_ORDER = [
    ["psychosis", "Psicosis y esquizofrenia"],
    ["depression", "Depresión"],
    ["anxiety", "Ansiedad"],
    ["symptom_networks", "Redes de síntomas"],
    ["suicide", "Suicidio y autolesión"],
    ["adhd", "TDAH"],
    ["bipolar", "Trastorno bipolar"],
    ["bpd", "Trastorno límite de la personalidad"],
    ["alcohol", "Alcohol"],
    ["substances", "Otras sustancias"],
    ["ptsd", "Trauma y TEPT"],
    ["ocd", "TOC"],
    ["eating", "Conducta alimentaria"],
    ["child_adolescent", "Niñez y adolescencia"],
    ["older_adults", "Adultos mayores"],
    ["public_mental_health", "Salud mental pública"],
    ["peru_latam", "Perú y América Latina"],
    ["medical_education", "Educación médica"],
    ["digital", "Salud digital"],
    ["psychopharmacology", "Psicofarmacología"],
    ["psychotherapy", "Psicoterapia"],
    ["neuroscience", "Neurociencia y biomarcadores"],
    ["epidemiology", "Epidemiología"]
  ];

  var DESIGN_ORDER = [
    ["protocol", "Protocolo de estudio"],
    ["systematic_review_meta", "Revisión sistemática y metaanálisis"],
    ["meta_analysis", "Metaanálisis"],
    ["systematic_review", "Revisión sistemática"],
    ["scoping_review", "Revisión de alcance"],
    ["rct", "Ensayo clínico aleatorizado"],
    ["nonrandomized_trial", "Ensayo clínico no aleatorizado"],
    ["cohort", "Cohorte / longitudinal"],
    ["case_control", "Casos y controles"],
    ["mixed_methods", "Métodos mixtos"],
    ["qualitative", "Cualitativo"],
    ["cross_sectional", "Transversal"],
    ["case_report", "Reporte / serie de casos"],
    ["pilot", "Piloto / factibilidad"],
    ["modelling", "Modelado / economía de la salud"],
    ["guideline", "Guía / consenso"],
    ["narrative_review", "Revisión narrativa"]
  ];

  var LICENSE_LABELS = {
    "cc by": "CC BY",
    "cc by-nc": "CC BY-NC",
    "cc by-nc-nd": "CC BY-NC-ND",
    "cc by-nc-sa": "CC BY-NC-SA",
    "cc by-sa": "CC BY-SA",
    "cc by-nd": "CC BY-ND",
    "cc0": "CC0"
  };

  /* ---------------- Colores de pills (familias fijas; la clase nunca sale del dato) ---------------- */
  var PILL_FAMILIES = ["gray", "brown", "orange", "yellow", "green", "blue", "purple", "pink", "red", "teal"];
  var TAG_COLOR = {
    psychosis: "purple",        depression: "blue",          anxiety: "yellow",
    symptom_networks: "teal",   suicide: "red",              adhd: "orange",
    bipolar: "purple",          bpd: "pink",                 alcohol: "brown",
    substances: "brown",        ptsd: "yellow",              ocd: "yellow",
    eating: "pink",             child_adolescent: "green",   older_adults: "green",
    public_mental_health: "gray", peru_latam: "green",       medical_education: "gray",
    digital: "teal",            psychopharmacology: "orange", psychotherapy: "blue",
    neuroscience: "purple",     epidemiology: "gray"
  };
  var DESIGN_COLOR = {
    systematic_review_meta: "blue", meta_analysis: "blue", systematic_review: "blue", scoping_review: "blue",
    rct: "green", nonrandomized_trial: "green", pilot: "green",
    cohort: "orange", case_control: "orange", cross_sectional: "orange", case_report: "orange",
    qualitative: "purple", mixed_methods: "purple",
    protocol: "gray", modelling: "gray", guideline: "gray", narrative_review: "gray"
  };
  function pillFamily(map, id) {
    var f = Object.prototype.hasOwnProperty.call(map, id) ? map[id] : null;
    return PILL_FAMILIES.indexOf(f) !== -1 ? f : "gray";
  }

  var DOW = ["domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado"];
  var MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];
  var MONTHS_ABBR = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];

  var THEME_KEY = "red-psm-theme";
  var SLUG_RE = /^\d{4}-\d{2}-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*$/;

  var SITE_FALLBACK = {
    schema_version: 1,
    site: {
      name: "Red de Investigación de Psiquiatría y Salud Mental",
      short_name: "Red PSM",
      tagline: "Lecturas curadas con acceso verificable y un feed diario open access en psiquiatría, desde el Perú."
    },
    author: { name: "Javier Flores", role: "Psiquiatra e investigador", lines: [] },
    about: { paragraphs: [] },
    feed: { paragraphs: [] },
    oa_policy: { intro: "", criteria: [], rejections: [], ai_note: "", copyright_note: "" },
    links: []
  };

  /* ---------------- Helpers de DOM (createElement/textContent, sin marcado crudo) ---------------- */
  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (k) {
        var v = attrs[k];
        if (v === null || v === undefined || v === false) return;
        if (k === "class") { node.className = v; return; }
        if (k === "text") { node.textContent = v; return; }
        if (k.slice(0, 2) === "on" && typeof v === "function") { node.addEventListener(k.slice(2).toLowerCase(), v); return; }
        if (v === true) { node.setAttribute(k, ""); return; }
        node.setAttribute(k, String(v));
      });
    }
    if (children !== undefined && children !== null) {
      (Array.isArray(children) ? children : [children]).forEach(function (c) {
        if (c === null || c === undefined || c === "") return;
        if (typeof c === "string" || typeof c === "number") { node.appendChild(document.createTextNode(String(c))); return; }
        node.appendChild(c);
      });
    }
    return node;
  }

  function safeHref(u) {
    if (typeof u !== "string") return null;
    if (/^https?:\/\//.test(u)) return u;
    return null;
  }
  function extLink(label, url) {
    var href = safeHref(url);
    if (!href) return null;
    return el("a", { href: href, target: "_blank", rel: "noopener noreferrer" }, label);
  }
  function extLinkStrict(label, url) {
    if (typeof url !== "string" || !/^https:\/\//.test(url)) return null;
    return el("a", { href: url, target: "_blank", rel: "noopener noreferrer" }, label);
  }

  /* ---------------- Fechas ---------------- */
  function isValidDateStr(s) {
    if (typeof s !== "string") return false;
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s);
    if (!m) return false;
    var y = +m[1], mo = +m[2], d = +m[3];
    if (mo < 1 || mo > 12 || d < 1 || d > 31) return false;
    var dt = new Date(y, mo - 1, d);
    return dt.getFullYear() === y && dt.getMonth() === mo - 1 && dt.getDate() === d;
  }
  function parseYMD(s) {
    if (!isValidDateStr(s)) return null;
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s);
    return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  }
  function formatDateLong(s) {
    var d = parseYMD(s);
    if (!d) return s || "";
    return DOW[d.getDay()] + " " + d.getDate() + " de " + MONTHS[d.getMonth()] + " de " + d.getFullYear();
  }
  function formatDateShort(s) {
    var d = parseYMD(s);
    if (!d) return s || "";
    return d.getDate() + " " + MONTHS_ABBR[d.getMonth()] + " " + d.getFullYear();
  }
  function pad2(n) { return (n < 10 ? "0" : "") + n; }
  function formatLimaDateTime(iso) {
    if (!iso) return "";
    var d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    try {
      var fmt = new Intl.DateTimeFormat("es-PE", {
        timeZone: "America/Lima", hour: "2-digit", minute: "2-digit",
        hour12: false, day: "2-digit", month: "2-digit", year: "numeric"
      });
      var parts = fmt.formatToParts(d), map = {};
      parts.forEach(function (p) { map[p.type] = p.value; });
      return map.year + "-" + map.month + "-" + map.day + " " + map.hour + ":" + map.minute + " Lima";
    } catch (e) {
      var d2 = new Date(d.getTime() - 5 * 3600 * 1000);
      return d2.getUTCFullYear() + "-" + pad2(d2.getUTCMonth() + 1) + "-" + pad2(d2.getUTCDate()) + " " +
        pad2(d2.getUTCHours()) + ":" + pad2(d2.getUTCMinutes()) + " Lima (aprox.)";
    }
  }
  function isValidSlug(s) { return typeof s === "string" && s.length <= 80 && SLUG_RE.test(s); }

  /* ---------------- Texto / búsqueda ---------------- */
  function normalizeSearch(s) {
    if (!s) return "";
    // Rango de marcas combinantes U+0300-U+036F escrito como escape \uXXXX
    // (no como caracteres Unicode crudos en el literal de la regex): un
    // navegador o servidor que sirva este archivo sin charset UTF-8
    // explícito (p. ej. dist/snapshot.html abierto directo del disco, sin el
    // wrapper del Artifact) decodifica esos bytes distinto y la regex entera
    // deja de compilar, tumbando todo app.js (hallazgo de verificación).
    try { return String(s).normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase(); }
    catch (e) { return String(s).toLowerCase(); }
  }
  function debounce(fn, wait) {
    var t;
    return function () {
      var args = arguments, ctx = this;
      clearTimeout(t);
      t = setTimeout(function () { fn.apply(ctx, args); }, wait);
    };
  }

  /* ---------------- Vocabulario: etiquetas con datos primero ---------------- */
  function tagLabel(id, labelsMap) {
    if (labelsMap && labelsMap.tags && Object.prototype.hasOwnProperty.call(labelsMap.tags, id)) return labelsMap.tags[id];
    for (var i = 0; i < TAG_ORDER.length; i++) if (TAG_ORDER[i][0] === id) return TAG_ORDER[i][1];
    return id;
  }
  function designLabel(id, labelsMap) {
    if (!id) return null;
    if (labelsMap && labelsMap.designs && Object.prototype.hasOwnProperty.call(labelsMap.designs, id)) return labelsMap.designs[id];
    for (var i = 0; i < DESIGN_ORDER.length; i++) if (DESIGN_ORDER[i][0] === id) return DESIGN_ORDER[i][1];
    return id;
  }
  function licenseLabel(raw) {
    if (!raw) return "Licencia no declarada";
    var key = String(raw).toLowerCase();
    if (LICENSE_LABELS[key]) return LICENSE_LABELS[key];
    return String(raw).toUpperCase();
  }

  /* ---------------- Tipología v2: tipo de resumen / principio ---------------- */
  var SUMMARY_TYPE_LABEL_DEFAULT = { empirico: "Empírico", conceptual: "Conceptual" };
  function summaryTypeLabel(id, labelsMap) {
    if (labelsMap && labelsMap.summary_types && Object.prototype.hasOwnProperty.call(labelsMap.summary_types, id)) return labelsMap.summary_types[id];
    return SUMMARY_TYPE_LABEL_DEFAULT[id] || id;
  }
  var STRENGTH_LABEL_DEFAULT = { alta: "Alta", moderada: "Moderada", baja: "Baja", "muy baja": "Muy baja", argumental: "Argumental" };
  function strengthLabel(id, labelsMap) {
    if (labelsMap && labelsMap.strengths && Object.prototype.hasOwnProperty.call(labelsMap.strengths, id)) return labelsMap.strengths[id];
    return STRENGTH_LABEL_DEFAULT[id] || id;
  }
  // Familias de pill (mismo vocabulario cerrado que PILL_FAMILIES) para el
  // nivel de Fuerza del principio: alta > moderada > baja > muy baja, y
  // argumental (conceptual) en gris neutro, sin implicar un rango numérico.
  var STRENGTH_COLOR = { alta: "green", moderada: "teal", baja: "yellow", "muy baja": "orange", argumental: "gray" };
  var PROVENANCE_LABEL = { autores: "según los autores", curador: "lectura del curador" };

  function idsInCanonicalOrder(present, orderTable) {
    var out = orderTable.map(function (t) { return t[0]; }).filter(function (id) { return present[id]; });
    Object.keys(present).forEach(function (id) {
      if (orderTable.every(function (t) { return t[0] !== id; })) out.push(id);
    });
    return out;
  }
  function uniqueTagsIn(list) {
    var present = {};
    list.forEach(function (x) { (x.tags || []).forEach(function (t) { present[t] = true; }); });
    return idsInCanonicalOrder(present, TAG_ORDER);
  }
  function uniqueDesignsIn(list) {
    var present = {};
    list.forEach(function (x) { if (x.study_design && x.study_design.id) present[x.study_design.id] = true; });
    return idsInCanonicalOrder(present, DESIGN_ORDER);
  }

  /* ---------------- Carga de datos (embebido → fetch) ---------------- */
  var jsonCache = {};
  function loadJson(id, path) {
    var cacheKey = id + "::" + path;
    if (Object.prototype.hasOwnProperty.call(jsonCache, cacheKey)) return jsonCache[cacheKey];
    var promise;
    var node = document.getElementById(id);
    if (node) {
      promise = new Promise(function (resolve, reject) {
        try { resolve(JSON.parse(node.textContent)); }
        catch (e) { reject(new Error("JSON embebido inválido para " + id)); }
      });
    } else if (document.getElementById("data-daily-index")) {
      promise = Promise.resolve(null);
    } else {
      promise = fetch(path, { cache: "no-cache" }).then(function (res) {
        if (!res.ok) { var e = new Error("HTTP " + res.status); e.path = path; throw e; }
        return res.json();
      }, function () {
        var e = new Error("network"); e.path = path; throw e;
      }).catch(function (e) {
        if (!e.path) e.path = path;
        // Un fallo transitorio (servidor caído un instante, offline) no debe
        // quedar cacheado para siempre: la próxima vez que se pida este id
        // se reintenta el fetch en vez de repetir el mismo error indefinido
        // (hallazgo de verificación).
        delete jsonCache[cacheKey];
        throw e;
      });
    }
    jsonCache[cacheKey] = promise;
    return promise;
  }
  function loadSite() { return loadJson("data-site", "content/site.json"); }
  function loadSummaries() { return loadJson("data-summaries", "data/summaries.json"); }
  function loadDailyIndex() { return loadJson("data-daily-index", "data/daily/index.json"); }
  function loadDailyDay(date) { return loadJson("data-daily-" + date, "data/daily/" + date + ".json"); }

  /* ---------------- Estado global de vista / DOM ---------------- */
  function getMain() { return document.getElementById("main"); }
  function clearMain() { var m = getMain(); while (m.firstChild) m.removeChild(m.firstChild); }
  function mountContainer() { var c = el("div", { class: "container" }); getMain().appendChild(c); return c; }
  function setStatus(text) { var s = document.getElementById("status"); if (s) s.textContent = text; }

  function updateNavCurrent() {
    var h = location.hash || "#/";
    var qIdx = h.indexOf("?");
    var path = qIdx === -1 ? h : h.slice(0, qIdx);
    var top = path.replace(/^#\//, "").split("/")[0] || "";
    document.querySelectorAll(".site-nav a").forEach(function (a) {
      var href = a.getAttribute("href");
      var match = (top === "papers" && href === "#/papers") ||
        (top === "resumenes" && href === "#/resumenes") ||
        (top === "acerca" && href === "#/acerca");
      if (match) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
    });
  }
  // En la carga inicial NO se mueve el foco a #main: hacerlo siempre ocultaba
  // la cabecera (marca, nav, botón de tema) al primer Tab del lector de
  // teclado, que aterrizaba dentro del contenido en vez de en el skip link
  // (hallazgo de verificación, alta severidad). En navegaciones posteriores
  // sí se enfoca #main y se resetea el scroll (si no, el lector caía a mitad
  // de la página anterior).
  var isInitialRoute = true;
  function finishView(viewName) {
    document.title = viewName + " · Red de Investigación de Psiquiatría y Salud Mental";
    var m = getMain();
    if (!isInitialRoute) {
      window.scrollTo(0, 0);
      if (m && m.focus) m.focus({ preventScroll: true });
    }
    isInitialRoute = false;
    setStatus("Vista cargada: " + viewName);
    updateNavCurrent();
  }
  function renderLoading() {
    clearMain();
    var c = mountContainer();
    c.appendChild(el("p", { class: "state" }, "Cargando…"));
    return c;
  }
  function renderErrorState(path) {
    clearMain();
    var c = mountContainer();
    c.appendChild(el("div", { class: "state" }, el("p", {}, [
      "No se pudieron cargar los datos (" + path + "). Si abriste ",
      el("code", {}, "index.html"),
      " directamente desde el disco, inicia un servidor local: ",
      el("code", {}, "python3 -m http.server 8742"),
      " en la carpeta del proyecto y abre ",
      el("code", {}, "http://localhost:8742/"),
      ". Si el archivo no existe, genera el feed con ",
      el("code", {}, "python3 scripts/fetch_daily.py --days 3"),
      "."
    ])));
    finishView("Error de carga");
  }
  function showNotFound(message, linkHref, linkText, heading) {
    // Antes el h1 siempre decía "No encontramos esa ruta", seguido por el
    // mismo texto otra vez como párrafo, incluso cuando el problema real era
    // "ese día no está en el feed" o "no existe ese resumen" (hallazgo de
    // verificación: mensaje duplicado y poco específico).
    clearMain();
    var c = mountContainer();
    var box = el("div", { class: "state" });
    box.appendChild(el("h1", {}, heading || "No encontramos esa ruta"));
    box.appendChild(el("p", {}, message || "Prueba desde el inicio."));
    box.appendChild(el("p", {}, el("a", { href: linkHref || "#/", class: "btn" }, linkText || "Ir al inicio")));
    c.appendChild(box);
    finishView("No encontrado");
  }

  /* ---------------- Componentes compartidos ---------------- */
  function formatAuthors(authorsStr) {
    if (!authorsStr) return null;
    var names = authorsStr.split(",").map(function (s) { return s.trim(); }).filter(Boolean);
    if (names.length > 6) return names.slice(0, 6).join(", ") + " et al.";
    return names.join(", ");
  }

  // "manual" = Javier lo confirmó · "draft" = viene de un borrador IA, sin
  // revisar todavía · "pubtype"/"heuristic" = detectado automáticamente por
  // el pipeline, con distinto grado de confianza. site.json promete que todo
  // lo detectado automáticamente se marca como estimado; antes solo el N
  // heurístico llevaba el calificativo y el diseño nunca (hallazgo de
  // verificación).
  // "draft" no lleva sufijo en esta fila: solo aparece en tarjetas de
  // resúmenes que ya muestran el pill de estado de la tarjeta, y la ficha
  // del detalle conserva el calificativo completo.
  function _confidenceSuffix(confidence) {
    if (confidence === "heuristic") return " (estimado)";
    return "";
  }
  function buildDesignRow(opts) {
    var parts = [];
    if (opts.isPreprint) parts.push(el("span", { class: "preprint-flag" }, "Preprint · sin revisión por pares"));
    if (opts.design && opts.design.id) {
      var dLabel = designLabel(opts.design.id, opts.labelsMap) + _confidenceSuffix(opts.design.confidence);
      var dSpan = el("span", {}, dLabel);
      if (opts.design.confidence === "heuristic") {
        dSpan.setAttribute("title", "Detectado automáticamente a partir del resumen; puede ser impreciso");
      }
      parts.push(dSpan);
    }
    if (opts.sampleSize && typeof opts.sampleSize.value === "number") {
      var conf = opts.sampleSize.confidence;
      var symbol = conf === "heuristic" ? "N ≈ " : "N = ";
      var nText = symbol + Number(opts.sampleSize.value).toLocaleString("es-PE") + _confidenceSuffix(conf);
      var span = el("span", { class: "n-est" }, nText);
      if (conf === "heuristic") span.setAttribute("title", "Estimado automáticamente a partir del resumen; puede ser impreciso");
      parts.push(span);
    }
    if (!parts.length) return null;
    var row = el("div", { class: "design-row" });
    parts.forEach(function (p, i) { if (i > 0) row.appendChild(document.createTextNode(" · ")); row.appendChild(p); });
    return row;
  }

  function buildTagsRow(tagIds, labelsMap, withAutoLabel) {
    if (!tagIds || !tagIds.length) return null;
    var row = el("div", { class: "tags-row" });
    if (withAutoLabel) row.appendChild(el("span", { class: "tags-label" }, "Etiquetas automáticas"));
    tagIds.forEach(function (id, i) {
      if (i > 0) row.appendChild(document.createTextNode(" · "));
      row.appendChild(el("span", {}, tagLabel(id, labelsMap)));
    });
    return row;
  }

  function buildRegLine(paper) {
    if (!paper) return null;
    var parts = [];
    if (paper.pmcid) parts.push(paper.pmcid);
    if (paper.doi) parts.push("doi " + paper.doi);
    var oa = paper.open_access || {};
    var isFreeToRead = oa.status === "free_to_read" || oa.access_type === "free_to_read";
    if (isFreeToRead) parts.push("acceso gratuito");
    var licLabel = oa.license_label || licenseLabel(oa.license);
    if (licLabel) parts.push(licLabel);
    if (paper.first_index_date) parts.push("indexado " + paper.first_index_date);
    else if (oa.checked_at) parts.push((isFreeToRead ? "acceso comprobado " : "OA verificado ") + String(oa.checked_at).slice(0, 10));
    if (!parts.length) return null;
    var line = el("p", { class: "reg-line" });
    line.appendChild(el("span", { class: isFreeToRead ? "access-mark" : "oa-mark" },
      el("span", { class: "visually-hidden" }, isFreeToRead ? "Acceso gratuito; licencia no verificada" : "Open access verificado")));
    line.appendChild(document.createTextNode(parts.join(" · ")));
    return line;
  }

  function summaryLabel(summary) {
    var base = summary.section === "abstract_tail" ? "Cierre del resumen original" : "Conclusión de los autores";
    var out = base + " (idioma original, sin editar)";
    if (summary.truncated) out += " · recortado";
    return out;
  }
  function buildSummaryBlock(summary, paperSource) {
    var block = el("div", { class: "summary-block" });
    if (!summary) {
      // Hallazgo de verificación: en ~39% de los ítems fuente PMC, la
      // búsqueda "core" de Europe PMC no trae abstractText aunque el
      // artículo sí lo tenga (verificable en su fullTextXML) — "sin
      // resumen" afirmaba algo que no es cierto para esos casos.
      var msg = paperSource === "PMC"
        ? "El registro de búsqueda de Europe PMC no incluye el resumen para este artículo; consúltalo en el texto completo."
        : "Sin resumen disponible en Europe PMC.";
      block.appendChild(el("p", {}, msg));
      return block;
    }
    block.appendChild(el("p", { class: "summary-label label-upper" }, summaryLabel(summary)));
    var p = el("p", {}, summary.text);
    if (summary.lang) p.setAttribute("lang", summary.lang);
    block.appendChild(p);
    return block;
  }
  function buildAiSummaryBlock(aiSummary) {
    if (!aiSummary) return null;
    var block = el("div", { class: "ai-summary-block" });
    // POLITICA-EDITORIAL promete mostrar modelo Y fecha de generación; antes
    // solo se mostraba el modelo (hallazgo de verificación).
    var genDate = aiSummary.generated_at ? String(aiSummary.generated_at).slice(0, 10) : null;
    block.appendChild(el("p", { class: "summary-label label-upper" },
      "Resumen generado con IA (" + aiSummary.model + (genDate ? ", " + genDate : "") + ") · no revisado por un humano"));
    var p = el("p", {}, aiSummary.text);
    if (aiSummary.lang) p.setAttribute("lang", aiSummary.lang);
    block.appendChild(p);
    return block;
  }

  var LANG_WORDS = { en: "inglés", es: "español", pt: "portugués" };
  function buildAbstractDetails(abstract) {
    if (!abstract) return null;
    // El lang="..." iba en <details>, que también envuelve el <summary> y la
    // nota de recorte en español: un lector de pantalla anunciaba ese texto
    // en inglés. Se mueve al contenedor del contenido en el idioma
    // original únicamente; "(inglés)" fijo se reemplaza por el idioma real
    // cuando se conoce (abstract.lang), o un rótulo neutral si no (hallazgo
    // de verificación, enmienda 15).
    var det = el("details", { class: "abstract-original" });
    var langWord = LANG_WORDS[abstract.lang] || "idioma original";
    det.appendChild(el("summary", {}, "Ver resumen original (" + langWord + ")"));
    var body = el("div", {});
    if (abstract.lang) body.setAttribute("lang", abstract.lang);
    if (abstract.sections && abstract.sections.length > 0) {
      abstract.sections.forEach(function (sec) {
        var s = el("div", { class: "abs-section" });
        if (sec.heading) s.appendChild(el("p", { class: "abs-heading label-upper" }, sec.heading));
        s.appendChild(el("p", {}, sec.text));
        body.appendChild(s);
      });
    } else if (abstract.text) {
      abstract.text.split(/\n\n+/).forEach(function (para) { body.appendChild(el("p", {}, para)); });
    }
    det.appendChild(body);
    if (abstract.truncated) det.appendChild(el("p", { class: "abs-note" },
      "Resumen recortado en esta instantánea; el texto completo está en Europe PMC."));
    return det;
  }

  function buildPaperLinks(links) {
    if (!links) return null;
    var items = [];
    var fullText = links.fulltext_html || links.europepmc;
    // fulltext_html apunta a la revista (vía DOI) cuando el paper no tiene
    // PMCID (regla OA v2, ruta B); el rótulo debe reflejar el destino real
    // del enlace, no asumir siempre Europe PMC.
    var fullTextLabel = (typeof fullText === "string" && fullText.indexOf("europepmc.org") !== -1)
      ? "Texto completo en Europe PMC" : "Texto completo en la revista";
    var a1 = extLinkStrict(fullTextLabel, fullText);
    var a2 = extLinkStrict("PDF", links.pdf);
    var a3 = extLinkStrict("DOI", links.doi);
    [a1, a2, a3].forEach(function (a) { if (a) items.push(a); });
    if (!items.length) return null;
    var row = el("div", { class: "paper-links" });
    items.forEach(function (a) { row.appendChild(a); });
    return row;
  }

  var EPMC_LANG_TO_BCP47 = { eng: "en", spa: "es", por: "pt" };
  function paperTitleLangAttr(paper) {
    // Antes lang="en" fijo en los 3 sitios donde se muestra un título
    // original (aunque paper.language sea null, como en el preprint
    // PPR1313962, o spa/por con la cláusula Perú) — hallazgo de
    // verificación.
    return EPMC_LANG_TO_BCP47[paper && paper.language] || null;
  }
  function buildPaperArticle(paper, labelsMap) {
    var art = el("article", { class: "paper" });
    var titleAttrs = {};
    var titleLang = paperTitleLangAttr(paper);
    if (titleLang) titleAttrs.lang = titleLang;
    art.appendChild(el("h3", {}, el("span", titleAttrs, paper.title)));
    var authors = formatAuthors(paper.authors);
    if (authors) art.appendChild(el("p", { class: "authors" }, authors));
    var venueParts = [];
    if (paper.journal) venueParts.push(paper.journal);
    if (paper.pub_year) venueParts.push(String(paper.pub_year));
    if (venueParts.length) art.appendChild(el("p", { class: "venue" }, venueParts.join(" · ")));
    var dRow = buildDesignRow({ isPreprint: paper.is_preprint, design: paper.study_design, sampleSize: paper.sample_size, labelsMap: labelsMap });
    if (dRow) art.appendChild(dRow);
    var tRow = buildTagsRow(paper.tags, labelsMap, true);
    if (tRow) art.appendChild(tRow);
    art.appendChild(buildSummaryBlock(paper.summary, paper.source));
    var aiBlock = buildAiSummaryBlock(paper.ai_summary);
    if (aiBlock) art.appendChild(aiBlock);
    var linksRow = buildPaperLinks(paper.links);
    if (linksRow) art.appendChild(linksRow);
    var absDet = buildAbstractDetails(paper.abstract);
    if (absDet) art.appendChild(absDet);
    var reg = buildRegLine(paper);
    if (reg) art.appendChild(reg);
    return art;
  }

  function buildBadges(item) {
    // {short: texto visible en pill de galería, full: texto completo (detalle + texto accesible)}
    var badges = [];
    function add(short, full) { badges.push({ short: short, full: full }); }
    if (item.example && item.status === "draft" && item.ai_draft) {
      add("Borrador IA · ejemplo", "Borrador de ejemplo · IA · sin revisión humana");
    } else {
      if (item.example) add("Ejemplo", "Borrador de ejemplo");
      if (item.status === "draft") {
        if (item.ai_draft) add("Borrador IA", "Borrador IA · pendiente de revisión");
        else add("Borrador", "Borrador");
      } else if (item.status === "published" && item.ai_draft) {
        add("Generado con IA", "Resumen generado con IA · no revisado por un humano");
      } else if (item.status === "published" && item.adapted_with_ai) {
        // Distinto de "Asistido por IA": aquí el texto es del autor humano y
        // la IA solo lo adaptó al formato del sitio (nunca lo redactó), y son
        // excluyentes por contrato (ai_draft y adapted_with_ai no pueden ser
        // ambos true en published).
        add("Adaptado con IA", "Resumen de " + (item.author || "") + " · adaptado al formato del sitio con asistencia de IA");
      }
    }
    return badges;
  }

  function buildStatusPill(badge, id) {
    var attrs = { class: "pill pill-ai", title: badge.full };
    if (id) attrs.id = id;
    return el("span", attrs, [
      el("span", { "aria-hidden": "true" }, badge.short),
      el("span", { class: "visually-hidden" }, badge.full)
    ]);
  }

  function buildSummaryCard(item, labelsMap) {
    var tags = item.tags || [];
    // aria-labelledby en el article: sin esto, el article no tenía nombre
    // accesible (hallazgo de verificación).
    var titleId = "gcard-title-" + item.slug;
    var card = el("article", { class: "gcard", "aria-labelledby": titleId });

    var body = el("div", { class: "gcard-body" });

    // Fila 1: estado de borrador IA / preprint + fecha. Se construye antes
    // que el título para poder enlazar el pill de estado al enlace vía
    // aria-describedby: antes, quien navegaba por Tab o por la lista de
    // enlaces del lector de pantalla oía solo el título, sin "sin revisión
    // humana" (hallazgo de verificación).
    var statusRow = el("div", { class: "gcard-row" });
    var describedBy = [];
    buildBadges(item).forEach(function (b, i) {
      var pid = "gcard-status-" + item.slug + (i ? "-" + i : "");
      describedBy.push(pid);
      statusRow.appendChild(buildStatusPill(b, pid));
    });
    if (item.paper && item.paper.is_preprint) {
      var preprintId = "gcard-preprint-" + item.slug;
      describedBy.push(preprintId);
      statusRow.appendChild(el("span", { class: "pill pill-preprint", id: preprintId }, "Preprint · sin revisión por pares"));
    }
    if (item.date) statusRow.appendChild(el("time", { class: "gcard-date", datetime: item.date }, formatDateShort(item.date)));

    var linkAttrs = { class: "gcard-link", href: "#/resumenes/" + item.slug };
    if (describedBy.length) linkAttrs["aria-describedby"] = describedBy.join(" ");
    body.appendChild(el("h3", { class: "gcard-title", id: titleId }, el("a", linkAttrs, item.title)));
    if (statusRow.childNodes.length) body.appendChild(statusRow);

    // Fila 2: etiquetas (multi-select)
    if (tags.length) {
      var ul = el("ul", { class: "gcard-row gcard-tags", "aria-label": "Etiquetas" });
      tags.forEach(function (id) {
        ul.appendChild(el("li", { class: "pill pill-c-" + pillFamily(TAG_COLOR, id) }, tagLabel(id, labelsMap)));
      });
      body.appendChild(ul);
    }

    // Fila 3: tipo de resumen · diseño (select) · N · licencia
    var metaRow = el("div", { class: "gcard-row" });
    metaRow.appendChild(el("span", { class: "pill pill-type" }, [
      el("span", { class: "visually-hidden" }, "Tipo de resumen: "),
      summaryTypeLabel(item.summary_type, labelsMap)
    ]));
    var dsg = item.study_design;
    if (dsg && dsg.id) {
      var dPill = el("span", { class: "pill pill-c-" + pillFamily(DESIGN_COLOR, dsg.id) }, [
        el("span", { class: "visually-hidden" }, "Diseño: "),
        designLabel(dsg.id, labelsMap) + _confidenceSuffix(dsg.confidence)
      ]);
      if (dsg.confidence === "heuristic") dPill.setAttribute("title", "Detectado automáticamente a partir del resumen; puede ser impreciso");
      metaRow.appendChild(dPill);
    }
    var ss = item.sample_size;
    if (ss && typeof ss.value === "number") {
      var nSpan = el("span", { class: "gcard-n" },
        (ss.confidence === "heuristic" ? "N ≈ " : "N = ") + Number(ss.value).toLocaleString("es-PE") + _confidenceSuffix(ss.confidence));
      if (ss.confidence === "heuristic") nSpan.setAttribute("title", "Estimado automáticamente a partir del resumen; puede ser impreciso");
      metaRow.appendChild(nSpan);
    }
    var oa = (item.paper && item.paper.open_access) || {};
    var isFreeToRead = oa.status === "free_to_read" || oa.access_type === "free_to_read";
    if (isFreeToRead) metaRow.appendChild(el("span", { class: "pill pill-access" }, "Acceso gratuito"));
    var lic = oa.license_label || (oa.license ? licenseLabel(oa.license) : null);
    if (lic) metaRow.appendChild(el("span", { class: "pill pill-outline" }, [el("span", { class: "visually-hidden" }, "Licencia: "), lic]));
    if (metaRow.childNodes.length) body.appendChild(metaRow);

    // Cover: inicio del contenido (one_liner) sobre el tinte de la etiqueta
    // principal. Va después de .gcard-body en el DOM (order:-1 en CSS lo
    // sube visualmente): antes el one_liner se leía en voz alta ANTES que
    // el título de la tarjeta (hallazgo de verificación).
    var cover = el("div", { class: "gcard-cover" + (tags.length ? " pc-" + pillFamily(TAG_COLOR, tags[0]) : "") });
    if (item.principle && item.principle.statement) {
      cover.appendChild(el("p", { class: "gcard-cover-label label-upper" }, "Principio"));
      cover.appendChild(el("p", { class: "gcard-cover-text" }, item.principle.statement));
    } else if (item.one_liner) {
      cover.appendChild(el("p", { class: "gcard-cover-label label-upper" }, "En una frase"));
      cover.appendChild(el("p", { class: "gcard-cover-text" }, item.one_liner));
    } else {
      cover.appendChild(el("p", { class: "gcard-cover-text is-pending" }, "Sección pendiente de redacción."));
    }

    card.appendChild(body);
    card.appendChild(cover);
    return card;
  }

  function buildFicha(item, labelsMap) {
    var paper = item.paper || {};
    var aside = el("aside", { class: "ficha", "aria-label": "Ficha del artículo" });
    aside.appendChild(el("h2", { class: "label-upper" }, "Ficha del artículo"));
    var dl = el("dl", {});
    function row(term, valueNode) {
      if (!valueNode) return;
      dl.appendChild(el("dt", { class: "label-upper" }, term));
      dl.appendChild(el("dd", {}, valueNode));
    }
    row("Tipo de resumen", item.summary_type ? summaryTypeLabel(item.summary_type, labelsMap) : null);
    var fichaTitleAttrs = { class: "ficha-en" };
    var fichaTitleLang = paperTitleLangAttr(paper);
    if (fichaTitleLang) fichaTitleAttrs.lang = fichaTitleLang;
    row("Título original", paper.title ? el("span", fichaTitleAttrs, paper.title) : null);
    row("Autores", paper.authors || null);
    row("Revista", paper.journal || null);
    row("Año", paper.pub_year ? String(paper.pub_year) : null);
    row("Fecha de publicación", paper.first_publication_date ? formatDateShort(paper.first_publication_date) : null);
    if (paper.is_preprint) row("Tipo", "Preprint · sin revisión por pares");
    var dsg = item.study_design;
    if (dsg && dsg.id) {
      var suffix = item.ai_draft ? " (indicado en el borrador)" : " (indicado por el curador)";
      row("Diseño", designLabel(dsg.id, labelsMap) + suffix);
    }
    if (item.sample_size && typeof item.sample_size.value === "number" &&
      (item.sample_size.confidence === "manual" || item.sample_size.confidence === "draft")) {
      var nSuffix = item.sample_size.confidence === "draft" ? " (indicado en el borrador)" : "";
      row("N", "N = " + Number(item.sample_size.value).toLocaleString("es-PE") + nSuffix);
    }
    var oa = paper.open_access || {};
    var isFreeToRead = oa.status === "free_to_read" || oa.access_type === "free_to_read";
    row("Acceso", isFreeToRead ? "Acceso gratuito · no es open access" : "Open access verificado");
    row("Licencia", oa.license_label || (oa.license ? licenseLabel(oa.license) : null));
    aside.appendChild(dl);
    var reg = buildRegLine(paper);
    if (reg) aside.appendChild(reg);
    var links = buildPaperLinks(paper.links);
    if (links) aside.appendChild(links);
    // "Palabras propias" atribuye autoría humana; en un borrador IA (todavía
    // sin revisión) eso es exactamente lo que la Enmienda 1 prohíbe sugerir
    // (hallazgo de verificación).
    var provenanceNote;
    if (item.adapted_with_ai && item.status === "published" && !item.ai_draft) {
      // El texto es del autor humano; la IA solo lo adaptó al formato del
      // sitio. No afirma que el autor revisó esa adaptación (Enmienda de
      // integridad del contrato v2).
      provenanceNote = "Resumen de " + item.author + " · adaptado al formato del sitio con asistencia de IA. No reemplaza la lectura del original.";
    } else if (item.ai_draft && item.status === "draft") {
      provenanceNote = "Borrador redactado con IA a partir del resumen del artículo; pendiente de revisión humana. No reemplaza la lectura del original.";
    } else if (item.ai_draft) {
      provenanceNote = "Resumen generado con asistencia de IA a partir del artículo; no ha sido revisado por un humano. No reemplaza la lectura del original.";
    } else {
      provenanceNote = "Resumen escrito con palabras propias a partir del artículo; no reemplaza la lectura del original.";
    }
    aside.appendChild(el("p", { class: "ficha-note" }, provenanceNote));
    return aside;
  }

  // Bloques planos (p/ul/ol/kv) tal como los define el esquema v2; se usa
  // tanto en el dispatch genérico de ## como en las subsecciones ### de la
  // nota completa (mismo vocabulario de bloques en ambos niveles).
  function appendBlocksGeneric(container, blocks) {
    (blocks || []).forEach(function (b) {
      if (b.type === "p") {
        container.appendChild(el("p", {}, b.text));
      } else if (b.type === "ul") {
        var ul = el("ul", {});
        (b.items || []).forEach(function (it) { ul.appendChild(el("li", {}, it)); });
        container.appendChild(ul);
      } else if (b.type === "ol") {
        var ol = el("ol", {});
        (b.items || []).forEach(function (it) { ol.appendChild(el("li", {}, it)); });
        container.appendChild(ol);
      } else if (b.type === "kv") {
        var dl = el("dl", { class: "kv-list" });
        (b.items || []).forEach(function (kvItem) {
          dl.appendChild(el("dt", {}, kvItem.key));
          dl.appendChild(el("dd", {}, kvItem.value));
        });
        container.appendChild(dl);
      }
    });
  }

  function buildSectionShell(heading) {
    var s = el("section", {});
    s.appendChild(el("h2", {}, heading));
    var body = el("div", { class: "section-body" });
    s.appendChild(body);
    return { section: s, body: body };
  }

  function buildGenericSection(sec) {
    var shell = buildSectionShell(sec.heading);
    if (sec.pending) shell.body.appendChild(el("p", { class: "pending-note" }, "Sección pendiente de redacción."));
    else appendBlocksGeneric(shell.body, sec.blocks);
    return shell.section;
  }

  // Ficha rápida: dl.kv-grid a partir de item.quick_facts (el accesor
  // estructurado; sec.blocks trae el mismo contenido como kv plano, pero
  // aquí conviene el tipado).
  function buildFichaRapidaSection(sec, item) {
    var shell = buildSectionShell(sec.heading);
    var facts = item.quick_facts;
    if (sec.pending || !facts || !facts.length) {
      shell.body.appendChild(el("p", { class: "pending-note" }, "Sección pendiente de redacción."));
    } else {
      var dl = el("dl", { class: "kv-grid" });
      facts.forEach(function (f) {
        dl.appendChild(el("dt", { class: "label-upper" }, f.key));
        dl.appendChild(el("dd", {}, f.value));
      });
      shell.body.appendChild(dl);
    }
    return shell.section;
  }

  // El argumento (conceptual): párrafo(s) + a lo más un ol de pasos, con la
  // numeración nativa del <ol> (nunca "01/02/03" decorativo).
  function buildArgumentoSection(sec) {
    var shell = buildSectionShell(sec.heading);
    if (sec.pending) {
      shell.body.appendChild(el("p", { class: "pending-note" }, "Sección pendiente de redacción."));
    } else {
      (sec.blocks || []).forEach(function (b) {
        if (b.type === "p") {
          shell.body.appendChild(el("p", {}, b.text));
        } else if (b.type === "ol") {
          var ol = el("ol", { class: "argument-steps" });
          (b.items || []).forEach(function (it) { ol.appendChild(el("li", {}, it)); });
          shell.body.appendChild(ol);
        }
      });
    }
    return shell.section;
  }

  // Limitaciones: cada ítem trae un prefijo "Categoría: texto"; se separa en
  // el primer ": " para resaltar solo la categoría (span.lim-cat).
  function buildLimitacionesSection(sec) {
    var shell = buildSectionShell(sec.heading);
    if (sec.pending) {
      shell.body.appendChild(el("p", { class: "pending-note" }, "Sección pendiente de redacción."));
    } else {
      var ulBlock = (sec.blocks || []).filter(function (b) { return b.type === "ul"; })[0];
      var ul = el("ul", { class: "limitations" });
      (ulBlock ? ulBlock.items : []).forEach(function (raw) {
        var idx = raw.indexOf(": ");
        var li = el("li", {});
        if (idx > -1) {
          li.appendChild(el("span", { class: "lim-cat" }, raw.slice(0, idx)));
          li.appendChild(document.createTextNode(": " + raw.slice(idx + 2)));
        } else {
          li.appendChild(document.createTextNode(raw));
        }
        ul.appendChild(li);
      });
      shell.body.appendChild(ul);
    }
    return shell.section;
  }

  // Por qué importa para la clínica: párrafo(s) interpretativos + un ul
  // opcional de aplicaciones, cada una con un fragmento "Límite: …" resaltado.
  function buildClinicaSection(sec) {
    var shell = buildSectionShell(sec.heading);
    if (sec.pending) {
      shell.body.appendChild(el("p", { class: "pending-note" }, "Sección pendiente de redacción."));
    } else {
      (sec.blocks || []).forEach(function (b) {
        if (b.type === "p") {
          shell.body.appendChild(el("p", {}, b.text));
        } else if (b.type === "ul") {
          var ul = el("ul", { class: "applications" });
          (b.items || []).forEach(function (raw) {
            var idx = raw.indexOf("Límite:");
            var li = el("li", {});
            if (idx > -1) {
              li.appendChild(document.createTextNode(raw.slice(0, idx)));
              li.appendChild(el("span", { class: "app-limit" }, raw.slice(idx)));
            } else {
              li.appendChild(document.createTextNode(raw));
            }
            ul.appendChild(li);
          });
          shell.body.appendChild(ul);
        }
      });
    }
    return shell.section;
  }

  // Glosario y Lecturas recomendadas: plegables (mismo patrón que
  // details.abstract-original), a partir de los accesores estructurados
  // item.glossary / item.readings.
  function buildGlosarioSection(sec, item) {
    var shell = buildSectionShell(sec.heading);
    var terms = item.glossary;
    if (sec.pending || !terms || !terms.length) {
      shell.body.appendChild(el("p", { class: "pending-note" }, "Sección pendiente de redacción."));
    } else {
      var det = el("details", { class: "fold" });
      det.appendChild(el("summary", {}, "Glosario (" + terms.length + " términos)"));
      var dl = el("dl", {});
      terms.forEach(function (g) {
        dl.appendChild(el("dt", {}, g.term));
        dl.appendChild(el("dd", {}, g.definition));
      });
      det.appendChild(dl);
      shell.body.appendChild(det);
    }
    return shell.section;
  }

  function buildLecturasSection(sec, item) {
    var shell = buildSectionShell(sec.heading);
    var readings = item.readings;
    if (sec.pending || !readings || !readings.length) {
      shell.body.appendChild(el("p", { class: "pending-note" }, "Sección pendiente de redacción."));
    } else {
      var det = el("details", { class: "fold" });
      det.appendChild(el("summary", {}, "Lecturas recomendadas (" + readings.length + ")"));
      var ul = el("ul", { class: "readings" });
      readings.forEach(function (r) {
        var li = el("li", { class: "reading-item" });
        li.appendChild(el("p", {}, r.citation));
        var label = r.doi ? "DOI" : (r.pmid ? "PMID" : "Enlace");
        var a = extLinkStrict(label, r.url);
        if (a) li.appendChild(a);
        if (r.why) li.appendChild(el("p", { class: "reading-why" }, r.why));
        ul.appendChild(li);
      });
      det.appendChild(ul);
      shell.body.appendChild(det);
    }
    return shell.section;
  }

  // El principio: no es una <section> genérica sino un <aside> con su
  // propio h2 (aria-labelledby), a partir de item.principle (el objeto
  // estructurado de 7 claves).
  function buildPrincipioAside(sec, item, labelsMap) {
    var aside = el("aside", { class: "principle", "aria-labelledby": "principle-heading" });
    aside.appendChild(el("h2", { id: "principle-heading" }, sec.heading || "El principio"));
    var p = item.principle;
    if (sec.pending || !p) {
      aside.appendChild(el("p", { class: "pending-note" }, "Sección pendiente de redacción."));
      return aside;
    }
    aside.appendChild(el("p", { class: "principle-statement" }, p.statement));
    var dl = el("dl", { class: "principle-meta" });
    function row(term, valueNode) {
      if (!valueNode) return;
      dl.appendChild(el("dt", {}, term));
      dl.appendChild(el("dd", {}, valueNode));
    }
    row("Fundamento", p.rationale);
    row("Evidencia", p.evidence);
    var strengthColor = STRENGTH_COLOR[p.strength] || "gray";
    row("Fuerza", el("span", { class: "pill pill-strength pill-c-" + strengthColor }, strengthLabel(p.strength, labelsMap)));
    if (p.transfer && p.transfer.length) {
      var transferWrap = el("span", {});
      p.transfer.forEach(function (t, i) {
        if (i > 0) transferWrap.appendChild(document.createTextNode(" "));
        transferWrap.appendChild(el("span", { class: "pill pill-outline" }, t));
      });
      row("Transferencia", transferWrap);
    }
    row("Límite", p.limit);
    row("Procedencia", PROVENANCE_LABEL[p.provenance] || p.provenance);
    aside.appendChild(dl);
    if (item.ai_draft && item.status === "draft") {
      aside.appendChild(el("p", { class: "principle-note" }, "Principio extraído con IA · pendiente de revisión"));
    }
    return aside;
  }

  function buildDetailSections(item, labelsMap) {
    var wrap = el("div", { class: "detail-sections" });
    (item.sections || []).forEach(function (sec) {
      if (sec.id === "en_una_frase") return; // ya se muestra como one-liner-display
      var node;
      switch (sec.id) {
        case "ficha_rapida": node = buildFichaRapidaSection(sec, item); break;
        case "principio": node = buildPrincipioAside(sec, item, labelsMap); break;
        case "argumento": node = buildArgumentoSection(sec); break;
        case "limitaciones": node = buildLimitacionesSection(sec); break;
        case "clinica": node = buildClinicaSection(sec); break;
        case "glosario": node = buildGlosarioSection(sec, item); break;
        case "lecturas": node = buildLecturasSection(sec, item); break;
        default: node = buildGenericSection(sec);
      }
      wrap.appendChild(node);
    });
    return wrap;
  }

  // Enlace interno de la nota completa: nunca toca location.hash (el router
  // por hash mostraría "No encontramos esa ruta" al recargar sobre un
  // fragmento #nc-…), solo desplaza y mueve el foco al destino.
  function bindInternalAnchor(a, targetId) {
    a.addEventListener("click", function (e) {
      var targetEl = document.getElementById(targetId);
      if (!targetEl) return;
      e.preventDefault();
      targetEl.scrollIntoView({ block: "start" });
      if (targetEl.focus) targetEl.focus({ preventScroll: true });
    });
  }

  function buildFullNote(item) {
    if (!item.full_note) return null;
    var wrap = el("section", { class: "full-note-wrap" });
    wrap.appendChild(el("h2", { id: "nota-completa" }, "Nota completa"));
    var det = el("details", { class: "full-note" });
    det.appendChild(el("summary", {}, "Abrir la nota completa (17 apartados)"));
    var fn = item.full_note;
    if (fn.pending) {
      det.appendChild(el("p", { class: "pending-note" }, "Sección pendiente de redacción."));
    } else {
      var nav = el("nav", { class: "full-note-index", "aria-label": "Índice de la nota completa" });
      var indexList = el("ol", {});
      (fn.sections || []).forEach(function (sub) {
        var a = el("a", { href: "#nc-" + sub.id }, sub.heading);
        bindInternalAnchor(a, "nc-" + sub.id);
        indexList.appendChild(el("li", {}, a));
      });
      nav.appendChild(indexList);
      det.appendChild(nav);

      (fn.sections || []).forEach(function (sub) {
        var subSec = el("section", { class: "full-note-section", id: "nc-" + sub.id, tabindex: "-1" });
        subSec.appendChild(el("h3", {}, sub.heading));
        if (sub.pending) subSec.appendChild(el("p", { class: "pending-note" }, "Sección pendiente de redacción."));
        else appendBlocksGeneric(subSec, sub.blocks);
        var back = el("a", { class: "full-note-back", href: "#nota-completa" }, "Volver al índice");
        bindInternalAnchor(back, "nota-completa");
        subSec.appendChild(back);
        det.appendChild(subSec);
      });
    }
    if (item.ai_draft && item.status === "draft") {
      det.appendChild(el("p", { class: "full-note-note" }, "Extracción con IA a partir del texto del artículo · pendiente de revisión"));
    }
    wrap.appendChild(det);
    return wrap;
  }

  /* ---------------- Vistas ---------------- */
  function viewHome(isCurrent) {
    renderLoading();
    Promise.all([
      loadSite().catch(function () { return null; }),
      loadSummaries(),
      loadDailyIndex()
    ]).then(function (results) {
      if (!isCurrent()) return;
      var site = results[0] || SITE_FALLBACK;
      var summaries = results[1];
      var index = results[2];
      if (!summaries) { renderErrorState("data/summaries.json"); return; }
      if (!index) { renderErrorState("data/daily/index.json"); return; }
      // Antes, un fallo de RED al cargar el día más reciente se disfrazaba
      // de "día sin papers" (mismo `null`), contradiciendo el propio hero de
      // la misma página, que sí mostraba el conteo real (hallazgo de
      // verificación). Se distingue el error del vacío genuino.
      var latestDayPromise = index.latest
        ? loadDailyDay(index.latest).then(
          function (d) { return { ok: true, day: d }; },
          function (e) { return { ok: false, path: e && e.path }; }
        )
        : Promise.resolve({ ok: true, day: null });
      latestDayPromise.then(function (result) {
        if (!isCurrent()) return;
        renderHome(site, summaries, index, result.ok ? result.day : null, result.ok ? null : (result.path || "data/daily/" + index.latest + ".json"));
        finishView("Inicio");
      });
    }).catch(function (e) {
      if (!isCurrent()) return;
      renderErrorState(e.path || "data/summaries.json");
    });
  }

  // Etiquetas que nombran un cuadro clínico psiquiátrico real (mismo
  // criterio que apply_relevance en common.py); solo estas cuentan para
  // decidir si un paper es "on-topic" en el teaser del Inicio.
  var CORE_CLINICAL_TAGS = ["psychosis", "depression", "anxiety", "suicide", "adhd", "bipolar", "bpd",
    "alcohol", "substances", "ptsd", "ocd", "eating", "symptom_networks"];

  function renderHome(site, summaries, index, latestDay, latestDayErrorPath) {
    clearMain();
    var c = mountContainer();
    var hero = el("section", { class: "hero" });
    hero.appendChild(el("h1", {}, site.site.name));
    if (site.site.tagline) hero.appendChild(el("p", { class: "tagline" }, site.site.tagline));

    var items = summaries.items || [];
    var publishedCount = items.filter(function (i) { return i.status === "published"; }).length;
    var exampleCount = items.filter(function (i) { return i.example === true; }).length;
    var statusParts = [];
    if (publishedCount > 0) statusParts.push(publishedCount + (publishedCount === 1 ? " resumen publicado" : " resúmenes publicados"));
    if (exampleCount > 0) statusParts.push(exampleCount + (exampleCount === 1 ? " borrador de ejemplo" : " borradores de ejemplo"));
    if (!statusParts.length) statusParts.push("Sin resúmenes todavía");
    var latestEntry = index.latest ? (index.days || []).filter(function (d) { return d.date === index.latest; })[0] : null;
    if (latestEntry) statusParts.push("último feed: " + formatDateShort(latestEntry.date) + " · " + latestEntry.count + " papers OA");
    else statusParts.push("feed: aún no generado");
    hero.appendChild(el("p", { class: "hero-status mono" }, statusParts.join(" · ")));
    c.appendChild(hero);

    var sumSection = el("section", { class: "section-block" });
    sumSection.appendChild(el("h2", {}, "Últimos resúmenes"));
    var sumBody = el("div", { class: "section-body" });
    if (items.length === 0) {
      sumBody.appendChild(el("div", { class: "state" }, el("p", {}, [
        "Todavía no hay resúmenes. Crea uno con ", el("code", {}, "python3 scripts/add_paper.py <DOI>"),
        " y luego ", el("code", {}, "python3 scripts/build_summaries.py"), "."
      ])));
    } else {
      var grid = el("div", { class: "card-grid" });
      items.slice(0, 3).forEach(function (item) { grid.appendChild(buildSummaryCard(item, summaries.labels)); });
      sumBody.appendChild(grid);
      sumBody.appendChild(el("p", {}, el("a", { href: "#/resumenes" }, "Ver todos los resúmenes →")));
    }
    sumSection.appendChild(sumBody);
    c.appendChild(sumSection);

    var paperSection = el("section", { class: "section-block" });
    paperSection.appendChild(el("h2", {}, index.latest ? "Papers indexados el " + formatDateLong(index.latest) : "Papers del día"));
    var paperBody = el("div", { class: "section-body" });
    if (!index.latest) {
      paperBody.appendChild(el("div", { class: "state" }, el("p", {}, [
        "Aún no hay feed. Genera uno con ", el("code", {}, "python3 scripts/fetch_daily.py --days 3"), "."
      ])));
    } else if (latestDayErrorPath) {
      paperBody.appendChild(el("div", { class: "state" }, el("p", {},
        "No se pudo cargar el feed del " + formatDateShort(index.latest) + " (" + latestDayErrorPath + "). Revisa tu conexión y reintenta.")));
    } else if (!latestEntry || latestEntry.count === 0 || !latestDay || !latestDay.items || latestDay.items.length === 0) {
      paperBody.appendChild(el("div", { class: "state" }, el("p", {},
        "No se indexaron papers open access el " + formatDateLong(index.latest) +
        ". Los fines de semana y feriados suelen traer menos registros.")));
    } else {
      // Solo papers con señal clínica clara y score positivo en el teaser
      // del Inicio: el feed completo (enlace abajo) sigue mostrando todo,
      // pero esta vitrina no debe abrir con un paper de anestesia o de
      // glaucoma que solo mencionó "mental health" de pasada (hallazgo de
      // verificación).
      var onTopic = latestDay.items.filter(function (p) {
        var score = p.relevance && typeof p.relevance.score === "number" ? p.relevance.score : 0;
        var hasClinical = (p.tags || []).some(function (t) { return CORE_CLINICAL_TAGS.indexOf(t) !== -1; });
        return score > 0 && hasClinical;
      });
      var homeItems = onTopic.length ? onTopic : latestDay.items;
      var list = el("ul", { class: "paper-list" });
      homeItems.slice(0, 8).forEach(function (p) {
        var li = el("li", {});
        li.appendChild(buildPaperArticle(p, index.labels));
        list.appendChild(li);
      });
      paperBody.appendChild(list);
      paperBody.appendChild(el("p", {}, el("a", { href: "#/papers/" + index.latest }, "Ver los " + latestEntry.count + " del " + formatDateShort(index.latest) + " →")));
    }
    paperSection.appendChild(paperBody);
    c.appendChild(paperSection);
  }

  function viewPapersRedirect(isCurrent) {
    renderLoading();
    loadDailyIndex().then(function (index) {
      if (!isCurrent()) return;
      if (!index || !index.latest) { renderNoFeedYet(); return; }
      location.replace("#/papers/" + index.latest);
    }).catch(function (e) {
      if (!isCurrent()) return;
      renderErrorState(e.path || "data/daily/index.json");
    });
  }
  function renderNoFeedYet() {
    clearMain();
    var c = mountContainer();
    c.appendChild(el("div", { class: "state" }, [
      el("p", {}, "Aún no hay feed generado todavía."),
      el("p", {}, ["Genera el feed diario desde la raíz del proyecto con ", el("code", {}, "python3 scripts/fetch_daily.py --days 3"), "."])
    ]));
    finishView("Papers del día");
  }

  function viewPapersDay(dateStr, isCurrent) {
    renderLoading();
    if (!isValidDateStr(dateStr)) { showNotFound(null, "#/", "Ir al inicio"); return; }
    loadDailyIndex().then(function (index) {
      if (!isCurrent()) return;
      if (!index) { renderErrorState("data/daily/index.json"); return; }
      var entry = (index.days || []).filter(function (d) { return d.date === dateStr; })[0];
      if (!entry) {
        var latest = index.latest;
        showNotFound(
          "Ese día no está en el feed.",
          latest ? ("#/papers/" + latest) : "#/papers",
          latest ? "Ir al último día" : "Ver feed",
          "Ese día no está en el feed"
        );
        return;
      }
      loadDailyDay(dateStr).then(function (day) {
        if (!isCurrent()) return;
        if (!day) { renderErrorState("data/daily/" + dateStr + ".json"); return; }
        renderPapersDay(index, entry, day);
        finishView("Papers del " + formatDateShort(dateStr));
      }).catch(function (e) {
        if (!isCurrent()) return;
        renderErrorState(e.path || ("data/daily/" + dateStr + ".json"));
      });
    }).catch(function (e) {
      if (!isCurrent()) return;
      renderErrorState(e.path || "data/daily/index.json");
    });
  }

  function renderPapersDay(index, entry, day) {
    clearMain();
    var c = mountContainer();
    var labelsMap = index.labels || null;
    var totalCount = entry.count;
    var embeddedCount = (typeof day.embedded_count === "number") ? day.embedded_count : ((day.items || []).length);

    var header = el("div", { class: "day-header" });
    header.appendChild(el("h1", {}, "Indexados en Europe PMC el " + formatDateLong(entry.date)));
    var monoParts = [];
    if (typeof totalCount === "number") monoParts.push(totalCount + (totalCount === 1 ? " paper open access" : " papers open access"));
    if (day.fetched_at) monoParts.push("consulta ejecutada " + formatLimaDateTime(day.fetched_at));
    header.appendChild(el("p", { class: "day-mono" }, monoParts.join(" · ")));
    if (entry.complete === false) {
      header.appendChild(el("p", { class: "day-notice" }, "Día en curso: Europe PMC sigue indexando; vuelve mañana para el conteo completo."));
    }

    var nav = el("div", { class: "day-nav" });
    var idx = -1;
    (index.days || []).forEach(function (d, i) { if (d.date === entry.date) idx = i; });
    var prevEntry = idx > -1 ? index.days[idx + 1] : null;
    var nextEntry = idx > 0 ? index.days[idx - 1] : null;
    if (prevEntry) nav.appendChild(el("a", { href: "#/papers/" + prevEntry.date }, "← día anterior"));
    if (nextEntry) nav.appendChild(el("a", { href: "#/papers/" + nextEntry.date }, "día siguiente →"));
    // Enmienda de verificación: navegar en "change" hace que las flechas del
    // teclado sobre un <select> cerrado (Chrome/Edge en Windows, Firefox)
    // disparen un cambio de vista en CADA pulsación, así que nunca se puede
    // pasar de un día a otro con teclado (el <select> se destruye y recrea a
    // mitad de la navegación). Se navega solo al enviar el formulario.
    var selectField = el("form", { class: "day-select-field" });
    selectField.appendChild(el("label", { for: "day-select" }, "Ir a otro día"));
    var select = el("select", { id: "day-select" });
    (index.days || []).forEach(function (d) {
      var opt = el("option", { value: d.date }, formatDateShort(d.date) + " (" + d.count + ")");
      if (d.date === entry.date) opt.setAttribute("selected", "");
      select.appendChild(opt);
    });
    selectField.appendChild(select);
    selectField.appendChild(el("button", { type: "submit", class: "btn" }, "Ir"));
    selectField.addEventListener("submit", function (e) {
      e.preventDefault();
      location.hash = "#/papers/" + select.value;
    });
    nav.appendChild(selectField);
    header.appendChild(nav);
    c.appendChild(header);

    if (!day.items || day.items.length === 0) {
      var prevDate = prevEntry ? prevEntry.date : null;
      c.appendChild(el("div", { class: "state" }, [
        el("p", {}, "No se indexaron papers open access el " + formatDateLong(entry.date) +
          ". Los fines de semana y feriados suelen traer menos registros. Prueba el día anterior."),
        prevDate ? el("p", {}, el("a", { href: "#/papers/" + prevDate }, "← Ver " + formatDateLong(prevDate))) : null
      ]));
      return;
    }

    var availableTags = uniqueTagsIn(day.items);
    var availableDesigns = uniqueDesignsIn(day.items);
    var state = { tag: null, design: "" };

    var filters = el("div", { class: "filters" });
    var tagField = el("div", { class: "field" });
    tagField.appendChild(el("span", { class: "label-upper" }, "Etiquetas"));
    var chipRow = el("div", { class: "chip-row" });
    availableTags.forEach(function (id) {
      var chip = el("button", { type: "button", class: "chip", "aria-pressed": "false" }, tagLabel(id, labelsMap));
      chip.addEventListener("click", function () {
        state.tag = (state.tag === id) ? null : id;
        chipRow.querySelectorAll(".chip").forEach(function (b) { b.setAttribute("aria-pressed", "false"); });
        if (state.tag) chip.setAttribute("aria-pressed", "true");
        applyFilters();
      });
      chipRow.appendChild(chip);
    });
    tagField.appendChild(chipRow);
    filters.appendChild(tagField);

    var designField = el("div", { class: "field" });
    designField.appendChild(el("label", { for: "design-filter" }, "Diseño de estudio"));
    var designSelect = el("select", { id: "design-filter" });
    designSelect.appendChild(el("option", { value: "" }, "Todos"));
    availableDesigns.forEach(function (id) { designSelect.appendChild(el("option", { value: id }, designLabel(id, labelsMap))); });
    designSelect.addEventListener("change", function () { state.design = designSelect.value; applyFilters(); });
    designField.appendChild(designSelect);
    filters.appendChild(designField);
    c.appendChild(filters);

    // h2 visualmente oculto: sin él, la vista saltaba de h1 (cabecera de
    // jornada) a un h3 por cada paper, sin nivel intermedio (hallazgo de
    // verificación; WCAG 1.3.1/2.4.6).
    c.appendChild(el("h2", { class: "visually-hidden" }, "Papers del día"));
    var countLine = el("p", { class: "result-count", "aria-live": "polite" });
    c.appendChild(countLine);
    var list = el("ul", { class: "paper-list" });
    c.appendChild(list);
    var emptyFilterState = null;

    function applyFilters() {
      while (list.firstChild) list.removeChild(list.firstChild);
      if (emptyFilterState) { emptyFilterState.remove(); emptyFilterState = null; }
      var filtered = day.items.filter(function (p) {
        if (state.tag && (!p.tags || p.tags.indexOf(state.tag) === -1)) return false;
        if (state.design && (!p.study_design || p.study_design.id !== state.design)) return false;
        return true;
      });
      filtered.forEach(function (p) {
        var li = el("li", {});
        li.appendChild(buildPaperArticle(p, labelsMap));
        list.appendChild(li);
      });
      if (embeddedCount < totalCount) {
        countLine.textContent = filtered.length + " de " + embeddedCount +
          (embeddedCount === 1 ? " paper incluido" : " papers incluidos") +
          " en esta instantánea (el día tiene " + totalCount + ")";
      } else {
        countLine.textContent = filtered.length + " de " + day.items.length +
          (day.items.length === 1 ? " paper del día" : " papers del día");
      }
      if (filtered.length === 0) {
        emptyFilterState = el("div", { class: "state" });
        emptyFilterState.appendChild(el("p", {}, "Ningún paper de este día combina esos filtros."));
        var clearBtn = el("button", { type: "button", class: "btn" }, "Quitar filtros");
        clearBtn.addEventListener("click", function () {
          state.tag = null; state.design = "";
          chipRow.querySelectorAll(".chip").forEach(function (b) { b.setAttribute("aria-pressed", "false"); });
          designSelect.value = "";
          applyFilters();
        });
        emptyFilterState.appendChild(clearBtn);
        list.parentNode.insertBefore(emptyFilterState, list.nextSibling);
      }
    }
    applyFilters();

    if (embeddedCount < totalCount) {
      c.appendChild(el("p", { class: "snapshot-notice" },
        "Esta instantánea incluye " + embeddedCount + " de " + totalCount + " papers del día."));
    }
  }

  function viewResumenes(query, isCurrent) {
    renderLoading();
    loadSummaries().then(function (data) {
      if (!isCurrent()) return;
      if (!data) { renderErrorState("data/summaries.json"); return; }
      renderResumenesList(data, query || {});
      finishView("Resúmenes");
    }).catch(function (e) {
      if (!isCurrent()) return;
      renderErrorState(e.path || "data/summaries.json");
    });
  }

  function renderResumenesList(data, initialQuery) {
    clearMain();
    var c = mountContainer();
    var items = data.items || [];
    // Sin h1 propio, la vista abría directo en el buscador sin título ni
    // contexto y rompía la navegación por encabezados de lectores de
    // pantalla (hallazgo de verificación).
    c.appendChild(el("h1", {}, "Resúmenes"));
    c.appendChild(el("p", { class: "view-intro" },
      "Lecturas en español de artículos open access y reseñas de acceso gratuito claramente identificadas; el origen y la revisión humana se declaran en cada ficha."));
    if (items.length === 0) {
      c.appendChild(el("div", { class: "state" }, el("p", {}, [
        "Todavía no hay resúmenes. Crea uno con ", el("code", {}, "python3 scripts/add_paper.py <DOI>"),
        " y luego ", el("code", {}, "python3 scripts/build_summaries.py"), "."
      ])));
      return;
    }
    var labelsMap = data.labels || null;
    var availableTags = uniqueTagsIn(items);
    var availableDesigns = uniqueDesignsIn(items);

    var state = {
      q: initialQuery.q || "",
      tag: (initialQuery.tag && availableTags.indexOf(initialQuery.tag) !== -1) ? initialQuery.tag : null,
      design: (initialQuery.design && availableDesigns.indexOf(initialQuery.design) !== -1) ? initialQuery.design : "",
      type: (initialQuery.type === "empirico" || initialQuery.type === "conceptual") ? initialQuery.type : ""
    };

    var filters = el("div", { class: "filters" });
    var searchField = el("div", { class: "field" });
    searchField.appendChild(el("label", { for: "q" }, "Buscar en los resúmenes"));
    var input = el("input", { type: "search", id: "q", value: state.q });
    searchField.appendChild(input);
    filters.appendChild(searchField);

    var chipField = el("div", { class: "field" });
    chipField.appendChild(el("span", { class: "label-upper" }, "Etiquetas"));
    var chipRow = el("div", { class: "chip-row" });
    availableTags.forEach(function (id) {
      var pressed = state.tag === id;
      var chip = el("button", { type: "button", class: "chip", "aria-pressed": pressed ? "true" : "false" }, tagLabel(id, labelsMap));
      chip.addEventListener("click", function () {
        state.tag = (state.tag === id) ? null : id;
        chipRow.querySelectorAll(".chip").forEach(function (b) { b.setAttribute("aria-pressed", "false"); });
        if (state.tag) chip.setAttribute("aria-pressed", "true");
        syncAndRender();
      });
      chipRow.appendChild(chip);
    });
    chipField.appendChild(chipRow);
    filters.appendChild(chipField);

    var designField = el("div", { class: "field" });
    designField.appendChild(el("label", { for: "design-filter" }, "Diseño de estudio"));
    var designSelect = el("select", { id: "design-filter" });
    designSelect.appendChild(el("option", { value: "" }, "Todos"));
    availableDesigns.forEach(function (id) {
      var opt = el("option", { value: id }, designLabel(id, labelsMap));
      if (state.design === id) opt.setAttribute("selected", "");
      designSelect.appendChild(opt);
    });
    designSelect.addEventListener("change", function () { state.design = designSelect.value; syncAndRender(); });
    designField.appendChild(designSelect);
    filters.appendChild(designField);

    var typeField = el("div", { class: "field" });
    typeField.appendChild(el("label", { for: "type-filter" }, "Tipo de resumen"));
    var typeSelect = el("select", { id: "type-filter" });
    typeSelect.appendChild(el("option", { value: "" }, "Todos"));
    ["empirico", "conceptual"].forEach(function (id) {
      var opt = el("option", { value: id }, summaryTypeLabel(id, labelsMap));
      if (state.type === id) opt.setAttribute("selected", "");
      typeSelect.appendChild(opt);
    });
    typeSelect.addEventListener("change", function () { state.type = typeSelect.value; syncAndRender(); });
    typeField.appendChild(typeSelect);
    filters.appendChild(typeField);

    c.appendChild(filters);

    // h2 visualmente oculto: sin él, la vista saltaba de h1 ("Resúmenes") a
    // un h3 por cada tarjeta, sin nivel intermedio — mismo patrón que la
    // vista de papers del día (hallazgo de verificación; WCAG 1.3.1/2.4.6).
    c.appendChild(el("h2", { class: "visually-hidden" }, "Listado de resúmenes"));
    var countLine = el("p", { class: "result-count", "aria-live": "polite" });
    c.appendChild(countLine);
    var grid = el("div", { class: "card-grid" });
    c.appendChild(grid);

    var debouncedInput = debounce(function () { state.q = input.value; syncAndRender(); }, 150);
    input.addEventListener("input", debouncedInput);

    function syncAndRender() {
      var params = [];
      if (state.q) params.push("q=" + encodeURIComponent(state.q));
      if (state.tag) params.push("tag=" + encodeURIComponent(state.tag));
      if (state.design) params.push("design=" + encodeURIComponent(state.design));
      if (state.type) params.push("type=" + encodeURIComponent(state.type));
      var newHash = "#/resumenes" + (params.length ? "?" + params.join("&") : "");
      if (location.hash !== newHash) { try { history.replaceState(null, "", newHash); } catch (e) {} }
      renderList();
    }

    function renderList() {
      while (grid.firstChild) grid.removeChild(grid.firstChild);
      var qNorm = normalizeSearch(state.q);
      var filtered = items.filter(function (item) {
        if (state.tag && (!item.tags || item.tags.indexOf(state.tag) === -1)) return false;
        if (state.design && (!item.study_design || item.study_design.id !== state.design)) return false;
        if (state.type && item.summary_type !== state.type) return false;
        if (qNorm) {
          var hay = [item.title, item.one_liner,
            item.principle ? item.principle.statement : null,
            item.paper ? item.paper.title : null,
            item.paper ? item.paper.authors : null,
            item.paper ? item.paper.journal : null]
            .concat((item.tags || []).map(function (t) { return tagLabel(t, labelsMap); }))
            .concat((item.glossary || []).map(function (g) { return g.term; }))
            .concat((item.quick_facts || []).map(function (f) { return f.value; }))
            .filter(Boolean).map(normalizeSearch).join(" ");
          if (hay.indexOf(qNorm) === -1) return false;
        }
        return true;
      });
      countLine.textContent = filtered.length + " de " + items.length + " resúmenes";
      if (filtered.length === 0) {
        var empty = el("div", { class: "state" });
        var emptyMsg = state.q
          ? "Ningún resumen coincide con «" + state.q + "». Prueba con otra palabra o quita los filtros."
          : "Ningún resumen combina los filtros elegidos. Quita uno para ver más.";
        empty.appendChild(el("p", {}, emptyMsg));
        var clearBtn = el("button", { type: "button", class: "btn" }, "Quitar filtros");
        clearBtn.addEventListener("click", function () {
          state.q = ""; state.tag = null; state.design = ""; state.type = "";
          input.value = "";
          chipRow.querySelectorAll(".chip").forEach(function (b) { b.setAttribute("aria-pressed", "false"); });
          designSelect.value = "";
          typeSelect.value = "";
          syncAndRender();
        });
        empty.appendChild(clearBtn);
        grid.appendChild(empty);
        return;
      }
      filtered.forEach(function (item) { grid.appendChild(buildSummaryCard(item, labelsMap)); });
    }
    renderList();
  }

  function viewResumenDetail(slug, isCurrent) {
    renderLoading();
    if (!isValidSlug(slug)) { showNotFound(null, "#/resumenes", "Ver todos los resúmenes"); return; }
    loadSummaries().then(function (data) {
      if (!isCurrent()) return;
      if (!data) { renderErrorState("data/summaries.json"); return; }
      var item = (data.items || []).filter(function (i) { return i.slug === slug; })[0];
      if (!item) {
        showNotFound(
          "No encontramos ese resumen.", "#/resumenes", "Ver todos los resúmenes", "No encontramos ese resumen"
        );
        return;
      }
      renderResumenDetail(item, data.labels);
      finishView(item.title);
    }).catch(function (e) {
      if (!isCurrent()) return;
      renderErrorState(e.path || "data/summaries.json");
    });
  }

  function renderResumenDetail(item, labelsMap) {
    clearMain();
    var c = mountContainer();
    var header = el("div", { class: "detail-header" });

    // Fila de badges: la pill de tipo siempre está presente (summary_type es
    // obligatorio en el esquema v2), así que esta fila ya no depende de que
    // existan otros badges (borrador/ejemplo/IA) para renderizarse.
    var br = el("div", { class: "badges" });
    br.appendChild(el("span", { class: "pill pill-type" }, [
      el("span", { class: "visually-hidden" }, "Tipo de resumen: "),
      summaryTypeLabel(item.summary_type, labelsMap)
    ]));
    buildBadges(item).forEach(function (b) { br.appendChild(el("span", { class: "badge" }, b.full)); });
    header.appendChild(br);

    header.appendChild(el("h1", {}, item.title));
    var meta = el("div", { class: "detail-meta" });
    meta.appendChild(el("span", {}, formatDateLong(item.date)));
    if (item.author) meta.appendChild(el("span", {}, item.author));
    if (item.reading_minutes) meta.appendChild(el("span", {}, item.reading_minutes + " min de lectura"));
    header.appendChild(meta);

    // Procedencia visible cuando el texto es de Javier y la IA solo lo
    // adaptó al formato del sitio (nunca lo redactó): no afirma que él
    // revisó esa adaptación.
    if (item.adapted_with_ai && item.status === "published" && !item.ai_draft) {
      header.appendChild(el("p", { class: "provenance-line" },
        "Resumen de " + item.author + " · adaptado al formato del sitio con asistencia de IA"));
    } else if (item.ai_draft && item.status === "published") {
      header.appendChild(el("p", { class: "provenance-line" },
        "Resumen generado con IA · no revisado por un humano"));
    }
    c.appendChild(header);

    var enUnaFrase = (item.sections || []).filter(function (s) { return s.id === "en_una_frase"; })[0];
    var oneLinerText = item.one_liner;
    if (!oneLinerText && enUnaFrase && enUnaFrase.pending) oneLinerText = null;
    c.appendChild(el("p", { class: "one-liner-display" }, oneLinerText || "Sección pendiente de redacción."));

    // Capa Paper → Nota resumen: aside.ficha va PRIMERO en el DOM (así llega
    // primero en móvil y a lectores de pantalla); en ≥960px el CSS lo manda
    // de vuelta a la columna derecha con grid-column.
    var twoCol = el("div", { class: "two-col has-sidebar" });
    twoCol.appendChild(buildFicha(item, labelsMap));
    var mainCol = el("div", { class: "detail-main" });
    mainCol.appendChild(buildDetailSections(item, labelsMap));
    mainCol.appendChild(el("a", { href: "#/resumenes", class: "back-link" }, "← Todos los resúmenes"));
    twoCol.appendChild(mainCol);
    c.appendChild(twoCol);

    // Capa Nota completa: a ancho completo, debajo del grid, solo si el
    // resumen es empírico y trae nota completa.
    var fullNote = buildFullNote(item);
    if (fullNote) c.appendChild(fullNote);
  }

  function viewAcerca(isCurrent) {
    renderLoading();
    loadSite().then(function (site) {
      if (!isCurrent()) return;
      renderAcerca(site || SITE_FALLBACK);
      finishView("Acerca de");
    }).catch(function () {
      if (!isCurrent()) return;
      renderAcerca(SITE_FALLBACK);
      finishView("Acerca de");
    });
  }

  function renderAcerca(site) {
    clearMain();
    var c = mountContainer();
    c.appendChild(el("h1", {}, "Acerca de"));

    var about = el("section", { class: "section-block measure" });
    ((site.about && site.about.paragraphs) || []).forEach(function (p) { about.appendChild(el("p", {}, p)); });
    if (site.author) {
      var authorBlock = el("div", { class: "acerca-lines" });
      var nameLine = [el("strong", {}, site.author.name)];
      if (site.author.role) nameLine.push(" — " + site.author.role);
      authorBlock.appendChild(el("p", {}, nameLine));
      if (site.author.lines && site.author.lines.length) {
        var ul = el("ul", {});
        site.author.lines.forEach(function (l) { ul.appendChild(el("li", {}, l)); });
        authorBlock.appendChild(ul);
      }
      about.appendChild(authorBlock);
    }
    c.appendChild(about);

    if (site.feed && site.feed.paragraphs && site.feed.paragraphs.length) {
      var feedSection = el("section", { class: "section-block measure" });
      feedSection.appendChild(el("h2", {}, "El feed diario"));
      var fb = el("div", { class: "section-body" });
      site.feed.paragraphs.forEach(function (p) { fb.appendChild(el("p", {}, p)); });
      feedSection.appendChild(fb);
      c.appendChild(feedSection);
    }

    if (site.oa_policy) {
      var oa = el("section", { class: "section-block oa-policy measure" });
      oa.appendChild(el("h2", {}, "Acceso y licencias"));
      var body = el("div", { class: "section-body" });
      if (site.oa_policy.intro) body.appendChild(el("p", {}, site.oa_policy.intro));
      if (site.oa_policy.criteria && site.oa_policy.criteria.length) {
        var ul1 = el("ul", {});
        site.oa_policy.criteria.forEach(function (x) { ul1.appendChild(el("li", {}, x)); });
        body.appendChild(ul1);
      }
      if (site.oa_policy.rejections && site.oa_policy.rejections.length) {
        body.appendChild(el("p", {}, el("strong", {}, "Qué rechazamos")));
        var ul2 = el("ul", {});
        site.oa_policy.rejections.forEach(function (x) { ul2.appendChild(el("li", {}, x)); });
        body.appendChild(ul2);
      }
      if (site.oa_policy.ai_note) body.appendChild(el("p", {}, site.oa_policy.ai_note));
      if (site.oa_policy.copyright_note) body.appendChild(el("p", {}, site.oa_policy.copyright_note));
      oa.appendChild(body);
      c.appendChild(oa);
    }

    if (site.links && site.links.length) {
      var linksSection = el("section", { class: "section-block" });
      linksSection.appendChild(el("h2", {}, "Enlaces"));
      var ul3 = el("ul", { class: "external-links" });
      site.links.forEach(function (l) {
        var a = extLink(l.label, l.url);
        if (a) ul3.appendChild(el("li", {}, a));
      });
      linksSection.appendChild(ul3);
      c.appendChild(linksSection);
    }
  }

  /* ---------------- Router ---------------- */
  var routeState = { seq: 0 };
  function shouldProcessHash(h) { return h === "" || h === "#" || h.indexOf("#/") === 0; }
  function normalizeHash() { var h = location.hash; return (!h || h === "#") ? "#/" : h; }
  function parseQuery(hash) {
    var qIndex = hash.indexOf("?");
    if (qIndex === -1) return {};
    try {
      var sp = new URLSearchParams(hash.slice(qIndex + 1));
      var out = {};
      sp.forEach(function (v, k) { out[k] = v; });
      return out;
    } catch (e) { return {}; }
  }
  function routePath(hash) {
    var qIndex = hash.indexOf("?");
    return qIndex === -1 ? hash : hash.slice(0, qIndex);
  }

  function route() {
    var mySeq = ++routeState.seq;
    function isCurrent() { return mySeq === routeState.seq; }
    var hash = normalizeHash();
    var path = routePath(hash);
    var query = parseQuery(hash);
    var segs = path.replace(/^#\//, "").split("/").filter(Boolean);

    if (segs.length === 0) { viewHome(isCurrent); }
    else if (segs[0] === "papers" && segs.length === 1) { viewPapersRedirect(isCurrent); }
    else if (segs[0] === "papers" && segs.length === 2) { viewPapersDay(segs[1], isCurrent); }
    else if (segs[0] === "resumenes" && segs.length === 1) { viewResumenes(query, isCurrent); }
    else if (segs[0] === "resumenes" && segs.length === 2) { viewResumenDetail(segs[1], isCurrent); }
    else if (segs[0] === "acerca" && segs.length === 1) { viewAcerca(isCurrent); }
    else { showNotFound(null, "#/", "Ir al inicio"); }
  }

  /* ---------------- Tema ---------------- */
  // El modo vive en esta variable de módulo, no se relee de localStorage en
  // cada clic: si el storage está bloqueado (contexto privado/sandboxed, que
  // los avisos de Artifacts advierten como posible), currentMode seguía
  // devolviendo "system" para siempre y el toggle quedaba atascado en
  // "claro" (hallazgo de verificación). Se inicializa una sola vez, best-
  // effort, y a partir de ahí se mueve en memoria.
  var currentThemeMode_ = null;
  function getStoredTheme() { try { return localStorage.getItem(THEME_KEY); } catch (e) { return null; } }
  function setStoredTheme(v) {
    try { if (v === null) localStorage.removeItem(THEME_KEY); else localStorage.setItem(THEME_KEY, v); }
    catch (e) {}
  }
  function currentThemeMode() {
    if (currentThemeMode_ === null) {
      var stored = getStoredTheme();
      currentThemeMode_ = (stored === "light" || stored === "dark") ? stored : "system";
    }
    return currentThemeMode_;
  }
  function updateThemeButtonLabel(mode) {
    var btn = document.getElementById("theme-toggle");
    if (btn) btn.textContent = "Tema: " + (mode === "light" ? "claro" : mode === "dark" ? "oscuro" : "sistema");
  }
  function applyThemeMode(mode) {
    currentThemeMode_ = mode;
    if (mode === "light" || mode === "dark") {
      document.documentElement.setAttribute("data-theme", mode);
      setStoredTheme(mode);
    } else {
      // "sistema": solo el clic explícito en el toggle llega aquí y quita el
      // atributo. En la carga inicial NO se llama con "system" para no
      // pisar un data-theme que el host (p. ej. el Artifact) ya haya puesto
      // según la elección del lector (enmienda 23a).
      document.documentElement.removeAttribute("data-theme");
      setStoredTheme(null);
    }
    updateThemeButtonLabel(mode);
  }
  function cycleTheme() {
    var mode = currentThemeMode();
    var next = mode === "system" ? "light" : mode === "light" ? "dark" : "system";
    applyThemeMode(next);
  }
  function initTheme() {
    var mode = currentThemeMode();
    // Solo se toca el DOM si HAY una preferencia guardada explícita; sin
    // ella, se deja cualquier data-theme existente tal cual (lo puso el
    // host) y solo se sincroniza la etiqueta del botón.
    if (mode === "light" || mode === "dark") {
      document.documentElement.setAttribute("data-theme", mode);
    }
    updateThemeButtonLabel(mode);
    var btn = document.getElementById("theme-toggle");
    if (btn) btn.addEventListener("click", cycleTheme);
  }

  /* ---------------- Skip link ---------------- */
  function initSkipLink() {
    var skip = document.querySelector(".skip-link");
    if (!skip) return;
    skip.addEventListener("click", function (e) {
      e.preventDefault();
      var m = getMain();
      if (m) m.focus();
    });
  }

  /* ---------------- Init ---------------- */
  function init() {
    initSkipLink();
    initTheme();
    window.addEventListener("hashchange", function () {
      if (!shouldProcessHash(location.hash)) return;
      route();
    });
    route();
  }

  if (document.readyState !== "loading") init();
  else document.addEventListener("DOMContentLoaded", init);
})();
