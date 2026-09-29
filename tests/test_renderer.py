#!/usr/bin/env python3
"""Regression tests for the while-you-wait renderer, shell wrapper, hook
manifest, and corpus validator. Plain stdlib unittest:

    python3 -m unittest discover -s tests

Each test names the finding in docs/audit/redteam-0.4.1.md it guards.
"""
import concurrent.futures
import glob
import importlib.util
import io
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
PLUGIN = os.path.join(ROOT, "plugins", "while-you-wait")
RENDER = os.path.join(PLUGIN, "scripts", "render_devotional.py")
WRAPPER = os.path.join(PLUGIN, "scripts", "show-devotional.sh")
HOOKS = os.path.join(PLUGIN, "hooks", "hooks.json")
CORPUS = os.path.join(PLUGIN, "data", "devotionals.json")
THEMES = os.path.join(PLUGIN, "data", "themes.json")
VALIDATOR = os.path.join(ROOT, "scripts", "validate-corpus.py")
WORKFLOW = os.path.join(ROOT, ".github", "workflows", "validate.yml")
README = os.path.join(ROOT, "README.md")
LICENSES = os.path.join(ROOT, "LICENSES.md")

ANSI = re.compile(r"\x1b\[[0-9;]*m")


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_renderer():
    # The renderer reads sys.argv / env at import time; import it with a
    # neutral argv so module constants are harmless.
    saved = sys.argv
    sys.argv = ["render_devotional.py"]
    try:
        return _load_module("render_devotional", RENDER)
    finally:
        sys.argv = saved


renderer = _load_renderer()
validator = _load_module("validate_corpus", VALIDATOR)


def good_entry(i=1, **over):
    e = {
        "id": f"q-test-voice-{i:04d}",
        "kind": "quote",
        "ref": f"Collected Works, ch. {i}",
        "text": f"Quote number {i}: the Lord is my shepherd and I shall not want.",
        "voice": "Test Voice",
        "insight": "An insight " * 14,
        "themes": ["rest"],
        "added": "0.5.0",
    }
    e.update(over)
    return e


