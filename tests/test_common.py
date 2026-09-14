import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import common as c

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


class TestStripHtml(unittest.TestCase):
    def test_entities_and_italics(self):
        self.assertEqual(
            c.strip_html("Effectiveness of &lt;i&gt;attexis&lt;/i&gt;, a digital intervention"),
            "Effectiveness of attexis, a digital intervention",
        )

    def test_raw_lt_not_swallowed(self):
        self.assertEqual(c.strip_html("p<0.05 in <i>n</i>"), "p<0.05 in n")

    def test_sup_sub_preserved_as_caret_underscore(self):
        self.assertEqual(c.strip_html("3 &#215; 10<sup>-5</sup>"), "3 × 10^-5")
        self.assertEqual(c.strip_html("H<sub>2</sub>O"), "H_2O")


class TestParseAbstract(unittest.TestCase):
    def test_structured(self):
        raw = "<h4>Objectives</h4>Text A.<h4>Conclusion</h4>Text B."
        a = c.parse_abstract(raw)
        self.assertTrue(a["structured"])
        self.assertEqual([s["heading"] for s in a["sections"]], ["Objectives", "Conclusion"])
        self.assertEqual(a["text"], "Text A.\n\nText B.")

    def test_unstructured(self):
        a = c.parse_abstract("Just plain text.")
        self.assertFalse(a["structured"])
        self.assertEqual(a["sections"], [{"heading": None, "text": "Just plain text."}])

    def test_none(self):
        self.assertIsNone(c.parse_abstract(None))
        self.assertIsNone(c.parse_abstract("   "))


class TestDeriveSummary(unittest.TestCase):
    def test_conclusions_heading(self):
        a = c.parse_abstract("<h4>Methods</h4>We did X.<h4>Conclusions</h4>We found Y clearly.")
        s = c.derive_summary(a, "eng")
        self.assertEqual(s["section"], "Conclusions")
        self.assertEqual(s["text"], "We found Y clearly.")
        self.assertEqual(s["lang"], "en")

    def test_interpretation_heading(self):
        a = c.parse_abstract("<h4>Methods</h4>We did X.<h4>Interpretation</h4>It matters.")
        s = c.derive_summary(a, "eng")
        self.assertEqual(s["section"], "Interpretation")

    def test_tail_fallback(self):
        a = c.parse_abstract("First sentence here. Second sentence here. Third sentence here.")
        s = c.derive_summary(a, "eng")
        self.assertEqual(s["section"], "abstract_tail")
        self.assertIn("Third sentence here.", s["text"])

    def test_tail_skips_registration_sections(self):
        a = c.parse_abstract(
            "<h4>Methods</h4>We measured outcomes carefully in this cohort."
            "<h4>Trial registration</h4>NCT01234567."
        )
        s = c.derive_summary(a, "eng")
        self.assertNotIn("NCT01234567", s["text"])

    def test_none_without_abstract(self):
        self.assertIsNone(c.derive_summary(None))


