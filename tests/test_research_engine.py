"""
Tests for the research engine — no network, no model, no key.

Run:

    python tests/test_research_engine.py

The engine takes its four outside dependencies through `Deps` (search, fetch,
ask, ask_json), which is what makes a full five-stage run testable in a second:
the fakes below return plans, pages and prose with a deliberately broken
citation, and the assertions check the properties that matter more than output
style — every marker resolves to a source the run actually fetched, the report
exists, and a resume never touches the network.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research import (config, engine, jobs as jobs_mod, report, search, skills,
                      store, subagents, theology)
from research.fetcher import Page, public_url_error

DEMO_PLAN = {
    "title": "Ephesus and the Christological settlement",
    "objective": "Establish what the council of 431 defined and why.",
    "language": "en",
    "keywords": ["ephesus", "nestorius", "theotokos"],
    "sub_questions": [
        {"question": "What did the council of Ephesus define?",
         "queries": ["council of ephesus definition"]},
        {"question": "Why was Nestorius condemned?",
         "queries": ["nestorius condemnation"]},
        {"question": "How is the settlement received today?",
         "queries": ["ephesus reception ecumenism"]},
    ],
    "skills": ["theology-source-critique"],
}

DEMO_OUTLINE = {
    "title": "Ephesus: one nature, two natures",
    "thesis": "The council settled a word, not a doctrine.",
    "tldr": ["One sentence on the definition [99].", "One on the reception [1]."],
    "sections": [
        {"heading": "What was defined",
         "claims": ["The council affirmed the title Theotokos [1].",
                    "It did not define a formula of two natures [2]."],
         "sources": [1, 2],
         "evidence": ["Theotokos was affirmed against Nestorius [1]"]},
        {"heading": "Why it mattered",
         "claims": ["The settlement split the Eastern churches [3]."],
         "sources": [3]},
    ],
    "contradictions": [{"claim_a": "One nature", "claim_b": "Two natures",
                        "sources": [1, 2], "note": "different vocabularies"}],
    "gaps": ["How did Chalcedon answer Ephesus?"],
    "confidence": "medium",
}

DEMO_CRITIQUE = {
    "issues": [{"claim": "The council affirmed the title Theotokos [1].",
                "problem": "overstated",
                "fix": "The council affirmed the title in its second letter [1]."}],
    "verdict": "sound",
}


def fake_ask(prompt: str, tier: str = "", timeout_ms: int = 0,
             system: str = "", default: str = "") -> str:
    """Writes prose with one citation that does not exist, and a heading that
    the report must strip."""
    return ("## A heading the writer added\n\n"
            "The definition turned on a word [1]. A later claim cites [99]. "
            "Another cites [2] and [3].")


def fake_ask_json(prompt: str, tier: str = "", timeout_ms: int = 0,
                  system: str = "", default=None):
    if "planner of a research team" in system:
        return dict(DEMO_PLAN)
    if "analyst of a research team" in system:
        return dict(DEMO_OUTLINE)
    if "critic of a research team" in system:
        return dict(DEMO_CRITIQUE)
    return default


class FakeWeb:
    def __init__(self):
        self.searches = 0
        self.fetches = 0
        self.fail = False

    def search(self, query: str, max_results: int = 6, grounded_fallback: bool = True):
        self.searches += 1
        if self.fail:
            raise AssertionError("search must not be called")
        if query.startswith("empty:"):
            return []
        slug = "".join(c if c.isalnum() else "-" for c in query)[:40]
        return [
            {"title": f"{query} — overview", "url": f"https://example.org/{slug}-a",
             "snippet": "A long enough abstract to look like a real result. " * 3},
            {"title": f"{query} — study", "url": f"https://example.net/{slug}-b",
             "snippet": "A second abstract with different evidence. " * 3},
        ]

    def fetch(self, url: str, timeout: float = 12, max_chars: int = 4000):
        self.fetches += 1
        if self.fail:
            raise AssertionError("fetch must not be called")
        return Page(url=url, final_url=url, title=f"Page {url[-6:]}",
                    text=("The council affirmed the title Theotokos in 431. "
                          "Nestorius was condemned. Chalcedon later defined two "
                          "natures. " * 12), status=200, fetched_at="2026-10-21")


def deps(web: FakeWeb) -> engine.Deps:
    return engine.Deps(ask=fake_ask, ask_json=fake_ask_json,
                       search=web.search, fetch=web.fetch,
                       available=lambda: True)


class ResearchEngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="research-test-"))
        self._root = config.research_root
        config.research_root = lambda: self.tmp
        self._remember = store.remember
        store.remember = lambda run: "test"          # never touch real memory
        self.web = FakeWeb()

    def tearDown(self):
        config.research_root = self._root
        store.remember = self._remember
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ── the whole loop ───────────────────────────────────────────────────────
    def test_quick_run_produces_a_valid_cited_report(self):
        run, eng = engine.start("Council of Ephesus", depth="quick",
                                language="auto", deps=deps(self.web))
        result = eng.run()

        self.assertEqual(result.status, "done", result.error)
        self.assertTrue(Path(result.report_path).exists())
        text = Path(result.report_path).read_text(encoding="utf-8")

        self.assertIn("# Ephesus: one nature, two natures", text)
        self.assertIn("## What was defined", text)
        self.assertIn("**TL;DR**", text)
        self.assertIn("## Sources", text)
        self.assertIn("6 sources", text)              # method counts sources
        self.assertIn("1 round", text)                # and singularises it
        self.assertEqual(len(result.sources), 6)      # 3 questions × 2 pages
        self.assertEqual(self.web.fetches, 6)

        # the invalid [99] was removed, real markers kept, heading stripped
        self.assertNotIn("[99]", text)
        self.assertIn("[1]", text)
        self.assertNotIn("A heading the writer added", text)

        # every marker resolves to a source the run actually fetched
        import re
        markers = {int(n) for n in re.findall(r"\[(\d+)\]", text)}
        self.assertTrue(markers)
        self.assertTrue(markers <= {s["n"] for s in result.sources})

        # sources are numbered once, without holes or duplicates
        numbers = [s["n"] for s in result.sources]
        self.assertEqual(numbers, sorted(numbers))
        self.assertEqual(len(numbers), len(set(numbers)))

        # skills: the planner selected one, and it is recorded
        self.assertIn("theology-source-critique", result.skills)

    def test_plan_failure_falls_back_to_generic_questions(self):
        def broken_json(prompt, tier="", timeout_ms=0, system="", default=None):
            if "planner" in system:
                return None
            return fake_ask_json(prompt, tier, timeout_ms, system, default)

        d = engine.Deps(ask=fake_ask, ask_json=broken_json,
                        search=self.web.search, fetch=self.web.fetch,
                        available=lambda: True)
        run, eng = engine.start("some obscure topic", depth="quick", deps=d)
        result = eng.run()
        self.assertEqual(result.status, "done", result.error)
        self.assertGreaterEqual(len(result.plan["sub_questions"]), 3)
        self.assertTrue(Path(result.report_path).exists())

    def test_no_evidence_still_produces_an_honest_report(self):
        class Empty(FakeWeb):
            def search(self, query, max_results=6, grounded_fallback=False):
                return []
        d = engine.Deps(ask=fake_ask, ask_json=fake_ask_json,
                        search=Empty().search, fetch=self.web.fetch,
                        available=lambda: True)
        run, eng = engine.start("a topic with no sources", depth="quick", deps=d)
        result = eng.run()
        self.assertEqual(result.status, "done", result.error)
        self.assertEqual(result.sources, [])
        self.assertIn("No citable source was found", Path(result.report_path).read_text(encoding="utf-8"))

    def test_resume_rewrites_the_report_without_touching_the_network(self):
        run, eng = engine.start("Council of Ephesus", depth="quick",
                                deps=deps(self.web))
        result = eng.run()
        Path(result.report_path).unlink()

        self.web.fail = True                    # any search/fetch now fails loudly
        resumed = engine.resume(result.id, deps=deps(self.web))
        self.assertIsNotNone(resumed)
        self.assertEqual(resumed.status, "done", resumed.error)
        self.assertTrue(Path(resumed.report_path).exists())
        self.assertEqual(self.web.searches, 3)  # the original round only
        self.assertEqual(self.web.fetches, 6)

    def test_missing_key_is_reported_not_crashed(self):
        d = engine.Deps(ask=fake_ask, ask_json=fake_ask_json,
                        search=self.web.search, fetch=self.web.fetch,
                        available=lambda: False)
        run, eng = engine.start("anything", depth="quick", deps=d)
        result = eng.run()
        self.assertEqual(result.status, "failed")
        self.assertIn("API key", result.error)

    # ── units ────────────────────────────────────────────────────────────────
    def test_citation_sanitiser_expands_ranges_and_drops_unknown(self):
        text, stats = report.sanitise_citations("a [1-3] b [99] c [2,4] d", 4)
        self.assertIn("[1][2][3]", text)
        self.assertIn("[2][4]", text)
        self.assertNotIn("[99]", text)
        self.assertIn(99, stats["dropped"])

    def test_sanitiser_leaves_a_bracketed_year_alone(self):
        text, _ = report.sanitise_citations("in [2024] the council [2] met", 5)
        self.assertIn("[2024]", text)      # a year, not a citation
        self.assertIn("[2]", text)

    def test_public_url_policy(self):
        self.assertTrue(public_url_error("file:///etc/passwd"))
        self.assertTrue(public_url_error("http://127.0.0.1:8000/"))
        self.assertTrue(public_url_error("http://localhost/x"))
        self.assertTrue(public_url_error("http://169.254.169.254/latest/meta-data"))
        self.assertEqual(public_url_error("https://93.184.216.34/page"), "")

    def test_ranker_deduplicates_and_limits_domains(self):
        rows = [{"title": f"t{i}", "snippet": "x" * 200,
                 "url": "https://same.example/page"} for i in range(5)]
        rows.append({"title": "other", "snippet": "y" * 200,
                     "url": "https://different.example/x"})
        picked = search.rank(rows, 4)
        urls = [r["url"] for r in picked]
        self.assertEqual(len(urls), len(set(urls)))
        self.assertIn("https://different.example/x", urls)

    def test_skills_and_agents_discover(self):
        found = skills.discover(self.tmp)
        self.assertIn("sourced-brief", found)
        self.assertIn("fact-check", found)
        catalog = skills.catalog(found)
        self.assertIn("sourced-brief", catalog)
        self.assertNotIn("## The rule", catalog)     # bodies are not in the index

        agents = subagents.discover(self.tmp)
        self.assertIn("researcher", agents)
        self.assertIn("planner", agents)
        self.assertEqual(subagents.resolve("researcher", agents).tools,
                         ("search", "fetch"))

    def test_user_skill_and_agent_override_shipped_ones(self):
        (self.tmp / "skills").mkdir(parents=True)
        (self.tmp / "skills" / "sourced-brief.md").write_text(
            "---\nname: sourced-brief\ndescription: mine\nwhen: always\n---\n"
            "MY BODY\n", encoding="utf-8")
        (self.tmp / "agents").mkdir(parents=True)
        (self.tmp / "agents" / "researcher.md").write_text(
            "---\nname: researcher\ndescription: mine\ntools: fetch\nmax_sources: 2\n---\n"
            "YOU ARE MY READER\n", encoding="utf-8")

        self.assertEqual(skills.discover(self.tmp)["sourced-brief"].body, "MY BODY")
        agent = subagents.discover(self.tmp)["researcher"]
        self.assertFalse(agent.builtin)
        self.assertEqual(agent.tools, ("fetch",))
        self.assertEqual(agent.max_sources, 2)

    def test_two_runs_in_the_same_second_get_distinct_folders(self):
        first = store.create_run("the same topic", root=self.tmp)
        second = store.create_run("the same topic", root=self.tmp)
        self.assertNotEqual(first.id, second.id)
        self.assertNotEqual(first.dir, second.dir)

    def test_store_round_trip_and_listing(self):
        run = store.create_run("a stored topic", root=self.tmp)
        store.save_note(run, "r1-q1", "researcher", "Q?", "note body")
        store.save(run)
        loaded = store.load_run(run.id, root=self.tmp)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.topic, "a stored topic")
        self.assertEqual(len(store.read_notes(loaded)), 1)
        self.assertEqual(store.list_runs(root=self.tmp)[0]["id"], run.id)

    def test_clip_cuts_on_a_boundary(self):
        from research.util import clip
        text = "First sentence here. Second sentence follows. Third one is long."
        self.assertTrue(clip(text, 30).endswith("…"))
        self.assertIn(".", clip(text, 30))


class ActionSurfaceTests(unittest.TestCase):
    """The voice tool itself — declaration, offline verbs, and the background
    plumbing that keeps a three-minute run out of the conversation turn."""

    def setUp(self):
        sys.path.insert(0, str(ROOT / "actions"))
        import deep_research as mod
        self.mod = mod
        self.tmp = Path(tempfile.mkdtemp(prefix="research-action-"))
        self._root = config.research_root
        config.research_root = lambda: self.tmp
        jobs_mod._JOBS.clear()
        theology.reset_state()

    def tearDown(self):
        config.research_root = self._root
        jobs_mod._JOBS.clear()
        theology.reset_state()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_tool_declaration_is_loadable(self):
        spec = self.mod.TOOL
        self.assertEqual(spec["name"], "deep_research")
        self.assertEqual(spec["behavior"], "NON_BLOCKING")
        self.assertEqual(spec["scheduling"], "SILENT")
        self.assertEqual(spec["parameters"]["type"], "OBJECT")
        self.assertTrue(callable(spec["handler"]))

    def test_agents_and_skills_verbs_answer(self):
        text = self.mod.deep_research({"action": "agents"})
        self.assertIn("researcher", text)
        text = self.mod.deep_research({"action": "skills"})
        self.assertIn("sourced-brief", text)

    def test_run_without_topic_asks_for_one(self):
        text = self.mod.deep_research({"action": "run"})
        self.assertIn("sujet", text.lower())

    def test_run_returns_immediately_then_announces(self):
        """The whole point of the action: the turn is not held for two minutes."""
        import threading
        import time

        report = self.tmp / "report.md"
        report.write_text("# Report\n\nbody", encoding="utf-8")
        run = store.create_run("a background topic", root=self.tmp)
        run.report_path = str(report)

        class FakeEngine:
            def __init__(self, rec):
                self.rec = rec
                self.cancel = threading.Event()
                self.on_event = None

            def run(self):
                if self.on_event:
                    self.on_event("researching", "Round 1: reading")
                time.sleep(0.05)
                self.rec.status = "done"
                self.rec.duration_s = 1.0
                return self.rec

        original = jobs_mod.engine.start
        jobs_mod.engine.start = lambda topic, depth="standard", language="auto", \
            requested_skills=None, **kw: (run, FakeEngine(run))
        try:
            class Player:
                logs, shown = [], []

                def write_log(self, text):
                    self.logs.append(text)

                def show_content(self, title, text):
                    self.shown.append((title, text))

            spoken = []
            player = Player()
            started = time.time()
            answer = self.mod.deep_research(
                {"action": "run", "topic": "a background topic", "depth": "quick"},
                player=player, speak=spoken.append)
            self.assertLess(time.time() - started, 1.0)   # did not run inline
            self.assertIn("lancée", answer)

            job = jobs_mod.get(run.id)
            self.assertIsNotNone(job)
            job["thread"].join(timeout=5)
            self.assertFalse(job["thread"].is_alive())
            self.assertTrue(spoken, "completion must be announced")
            self.assertIn("three most important findings", spoken[0])
            self.assertTrue(any("RAPPORT" in title for title, _ in player.shown))
        finally:
            jobs_mod.engine.start = original


class TheologyGapTests(unittest.TestCase):
    """The vault notices a hole, the research fills it, the vault keeps it."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="theology-gap-"))
        self.vault = self.tmp / "vault"
        (self.vault / "wiki" / "concepts").mkdir(parents=True)
        (self.vault / "raw").mkdir()
        jobs_mod._JOBS.clear()
        theology.reset_state()
        self.bridge = theology._bridge()
        self._push = self.bridge._xerj_push
        self.bridge._xerj_push = lambda path: None      # no HTTP in tests

    def tearDown(self):
        self.bridge._xerj_push = self._push
        jobs_mod._JOBS.clear()
        theology.reset_state()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _page(self, stem, title, body, dirname="concepts"):
        folder = self.vault / "wiki" / dirname
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{stem}.md").write_text(
            f"---\ntitle: {title}\nkind: concept\ncreated: 2026-01-01\n"
            f"updated: 2026-01-01\n---\n\n{body}\n", encoding="utf-8")

    # ── measurement ─────────────────────────────────────────────────────────
    def test_a_page_that_answers_is_not_a_gap(self):
        self._page("nicee", "Concile de Nicée",
                   "Le concile de Nicée définit le credo et l'homoousios.")
        cov = theology.coverage("concile de Nicée", vault=self.vault)
        self.assertFalse(cov.gap, cov.describe())
        self.assertEqual(cov.hits, 1)
        self.assertEqual(cov.pages, 1)
        self.assertGreaterEqual(cov.best_coverage, 0.6)

    def test_a_partial_page_is_a_gap(self):
        self._page("nicee", "Concile de Nicée",
                   "Le concile de Nicée définit le credo.")
        cov = theology.coverage("concile de Chalcédoine", vault=self.vault)
        self.assertTrue(cov.gap, cov.describe())
        self.assertIn(cov.reason, ("couverture insuffisante", "mention unique"))

    def test_an_incidental_word_is_not_coverage(self):
        self._page("histoire", "Histoire des conciles",
                   "Le concile de Nicée ouvre une période de conflits.")
        cov = theology.coverage("concile de Chalcédoine et les deux natures",
                                vault=self.vault)
        self.assertTrue(cov.gap, cov.describe())

    def test_how_the_question_is_asked_does_not_decide(self):
        """The phrasing of a request is not a hole in the vault.

        "peux-tu m'expliquer le concile de Chalcédoine" is about one thing, and
        a vault that holds that thing answers it. Measuring the words of the
        request instead of its subject made every polite question look like a
        gap — and a gap costs a research run."""
        self._page("chalcedoine", "Chalcédoine",
                   "Le concile de Chalcédoine (451) définit les deux natures.")
        for query in ("concile de Chalcédoine",
                      "peux-tu m'expliquer le concile de Chalcédoine",
                      "raconte-moi l'histoire du concile de Chalcédoine",
                      "qu'est-ce que le concile de Chalcédoine et ses conséquences"):
            cov = theology.coverage(query, vault=self.vault)
            self.assertFalse(cov.gap, f"{query!r} -> {cov.describe()}")

    def test_a_page_in_another_language_answers_the_question(self):
        """The vault is bilingual: the question is French, the source is not."""
        self._page("nicaea", "Council of Nicaea",
                   "The Council of Nicaea was the first ecumenical council.")
        for query in ("concile de Nicée", "peux-tu m'expliquer le concile de Nicée"):
            cov = theology.coverage(query, vault=self.vault)
            self.assertFalse(cov.gap, f"{query!r} -> {cov.describe()}")

    def test_a_plural_still_matches_its_singular(self):
        self._page("natures", "Les deux natures",
                   "Le concile de Chalcédoine définit les deux natures du Christ.")
        cov = theology.coverage("les deux natures du Christ", vault=self.vault)
        self.assertFalse(cov.gap, cov.describe())

    def test_a_subject_mentioned_once_in_passing_is_still_a_gap(self):
        """A page that mentions the subject while writing about something
        else has not answered the question: the rest of the question is
        nowhere in the vault."""
        self._page("histoire", "Histoire de l'Église",
                   "Nicée y est mentionné une seule fois.")
        cov = theology.coverage("concile de Nicée", vault=self.vault)
        self.assertTrue(cov.gap, cov.describe())
        self.assertIn(cov.reason, ("mention unique", "couverture insuffisante"))

    def test_a_page_that_speaks_of_the_subject_covers_it(self):
        """No page is titled after the subject — but the vault comes back to
        it, so it is not a hole either."""
        self._page("notes", "Notes de lecture",
                   "Le concile de Chalcédoine, en 451, a défini les deux natures "
                   "du Christ. Chalcédoine est le concile qui a defined la "
                   "foi de l'Eglise pour toujours.")
        cov = theology.coverage("concile de Chalcédoine", vault=self.vault)
        self.assertFalse(cov.gap, cov.describe())

    def test_two_pages_that_between_them_cover_the_question_are_enough(self):
        self._page("chalcedoine", "Chalcédoine",
                   "Le concile de Chalcédoine définit les deux natures.")
        self._page("credo", "Le Credo",
                   "Le Credo de Nicée est le symbole de la foi.")
        cov = theology.coverage("concile de Chalcédoine et le Credo",
                                vault=self.vault)
        self.assertFalse(cov.gap, cov.describe())

    def test_the_subject_of_the_question_is_reported(self):
        self._page("chalcedoine", "Chalcédoine",
                   "Le concile de Chalcédoine (451) définit les deux natures.")
        cov = theology.coverage("peux-tu m'expliquer le concile de Chalcédoine",
                                vault=self.vault)
        self.assertEqual(cov.subject, "chalcedon")
        self.assertIn("chalcedon", cov.describe())

    def test_the_cooldown_survives_a_rephrasing(self):
        """The same subject, asked differently, is the same run."""
        self._page("chalcedoine", "Chalcédoine",
                   "Le concile de Chalcédoine (451) définit les deux natures.")
        self.assertEqual(theology._key("concile de Chalcédoine"),
                         theology._key("peux-tu m'expliquer le concile de Chalcédoine"))

    def test_an_empty_or_missing_vault_never_triggers(self):
        empty = self.tmp / "empty"
        empty.mkdir()
        self.assertFalse(theology.coverage("concile d'Éphèse", vault=empty).gap)
        self.assertFalse(theology.coverage("concile d'Éphèse",
                                           vault=self.tmp / "absent").gap)

    def test_raw_sources_are_reported_but_do_not_trigger_a_run(self):
        """An unprocessed source is a lead: structure it instead of buying a
        second report on top of it."""
        (self.vault / "raw" / "concile-de-chalcedoine.docx").write_bytes(b"x")
        cov = theology.coverage("concile de Chalcédoine", vault=self.vault)
        self.assertFalse(cov.gap)
        self.assertEqual(cov.hits, 0)
        self.assertEqual(cov.raw_hits, 1)
        self.assertIn("brute", cov.reason)

    # ── the trigger ─────────────────────────────────────────────────────────
    def test_maybe_start_fires_once_then_respects_the_cooldown(self):
        self._page("nicee", "Concile de Nicée",
                   "Le concile de Nicée définit le credo.")
        calls = []
        original = jobs_mod.start
        jobs_mod.start = lambda topic, **kw: (calls.append((topic, kw))
                                             or ("run-1", ""))
        try:
            note = theology.maybe_start("concile de Chalcédoine", vault=self.vault)
            self.assertIn("run-1", note)
            self.assertIn("Recherche profonde lancée", note)
            self.assertEqual(len(calls), 1)
            self.assertIn("theology-source-critique", calls[0][1]["skills"])
            self.assertIs(calls[0][1]["on_done"], theology.ingest)

            # the same question again: no second run, no second report
            self.assertEqual(
                theology.maybe_start("concile de Chalcédoine", vault=self.vault), "")
            self.assertEqual(len(calls), 1)

            # a question the vault answers: no run either
            theology.reset_state()
            self.assertEqual(
                theology.maybe_start("concile de Nicée", vault=self.vault), "")
            self.assertEqual(len(calls), 1)
        finally:
            jobs_mod.start = original

    def test_one_run_at_a_time_across_both_entry_points(self):
        jobs_mod._JOBS["busy"] = {"run": store.Run(id="busy", topic="x",
                                                     status="researching"),
                                   "thread": None}
        self.assertIsNotNone(jobs_mod.active())
        self.assertEqual(theology.maybe_start("concile de Chalcédoine",
                                              vault=self.vault), "")

    def test_the_cooldown_survives_a_restart(self):
        """Closing the app and opening it again is not a way to buy the same
        report twice: what was asked is written down."""
        self._page("nicee", "Concile de Nicée",
                   "Le concile de Nicée définit le credo.")
        calls = []
        original = jobs_mod.start
        jobs_mod.start = lambda topic, **kw: (calls.append((topic, kw))
                                             or ("run-1", ""))
        try:
            self.assertIn("run-1", theology.maybe_start("concile de Chalcédoine",
                                                        vault=self.vault))
            # a restart: the in-memory state is gone, the file is not
            theology._STATE.clear()
            self.assertEqual(theology.maybe_start("concile de Chalcédoine",
                                                  vault=self.vault), "")
            self.assertEqual(len(calls), 1)
        finally:
            jobs_mod.start = original

    def test_a_rephrased_question_is_the_same_question(self):
        self._page("nicee", "Concile de Nicée",
                   "Le concile de Nicée définit le credo.")
        calls = []
        original = jobs_mod.start
        jobs_mod.start = lambda topic, **kw: (calls.append((topic, kw))
                                             or ("run-1", ""))
        try:
            self.assertIn("run-1", theology.maybe_start("concile de Chalcédoine",
                                                        vault=self.vault))
            self.assertEqual(
                theology.maybe_start("peux-tu m'expliquer le concile de Chalcédoine",
                                     vault=self.vault), "")
            self.assertEqual(len(calls), 1)
        finally:
            jobs_mod.start = original

    def test_the_daily_ceiling_stops_the_spending(self):
        """A gap is a trigger, not a purchase order."""
        self._page("nicee", "Concile de Nicée",
                   "Le concile de Nicée définit le credo.")
        calls = []
        original_start = jobs_mod.start
        original_setting = config.setting
        jobs_mod.start = lambda topic, **kw: (calls.append((topic, kw))
                                             or ("run-1", ""))
        config.setting = lambda name, default=None: (
            1 if name == "theology_auto_research_max_per_day"
            else original_setting(name, default))
        try:
            self.assertIn("run-1", theology.maybe_start("concile de Chalcédoine",
                                                        vault=self.vault))
            note = theology.maybe_start("concile de Constantinople",
                                        vault=self.vault)
            self.assertIn("plafond", note.lower())
            self.assertEqual(len(calls), 1)
        finally:
            jobs_mod.start = original_start
            config.setting = original_setting

    def test_a_gap_that_waits_for_a_run_is_served_after_it(self):
        """A gap found while a run is paying for the web is not thrown away."""
        self._page("nicee", "Concile de Nicée",
                   "Le concile de Nicée définit le credo.")
        calls = []
        original = jobs_mod.start
        jobs_mod.start = lambda topic, **kw: (calls.append((topic, kw))
                                             or ("run-1", ""))
        jobs_mod._JOBS["busy"] = {"run": store.Run(id="busy", topic="x",
                                                    status="researching"),
                                  "thread": None}
        try:
            self.assertEqual(theology.maybe_start("concile de Chalcédoine",
                                                  vault=self.vault), "")
            self.assertEqual(len(calls), 0)
            # the other run is over: the waiting gap is served
            jobs_mod._JOBS.pop("busy", None)
            note = theology.maybe_start("concile de Constantinople",
                                        vault=self.vault)
            self.assertIn("run-1", note)
            self.assertIn("en attente", note)
            self.assertEqual(len(calls), 1)
        finally:
            jobs_mod.start = original
            jobs_mod._JOBS.pop("busy", None)

    def test_configuration_can_turn_the_trigger_off(self):
        original = config.setting
        config.setting = lambda name, default=None: (
            False if name == "theology_auto_research" else original(name, default))
        try:
            self.assertFalse(theology.enabled())
            self.assertEqual(theology.maybe_start("concile de Chalcédoine",
                                                  vault=self.vault), "")
        finally:
            config.setting = original

    # ── the loop back ───────────────────────────────────────────────────────
    def test_ingest_files_the_report_as_a_synthesis_page(self):
        report = self.tmp / "report.md"
        report.write_text(
            "---\ntitle: X\n---\n\n# Chalcédoine et les deux natures\n\n"
            "Le concile définit deux natures [1].\n\n"
            "## Sources\n\n1. [Source](https://e.org/chalcedoine)\n",
            encoding="utf-8")
        run = store.Run(id="run-1", topic="concile de Chalcédoine",
                        status="done", report_path=str(report),
                        title="Chalcédoine",
                        outline={"title": "Chalcédoine, deux natures"},
                        sources=[{"n": 1, "url": "https://e.org/chalcedoine",
                                  "title": "Source"}])
        out = theology.ingest(run, vault=self.vault)
        self.assertIn("vault", out.lower())

        pages = list((self.vault / "wiki" / "synthesis").glob("*.md"))
        self.assertEqual(len(pages), 1)
        text = pages[0].read_text(encoding="utf-8")
        self.assertIn("Recherche automatique", text)
        self.assertIn("https://e.org/chalcedoine", text)
        self.assertNotIn("title: X", text)            # report frontmatter gone
        self.assertIn("Chalcédoine", text)

        # the next question on the same subject now hits the vault
        cov = theology.coverage("Chalcédoine deux natures", vault=self.vault)
        self.assertFalse(cov.gap, cov.describe())

    def test_an_ingested_report_carries_its_subject_in_the_title(self):
        """A report filed under a title that does not name its subject reads
        as a passing mention, and the next question buys the same report
        again. The title keeps the subject."""
        report = self.tmp / "report.md"
        report.write_text("# Rapport\n\nLe concile définit deux natures.\n",
                          encoding="utf-8")
        run = store.Run(id="run-3", topic="concile de Chalcédoine",
                        status="done", report_path=str(report),
                        outline={"title": "Rapport de recherche"})
        theology.ingest(run, vault=self.vault)
        pages = list((self.vault / "wiki" / "synthesis").glob("*.md"))
        self.assertEqual(len(pages), 1)
        self.assertIn("Chalcédoine", pages[0].read_text(encoding="utf-8"))
        cov = theology.coverage("concile de Chalcédoine", vault=self.vault)
        self.assertFalse(cov.gap, cov.describe())

    def test_only_a_finished_run_is_filed(self):
        failed = store.Run(id="run-2", topic="x", status="failed")
        self.assertEqual(theology.ingest(failed, vault=self.vault), "")
        self.assertFalse((self.vault / "wiki" / "synthesis").exists())

    # ── wiring ──────────────────────────────────────────────────────────────
    def test_a_plugin_namespace_setting_is_read_by_the_engine(self):
        """The settings tab stores what a plugin declares under
        plugin_config[<namespace>]; the engine reads those by name too."""
        original = config.config_data
        config.config_data = lambda: {
            "plugin_config": {"theology_brain": {
                "theology_auto_research_max_per_day": "7"}}}
        try:
            self.assertEqual(
                str(config.setting("theology_auto_research_max_per_day")), "7")
        finally:
            config.config_data = original

    def test_the_vault_settings_are_declared_for_the_settings_tab(self):
        """A knob the user cannot find is a knob the user cannot turn off."""
        fields = {f["key"] for f in
                  self.bridge.PLUGIN_SETTINGS.get("fields", [])}
        for key in ("theology_auto_research",
                    "theology_auto_research_max_per_day",
                    "theology_auto_research_cooldown",
                    "theology_auto_research_depth"):
            self.assertIn(key, fields)

    def test_the_action_handler_accepts_the_speech_channel(self):
        import inspect
        self.assertIn("speak", inspect.signature(self.bridge.theology_brain).parameters)
        self.assertIn("speak", inspect.signature(self.bridge.run).parameters)

    def test_xerj_appends_the_same_note(self):
        sys.path.insert(0, str(ROOT / "actions"))
        import xerj_search as xerj
        original = theology.maybe_start
        theology.maybe_start = lambda query, **kw: "NOTE XERJ"
        try:
            out = xerj._maybe_auto_research("Aucun passage.",
                                            "concile de Chalcédoine")
        finally:
            theology.maybe_start = original
        self.assertIn("NOTE XERJ", out)
        self.assertTrue(out.startswith("Aucun passage."))

    def test_a_brain_search_appends_the_trigger_note(self):
        original_vault = self.bridge._vault
        original_maybe = theology.maybe_start
        self.bridge._vault = lambda: self.vault
        theology.maybe_start = lambda query, **kw: "NOTE AUTO"
        try:
            out = self.bridge.run({"action": "search",
                                   "query": "concile de Chalcédoine"})
            self.assertIn("NOTE AUTO", out)
            self.assertIn("No wiki page matches", out)

            status = self.bridge.run({"action": "status"})
            self.assertNotIn("NOTE AUTO", status)
        finally:
            self.bridge._vault = original_vault
            theology.maybe_start = original_maybe