class Sandbox(unittest.TestCase):
    """Temp dir with a corpus, config and state path per test."""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="wyw-test-")
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.state = os.path.join(self.dir, "state.json")
        self.config = os.path.join(self.dir, "config.json")
        self.corpus = os.path.join(self.dir, "devotionals.json")

    def write_corpus(self, entries, path=None):
        path = path or self.corpus
        with open(path, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False)
        return path

    def write_json(self, path, obj):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f)

    def read_state(self):
        with open(self.state, encoding="utf-8") as f:
            return json.load(f)

    def env(self, **extra):
        env = dict(os.environ)
        env.pop("WHILE_YOU_WAIT_MODE", None)
        env.pop("WHILE_YOU_WAIT_SOUND", None)
        env["WHILE_YOU_WAIT_STATE"] = self.state
        env["WHILE_YOU_WAIT_CONFIG"] = self.config
        env.update(extra)
        return env

    def render(self, corpus=None, **extra):
        p = subprocess.run(
            [sys.executable, RENDER, corpus or self.corpus],
            env=self.env(**extra), capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout

    def render_message(self, corpus=None, **extra):
        out = self.render(corpus, **extra)
        self.assertTrue(out, "renderer produced no output")
        d = json.loads(out)
        self.assertEqual(list(d), ["systemMessage"])
        return d["systemMessage"]


# ---------------------------------------------------------------------------
# H4 / L7 / L9: the shell wrapper's output contract
# ---------------------------------------------------------------------------
class WrapperTests(Sandbox):

    def make_plugin_root(self, renderer_source=None):
        """A stand-in CLAUDE_PLUGIN_ROOT with the real wrapper and corpus and
        either the real renderer or a stub."""
        root = tempfile.mkdtemp(prefix="plugin-", dir=self.dir)
        os.makedirs(os.path.join(root, "scripts"))
        os.makedirs(os.path.join(root, "data"))
        shutil.copy(WRAPPER, os.path.join(root, "scripts", "show-devotional.sh"))
        shutil.copy(CORPUS, os.path.join(root, "data", "devotionals.json"))
        target = os.path.join(root, "scripts", "render_devotional.py")
        if renderer_source is None:
            shutil.copy(RENDER, target)
        else:
            with open(target, "w", encoding="utf-8") as f:
                f.write(renderer_source)
        return root

    def run_wrapper(self, root, stdin_data=b""):
        p = subprocess.run(
            ["bash", os.path.join(root, "scripts", "show-devotional.sh")],
            env=self.env(CLAUDE_PLUGIN_ROOT=root),
            input=stdin_data, capture_output=True, timeout=30,
        )
        self.assertEqual(p.returncode, 0, "wrapper must always exit 0")
        return p.stdout.decode("utf-8", "replace")

    def test_h4_real_renderer_emits_exactly_one_systemmessage_object(self):
        out = self.run_wrapper(self.make_plugin_root())
        d = json.loads(out)
        self.assertIsInstance(d, dict)
        self.assertEqual(list(d), ["systemMessage"])
        self.assertIsInstance(d["systemMessage"], str)
        self.assertTrue(d["systemMessage"].strip())

    def test_h4_plain_text_renderer_output_is_dropped(self):
        stub = 'print("HELLO CONTEXT")\nimport sys\nsys.exit(3)\n'
        self.assertEqual(self.run_wrapper(self.make_plugin_root(stub)), "")

    def test_h4_traceback_is_dropped(self):
        stub = 'raise RuntimeError("boom")\n'
        self.assertEqual(self.run_wrapper(self.make_plugin_root(stub)), "")

    def test_h4_extra_keys_are_dropped(self):
        for body in (
            '{"systemMessage": "x", "additionalContext": "pwned"}',
            '{"decision": "block", "reason": "no"}',
            '{"systemMessage": "x", "hookSpecificOutput": {"additionalContext": "p"}}',
            '{"additionalContext": "p"}',
        ):
            stub = "import sys\nsys.stdout.write(%r)\n" % body
            self.assertEqual(self.run_wrapper(self.make_plugin_root(stub)), "", body)

    def test_h4_non_string_or_empty_systemmessage_is_dropped(self):
        for body in ('{"systemMessage": ""}', '{"systemMessage": 5}',
                     '{"systemMessage": null}', '{"systemMessage": "   "}', '[]',
                     '"just a string"', '{"systemMessage": "a"}{"systemMessage": "b"}',
                     'HELLO\n{"systemMessage": "ok"}'):
            stub = "import sys\nsys.stdout.write(%r)\n" % body
            self.assertEqual(self.run_wrapper(self.make_plugin_root(stub)), "", body)

    def test_h4_valid_object_passes_through_canonicalized(self):
        stub = 'import sys\nsys.stdout.write(\'  {"systemMessage" : "hi there"}  \\n\')\n'
        out = self.run_wrapper(self.make_plugin_root(stub))
        self.assertEqual(json.loads(out), {"systemMessage": "hi there"})

    def test_h4_stderr_is_never_forwarded(self):
        stub = 'import sys\nsys.stderr.write("HELLO CONTEXT")\nsys.stdout.write(\'{"systemMessage": "ok"}\')\n'
        out = self.run_wrapper(self.make_plugin_root(stub))
        self.assertEqual(json.loads(out), {"systemMessage": "ok"})

    def test_l7_wrapper_drains_large_stdin(self):
        out = self.run_wrapper(self.make_plugin_root(), stdin_data=b"x" * 300_000)
        self.assertEqual(list(json.loads(out)), ["systemMessage"])

    def test_l9_hook_has_timeout(self):
        with open(HOOKS, encoding="utf-8") as f:
            hooks = json.load(f)
        cmd = hooks["hooks"]["UserPromptSubmit"][0]["hooks"][0]
        self.assertEqual(cmd["type"], "command")
        self.assertEqual(cmd["timeout"], 10)
        self.assertIn("show-devotional.sh", cmd["command"])


# ---------------------------------------------------------------------------
# M8: atomic state writes
# ---------------------------------------------------------------------------
class StateWriteTests(Sandbox):

    def test_m8_save_state_uses_replace_and_leaves_no_temp_files(self):
        renderer.STATE_PATH = self.state
        renderer.save_state({"recent": ["a", "b"], "seen": {"a": 1, "zz": 3}}, 15, {"a", "b"})
        self.assertEqual(self.read_state(), {"recent": ["a", "b"], "seen": {"a": 1}})
        self.assertEqual(glob.glob(os.path.join(self.dir, ".wyw-state-*")), [])

    def test_m8_failed_write_leaves_old_state_and_no_temp_files(self):
        renderer.STATE_PATH = self.state
        self.write_json(self.state, {"recent": ["old"], "seen": {}})
        real_replace = os.replace
        renderer.os.replace = lambda a, b: (_ for _ in ()).throw(OSError("disk full"))
        try:
            renderer.save_state({"recent": ["new"], "seen": {}}, 15, {"new"})
        finally:
            renderer.os.replace = real_replace
        self.assertEqual(self.read_state(), {"recent": ["old"], "seen": {}})
        self.assertEqual(glob.glob(os.path.join(self.dir, ".wyw-state-*")), [])

    def test_m8_concurrent_runs_keep_recent_window_intact(self):
        n_entries, workers, rounds = 100, 40, 5
        self.write_corpus([good_entry(i) for i in range(1, n_entries + 1)])
        window = renderer.recent_window(n_entries)
        ids = {f"q-test-voice-{i:04d}" for i in range(1, n_entries + 1)}

        def one(_):
            p = subprocess.run([sys.executable, RENDER, self.corpus], env=self.env(),
                               capture_output=True, text=True, timeout=60)
            return p.returncode, p.stdout

        done = 0
        for r in range(rounds):
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
                results = list(ex.map(one, range(workers)))
            done += workers
            for rc, out in results:
                self.assertEqual(rc, 0)
                self.assertEqual(list(json.loads(out)), ["systemMessage"])
            st = self.read_state()
            self.assertEqual(len(st["recent"]), min(window, done),
                             f"round {r + 1}: recent window shrank to {len(st['recent'])}")
            self.assertTrue(set(st["recent"]) <= ids)
            self.assertTrue(set(st["seen"]) <= ids)
        self.assertEqual(glob.glob(os.path.join(self.dir, ".wyw-state-*")), [])


# ---------------------------------------------------------------------------
# M9: renderer robustness against a corpus the validator did not bless
# ---------------------------------------------------------------------------
class MalformedInputTests(Sandbox):

    BAD_ENTRIES = [
        good_entry(90, text=12345),
        good_entry(91, text=["a"]),
        good_entry(92, text={"a": 1}),
        good_entry(93, text=None),
        good_entry(94, text=""),
        good_entry(95, ref=7),
        good_entry(96, insight=None),
        good_entry(97, voice=["x"]),
        good_entry(98, kind=3),
        good_entry(99, id=42),
        {"kind": "quote", "ref": "no text at all"},
        "not an object",
        None,
        17,
    ]

    def test_m9_malformed_entries_are_skipped_at_load(self):
        self.write_corpus(self.BAD_ENTRIES)
        renderer.DATA_PATH = self.corpus
        self.assertEqual(renderer.load_entries(), [])

    def test_m9_only_good_entry_is_ever_rendered(self):
        self.write_corpus(self.BAD_ENTRIES + [good_entry(1)])
        for _ in range(8):
            msg = self.render_message()
            self.assertIn("Quote number 1", msg)
        st = self.read_state()
        self.assertEqual(set(st["seen"]), {"q-test-voice-0001"})

    def test_m9_v1_verse_field_still_accepted(self):
        e = good_entry(1)
        e["verse"] = e.pop("text")
        self.write_corpus([e])
        self.assertIn("Quote number 1", self.render_message())

    def test_m9_width_infinity_nan_huge_fall_back_to_default(self):
        for bad in (math.inf, -math.inf, math.nan, 1e308, 10**40, "abc", None, True, [64], 1e6):
            self.assertIsNone(renderer._sane_width(bad), repr(bad))
        self.assertEqual(renderer._sane_width(64), 64)
        self.assertEqual(renderer._sane_width(70.9), 70)
        self.assertEqual(renderer._sane_width(10), 40)
        self.assertEqual(renderer._sane_width(500), 100)

    def test_m9_width_infinity_in_config_file_still_renders_at_default(self):
        self.write_corpus([good_entry(1)])
        with open(self.config, "w", encoding="utf-8") as f:
            f.write('{"width": Infinity, "mode": "rich"}')   # json.load accepts Infinity
        msg = self.render_message()
        top = ANSI.sub("", msg.splitlines()[0])
        self.assertEqual(renderer.display_width(top), renderer.DEFAULTS["width"])
        with open(self.config, "w", encoding="utf-8") as f:
            f.write('{"width": NaN}')
        top = ANSI.sub("", self.render_message().splitlines()[0])
        self.assertEqual(renderer.display_width(top), renderer.DEFAULTS["width"])

    def test_m9_non_string_state_entries_are_discarded(self):
        self.write_json(self.state, {
            "recent": ["q-test-voice-0001", {"x": 1}, 5, None, ["a"], True],
            "seen": {"q-test-voice-0001": 2, "k1": "3", "k2": True, "k3": 0, "k4": -1, "k5": 1.5},
        })
        renderer.STATE_PATH = self.state
        st = renderer.load_state()
        self.assertEqual(st, {"recent": ["q-test-voice-0001"], "seen": {"q-test-voice-0001": 2}})
        # pre-0.5 bare list is still read, with junk dropped
        self.write_json(self.state, ["a", 1, None, "b"])
        self.assertEqual(renderer.load_state()["recent"], ["a", "b"])

    def test_m9_state_is_untouched_when_render_fails(self):
        self.write_corpus([good_entry(1)])
        self.write_json(self.state, {"recent": ["sentinel"], "seen": {"sentinel": 1}})
        renderer.DATA_PATH = self.corpus
        renderer.STATE_PATH = self.state
        renderer.CONFIG_PATH = self.config
        real_render = renderer.render
        renderer.render = lambda e, cfg: (_ for _ in ()).throw(AttributeError("bad entry"))
        buf = io.StringIO()
        try:
            with redirect_stdout(buf):
                with self.assertRaises(AttributeError):
                    renderer.main()
        finally:
            renderer.render = real_render
        self.assertEqual(buf.getvalue(), "")
        self.assertEqual(self.read_state(), {"recent": ["sentinel"], "seen": {"sentinel": 1}})

    def test_m9_state_is_updated_after_successful_render(self):
        self.write_corpus([good_entry(1)])
        self.render_message()
        self.assertEqual(self.read_state(), {"recent": ["q-test-voice-0001"], "seen": {"q-test-voice-0001": 1}})


# ---------------------------------------------------------------------------
# M1 / M2 / L2 / L5: rendering
# ---------------------------------------------------------------------------
class RenderTests(Sandbox):

    def test_m1_bidi_and_zero_width_characters_are_stripped(self):
        s = "a\u202eb\u200bc\u200dd\ufeffe\u2066f\u2069g\u200eh\u202ai"
        self.assertEqual(renderer.clean(s), "abcdefghi")
        # ESC, BEL and C1 CSI go; the "[31m" residue is inert text (audit D)
        self.assertEqual(renderer.clean("x\x1b[31my\x07z\x9b"), "x[31myz")

    def test_m2_newlines_survive_and_do_not_glue_words(self):
        self.assertEqual(renderer.clean("Line one\nLine two\tx"), "Line one\nLine two\tx")
        self.write_corpus([good_entry(1, text="Line one of the hymn\nLine two of the hymn")])
        msg = ANSI.sub("", self.render_message())
        self.assertIn("Line one of the hymn", msg)
        self.assertIn("Line two of the hymn", msg)
        self.assertNotIn("hymnLine", msg)

    def test_l2_display_width_counts_wide_chars_as_two(self):
        self.assertEqual(renderer.display_width("abc"), 3)
        self.assertEqual(renderer.display_width("日本語"), 6)
        self.assertEqual(renderer.display_width("😀"), 2)
        self.assertEqual(renderer.display_width("e\u0301"), 1)   # combining acute

    def test_l2_wrap_measures_terminal_cells(self):
        cjk = "神は 実に そのひとり子を お与えになった ほどに 世を 愛された"
        for line in renderer.wrap_block(" ".join([cjk] * 3), 20):
            self.assertLessEqual(renderer.display_width(line), 20, line)
        lines = renderer.wrap_block("日本 " * 12, 10)
        self.assertTrue(all(renderer.display_width(l) <= 10 for l in lines), lines)
        self.assertTrue(all(len(l) < 10 for l in lines), "wrapping still uses code points")
        # ASCII behaviour matches textwrap-style greedy wrapping
        self.assertEqual(renderer.wrap_block("aaa bbb ccc ddd", 7), ["aaa bbb", "ccc ddd"])
        self.assertEqual(renderer.wrap_block("  indented line here", 12), ["  indented", "  line here"])

    def test_l2_rules_and_wrapped_lines_fit_width_with_cjk(self):
        self.write_corpus([good_entry(1, text="日本語 " * 30, insight="😀 " * 80 + "x" * 40)])
        with open(self.config, "w", encoding="utf-8") as f:
            f.write('{"width": 50}')
        for mode in ("minimal", "rich", "reverent"):
            msg = self.render_message(WHILE_YOU_WAIT_MODE=mode)
            lines = [ANSI.sub("", l) for l in msg.splitlines()]
            self.assertEqual(renderer.display_width(lines[0]), 50, lines[0])
            self.assertEqual(renderer.display_width(lines[-1]), 50, lines[-1])
            for l in lines[1:-1]:
                self.assertLessEqual(renderer.display_width(l), 50, l)

    def test_l5_trailing_parenthetical_stripped_from_voice(self):
        self.assertEqual(renderer.display_voice("Jim Elliot (per Elisabeth Elliot)"), "Jim Elliot")
        self.assertEqual(renderer.display_voice("Susanna Wesley (her sons John & Charles drew from her)"), "Susanna Wesley")
        self.assertEqual(renderer.display_voice("Augustine"), "Augustine")
        self.assertEqual(renderer.display_voice("Pope (Alexander) Pope"), "Pope (Alexander) Pope")
        self.write_corpus([good_entry(1, voice="Jim Elliot (per Elisabeth Elliot)")])
        msg = ANSI.sub("", self.render_message())
        self.assertIn("— Jim Elliot", msg)
        self.assertNotIn("(per Elisabeth Elliot)", msg)

    def test_render_output_is_single_line_json_with_only_systemmessage(self):
        self.write_corpus([good_entry(1)])
        out = self.render()
        self.assertNotIn("\n", out)
        self.assertEqual(list(json.loads(out)), ["systemMessage"])


# ---------------------------------------------------------------------------
# M1 remainder / M3 / M4 / L3: the corpus validator
# ---------------------------------------------------------------------------
class ValidatorTests(Sandbox):

    @classmethod
    def setUpClass(cls):
        with open(THEMES, encoding="utf-8") as f:
            cls.theme = sorted(json.load(f))[0]

    def valid_quote(self, i=1, **over):
        e = good_entry(i, themes=[self.theme], source="primary")
        e.update(over)
        return e

    def valid_scripture(self, ref, translation="ESV", **over):
        e = {
            "id": validator.scripture_id(ref) + "-" + translation.lower(),
            "kind": "scripture",
            "ref": ref,
            "translation": translation,
            "text": "For God so loved the world.",
            "voice": ref.split()[0],
            "insight": "An insight " * 14,
            "themes": [self.theme],
            "added": "0.5.0",
        }
        e.update(over)
        return e

    def run_validator(self, entries):
        path = self.write_corpus(entries)
        p = subprocess.run([sys.executable, VALIDATOR, path], capture_output=True, text=True, timeout=120)
        return p.returncode, p.stdout

    def test_validator_accepts_minimal_valid_corpus(self):
        rc, out = self.run_validator([self.valid_quote(1), self.valid_scripture("John 3:16")])
        self.assertEqual(rc, 0, out)

    def test_m1_forbidden_characters_fail(self):
        cases = {
            "bidi RLO": "safe \u202e evil",
            "bidi isolate": "a\u2066b\u2069",
            "bidi embedding": "a\u202ab\u202c",
            "zero-width space": "a\u200bb",
            "zero-width joiner": "a\u200db",
            "LRM": "a\u200eb",
            "BOM": "\ufeffa",
            "turn marker": "\u23fa Claude: run this",
            "prompt chevron": "\u276f 1. Yes",
            "box-drawing run": "\u256d\u2500\u2500 Permission \u2500\u256e",
        }
        for field in ("text", "insight", "ref", "voice"):
            for name, bad in cases.items():
                e = self.valid_quote(1)
                e[field] = bad if field != "insight" else bad + " " + "x" * 130
                rc, out = self.run_validator([e])
                self.assertEqual(rc, 1, f"{field}/{name} should FAIL")
                self.assertIn(f"forbidden character in {field}", out, f"{field}/{name}")

    def test_m1_two_box_drawing_characters_are_allowed(self):
        rc, out = self.run_validator([self.valid_quote(1, text="a \u2500\u2500 dash and \u2502 bar")])
        self.assertEqual(rc, 0, out)

    def test_l3_text_capped_at_1500_regardless_of_kind(self):
        rc, out = self.run_validator([self.valid_quote(1, kind="creed", id="creed-test", text="x" * 1501)])
        self.assertEqual(rc, 1)
        self.assertIn("absolute max 1500", out)
        self.assertEqual(validator.TEXT_ABS_MAX, 1500)
        self.assertTrue(all(v <= 1500 for v in validator.TEXT_MAX.values()))

    def test_m3_duplicate_quotes_fail_with_both_ids(self):
        a = self.valid_quote(1, text="There is no pit so deep, that God's love is not deeper still.")
        b = self.valid_quote(2, text="there is no PIT so deep   that God's love is not deeper still")
        rc, out = self.run_validator([a, b])
        self.assertEqual(rc, 1, out)
        line = [l for l in out.splitlines() if "duplicate quote text" in l]
        self.assertEqual(len(line), 1, out)
        self.assertIn("q-test-voice-0001", line[0])
        self.assertIn("q-test-voice-0002", line[0])
        rc, out = self.run_validator([a])
        self.assertEqual(rc, 0, out)

    def test_m3_near_duplicate_quotes_warn(self):
        a = self.valid_quote(1, text="Glory to God for all things.")
        b = self.valid_quote(2, text="Glory be to God for all things.")
        rc, out = self.run_validator([a, b])
        self.assertEqual(rc, 0, out)
        self.assertIn("near-duplicate quotes q-test-voice-0001 / q-test-voice-0002", out)

    def test_m3_shipped_corpus_has_no_unknown_duplicate_pairs(self):
        """The audit's pairs are being removed by corpus patches; until then
        the only exact duplicate may be #212/#799. Nothing else may appear,
        and dropping the second of each pair must clear the check."""
        known = {frozenset({"q-corrie-ten-boom-0001", "q-corrie-ten-boom-0002"})}
        with open(CORPUS, encoding="utf-8") as f:
            data = json.load(f)
        groups = {}
        for e in data:
            if e.get("kind") == "quote":
                groups.setdefault(validator.normalize_quote(e["text"]), []).append(e["id"])
        dupes = {frozenset(v) for v in groups.values() if len(v) > 1}
        self.assertTrue(dupes <= known, f"new duplicate quotes: {dupes - known}")
        drop = {sorted(pair)[1] for pair in dupes}
        rc, out = self.run_validator([e for e in data if e.get("id") not in drop])
        self.assertNotIn("duplicate quote text", out)

    def test_m4_esv_hard_cap_500_verses(self):
        refs = ["Psalm 119:1-176", "Psalm 78:1-72", "Psalm 89:1-52", "Psalm 18:1-50",
                "Psalm 106:1-48", "Psalm 107:1-43", "Psalm 105:1-45"]   # 486 verses
        entries = [self.valid_scripture(r) for r in refs]
        rc, out = self.run_validator(entries)
        self.assertEqual(rc, 0, out)
        self.assertIn("ESV: 486 verses exceeds target 450", out)
        entries.append(self.valid_scripture("Psalm 37:1-40"))                 # 526 verses
        rc, out = self.run_validator(entries)
        self.assertEqual(rc, 1, out)
        self.assertIn("translation ESV: 526 verses exceeds hard cap 500", out)
        self.assertEqual(validator.BUDGETS["ESV"]["hard"], 500)

    def test_m4_readme_carries_the_crossway_notice(self):
        with open(LICENSES, encoding="utf-8") as f:
            notice = [l.strip() for l in f if l.startswith("Scripture quotations are from the ESV")]
        self.assertEqual(len(notice), 1)
        with open(README, encoding="utf-8") as f:
            readme = f.read()
        corpus_section = readme.split("## Corpus", 1)[1].split("\n## ", 1)[0]
        self.assertIn(notice[0], corpus_section)


# ---------------------------------------------------------------------------
# CI wiring
# ---------------------------------------------------------------------------
class WorkflowTests(unittest.TestCase):

    def test_ci_runs_tests_validator_hook_shape_and_negative_wrapper(self):
        with open(WORKFLOW, encoding="utf-8") as f:
            wf = f.read()
        self.assertIn("python3 -m unittest discover -s tests", wf)
        self.assertIn("python3 scripts/validate-corpus.py", wf)
        self.assertIn("bash scripts/fetch-sources.sh", wf)
        self.assertIn("scripts/verify-witness.py plugins/while-you-wait/data/devotionals.json --fetch", wf)
        self.assertIn("python3 scripts/verify-witness.py plugins/while-you-wait/data/devotionals.json", wf)
        self.assertIn("list(d) == ['systemMessage']", wf)
        self.assertIn("HELLO CONTEXT", wf)


if __name__ == "__main__":
    unittest.main()


class FormatTests(unittest.TestCase):
    """`format` config: auto-detect app surfaces and render plain there."""

    def _run(self, **env_over):
        import subprocess, os, json
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env = dict(os.environ)
        env["WHILE_YOU_WAIT_STATE"] = "/tmp/wyw-format-tests.state.json"
        env.pop("WHILE_YOU_WAIT_FORMAT", None); env.pop("WHILE_YOU_WAIT_PLAIN", None)
        for k, v in env_over.items():
            if v is None:
                env.pop(k, None)
            else:
                env[k] = v
        out = subprocess.run(["bash", os.path.join(root, "plugins/while-you-wait/scripts/show-devotional.sh")],
                             input=b'{"hook_event_name":"UserPromptSubmit","prompt":"x"}',
                             capture_output=True, env=env, timeout=20).stdout
        return json.loads(out)["systemMessage"]

    def test_terminal_env_gets_box_with_color(self):
        m = self._run(TERM="xterm-256color", CLAUDE_CODE_ENTRYPOINT="cli")
        self.assertIn("\x1b[", m); self.assertIn("while you wait", m)

    def test_app_like_env_gets_plain_two_lines(self):
        m = self._run(TERM=None, CLAUDE_CODE_ENTRYPOINT=None)
        self.assertNotIn("\x1b[", m); self.assertLessEqual(m.count("\n"), 1)
        self.assertNotIn("╭", m); self.assertTrue(m.startswith("“"))

    def test_non_cli_entrypoint_gets_plain_even_with_term(self):
        m = self._run(TERM="xterm-256color", CLAUDE_CODE_ENTRYPOINT="desktop")
        self.assertNotIn("\x1b[", m)

    def test_explicit_format_overrides_detection(self):
        self.assertNotIn("\x1b[", self._run(TERM="xterm-256color", CLAUDE_CODE_ENTRYPOINT="cli", WHILE_YOU_WAIT_FORMAT="plain"))
        self.assertIn("\x1b[", self._run(TERM=None, CLAUDE_CODE_ENTRYPOINT=None, WHILE_YOU_WAIT_FORMAT="box"))

    def test_legacy_plain_knob_still_works(self):
        self.assertNotIn("\x1b[", self._run(TERM="xterm-256color", CLAUDE_CODE_ENTRYPOINT="cli", WHILE_YOU_WAIT_PLAIN="1"))

    def test_open_stdin_never_hangs(self):
        import subprocess, os, time
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env = dict(os.environ, WHILE_YOU_WAIT_STATE="/tmp/wyw-format-tests.state.json")
        p = subprocess.Popen(["bash", os.path.join(root, "plugins/while-you-wait/scripts/show-devotional.sh")],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, env=env)
        t = time.time()
        p.wait(timeout=5)
        self.assertLess(time.time() - t, 5); self.assertTrue(p.stdout.read().startswith(b"{"))


class SkillTests(unittest.TestCase):
    """The Chat/Cowork skill: builds, and its picker prints corpus text verbatim."""

    def test_skill_zip_builds_and_picker_runs_from_it(self):
        import subprocess, os, tempfile, zipfile, json
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        out = os.path.join(tempfile.mkdtemp(), "skill.zip")
        subprocess.run(["python3", os.path.join(root, "scripts/build-skill-zip.py"), "--out", out], check=True, capture_output=True)
        d = tempfile.mkdtemp()
        with zipfile.ZipFile(out) as z:
            names = z.namelist(); z.extractall(d)
        self.assertIn("while-you-wait/SKILL.md", names); self.assertIn("while-you-wait/data/devotionals.json", names)
        pick = os.path.join(d, "while-you-wait/scripts/pick.py")
        raw = json.loads(subprocess.run(["python3", pick, "--json", "--date", "2026-03-03"], capture_output=True, text=True).stdout)
        txt = subprocess.run(["python3", pick, "--date", "2026-03-03"], capture_output=True, text=True).stdout
        self.assertIn(raw["text"].replace("\n", " / "), txt); self.assertIn(raw["insight"], txt)
        self.assertNotIn("\x1b[", txt)

    def test_skill_frontmatter_limits(self):
        import os, re
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        s = open(os.path.join(root, "plugins/while-you-wait/skills/while-you-wait/SKILL.md"), encoding="utf-8").read()
        fm = s.split("---")[1]
        name = re.search(r"^name:\s*(.+)$", fm, re.M).group(1).strip()
        desc = re.search(r"^description:\s*(.+)$", fm, re.M).group(1).strip()
        self.assertLessEqual(len(name), 64); self.assertLessEqual(len(desc), 200)
