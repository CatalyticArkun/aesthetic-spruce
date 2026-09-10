#!/usr/bin/env python3
"""Validate a generated PyUI theme folder against what spruceOS's PyUI actually reads.

Checks: config.json (+ config_<W>x<H>.json) parse and use only keys PyUI consumes, font files
referenced from configs exist, every skin/icon PNG matches the reference SPRUCE dimensions for its
resolution, resolution sets are complete (skin_/icons_/config_ triplets), preview.png exists.
Optionally runs spruceOS's own prebake --check when a spruceOS checkout is given.

Usage: utils/validate_theme.py <theme dir> [--spruce ~/ai/CFW/Spruce/git/spruceOS]
"""
import argparse, json, os, re, struct, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))

def png_size(p):
    with open(p, "rb") as f:
        d = f.read(24)
    return struct.unpack(">II", d[16:24]) if d[:8] == b"\x89PNG\r\n\x1a\n" else None

def lua_spec():
    """Parse src/spruce/skin_spec.lua (generated, regular shape) without a Lua runtime."""
    txt = open(os.path.join(ROOT, "src", "spruce", "skin_spec.lua")).read()
    spec = {}
    for group in ("skin", "icons", "icons_sel", "icons_app"):
        spec[group] = {}
        gstart = txt.index('["%s"] = {' % group)
        gend = txt.index("\n\t}", gstart)
        block = txt[gstart:gend]
        for m in re.finditer(r'\["(\d+x\d+)"\] = \{(.*?)\n\t\t\}', block, re.S):
            res, body = m.group(1), m.group(2)
            spec[group][res] = {n: (int(w), int(h)) for n, w, h in re.findall(r'\["([^"]+)"\] = \{ (\d+), (\d+) \}', body)}
    return spec