class TestDetectDesign(unittest.TestCase):
    def test_pubtype_priority_over_regex(self):
        # RCT por pubType debe ganar aunque el abstract mencione meta-analysis.
        d = c.detect_design(
            "A randomized trial", "we compare with a prior meta-analysis", ["Randomized Controlled Trial"]
        )
        self.assertEqual(d, {"id": "rct", "confidence": "pubtype"})

    def test_generic_review_pubtype_does_not_hide_specific_title_design(self):
        review_types = ["review-article", "Review", "Journal Article"]
        d = c.detect_design("eHealth interventions for parents: A meta-analysis of randomized controlled trials.", "", review_types)
        self.assertEqual(d["id"], "meta_analysis")
        d = c.detect_design("Resilience programmes in high-risk occupations: A Systematic Review.", "", review_types)
        self.assertEqual(d["id"], "systematic_review")
        d = c.detect_design("PROTOCOL: Asylum processing time and mental health: A Systematic Review", "", review_types)
        self.assertEqual(d["id"], "protocol")
        d = c.detect_design("Psychobiotics for mental health treatment.", "", review_types)
        self.assertEqual(d, {"id": "narrative_review", "confidence": "pubtype"})

    def test_jats_hyphenated_pubtype(self):
        d = c.detect_design("Some title", "", ["systematic-review"])
        self.assertEqual(d["id"], "systematic_review")
        self.assertEqual(d["confidence"], "pubtype")

    def test_protocol_title_only(self):
        d = c.detect_design("Study protocol for a new trial", "no protocol word here", [])
        self.assertEqual(d["id"], "protocol")

    def test_rct_regex_lowercase(self):
        d = c.detect_design("Some study", "this RCT examined outcomes", [])
        self.assertEqual(d["id"], "rct")
        self.assertEqual(d["confidence"], "heuristic")

    def test_none_when_nothing_matches(self):
        self.assertIsNone(c.detect_design("Unrelated title", "unrelated text", []))

    def test_title_cross_sectional_wins_over_background_cohort_mention(self):
        # Caso real MED:42732358: el título dice "Cross-Sectional Analysis" pero
        # el abstract menciona "previous cross-sectional and prospective studies"
        # en los antecedentes; el diseño explícito del título debe ganar.
        title = "Association Between Sleep Duration and Depressive Symptoms: A Cross-Sectional Analysis"
        abstract = "have been associated with depressive symptoms in previous cross-sectional and prospective studies, typically demonstrating..."
        d = c.detect_design(title, abstract, [])
        self.assertEqual(d, {"id": "cross_sectional", "confidence": "heuristic"})

    def test_cohort_regex_excludes_future_work_mentions(self):
        # Caso real MED:42729447: "Longitudinal studies are needed to determine
        # whether..." es trabajo futuro, no el diseño del propio estudio; el
        # abstract sí describe explícitamente "A cross-sectional study".
        title = "Psychological distress among prostate cancer survivors: a network analysis"
        abstract = (
            "A cross-sectional study was conducted among 251 prostate cancer survivors. "
            "Longitudinal studies are needed to determine whether these central symptoms predict..."
        )
        d = c.detect_design(title, abstract, [])
        self.assertEqual(d, {"id": "cross_sectional", "confidence": "heuristic"})

    def test_unicode_hyphen_normalized_for_ptsd_style_terms(self):
        # U+2010 (guion Unicode) en vez de '-' ASCII, como en títulos reales.
        title = "Study on Post‐Traumatic Stress Disorder in staff: a qualitative study"
        d = c.detect_design(title, "", [])
        self.assertEqual(d["id"], "qualitative")


class TestDetectTags(unittest.TestCase):
    def test_canonical_order(self):
        text = "This study examines alcohol use and psychosis and suicide risk."
        config = {
            "tag_patterns": {
                "psychosis": r"\bpsychosis\b",
                "suicide": r"\bsuicide\b",
                "alcohol": r"\balcohol\b",
            }
        }
        tags = c.detect_tags(text, config)
        # orden canónico: psychosis antes que suicide antes que alcohol
        self.assertEqual(tags, ["psychosis", "suicide", "alcohol"])

    def test_no_false_peru_latam_on_lmic(self):
        import json

        cfg_path = os.path.join(os.path.dirname(__file__), "..", "scripts", "feed_config.json")
        with open(cfg_path, encoding="utf-8") as f:
            cfg = json.load(f)
        tags = c.detect_tags("This study was conducted in a low- and middle-income country (LMIC).", cfg)
        self.assertNotIn("peru_latam", tags)

    def test_unicode_hyphen_normalized_for_ptsd(self):
        import json

        cfg_path = os.path.join(os.path.dirname(__file__), "..", "scripts", "feed_config.json")
        with open(cfg_path, encoding="utf-8") as f:
            cfg = json.load(f)
        # U+2010 real en títulos de PMC (35 de 481 ítems observados).
        text = "Longitudinal Study on Post‐Traumatic Stress Disorder Among Medical Staff"
        tags = c.detect_tags(text, cfg)
        self.assertIn("ptsd", tags)


