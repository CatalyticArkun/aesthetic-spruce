#!/usr/bin/env python3
"""Self-test for utils/validate_theme.py: builds throwaway themes and checks what it reports.

Stdlib only, so it runs in CI and on a device's own python. Run: python3 -m unittest discover tests
"""
import json, os, struct, subprocess, sys, tempfile, unittest, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
VALIDATE = os.path.join(HERE, "..", "utils", "validate_theme.py")


def _chunk(kind, body):
    return (struct.pack(">I", len(body)) + kind + body
            + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF))


def write_rgba(path, w, h, pixel):
    """Truecolour 8-bit RGBA PNG, the shape the app's own writer emits."""
    rows = b"".join(b"\0" + b"".join(bytes(pixel(x, y)) for x in range(w)) for y in range(h))
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(_chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)))
        f.write(_chunk(b"IDAT", zlib.compress(rows)))
        f.write(_chunk(b"IEND", b""))


def write_indexed(path, w, h):
    """Palette PNG (colour type 3) -- what LOVE's encode() produces for <=256 colours."""
    rows = b"".join(b"\0" + bytes((x * 2 // max(w, 1)) % 2 for x in range(w)) for _ in range(h))
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(_chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 3, 0, 0, 0)))
        f.write(_chunk(b"PLTE", bytes((255, 0, 0, 0, 0, 255))))
        f.write(_chunk(b"IDAT", zlib.compress(rows)))
        f.write(_chunk(b"IEND", b""))


def gradient(top, bottom, h):
    def pixel(x, y):
        t = y / (h - 1)
        return tuple(round(a + (b - a) * t) for a, b in zip(top, bottom)) + (255,)
    return pixel


def make_theme(root, *, bg="gradient", indexed=False, mono_icons=True, config=None,
               screensaver_sizes=None):
    os.makedirs(os.path.join(root, "skin"), exist_ok=True)
    os.makedirs(os.path.join(root, "icons"), exist_ok=True)
    w, h = 64, 48
    bgp = os.path.join(root, "skin", "background.png")
    if bg == "gradient":
        write_rgba(bgp, w, h, gradient((255, 0, 0), (0, 0, 255), h))
    elif bg == "solid":
        write_rgba(bgp, w, h, lambda x, y: (30, 30, 30, 255))
    elif bg == "flat-gradient":  # the bug: both stops drawn the same
        write_rgba(bgp, w, h, lambda x, y: (255, 0, 0, 255))
    if indexed:
        write_indexed(os.path.join(root, "skin", "bg-list-l.png"), w, h)
    tones = ((200, 200, 200), (90, 90, 90))
    iw, ih = 120, 130  # the 640x480 system-icon size SPRUCE ships, so the dimension check passes
    for name in ("gb", "snes"):
        p = os.path.join(root, "icons", name + ".png")
        if mono_icons:
            write_rgba(p, iw, ih, lambda x, y: tones[0] + (255 if (x + y) % 3 else 0,))
        else:
            write_rgba(p, iw, ih, lambda x, y: tones[(x + y) % 2] + (255,))
    cfg = {"name": "T", "showClock": True, "systemSelectViewType": "GRID"}
    cfg.update(config or {})
    if screensaver_sizes:
        cfg["screensaver"] = {"widgets": [{"fontSize": s} for s in screensaver_sizes[0]]}
    json.dump(cfg, open(os.path.join(root, "config.json"), "w"))
    if screensaver_sizes and len(screensaver_sizes) > 1:
        os.makedirs(os.path.join(root, "skin_1280x720"), exist_ok=True)
        write_rgba(os.path.join(root, "skin_1280x720", "background.png"), w, h,
                   lambda x, y: (10, 10, 10, 255))
        other = dict(cfg, screensaver={"widgets": [{"fontSize": s} for s in screensaver_sizes[1]]})
        json.dump(other, open(os.path.join(root, "config_1280x720.json"), "w"))
    return root


def run(theme, *args):
    r = subprocess.run([sys.executable, VALIDATE, theme, "--spruce", "/nonexistent",
                        "--prebake", "/nonexistent", *args], capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


class ValidateTheme(unittest.TestCase):
    def theme(self, **kw):
        d = tempfile.mkdtemp(prefix="theme-")
        self.addCleanup(__import__("shutil").rmtree, d, True)
        return make_theme(d, **kw)

    def test_clean_theme_passes(self):
        rc, out = run(self.theme(), "--gradient", "vertical:#FF0000,#0000FF", "--icon-style", "mono")
        self.assertEqual(rc, 0, out)
        self.assertIn("0 errors", out)

    def test_indexed_png_is_an_error(self):
        rc, out = run(self.theme(indexed=True))
        self.assertEqual(rc, 1)
        self.assertIn("INDEXED", out)

    def test_gradient_that_did_not_render(self):
        rc, out = run(self.theme(bg="flat-gradient"), "--gradient", "vertical:#FF0000,#0000FF")
        self.assertEqual(rc, 1)
        self.assertIn("endpoints identical", out)

    def test_gradient_wrong_endpoints(self):
        rc, out = run(self.theme(), "--gradient", "vertical:#00FF00,#0000FF")
        self.assertEqual(rc, 1)
        self.assertIn("expected", out)

    def test_solid_background_must_be_flat(self):
        rc, out = run(self.theme(bg="gradient"), "--gradient", "solid")
        self.assertEqual(rc, 1)
        self.assertIn("not flat", out)

    def test_solid_passes_when_flat(self):
        rc, out = run(self.theme(bg="solid"), "--gradient", "solid")
        self.assertEqual(rc, 0, out)

    def test_mono_icons_with_two_tones_fail(self):
        rc, out = run(self.theme(mono_icons=False), "--icon-style", "mono")
        self.assertEqual(rc, 1)
        self.assertIn("SPRUCE Mono must be one", out)

    def test_multi_style_with_one_tone_fails(self):
        rc, out = run(self.theme(mono_icons=True), "--icon-style", "multi")
        self.assertEqual(rc, 1)
        self.assertIn("expected a two-tone style", out)

    def test_expect_matches_and_mismatches(self):
        t = self.theme()
        self.assertEqual(run(t, "--expect", "systemSelectViewType=GRID")[0], 0)
        rc, out = run(t, "--expect", "systemSelectViewType=LIST")
        self.assertEqual(rc, 1)
        self.assertIn("expected 'LIST'", out)
        rc, out = run(t, "--expect", "showClock=false")
        self.assertEqual(rc, 1)
        self.assertIn("expected False", out)
        self.assertEqual(run(t, "--expect", "showClock=true")[0], 0)
        rc, out = run(t, "--expect", "nope=1")
        self.assertEqual(rc, 1)
        self.assertIn("absent from config.json", out)

    def test_screensaver_sizes_must_match_across_configs(self):
        rc, out = run(self.theme(screensaver_sizes=([64, 22, 18], [128, 44, 36])))
        self.assertEqual(rc, 1)
        self.assertIn("screensaver widget fontSize differs", out)
        rc, out = run(self.theme(screensaver_sizes=([64, 22, 18], [64, 22, 18])))
        self.assertEqual(rc, 0, out)

    def test_prebake_ignores_icons_only_where_spruce_has_no_icon_set(self):
        sys.path.insert(0, os.path.join(HERE, "..", "utils"))
        from validate_theme import prebake_missing
        lines = ["Themes/T is missing 2 item(s) for 480x800:", "  icons_480x800/gb.png",
                 "  skin_480x800/background.png is 640x480, expected 480x800"]
        icon_sets = {"640x480": {}, "720x720": {}}
        self.assertEqual(prebake_missing(lines, "480x800", icon_sets),
                         ["skin_480x800/background.png is 640x480, expected 480x800"])
        self.assertEqual(len(prebake_missing(lines, "480x800", dict(icon_sets, **{"480x800": {}}))), 2)
        self.assertEqual(prebake_missing(lines[:2], "480x800", icon_sets), [])


if __name__ == "__main__":
    unittest.main()
