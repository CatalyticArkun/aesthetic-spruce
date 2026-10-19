#!/usr/bin/env python3
"""Checks on the stage-2 case matrix produced by utils/make_stage2_cases.py.

What this proves: every case is complete and its generated --expect/--gradient/--icon-style
arguments are well formed and actually enforced by validate_theme.py -- a theme that satisfies
them passes, and one that violates any single one fails.

What it cannot prove: that the app really writes those values. That is what the device run tests.
Stdlib only. Run: python3 -m unittest discover tests
"""
import json, os, re, subprocess, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
GEN = os.path.join(ROOT, "utils", "make_stage2_cases.py")
VALIDATE = os.path.join(ROOT, "utils", "validate_theme.py")
sys.path.insert(0, HERE)
from test_validate_theme import write_rgba, gradient  # noqa: E402  (fixture helpers)


def hex_rgb(s):
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


class Stage2Cases(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(prefix="stage2-")
        r = subprocess.run([sys.executable, GEN, cls.dir], capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        cls.cases = [l.split("\t") for l in
                     open(os.path.join(cls.dir, "CASES.txt")).read().splitlines() if l]

    @classmethod
    def tearDownClass(cls):
        __import__("shutil").rmtree(cls.dir, ignore_errors=True)

    def test_case_count_and_shape(self):
        self.assertEqual(len(self.cases), 71, "33 per-option + 4 combinations + 34 presets")
        kinds = [s.split("-", 1)[1].split("-")[0] for s, _ in self.cases]
        self.assertEqual(kinds.count("opt"), 33)
        self.assertEqual(kinds.count("combo"), 4)
        self.assertEqual(kinds.count("preset"), 34)

    def test_every_case_is_complete(self):
        for stem, theme in self.cases:
            p = os.path.join(self.dir, stem)
            self.assertTrue(os.path.exists(p + ".args"), stem)
            self.assertTrue(os.path.exists(p + ".theme"), stem)
            self.assertTrue(os.path.exists(p + ".lua"), stem)
            self.assertEqual(open(p + ".theme").read().strip(), theme)

    def test_every_theme_name_is_one_we_own(self):
        """A case must never build under a preset's own name: it would overwrite a user theme and
        then the pass path would delete it."""
        for stem, theme in self.cases:
            self.assertRegex(theme, r"^S2\d{3}$", f"{stem} would build under {theme!r}")
        src = open(os.path.join(ROOT, "src", "presets", "win95.lua")).read()
        self.assertIn("Win95", src, "fixture assumption: the preset names itself Win95")
        case = next(s for s, _ in self.cases if s.endswith("preset-win95"))
        body = open(os.path.join(self.dir, case + ".lua")).read()
        self.assertNotIn('themeName = "Win95"', body, "the preset's own name must be rewritten")
        self.assertIn('themeName = "S2', body)

    def test_only_sprite_art_is_asserted_two_tone(self):
        """Glyph (the default) and Letter draw one ink colour; only SPRUCE Art is two-tone.
        Asserting otherwise failed every icon-bearing case on the device on 2026-10-19."""
        seen = {"mono": 0, "multi": 0}
        for stem, _ in self.cases:
            args = open(os.path.join(self.dir, stem + ".args")).read()
            lua = open(os.path.join(self.dir, stem + ".lua")).read()
            m = re.search(r'systemIconStyle = "([^"]+)"', lua)
            style = m.group(1) if m else "Glyph"
            if "--icon-style" not in args:
                continue
            want = "multi" if style == "SPRUCE Art" else "mono"
            got = args.split("--icon-style")[1].split()[0]
            self.assertEqual(got, want, f"{stem} (style {style}) asserts {got}")
            seen[got] += 1
        self.assertGreater(seen["mono"], 0)
        self.assertGreater(seen["multi"], 0, "no case covers the two-tone style")

    def test_theme_names_are_unique(self):
        names = [t for _, t in self.cases]
        self.assertEqual(len(names), len(set(names)), "two cases would write the same theme dir")

    def test_only_known_flags_are_emitted(self):
        known = {"--expect", "--gradient", "--icon-style"}
        for stem, _ in self.cases:
            for tok in open(os.path.join(self.dir, stem + ".args")).read().split():
                if tok.startswith("--"):
                    self.assertIn(tok, known, f"{stem} emits an unknown flag {tok}")

    def test_icon_checks_are_skipped_when_there_are_no_icons(self):
        """systemIcons=false produces no icons dir, so asserting a tone would be a false failure."""
        stem = next(s for s, _ in self.cases if "opt-systemIcons" in s)
        args = open(os.path.join(self.dir, stem + ".args")).read()
        self.assertNotIn("--icon-style", args)
        self.assertIn('systemSelectViewType="TEXT_ONLY"', args,
                      "pyui_config forces TEXT_ONLY when icons are off")

    # ---- the generated arguments are enforceable ------------------------------------------------

    def _theme_for(self, args, root):
        """Build a theme that satisfies `args`, so the validator must pass it."""
        os.makedirs(os.path.join(root, "skin"), exist_ok=True)
        os.makedirs(os.path.join(root, "icons"), exist_ok=True)
        w, h = 64, 48
        toks = args.split()
        grad = next((toks[i + 1] for i, t in enumerate(toks) if t == "--gradient"), None)
        bgp = os.path.join(root, "skin", "background.png")
        if grad and grad != "solid":
            direction, _, stops = grad.partition(":")
            a, b = [hex_rgb(x) for x in stops.split(",")]
            if direction == "vertical":
                write_rgba(bgp, w, h, gradient(a, b, h))
            else:
                write_rgba(bgp, w, h, lambda x, y, a=a, b=b: tuple(
                    round(p + (q - p) * (x / (w - 1))) for p, q in zip(a, b)) + (255,))
        else:
            write_rgba(bgp, w, h, lambda x, y: (30, 30, 30, 255))
        style = next((toks[i + 1] for i, t in enumerate(toks) if t == "--icon-style"), None)
        if style:
            tones = ((200, 200, 200), (90, 90, 90))
            for n in ("gb", "snes"):
                p = os.path.join(root, "icons", n + ".png")
                if style == "mono":
                    write_rgba(p, 120, 130, lambda x, y: tones[0] + (255 if (x + y) % 3 else 0,))
                else:
                    write_rgba(p, 120, 130, lambda x, y: tones[(x * 7 + y * 3) % 2] + (255,))
        cfg = {"name": "T"}
        for i, t in enumerate(toks):
            if t == "--expect":
                k, _, v = toks[i + 1].partition("=")
                try:
                    cfg[k] = json.loads(v)
                except ValueError:
                    cfg[k] = v
        json.dump(cfg, open(os.path.join(root, "config.json"), "w"))
        return cfg

    def _run(self, theme, args):
        r = subprocess.run([sys.executable, VALIDATE, theme, "--spruce", "/nonexistent",
                            "--prebake", "/nonexistent", *args.split()],
                           capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr

    def test_a_conforming_theme_passes_every_case(self):
        for stem, _ in self.cases:
            args = open(os.path.join(self.dir, stem + ".args")).read().strip()
            if not args:
                continue
            with tempfile.TemporaryDirectory() as t:
                self._theme_for(args, t)
                rc, out = self._run(t, args)
                self.assertEqual(rc, 0, f"{stem}: a conforming theme was rejected:\n{out}")

    def test_each_expectation_is_actually_enforced(self):
        """Violate one --expect per case and the validator must fail. Guards vacuous assertions."""
        checked = 0
        for stem, _ in self.cases[:20]:
            args = open(os.path.join(self.dir, stem + ".args")).read().strip()
            toks = args.split()
            if "--expect" not in toks:
                continue
            with tempfile.TemporaryDirectory() as t:
                cfg = self._theme_for(args, t)
                k = toks[toks.index("--expect") + 1].split("=")[0]
                cfg[k] = "WRONG-VALUE" if not isinstance(cfg[k], bool) else (not cfg[k])
                json.dump(cfg, open(os.path.join(t, "config.json"), "w"))
                rc, out = self._run(t, args)
                self.assertEqual(rc, 1, f"{stem}: breaking {k} did not fail the checker")
                self.assertIn(k, out)
                checked += 1
        self.assertGreater(checked, 10, "too few cases exercised")

    def test_gradient_cases_detect_a_flat_background(self):
        stem = next(s for s, _ in self.cases if "combo-reporter" in s)
        args = open(os.path.join(self.dir, stem + ".args")).read().strip()
        self.assertIn("--gradient vertical:", args)
        with tempfile.TemporaryDirectory() as t:
            self._theme_for(args, t)
            write_rgba(os.path.join(t, "skin", "background.png"), 64, 48,
                       lambda x, y: (30, 64, 175, 255))      # the gradient that never rendered
            rc, out = self._run(t, args)
            self.assertEqual(rc, 1)
            self.assertIn("endpoints identical", out)


if __name__ == "__main__":
    unittest.main()