class TestDetectSampleSize(unittest.TestCase):
    def test_sample_of(self):
        a = {"structured": False, "text": "We recruited a sample of 100 adults for this study."}
        self.assertEqual(c.detect_sample_size(a), {"value": 100, "confidence": "heuristic"})

    def test_year_not_merged_into_n(self):
        a = {"structured": False, "text": "In 2019 100 participants were enrolled in the study."}
        r = c.detect_sample_size(a)
        self.assertIsNotNone(r)
        self.assertEqual(r["value"], 100)

    def test_comma_grouped_large_n(self):
        a = {
            "structured": True,
            "sections": [
                {
                    "heading": "Methods",
                    "text": "We used UK Biobank data. A total of 242,947 participants were included in the analysis. (n= 40) subgroup.",
                }
            ],
        }
        r = c.detect_sample_size(a)
        self.assertEqual(r["value"], 242947)

    def test_excluded_screened_sentence(self):
        a = {
            "structured": False,
            "text": (
                "A total of 3159 individuals were screened for eligibility. "
                "Of these, 306 participants were included in the analysis."
            ),
        }
        r = c.detect_sample_size(a)
        # la oración con "screened" se descarta; debe quedar 306 vía la oración restante
        self.assertIsNotNone(r)
        self.assertEqual(r["value"], 306)

    def test_none_below_minimum(self):
        a = {"structured": False, "text": "A sample of 3 patients was described."}
        self.assertIsNone(c.detect_sample_size(a))


class TestFrontmatter(unittest.TestCase):
    def _valid_text(self):
        path = os.path.join(os.path.dirname(__file__), "fixtures", "summary_valid.md")
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_valid_parses(self):
        fm, body = c.parse_frontmatter(self._valid_text(), "summary_valid.md")
        self.assertEqual(fm["study_design"], "pilot")
        self.assertEqual(fm["paper_license"], "cc by")
        self.assertTrue(fm["paper_oa_verified"])
        self.assertIn("## En una frase", body)

    def test_duplicate_key_errors(self):
        text = self._valid_text().replace(
            'paper_license: "cc by"', 'paper_license: "cc by"\npaper_license: "cc by"'
        )
        with self.assertRaises(c.SummaryFormatError):
            c.parse_frontmatter(text, "x.md")

    def test_list_with_quoted_commas(self):
        text = '---\ntitle: "Un titulo de prueba suficientemente largo"\ndate: "2026-09-14"\nstatus: "draft"\ntags: [depression]\nstudy_design: "cross_sectional"\nsummary_type: "empirico"\npaper_title: "T"\npaper_authors: "A"\npaper_journal: "J"\npaper_year: 2026\npaper_source: "MED"\npaper_epmc_id: "1"\npaper_doi: "10.1/x"\npaper_license: "cc by"\npaper_oa_verified: true\npaper_oa_checked: "2026-09-14"\npaper_pub_types: ["Research Support, Non-U.S. Gov\'t", "Journal Article"]\n---\n\n## En una frase\nTexto.\n\n## Pregunta\nTexto.\n\n## Métodos\nTexto.\n\n## Hallazgos clave\n- Texto.\n\n## Limitaciones\n- Otra: texto.\n\n## Por qué importa para la clínica\nTexto.\n'
        fm, body = c.parse_frontmatter(text, "x.md")
        self.assertEqual(fm["paper_pub_types"][0], "Research Support, Non-U.S. Gov't")

    def test_not_oa_rejected(self):
        path = os.path.join(os.path.dirname(__file__), "fixtures", "summary_invalid_not_oa.md")
        with open(path, encoding="utf-8") as f:
            text = f.read()
        with self.assertRaises(c.SummaryFormatError):
            c.parse_frontmatter(text, "summary_invalid_not_oa.md")

    def test_license_not_cc_rejected(self):
        text = self._valid_text().replace('paper_license: "cc by"', 'paper_license: "all rights reserved"')
        with self.assertRaises(c.SummaryFormatError):
            c.parse_frontmatter(text, "x.md")

    def test_epmc_id_int_converted_to_str(self):
        text = self._valid_text().replace('paper_epmc_id: "41784296"', "paper_epmc_id: 41784296")
        fm, _ = c.parse_frontmatter(text, "x.md")
        self.assertEqual(fm["paper_epmc_id"], "41784296")
        self.assertIsInstance(fm["paper_epmc_id"], str)

    def test_unquoted_string_for_str_field_errors(self):
        text = self._valid_text().replace('paper_journal: "Bipolar disorders"', "paper_journal: 12345")
        with self.assertRaises(c.SummaryFormatError):
            c.parse_frontmatter(text, "x.md")

    def test_slug_key_forbidden(self):
        text = self._valid_text().replace("---\n\n## En una frase", 'slug: "foo"\n---\n\n## En una frase')
        with self.assertRaises(c.SummaryFormatError):
            c.parse_frontmatter(text, "x.md")


