#!/usr/bin/env python3
"""The skin assets a theme emits against the SPRUCE sizes they are drawn at.

PyUI draws the bottom-bar hints with context-<button> images once a theme sets
hint.contextbuttons, and prints only the label where one is missing, so a theme that turns them
on must ship every button SPRUCE does, at every resolution it generates.

Run: python3 -m unittest discover tests
"""
import os, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))

try:
    import lupa
except ImportError:  # same dependency the Lua syntax check uses; CI installs it
    lupa = None

BUTTONS = ("a", "b", "x", "y", "start", "select", "menu")


def lua_table(rel):
    L = lupa.LuaRuntime(unpack_returned_tuples=True)
    with open(os.path.join(ROOT, rel)) as f:
        return L.execute(f.read())


@unittest.skipIf(lupa is None, "lupa not installed")
class ContextButtons(unittest.TestCase):
    def setUp(self):
        self.assets = lua_table("src/spruce/pyui_assets.lua")
        self.spec = lua_table("src/spruce/skin_spec.lua")

    def test_every_spruce_context_button_is_drawn(self):
        for b in BUTTONS:
            spec = self.assets[f"context-{b}"]
            self.assertIsNotNone(spec, f"context-{b} missing from pyui_assets.lua")
            self.assertEqual(spec["kind"], "button")
            self.assertEqual(spec["label"], b.upper())

    def test_spruce_sizes_exist_for_every_resolution(self):
        skin = self.spec["skin"]
        for res in skin.keys():
            for b in BUTTONS:
                dims = skin[res][f"context-{b}"]
                self.assertIsNotNone(dims, f"no SPRUCE size for context-{b} at {res}")
                w, h = dims[1], dims[2]
                if len(b) == 1:
                    self.assertEqual(w, h, f"context-{b} at {res} is a circle")
                else:
                    self.assertGreater(w, h, f"context-{b} at {res} is a pill")

    def test_no_context_button_spruce_lacks(self):
        """Only buttons SPRUCE ships: an extra one would draw where SPRUCE prints a bare label."""
        ours = {k for k in self.assets.keys() if k.startswith("context-")}
        self.assertEqual(ours, {f"context-{b}" for b in BUTTONS})


if __name__ == "__main__":
    unittest.main()
