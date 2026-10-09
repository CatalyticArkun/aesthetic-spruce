#!/usr/bin/env python3
"""Syntax-check every Lua file under src/ with a LuaJIT 2.1 parser (pip install lupa)."""
import os, sys, importlib, importlib.util
# LÖVE runs LuaJIT 2.1, but lupa's macOS wheels ship only the reference runtimes, so
# fall back to 5.1: that is the grammar this codebase targets anyway.
RUNTIMES = ("luajit21", "luajit20", "lua51")
runtime = next((m for m in RUNTIMES if importlib.util.find_spec("lupa." + m)), None)
if runtime is None:
    sys.exit("no Lua 5.1 runtime in lupa (tried %s); pip install lupa" % ", ".join(RUNTIMES))
LuaRuntime = importlib.import_module("lupa." + runtime).LuaRuntime
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
print(f"checked {n} files with lupa.{runtime}, {bad} with syntax errors"); sys.exit(1 if bad else 0)