class TestParseBody(unittest.TestCase):
    def test_pending_in_draft_ok(self):
        path = os.path.join(os.path.dirname(__file__), "fixtures", "summary_draft_pending.md")
        with open(path, encoding="utf-8") as f:
            text = f.read()
        fm, body = c.parse_frontmatter(text, "x.md")
        sections = c.parse_body(body, fm["status"], "x.md", fm["summary_type"])
        by_id = {s["id"]: s for s in sections}
        self.assertTrue(by_id["en_una_frase"]["pending"])
        self.assertEqual(by_id["en_una_frase"]["blocks"], [])
        self.assertFalse(by_id["pregunta"]["pending"])

    def test_pending_in_published_errors(self):
        path = os.path.join(os.path.dirname(__file__), "fixtures", "summary_draft_pending.md")
        with open(path, encoding="utf-8") as f:
            text = f.read()
        with self.assertRaises(c.SummaryFormatError):
            c.parse_body(text.split("---\n", 2)[2], "published", "x.md", "empirico")

    def test_missing_heading_errors(self):
        body = "\n## En una frase\nTexto.\n\n## Pregunta\nTexto.\n"
        with self.assertRaises(c.SummaryFormatError):
            c.parse_body(body, "draft", "x.md", "empirico")

    def test_unknown_heading_errors(self):
        body = (
            "\n## En una frase\nT.\n\n## Pregunta\nT.\n\n## Métodos\nT.\n\n## Hallazgos clave\n- T.\n\n"
            "## Limitaciones\n- T.\n\n## Por qué importa para la clínica\nT.\n\n## Encabezado inventado\nT.\n"
        )
        with self.assertRaises(c.SummaryFormatError):
            c.parse_body(body, "draft", "x.md", "empirico")

    def test_html_in_body_raises_summary_format_error_not_value_error(self):
        # Antes, un <i> u otra etiqueta HTML en el cuerpo levantaba ValueError
        # crudo (no capturado) en vez de SummaryFormatError con archivo:línea.
        body = (
            "\n## En una frase\nVer <i>attexis</i>.\n\n## Pregunta\nT.\n\n## Métodos\nT.\n\n"
            "## Hallazgos clave\n- T.\n\n## Limitaciones\n- T.\n\n"
            "## Por qué importa para la clínica\nT.\n"
        )
        with self.assertRaises(c.SummaryFormatError) as ctx:
            c.parse_body(body, "draft", "x.md", "empirico")
        self.assertEqual(ctx.exception.path, "x.md")
        self.assertGreater(ctx.exception.line, 1)

    def test_mixed_list_and_plain_errors(self):
        body = (
            "\n## En una frase\nT.\n\n## Pregunta\nT.\n\n## Métodos\nT.\n\n## Hallazgos clave\n- item uno\ntexto plano\n\n"
            "## Limitaciones\n- T.\n\n## Por qué importa para la clínica\nT.\n"
        )
        with self.assertRaises(c.SummaryFormatError):
            c.parse_body(body, "draft", "x.md", "empirico")


class TestInlineToPlain(unittest.TestCase):
    def test_multiplication_not_touched(self):
        self.assertEqual(c.inline_to_plain("2 * 3 * 4"), "2 * 3 * 4")

    def test_underscored_identifier_not_touched(self):
        self.assertEqual(c.inline_to_plain("PHQ_9_total"), "PHQ_9_total")

    def test_emphasis_and_backticks_stripped(self):
        self.assertEqual(c.inline_to_plain("**bold** and _em_ and `code`"), "bold and em and code")

    def test_link_with_http_kept(self):
        self.assertEqual(
            c.inline_to_plain("[texto](https://example.com)"), "texto (https://example.com)"
        )

    def test_link_without_http_dropped(self):
        self.assertEqual(c.inline_to_plain("[texto](ref1)"), "texto")

    def test_raw_html_raises(self):
        with self.assertRaises(ValueError):
            c.inline_to_plain("this has <b>html</b>")

    def test_p_less_than_not_html(self):
        self.assertEqual(c.inline_to_plain("p < 0.05"), "p < 0.05")


