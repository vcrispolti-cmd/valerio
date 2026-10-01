"""Core tests. Run with:  python -m unittest discover -s tests   (no extra dependencies)."""
import json
import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from orchestrator import roles, security  # noqa: E402
from orchestrator.classify import classify  # noqa: E402
from orchestrator.config import load_config  # noqa: E402
from orchestrator.exposure import ExposureError, build_input  # noqa: E402
from orchestrator.model import Claim  # noqa: E402
from orchestrator.pipeline import Pipeline  # noqa: E402
from orchestrator.strength import audit_draft, compare  # noqa: E402
from orchestrator.verify import match_quote, safe_eval  # noqa: E402

CFG = load_config(ROOT)
CASE = ROOT / "evaluation" / "cases" / "sample_case"


class TestStrength(unittest.TestCase):
    def f(self, a, b, t=""):
        return compare(a, b, CFG.strength, t)

    def test_hedge_not_mistaken_for_strong_causal(self):
        self.assertEqual(self.f("The reform appears to have contributed to lower arrears.",
                                "The reform appears to have contributed to lower arrears.", "CAU"), [])

    def test_causal_strengthening(self):
        self.assertIn("CAUSAL_STRENGTHENED", self.f("The reform appears to have contributed to lower arrears.",
                                                    "The reform drove lower arrears.", "CAU"))

    def test_hedge_dropped(self):
        self.assertIn("CAUSAL_STRENGTHENED", self.f("The reform may have contributed to higher collections.",
                                                    "The reform raised collections.", "CAU"))

    def test_causal_added_to_fact(self):
        self.assertIn("CAUSAL_STRENGTHENED", self.f("Collections rose in 2025.", "Collections rose in 2025, which caused arrears to fall.", "DAT"))

    def test_descriptive_verbs_are_not_causal(self):
        self.assertNotIn("CAUSAL_STRENGTHENED", self.f("Collection rates rose in 2025.", "Collection rates improved in 2025.", "DAT"))

    def test_epistemic_probability_scope_precision(self):
        self.assertIn("EPISTEMIC_STRENGTHENED", self.f("The data suggest a decline.", "The data show a decline."))
        self.assertIn("PROBABILITY_STRENGTHENED", self.f("Arrears could rise.", "Arrears will rise.", "RSK"))
        self.assertIn("SCOPE_WIDENED", self.f("Some banks are exposed.", "All banks are exposed."))
        self.assertIn("PRECISION_INFLATED", self.f("Growth was about 5 percent.", "Growth was 5 percent."))

    def test_numbers_dates_units_attribution_negation(self):
        self.assertIn("NUMBER_CHANGED", self.f("Debt was 60 percent of GDP in 2025.", "Debt was 65 percent of GDP in 2025."))
        self.assertIn("DATE_CHANGED", self.f("Debt was 60 percent of GDP in 2025.", "Debt was 60 percent of GDP in 2026."))
        self.assertIn("UNIT_CHANGED", self.f("Spending rose by 2 percent.", "Spending rose by 2 percentage points."))
        self.assertIn("ATTRIBUTION_CHANGED", self.f("The authorities expect growth to recover.", "Staff expects growth to recover."))
        self.assertIn("NEGATION_CHANGED", self.f("Arrears could rise if gains are not sustained.", "Arrears could not rise if gains are not sustained."))

    def test_staff_attribution_of_unattributed_claim_is_fine(self):
        self.assertNotIn("ATTRIBUTION_CHANGED", self.f("Tariffs remain below cost recovery.", "Staff assesses that tariffs remain below cost recovery."))

    def test_draft_audit_flags_unmapped_and_unapproved(self):
        claims = {"C001": Claim("C001", "Debt was 60 percent of GDP.", "DAT", status="VERIFIED"),
                  "C002": Claim("C002", "Growth will be 9 percent.", "FOR", status="UNRESOLVED")}
        draft = "# T\n\nDebt was 60 percent of GDP. [C001] Growth will be 9 percent. [C002] Inflation fell to 3 percent.\n"
        recs = audit_draft(draft, claims, CFG.strength)
        codes = {c for r in recs for c in r["red_codes"]}
        self.assertEqual(codes, {"RED-7"})
        self.assertEqual(sum(1 for r in recs if r["red_codes"]), 2)

    def test_appraisal_new_claim(self):
        claims = {"C001": Claim("C001", "Debt was 60 percent of GDP.", "DAT", status="VERIFIED"),
                  "C002": Claim("C002", "Reserves were adequate.", "FCT", status="VERIFIED")}
        draft = "# T\n\nDebt was 60 percent of GDP. [C001]\n\n## Staff Appraisal\n\nReserves were adequate. [C002]\n"
        recs = audit_draft(draft, claims, CFG.strength)
        self.assertIn("RED-9", recs[-1]["red_codes"])