def pyui_keys(spruce):
    """Keys theme.py reads from the config (cls._data.get("...") / cls._data["..."])."""
    tp = os.path.join(spruce, "App", "PyUI", "main-ui", "themes", "theme.py")
    if not os.path.exists(tp):
        return None
    src = open(tp).read()
    keys = set(re.findall(r'_data(?:\.get\(|\[)"([A-Za-z0-9_]+)"', src))
    return keys | {"name", "author", "description"}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("theme")
    ap.add_argument("--spruce", default=os.path.expanduser("~/ai/CFW/Spruce/git/spruceOS"), help="spruceOS checkout (for PyUI key list and prebake --repo)")
    ap.add_argument("--prebake", default=os.path.expanduser("~/ai/CFW/Spruce/tools/theme/prebake-theme-resolution.py"), help="spruce's prebake-theme-resolution.py (runs PyUI's ThemePatcher rules in --check mode)")
    a = ap.parse_args()
    T = a.theme.rstrip("/")
    errors, warnings = [], []
    spec = lua_spec()
    known = pyui_keys(a.spruce)

    # resolution sets
    sets = {"640x480": ("config.json", "skin", "icons")}
    for f in os.listdir(T):
        m = re.match(r"config_(\d+x\d+)\.json$", f)
        if m:
            r = m.group(1); sets[r] = (f, "skin_" + r, "icons_" + r)
    for res, (cfg, skin, icons) in sorted(sets.items()):
        cp = os.path.join(T, cfg)
        if not os.path.exists(cp):
            errors.append(f"{res}: missing {cfg}"); continue
        try:
            data = json.load(open(cp))
        except Exception as e:
            errors.append(f"{cfg}: invalid JSON: {e}"); continue
        if known:
            unknown = sorted(k for k in data if k not in known)
            if unknown: warnings.append(f"{cfg}: keys PyUI does not read: {unknown}")
        for purpose in ("list", "grid", "title", "currentpage", "total", "batteryPercentage", "shadowed"):
            font = (data.get(purpose) or {}).get("font")
            if font and not os.path.exists(os.path.join(T, font)):
                errors.append(f"{cfg}: {purpose}.font '{font}' not found in theme root")
        sd = os.path.join(T, skin)
        if not os.path.isdir(sd):
            errors.append(f"{res}: missing {skin}/"); continue
        if not os.path.exists(os.path.join(sd, "background.png")) and not os.path.exists(os.path.join(sd, "background.qoi")):
            errors.append(f"{skin}/background.png missing (ThemePatcher uses it to detect the native size)")
        ref = spec["skin"].get(res, {})
        for f in os.listdir(sd):
            if not f.endswith(".png"): continue
            name = f[:-4]; got = png_size(os.path.join(sd, f))
            exp = ref.get(name) or ref.get({"grid-system-selected": "grid-game-selected", "bg-game-item-single-f": "bg-game-item-f"}.get(name, ""))
            if name in ("icon-A-54", "icon-B-54", "background"):
                # A/B: deliberately compact (SPRUCE ships transparent 640x54 strips).
                # background: sized to the screen per PyUI's ThemePatcher rule (prebake --check
                # enforces it); SPRUCE's own 1280x720 set ships a 960x720 file.
                continue
            if exp and got != exp:
                errors.append(f"{skin}/{f}: {got[0]}x{got[1]} but SPRUCE has {exp[0]}x{exp[1]}")
        idir = os.path.join(T, icons)
        if os.path.isdir(idir):
            for sub, group in (("", "icons"), ("sel", "icons_sel"), ("app", "icons_app")):
                d = os.path.join(idir, sub); refi = spec[group].get(res, {})
                if not os.path.isdir(d): continue
                for f in os.listdir(d):
                    if not f.endswith(".png"): continue
                    got = png_size(os.path.join(d, f)); exp = refi.get(f[:-4])
                    if exp and got != exp:
                        errors.append(f"{icons}/{sub}/{f}: {got} but SPRUCE has {exp}")
            missing = [n for n in spec["icons"].get(res, {}) if not os.path.exists(os.path.join(idir, n + ".png"))]
            if missing: warnings.append(f"{icons}/: {len(missing)} systems without an icon (PyUI falls back): {missing[:6]}...")
    if not os.path.exists(os.path.join(T, "preview.png")):
        warnings.append("preview.png missing (theme picker shows no preview)")

    # spruce's own pre-bake checker (uses PyUI's ThemePatcher rules) if available
    pb = a.prebake
    if pb and os.path.exists(pb) and os.path.isdir(a.spruce):
        # prebake insists the theme lives inside --repo; build a throwaway repo skeleton of symlinks
        # so the spruceOS checkout is never written to.
        import tempfile
        tmp = tempfile.mkdtemp(prefix="aesthetic-validate-")
        os.makedirs(os.path.join(tmp, "App"), exist_ok=True); os.makedirs(os.path.join(tmp, "Themes"), exist_ok=True)
        os.symlink(os.path.join(a.spruce, "App", "PyUI"), os.path.join(tmp, "App", "PyUI"))
        tname = os.path.basename(os.path.abspath(T)).replace(" ", "_")
        import shutil
        shutil.copytree(os.path.abspath(T), os.path.join(tmp, "Themes", tname))  # prebake realpath-checks the theme
        for res in sorted(sets):
            if res == "640x480": continue
            r = subprocess.run([sys.executable, pb, "--repo", tmp, "--theme", "Themes/" + tname, "--size", res, "--check"], capture_output=True, text=True)
            tag = "OK" if r.returncode == 0 else "FAIL"
            print(f"prebake --check {res}: {tag} {(r.stdout or r.stderr).strip().splitlines()[-1] if (r.stdout or r.stderr).strip() else ''}")
            if r.returncode != 0: warnings.append(f"prebake --check {res} failed (see above)")
        shutil.rmtree(tmp, ignore_errors=True)

    for w in warnings: print("WARN ", w)
    for e in errors: print("ERROR", e)
    print(f"{T}: {len(sets)} resolution set(s), {len(errors)} errors, {len(warnings)} warnings")
    sys.exit(1 if errors else 0)

if __name__ == "__main__":
    main()