class TestRelevance(unittest.TestCase):
    def test_journal_overflow_two_pass(self):
        config = {
            "core_journal_abbrevs": [],
            "mesh_psychiatry": [],
            "journal_soft_cap": 2,
            "tag_patterns": {"depression": r"depress"},
        }
        items = []
        for i in range(4):
            items.append(
                {
                    "key": f"MED:{i}",
                    "journal": "Healthcare",
                    "journal_abbrev": "Healthcare",
                    "title": f"Depression Title {i}",
                    "tags": ["depression"],
                    "mesh_major": [],
                    "keywords": [],
                    "abstract": None,
                    "study_design": None,
                    "is_preprint": False,
                }
            )
        c.apply_relevance(items, config)
        overflowed = [it for it in items if "journal_overflow" in it["relevance"]["signals"]]
        self.assertEqual(len(overflowed), 2)  # cap=2, 4 items -> 2 exceden
        for it in overflowed:
            self.assertEqual(it["relevance"]["score"], -1)  # 1 (tags) - 2

    def test_no_circularity_stable_two_pass(self):
        config = {"core_journal_abbrevs": [], "mesh_psychiatry": [], "journal_soft_cap": 1}
        items = [
            {
                "key": "A",
                "journal": "J",
                "journal_abbrev": "J",
                "title": "A",
                "tags": ["a", "b", "c", "d"],
                "mesh_major": [],
                "study_design": None,
                "is_preprint": False,
            },
            {
                "key": "B",
                "journal": "J",
                "journal_abbrev": "J",
                "title": "B",
                "tags": ["a"],
                "mesh_major": [],
                "study_design": None,
                "is_preprint": False,
            },
        ]
        c.apply_relevance(items, config)
        # A tiene más tags -> mayor base_score -> A debe quedar primero (sin overflow)
        self.assertEqual(items[0]["key"], "A")
        self.assertNotIn("journal_overflow", items[0]["relevance"]["signals"])
        self.assertIn("journal_overflow", items[1]["relevance"]["signals"])

    def test_weak_topic_penalizes_incidental_mention(self):
        # Caso real MED:42729609 (anestesia BIS vs ETAG): "post-traumatic stress
        # disorder (PTSD)" aparece una sola vez, como consecuencia posible, no
        # en el título ni en keywords/MeSH -> no debe contar como on-topic.
        config = {
            "core_journal_abbrevs": [],
            "mesh_psychiatry": ["Anesthesia"],
            "journal_soft_cap": 8,
            "tag_patterns": {"ptsd": r"\bptsd\b|\bpost-?traumatic stress\b"},
        }
        off_topic = {
            "key": "MED:1",
            "journal": "J Anesth",
            "journal_abbrev": "J Anesth",
            "title": "Bispectral index versus end-tidal anesthetic gas monitoring",
            "tags": ["ptsd"],
            "mesh_major": ["Anesthesia"],
            "keywords": [],
            "abstract": {"text": "Patients may develop post-traumatic stress disorder (PTSD) after surgery."},
            "study_design": None,
            "is_preprint": False,
        }
        on_topic = {
            "key": "MED:2",
            "journal": "J Trauma",
            "journal_abbrev": "J Trauma",
            "title": "Post-traumatic stress disorder in ICU survivors: a cohort study",
            "tags": ["ptsd"],
            "mesh_major": [],
            "keywords": [],
            "abstract": {"text": "We studied PTSD outcomes."},
            "study_design": None,
            "is_preprint": False,
        }
        items = [off_topic, on_topic]
        c.apply_relevance(items, config)
        by_key = {it["key"]: it for it in items}
        self.assertIn("weak_topic", by_key["MED:1"]["relevance"]["signals"])
        self.assertNotIn("weak_topic", by_key["MED:2"]["relevance"]["signals"])
        self.assertLess(by_key["MED:1"]["relevance"]["score"], by_key["MED:2"]["relevance"]["score"])


class TestValidators(unittest.TestCase):
    def test_validate_date(self):
        self.assertTrue(c.validate_date("2026-09-14"))
        self.assertFalse(c.validate_date("2026-13-01"))
        self.assertFalse(c.validate_date("not-a-date"))

    def test_validate_slug(self):
        self.assertTrue(c.validate_slug("2026-09-14-foo-bar"))
        self.assertFalse(c.validate_slug("foo-bar"))
        self.assertFalse(c.validate_slug("2026-09-14-Foo"))

    def test_license_allowed(self):
        self.assertTrue(c.license_allowed("cc by-nc"))
        self.assertTrue(c.license_allowed("cc0"))
        self.assertFalse(c.license_allowed(None))
        self.assertFalse(c.license_allowed("all rights reserved"))

    def test_license_label(self):
        self.assertEqual(c.license_label("cc by-nc"), "CC BY-NC")
        self.assertEqual(c.license_label(None), "Licencia no declarada")
        self.assertEqual(c.license_label("weird license"), "WEIRD LICENSE")