class TestQuotes(unittest.TestCase):
    SRC = "Arrears fell from 4.1 percent of GDP at end-2023 to 2.6 percent of GDP at end-2025. Collections rose."

    def test_exact(self):
        self.assertEqual(match_quote("arrears fell from 4.1 percent of GDP", self.SRC, 0.92)[0], "FOUND")

    def test_altered_number_rejected(self):
        self.assertEqual(match_quote("Arrears fell from 4.1 percent of GDP at end-2023 to 2.1 percent of GDP at end-2025.", self.SRC, 0.92)[0], "NOT_FOUND")

    def test_altered_word_rejected(self):
        self.assertEqual(match_quote("Arrears fell sharply from 4.1 percent of GDP at end-2023 to 2.6 percent of GDP at end-2025.", self.SRC, 0.92)[0], "NOT_FOUND")

    def test_extraction_noise_tolerated(self):
        noisy = "Arrears fell from 4.1 percent of GDP at end- 2023 to 2.6 percent GDP at end-2025."
        self.assertIn(match_quote(noisy, self.SRC, 0.9)[0], ("FOUND", "FOUND_APPROX"))

    def test_safe_eval(self):
        self.assertAlmostEqual(safe_eval("a - b", {"a": 4.1, "b": 2.6}), 1.5)
        with self.assertRaises(ValueError):
            safe_eval("__import__('os')", {})


class TestGovernance(unittest.TestCase):
    def test_no_external_model_for_internal_by_default(self):
        self.assertEqual(security.permitted_agents(CFG, "INTERNAL", "live"), [])
        self.assertEqual(security.permitted_agents(CFG, "RESTRICTED", "manual"), [])
        with self.assertRaises(security.ConfidentialityError):
            security.check(CFG, "CONFIDENTIAL", "claude", "manual")

    def test_independence_constraints(self):
        a = roles.assign(CFG, list(CFG.agents))
        fam = CFG.family
        for role in ("adversarial_reviewer", "registrar", "substance_reviewer", "structure_reviewer"):
            self.assertNotEqual(fam(a[role][0]), fam(a["drafter"][0]), role)
        self.assertNotEqual(fam(a["framing_challenger"][0]), fam(a["framer"][0]))
        self.assertEqual(len({fam(x) for x in a["analyst"]}), 2)
        self.assertNotEqual(fam(a["adversarial_reviewer"][0]), fam(a["registrar"][0]))

    def test_per_claim_independence(self):
        a = roles.assign(CFG, list(CFG.agents))
        graders = roles.for_claim(CFG, "grader", a, list(CFG.agents), author="claude")
        self.assertEqual(len(graders), 2)
        self.assertNotIn("anthropic", {CFG.family(g) for g in graders})

    def test_assignment_fails_loudly(self):
        with self.assertRaises(roles.AssignmentError):
            roles.assign(CFG, ["chatgpt", "copilot"])

    def test_blind_roles_cannot_see_framing(self):
        payload = build_input(CFG, "analyst", {"research_question": "q", "framing": {"hypotheses": ["H1"]},
                                               "track_outputs": {"x": 1}, "neutral_subquestions": ["a"]})
        self.assertNotIn("framing", payload)
        self.assertNotIn("track_outputs", payload)
        bad = dict(CFG.exposure)
        bad["roles"] = dict(CFG.exposure["roles"], analyst=["research_question", "framing"])
        cfg2 = type(CFG)(**{**CFG.__dict__, "exposure": bad})
        with self.assertRaises(ExposureError):
            build_input(cfg2, "analyst", {"research_question": "q"})

    def test_classification_escalates_never_downgrades(self):
        lvl, _ = classify(CFG, "Is the debt sustainability analysis consistent?", "analytical_question", 1)
        self.assertEqual(lvl, 4)
        lvl, _ = classify(CFG, "What was GDP in 2025?", "analytical_question", 3)
        self.assertEqual(lvl, 3)


class TestEndToEndMock(unittest.TestCase):
    def test_sample_case(self):
        run_dir = ROOT / "runs" / "_test_e2e"
        shutil.rmtree(run_dir, ignore_errors=True)
        run_dir.mkdir(parents=True)
        spec = {"run_id": "_test_e2e", "question": "What explains the decline in Country A's energy-sector arrears?",
                "document_type": "analytical_question", "level": 3, "confidentiality": "INTERNAL", "mode": "mock",
                "as_of": "2026-09-30", "case_dir": str(CASE)}
        st = Pipeline(CFG, run_dir, spec).run()
        # fabricated quote and outdated source caught; fabricated claim rejected
        self.assertEqual(st.claims["C009"].status, "UNRESOLVED")
        self.assertEqual(st.claims["C010"].status, "REJECTED")
        # overstated causal proposal kept at hedged wording, rival explanations added by targeted fix
        self.assertIn("appears to have contributed", st.claims["C005"].wording())
        self.assertTrue(st.claims["C005"].alternatives)
        # the auditor's rubber-stamp of a fabricated quote is recorded against it
        self.assertGreaterEqual(st.reliability["perplexity"]["verification_excerpt_not_found"], 1)
        # draft v1 strengthening was removed in revision; final audit clean
        self.assertFalse([r for r in st.final_audit if r["red_codes"]])
        self.assertEqual(st.gates["final_gate"]["status"], "YELLOW")
        self.assertTrue((run_dir / "19_dashboard.md").exists())
        shutil.rmtree(run_dir, ignore_errors=True)


class TestBenchmark(unittest.TestCase):
    def test_runs_and_has_no_false_positives(self):
        from evaluation.harness import run_benchmark
        out = run_benchmark(ROOT, CASE, n=36, seed=1, write_report=False)
        self.assertIn("False positives on the clean draft: 0", out)


if __name__ == "__main__":
    unittest.main()
