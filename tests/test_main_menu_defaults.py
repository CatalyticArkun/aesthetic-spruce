#!/usr/bin/env python3
"""The main-menu defaults: as many tiles as the row can hold, everything in a list.

PyUI draws the main menu as a single row (mainMenuRowCount defaults to 1) and sizes it as
int(4 * width_multiplier), which is 4 on every supported panel except 16:9, where it is 5. Games,
Apps and Settings are always shown, so the spare slots go to Favorites, then Recents, then
Collections -- which reproduces the stock SPRUCE set on a 4-wide screen.

Run: python3 -m unittest discover tests
"""
import glob, os, re, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))

try:
    import lupa
except ImportError:  # same dependency the Lua syntax check uses; CI installs it
    lupa = None


def lua_state():
    """Run state.lua's two main-menu functions against a stub state table."""
    src = open(os.path.join(ROOT, "src", "state.lua")).read()
    body = src[src.index("function state.mainMenuColumns()"):src.index("state.applicationName =")]
    L = lupa.LuaRuntime(unpack_returned_tuples=True)
    L.execute("state = { screenWidth = 640, screenHeight = 480, homeScreenLayout = 'Grid' }\n" + body)
    return L.globals().state


@unittest.skipIf(lupa is None, "lupa not installed")
class MainMenuDefaults(unittest.TestCase):
    def setUp(self):
        self.state = lua_state()

    def tiles(self, w, h, layout):
        s = self.state
        s.screenWidth, s.screenHeight, s.homeScreenLayout = w, h, layout
        s.applyMainMenuDefaults()
        optional = [n for n, v in (("Recents", s.showRecents), ("Collections", s.showCollections),
                                   ("Favorites", s.showFavorites)) if v]
        return s.mainMenuColumns(), optional, len(optional) + 3  # + Games, Apps, Settings

    def test_four_wide_panels_get_the_spruce_set(self):
        for w, h in ((640, 480), (720, 480), (720, 720), (752, 560), (960, 720), (1024, 768), (480, 800)):
            cols, optional, total = self.tiles(w, h, "Grid")
            self.assertEqual(cols, 4, f"{w}x{h}")
            self.assertEqual(optional, ["Favorites"], f"{w}x{h}: Recents and Collections must be off")
            self.assertEqual(total, cols, f"{w}x{h}: the row must be exactly full")

    def test_sixteen_by_nine_gets_five_and_keeps_recents(self):
        cols, optional, total = self.tiles(1280, 720, "Grid")
        self.assertEqual(cols, 5)
        self.assertEqual(sorted(optional), ["Favorites", "Recents"], "Collections is the one dropped")
        self.assertEqual(total, cols)

    def test_a_list_shows_everything(self):
        for w, h in ((640, 480), (1280, 720), (480, 800)):
            _, optional, total = self.tiles(w, h, "List")
            self.assertEqual(sorted(optional), ["Collections", "Favorites", "Recents"], f"{w}x{h}")
            self.assertEqual(total, 6)

    def test_grid_never_overflows_its_row(self):
        """The point of the rule: a tile beyond the column count would be cut off."""
        for w, h in ((640, 480), (720, 480), (1280, 720), (480, 800), (1024, 768)):
            cols, _, total = self.tiles(w, h, "Grid")
            self.assertLessEqual(total, cols, f"{w}x{h}: {total} tiles in {cols} columns")

    def test_columns_follow_pyui_own_formula_clamped(self):
        """Not an invented rule: int(4 * width_multiplier) from theme.py, held to 4..5."""
        for w, h in ((640, 480), (720, 480), (1280, 720), (1024, 768), (480, 800), (1920, 1080)):
            sw, sh = w / 640, h / 480
            wm = ((sw - sh) / sh) + 1 if sw > sh else 1.0
            want = max(4, min(5, int(4 * wm)))
            self.state.screenWidth, self.state.screenHeight = w, h
            self.assertEqual(self.state.mainMenuColumns(), want, f"{w}x{h}")

    def test_defaults_in_state_match_a_four_wide_grid(self):
        """The static THEME_FIELDS defaults are the fallback when no device size is known yet."""
        src = open(os.path.join(ROOT, "src", "state.lua")).read()
        block = re.search(r'state\.THEME_FIELDS = \{(.*?)\n\}', src, re.S).group(1)
        got = dict(re.findall(r'\{ key = "(show(?:Recents|Collections|Favorites))".*?default = (\w+)', block))
        self.assertEqual(got, {"showRecents": "false", "showCollections": "false",
                               "showFavorites": "true"})


def full_state():
    """The whole state.lua through require(), with its error and log helpers stubbed."""
    L = lupa.LuaRuntime(unpack_returned_tuples=True)
    L.execute(f'package.path = "{os.path.join(ROOT, "src")}/?.lua;" .. package.path\n'
              'package.preload["utils.fail"] = function() return function(m) return false, m end end\n'
              'package.preload["utils.logger"] = function()\n'
              '  return setmetatable({}, { __index = function() return function() end end }) end')
    return L, L.eval('(require("state"))')


@unittest.skipIf(lupa is None, "lupa not installed")
class ImportedPresets(unittest.TestCase):
    """A preset sets the look, not the tiles: one without tile flags gets the device's defaults."""

    def load(self, w, h, snapshot_lua):
        L, s = full_state()
        s.screenWidth, s.screenHeight = w, h
        ok = s.importTheme(L.eval(snapshot_lua))
        self.assertTrue(ok if not isinstance(ok, tuple) else ok[0])
        return {n: bool(s[k]) for n, k in (("Favorites", "showFavorites"), ("Recents", "showRecents"),
                                           ("Collections", "showCollections"))}, s.homeScreenLayout

    def test_every_builtin_preset_follows_the_device(self):
        presets = sorted(glob.glob(os.path.join(ROOT, "src", "presets", "*.lua")))
        self.assertGreater(len(presets), 0)
        for p in presets:
            for (w, h), grid in (((1280, 720), {"Favorites": True, "Recents": True, "Collections": False}),
                                 ((640, 480), {"Favorites": True, "Recents": False, "Collections": False})):
                tiles, layout = self.load(w, h, f'dofile("{p}")')
                want = dict.fromkeys(grid, True) if layout == "List" else grid
                self.assertEqual(tiles, want, f"{os.path.basename(p)} at {w}x{h} ({layout})")

    def test_a_snapshot_naming_a_tile_keeps_its_choice(self):
        tiles, _ = self.load(1280, 720, '{ homeScreenLayout = "Grid", showRecents = false }')
        self.assertEqual(tiles, {"Favorites": True, "Recents": False, "Collections": False})
        tiles, _ = self.load(640, 480, '{ homeScreenLayout = "Grid", showFavorites = true, '
                                        'showRecents = true, showCollections = true }')
        self.assertEqual(tiles, {"Favorites": True, "Recents": True, "Collections": True})


if __name__ == "__main__":
    unittest.main()