class TestParseKvBlock(unittest.TestCase):
    def test_valid(self):
        items = c.parse_kv_block(["- Población: 100 adultos", "- Comparador: No aplica"], "x.md", 1)
        self.assertEqual(
            items,
            [{"key": "Población", "value": "100 adultos"}, {"key": "Comparador", "value": "No aplica"}],
        )

    def test_missing_colon_errors(self):
        with self.assertRaises(c.SummaryFormatError):
            c.parse_kv_block(["- solo texto sin separador"], "x.md", 1)

    def test_continuation_line(self):
        items = c.parse_kv_block(["- Clave: valor largo", "  que continúa en la siguiente línea"], "x.md", 1)
        self.assertEqual(items[0]["value"], "valor largo que continúa en la siguiente línea")


class TestOlAndH3Restrictions(unittest.TestCase):
    def test_ol_forbidden_outside_argumento(self):
        body = (
            "\n## En una frase\nT.\n\n## Pregunta\nT.\n\n## Métodos\n1. paso uno\n2. paso dos\n\n"
            "## Hallazgos clave\n- T.\n- T2.\n\n## Limitaciones\n- Otra: T.\n\n"
            "## Por qué importa para la clínica\nT.\n"
        )
        with self.assertRaises(c.SummaryFormatError):
            c.parse_body(body, "draft", "x.md", "empirico")

    def test_h3_forbidden_outside_nota_completa(self):
        body = (
            "\n## En una frase\nT.\n\n## Pregunta\nT.\n\n## Métodos\nT.\n\n"
            "## Hallazgos clave\n- T.\n- T2.\n\n## Limitaciones\n- Otra: T.\n\n"
            "## Por qué importa para la clínica\nT.\n\n### Encabezado suelto\nT.\n"
        )
        with self.assertRaises(c.SummaryFormatError):
            c.parse_body(body, "draft", "x.md", "empirico")


class TestArgumentoAllowsOl(unittest.TestCase):
    def test_conceptual_argumento_with_ol(self):
        body = (
            "\n## En una frase\nT.\n\n## Pregunta\nT.\n\n"
            "## El argumento\nT.\n\n1. paso uno\n2. paso dos\n\n"
            "## Ideas clave\n- T.\n- T2.\n\n## Limitaciones\n- Otra: T.\n\n"
            "## Por qué importa para la clínica\nT.\n"
        )
        sections = c.parse_body(body, "draft", "x.md", "conceptual")
        by_id = {s["id"]: s for s in sections}
        self.assertEqual(by_id["argumento"]["blocks"][-1]["type"], "ol")
        self.assertEqual(len(by_id["argumento"]["blocks"][-1]["items"]), 2)


class TestFullNoteParsing(unittest.TestCase):
    def test_full_note_from_fixture_parses(self):
        path = os.path.join(FIXTURES_DIR, "summary_empirico_full_note.md")
        with open(path, encoding="utf-8") as f:
            text = f.read()
        fm, body = c.parse_frontmatter(text, path)
        sections = c.parse_body(body, fm["status"], path, fm["summary_type"])
        by_id = {s["id"]: s for s in sections}
        nc = by_id["nota_completa"]
        self.assertFalse(nc["pending"])
        ids = [s["id"] for s in nc["full_note_sections"]]
        self.assertEqual(ids, c.FULL_NOTE_ORDER)

    def test_conceptual_forbids_nota_completa(self):
        body = (
            "\n## En una frase\nT.\n\n## Pregunta\nT.\n\n## El argumento\nT.\n\n"
            "## Ideas clave\n- T.\n- T2.\n\n## Limitaciones\n- Otra: T.\n\n"
            "## Por qué importa para la clínica\nT.\n\n## Nota completa\n[[PENDIENTE]]\n"
        )
        with self.assertRaises(c.SummaryFormatError):
            c.parse_body(body, "draft", "x.md", "conceptual")

    def test_nc_datos_item_count_must_match_nc_hallazgos_markers(self):
        path = os.path.join(FIXTURES_DIR, "summary_empirico_full_note.md")
        with open(path, encoding="utf-8") as f:
            text = f.read()
        text = text.replace(
            "3. El análisis fue exploratorio: no se reportan índices de ajuste confirmatorio "
            "(por ejemplo, CFI o RMSEA) para la estructura resultante.\n",
            "",
        )
        fm, body = c.parse_frontmatter(text, "x.md")
        with self.assertRaises(c.SummaryFormatError):
            c.parse_body(body, fm["status"], "x.md", fm["summary_type"])