class VaultRouterTests(unittest.TestCase):
    """The vault is consulted BEFORE the model answers.

    The application asks the vault itself, so the answer comes from the user's
    own reading — and a religious question the vault does not hold starts a
    research run without the model having to ask for one."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="vault-router-"))
        self.vault = self.tmp / "vault"
        (self.vault / "wiki" / "concepts").mkdir(parents=True)
        (self.vault / "wiki" / "concepts" / "chalcedoine.md").write_text(
            "---\ntitle: Chalcédoine\nkind: concept\n---\n\n"
            "Le concile de Chalcédoine (451) définit les deux natures.\n",
            encoding="utf-8")
        (self.vault / "wiki" / "concepts" / "coran.md").write_text(
            "---\ntitle: Le Coran\nkind: concept\n---\n\n"
            "Le Coran est le texte sacré de l'islam.\n", encoding="utf-8")
        self.router = theology._router()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_a_question_the_vault_holds_is_answered_from_the_vault(self):
        decision = self.router.route("qu'est-ce que l'abrogation du Coran",
                                     vault=self.vault)
        self.assertEqual(decision["kind"], "vault", decision)
        self.assertTrue(decision["pages"])
        self.assertIn("Coran", " ".join(p["title"] for p in decision["pages"]))
        # the conversation is told what it may use, and may cite it
        self.assertIn("[VAULT]", decision["context"])
        self.assertIn("[[", decision["context"])

    def test_a_question_that_is_not_the_vault_s_business_is_left_alone(self):
        for query in ("quelle heure est-il", "mets une alarme dans 10 minutes",
                      "ouvre le navigateur"):
            decision = self.router.route(query, vault=self.vault)
            self.assertEqual(decision["kind"], "none", query)

    def test_a_religious_question_the_vault_lacks_is_a_hole(self):
        decision = self.router.route(
            "quelle est la définition du concile de Constantinople",
            vault=self.vault)
        self.assertEqual(decision["kind"], "gap", decision)
        self.assertTrue(decision["measured"]["gap"])

    def test_a_name_or_a_date_is_not_worth_a_report(self):
        """The assistant knows who the pope is; a sourced report bought with
        the user's quota would be absurd."""
        for query in ("qui est le pape François",
                      "quand est mort le concile de Nicée"):
            decision = self.router.route(query, vault=self.vault)
            self.assertEqual(decision["kind"], "none", query)

    def test_the_router_and_the_trigger_never_disagree(self):
        """One measurement, two callers. If they could drift apart, the
        search the user sees and the report that is bought would be about
        two different questions."""
        for query in ("concile de Chalcédoine", "les deux natures du Christ",
                      "le Coran", "explique-moi l'homoousios"):
            measured = self.router.measure(query, vault=self.vault)
            covered = theology.coverage(query, vault=self.vault)
            self.assertEqual(bool(measured["gap"]), covered.gap, query)
            self.assertEqual(measured["subject"], covered.subject, query)


if __name__ == "__main__":
    unittest.main(verbosity=2)
