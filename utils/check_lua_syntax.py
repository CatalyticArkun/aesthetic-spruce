#!/usr/bin/env python3
"""Syntax-check every Lua file under src/ with a LuaJIT 2.1 parser (pip install lupa)."""
import os, sys
from lupa.luajit21 import LuaRuntime
root = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "src"))
L = LuaRuntime()
loadstring = L.eval("function(src, name) local f, err = loadstring(src, name); return f ~= nil, err end")
bad = 0; n = 0
for dp, _, fns in os.walk(root):
    for fn in sorted(fns):
        if fn.endswith(".lua"):
            p = os.path.join(dp, fn); n += 1
            ok, err = loadstring(open(p, encoding="utf-8").read(), "@" + os.path.relpath(p, root))
            if not ok:
                bad += 1; print("SYNTAX", err)
print(f"checked {n} files, {bad} with syntax errors"); sys.exit(1 if bad else 0)