class TestValidatePrinciple(unittest.TestCase):
    def _kv(self, **overrides):
        base = {
            "Enunciado": "La terapia mejora el funcionamiento diario de las personas con el trastorno.",
            "Fundamento": "El diseño y la muestra grande sostienen la inferencia.",
            "Evidencia": "mejora de 12.4 puntos (IC95% 8.1-16.7) frente al grupo control",
            "Fuerza": "moderada",
            "Transferencia": "clínica, investigación",
            "Límite": "no aplica a formas graves ni a pacientes hospitalizados.",
            "Procedencia": "autores",
        }
        base.update(overrides)
        return [{"key": k, "value": v} for k, v in base.items()]

    def test_valid_empirico(self):
        corpus = "Se observó una mejora de 12.4 puntos (IC95% 8.1-16.7) frente al grupo control."
        out = c.validate_principle(self._kv(), "empirico", "rct", corpus)
        self.assertEqual(out["strength"], "moderada")
        self.assertEqual(out["transfer"], ["clínica", "investigación"])

    def test_wrong_key_order_errors(self):
        kv = self._kv()
        kv[0], kv[1] = kv[1], kv[0]
        with self.assertRaises(ValueError):
            c.validate_principle(kv, "empirico", "rct", "cualquier texto")

    def test_forbidden_word_errors(self):
        with self.assertRaises(ValueError):
            c.validate_principle(
                self._kv(Enunciado="Esta terapia siempre mejora el funcionamiento diario."),
                "empirico", "rct", "x",
            )

    def test_digit_in_statement_errors(self):
        with self.assertRaises(ValueError):
            c.validate_principle(
                self._kv(Enunciado="La terapia mejora en un 30% el funcionamiento diario."),
                "empirico", "rct", "x",
            )

    def test_strength_over_cap_errors(self):
        with self.assertRaises(ValueError):
            c.validate_principle(
                self._kv(Fuerza="alta"), "empirico", "cohort",
                "mejora de 12.4 puntos (IC95% 8.1-16.7) frente al grupo control",
            )

    def test_conceptual_requires_argumental(self):
        with self.assertRaises(ValueError):
            c.validate_principle(
                self._kv(Fuerza="moderada", Evidencia="Argumento sin cifras."),
                "conceptual", "narrative_review", "x",
            )

    def test_conceptual_argumental_ok(self):
        out = c.validate_principle(
            self._kv(Fuerza="argumental", Evidencia="Argumento sin cifras."),
            "conceptual", "narrative_review", "x",
        )
        self.assertEqual(out["strength"], "argumental")

    def test_causal_word_on_observational_design_errors(self):
        kv = self._kv(Enunciado="El tratamiento causa una mejora del funcionamiento diario.")
        with self.assertRaises(ValueError):
            c.validate_principle(kv, "empirico", "cohort", "x")

    def test_evidence_number_absent_from_corpus_errors(self):
        with self.assertRaises(ValueError):
            c.validate_principle(self._kv(), "empirico", "rct", "no hay ninguna cifra parecida aquí")


class TestFindLongQuotes(unittest.TestCase):
    def test_short_quote_not_flagged(self):
        self.assertEqual(c.find_long_quotes('El autor dice "esto es corto".'), [])

    def test_long_quote_flagged(self):
        text = 'El autor escribe: "' + " ".join(["palabra"] * 15) + '".'
        violations = c.find_long_quotes(text)
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0][0], 15)

    def test_typographic_quotes(self):
        text = "Se afirma: “" + " ".join(["palabra"] * 16) + "”."
        violations = c.find_long_quotes(text)
        self.assertEqual(len(violations), 1)


class TestValidateLimitationsFn(unittest.TestCase):
    def test_valid(self):
        c.validate_limitations(["Muestra: pequeña.", "Diseño: transversal."], c.LIMITATION_CATEGORIES)

    def test_missing_colon_errors(self):
        with self.assertRaises(ValueError):
            c.validate_limitations(["sin categoría"], c.LIMITATION_CATEGORIES)

    def test_unknown_category_errors(self):
        with self.assertRaises(ValueError):
            c.validate_limitations(["Marketing: no es una categoría válida."], c.LIMITATION_CATEGORIES)

    def test_full_note_categories_are_different(self):
        c.validate_limitations(["Selección: sesgo de autoselección."], c.FULL_NOTE_LIMITATION_CATEGORIES)
        with self.assertRaises(ValueError):
            c.validate_limitations(["Muestra: no aplica a nota completa."], c.FULL_NOTE_LIMITATION_CATEGORIES)


class TestParseReadingsItemFn(unittest.TestCase):
    def test_valid_doi(self):
        item = c.parse_readings_item(
            "Kotov R (2017). HiTOP. J Abnorm Psychol · doi:10.1037/abn0000258 · Paper fundacional."
        )
        self.assertEqual(item["doi"], "10.1037/abn0000258")
        self.assertIsNone(item["pmid"])

    def test_valid_pmid(self):
        item = c.parse_readings_item("Autor A (2020). Título. Revista · PMID:12345678 · Por qué leerla.")
        self.assertEqual(item["pmid"], "12345678")

    def test_wrong_separator_count_errors(self):
        with self.assertRaises(ValueError):
            c.parse_readings_item("Cita sin separador correcto · doi:10.1037/abn0000258")

    def test_bad_identifier_prefix_errors(self):
        with self.assertRaises(ValueError):
            c.parse_readings_item("Cita · issn:1234-5678 · Por qué.")

    def test_malformed_doi_errors(self):
        with self.assertRaises(ValueError):
            c.parse_readings_item("Cita · doi:not-a-doi · Por qué.")


class TestOpenAlexHelpers(unittest.TestCase):
    def test_normalize_license(self):
        self.assertEqual(c.normalize_openalex_license("cc-by-nc"), "cc by-nc")
        self.assertEqual(c.normalize_openalex_license("cc-by"), "cc by")
        self.assertEqual(c.normalize_openalex_license("cc0"), "cc0")
        self.assertIsNone(c.normalize_openalex_license(None))

    def test_verdict_accepted(self):
        with open(os.path.join(FIXTURES_DIR, "openalex_work_hybrid_ccby.json"), encoding="utf-8") as f:
            work = json.load(f)
        ok, license_norm, reason = c.openalex_oa_verdict(work)
        self.assertTrue(ok)
        self.assertEqual(license_norm, "cc by")
        self.assertIsNone(reason)

    def test_verdict_closed_rejected(self):
        with open(os.path.join(FIXTURES_DIR, "openalex_work_closed.json"), encoding="utf-8") as f:
            work = json.load(f)
        ok, license_norm, reason = c.openalex_oa_verdict(work)
        self.assertFalse(ok)
        self.assertIsNotNone(reason)


class TestSummaryTypeFrontmatter(unittest.TestCase):
    def _valid_text(self):
        path = os.path.join(FIXTURES_DIR, "summary_valid.md")
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_missing_summary_type_errors(self):
        text = self._valid_text().replace('summary_type: "empirico"\n', "")
        with self.assertRaises(c.SummaryFormatError):
            c.parse_frontmatter(text, "x.md")

    def test_unknown_summary_type_errors(self):
        text = self._valid_text().replace('summary_type: "empirico"', 'summary_type: "mixto"')
        with self.assertRaises(c.SummaryFormatError):
            c.parse_frontmatter(text, "x.md")

    def test_empirico_with_narrative_review_design_errors(self):
        text = self._valid_text().replace('study_design: "pilot"', 'study_design: "narrative_review"')
        with self.assertRaises(c.SummaryFormatError):
            c.parse_frontmatter(text, "x.md")

    def test_ai_draft_and_adapted_with_ai_both_true_published_errors(self):
        text = self._valid_text()
        text = text.replace('status: "draft"', 'status: "published"')
        text = text.replace("ai_draft: true", "ai_draft: true\nadapted_with_ai: true")
        text = text.replace(
            'author: "Borrador de ejemplo generado con IA"', 'author: "Javier Flores"'
        )
        with self.assertRaises(c.SummaryFormatError):
            c.parse_frontmatter(text, "x.md")

    def test_invalid_paper_oa_source_errors(self):
        text = self._valid_text().replace(
            'summary_type: "empirico"', 'summary_type: "empirico"\npaper_oa_source: "wikipedia"'
        )
        with self.assertRaises(c.SummaryFormatError):
            c.parse_frontmatter(text, "x.md")


if __name__ == "__main__":
    unittest.main()
