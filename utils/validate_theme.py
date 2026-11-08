#!/usr/bin/env python3
"""Validate a generated PyUI theme folder against what spruceOS's PyUI actually reads.

Checks: config.json (+ config_<W>x<H>.json) parse and use only keys PyUI consumes, font files
referenced from configs exist, every skin/icon PNG matches the reference SPRUCE dimensions for its
resolution, resolution sets are complete (skin_/icons_/config_ triplets), preview.png exists.
Optionally runs spruceOS's own prebake --check when a spruceOS checkout is given.

Usage: utils/validate_theme.py <theme dir> [--spruce ~/ai/CFW/Spruce/git/spruceOS]
"""
import argparse, json, os, re, struct, subprocess, sys, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))

def png_size(p):
    with open(p, "rb") as f:
        d = f.read(24)
    return struct.unpack(">II", d[16:24]) if d[:8] == b"\x89PNG\r\n\x1a\n" else None

def png_info(p):
    """(width, height, bit depth, colour type) from IHDR. Colour type 3 is palette/indexed."""
    with open(p, "rb") as f:
        d = f.read(26)
    if d[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    w, h = struct.unpack(">II", d[16:24])
    return w, h, d[24], d[25]

def png_pixels(p):
    """(w, h, getpixel) for an 8-bit RGB/RGBA non-interlaced PNG; None otherwise.

    Enough to read back what this app writes (encodePngRGBA), deliberately not a general decoder.
    """
    info = png_info(p)
    if not info:
        return None
    w, h, depth, ctype = info
    if depth != 8 or ctype not in (2, 6):
        return None
    idat = b""
    with open(p, "rb") as f:
        f.read(8)
        while True:
            head = f.read(8)
            if len(head) < 8:
                break
            ln, kind = struct.unpack(">I", head[:4])[0], head[4:8]
            body = f.read(ln)
            f.read(4)
            if kind == b"IDAT":
                idat += body
            elif kind == b"IEND":
                break
    raw = zlib.decompress(idat)
    bpp = 4 if ctype == 6 else 3
    stride = w * bpp
    out = bytearray(h * stride)
    prev = bytearray(stride)
    pos = 0
    for y in range(h):
        ft = raw[pos]; pos += 1
        line = bytearray(raw[pos:pos + stride]); pos += stride
        for i in range(stride):
            a = line[i - bpp] if i >= bpp else 0
            b = prev[i]
            c = prev[i - bpp] if i >= bpp else 0
            if ft == 1: line[i] = (line[i] + a) & 0xFF
            elif ft == 2: line[i] = (line[i] + b) & 0xFF
            elif ft == 3: line[i] = (line[i] + ((a + b) >> 1)) & 0xFF
            elif ft == 4:
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 0xFF
        out[y * stride:(y + 1) * stride] = line
        prev = line
    def get(x, y):
        o = y * stride + x * bpp
        return (out[o], out[o + 1], out[o + 2], out[o + 3] if bpp == 4 else 255)
    return w, h, get

def hex_rgb(s):
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))

def near(a, b, tol=6):
    return all(abs(x - y) <= tol for x, y in zip(a[:3], b[:3]))

def lua_spec(path=None):
    """Parse skin_spec.lua (generated, regular shape) without a Lua runtime."""
    txt = open(path or os.path.join(ROOT, "src", "spruce", "skin_spec.lua")).read()
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

def prebake_missing(lines, res, icon_sets):
    """Items prebake --check lists for res, less icons_<res>/ where SPRUCE keeps no icon set for it.

    PyUI patches only when config_<res>.json is missing and otherwise reads icons/ when icons_<res>/
    is absent (theme.py); the checker predates SPRUCE serving 480x800 and 720x480 that way."""
    missing = [l.strip() for l in lines if l.startswith("  ")]
    if icon_sets and res not in icon_sets:
        missing = [m for m in missing if not m.startswith(f"icons_{res}/")]
    return missing

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("theme")
    ap.add_argument("--spruce", default=os.path.expanduser("~/ai/CFW/Spruce/git/spruceOS"), help="spruceOS checkout (for PyUI key list and prebake --repo)")
    ap.add_argument("--prebake", default=os.path.expanduser("~/ai/CFW/Spruce/tools/theme/prebake-theme-resolution.py"), help="spruce's prebake-theme-resolution.py (runs PyUI's ThemePatcher rules in --check mode)")
    ap.add_argument("--expect", action="append", default=[], metavar="KEY=VALUE",
                    help="assert config.json carries this value (JSON literal, else a string); repeatable")
    ap.add_argument("--gradient", metavar="SPEC",
                    help="background check: 'solid', or 'vertical:#FROM,#TO' / 'horizontal:#FROM,#TO'")
    ap.add_argument("--icon-style", choices=("mono", "multi"), help="system icon tone check")
    ap.add_argument("--spec", help="path to skin_spec.lua (on a device: <app>/.aesthetic/spruce/skin_spec.lua)")
    a = ap.parse_args()
    T = a.theme.rstrip("/")
    errors, warnings = [], []
    # On a device there is no repo and no spruceOS checkout; those checks drop out, the rest stand.
    try:
        spec = lua_spec(a.spec)
    except Exception:
        spec = {g: {} for g in ("skin", "icons", "icons_sel", "icons_app")}
        warnings.append("skin_spec.lua not readable: dimension checks skipped")
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

    # Every PNG must be truecolour. LOVE's encode() palettises images of <=256 colours, and some
    # device loaders render those wrong: a red-to-blue ramp came out red, black, blue on a Brick Pro.
    for dirpath, _, files in os.walk(T):
        for f in files:
            if not f.endswith(".png"):
                continue
            fp = os.path.join(dirpath, f)
            info = png_info(fp)
            if not info:
                errors.append(f"{os.path.relpath(fp, T)}: not a PNG")
            elif info[3] == 3:
                errors.append(f"{os.path.relpath(fp, T)}: INDEXED (colour type 3); must be truecolour")

    # Screensaver widget font sizes are written against the fixed 640x480 base and PyUI rescales
    # them, so every config in the theme must carry the same values, not per-resolution ones.
    sizes = {}
    for res, (cfg, _s, _i) in sorted(sets.items()):
        cp = os.path.join(T, cfg)
        if not os.path.exists(cp):
            continue
        try:
            ws = (json.load(open(cp)).get("screensaver") or {}).get("widgets") or []
        except Exception:
            continue
        got = tuple(w.get("fontSize") for w in ws)
        if got:
            sizes.setdefault(got, []).append(cfg)
    if len(sizes) > 1:
        errors.append(f"screensaver widget fontSize differs between configs (must be the 640x480 base in all): {dict(sizes)}")

    # Background: solid must be flat, a gradient must actually run between its two endpoints.
    if a.gradient:
        bg = os.path.join(T, "skin", "background.png")
        px = png_pixels(bg) if os.path.exists(bg) else None
        if not px:
            errors.append(f"--gradient: {os.path.relpath(bg, T)} missing or not an 8-bit RGB/RGBA PNG")
        else:
            w, h, get = px
            mode, _, spec_s = a.gradient.partition(":")
            if mode == "solid":
                if get(w // 2, 0)[:3] != get(w // 2, h - 1)[:3] or get(0, h // 2)[:3] != get(w - 1, h // 2)[:3]:
                    errors.append("--gradient solid: background is not flat")
            else:
                want = [hex_rgb(s.strip()) for s in spec_s.split(",")] if spec_s else []
                first, last = ((get(w // 2, 0), get(w // 2, h - 1)) if mode == "vertical"
                               else (get(0, h // 2), get(w - 1, h // 2)))
                if first[:3] == last[:3]:
                    errors.append(f"--gradient {mode}: endpoints identical ({first[:3]}): no gradient was drawn")
                elif want and not (near(first, want[0]) and near(last, want[1])):
                    errors.append(f"--gradient {mode}: ends are {first[:3]} -> {last[:3]}, expected {want[0]} -> {want[1]}")

    # SPRUCE Mono draws each system icon in a single colour; the two-tone styles do not.
    if a.icon_style:
        idir = os.path.join(T, "icons")
        shots = [os.path.join(idir, f) for f in sorted(os.listdir(idir))[:8]] if os.path.isdir(idir) else []
        shots = [p for p in shots if p.endswith(".png")]
        if not shots:
            errors.append("--icon-style: no icons/*.png to check")
        for p in shots:
            px = png_pixels(p)
            if not px:
                continue
            w, h, get = px
            # Every pixel, not a stride: a stride can alias with a regular pattern and miss a tone.
            tones = {get(x, y)[:3] for y in range(h) for x in range(w) if get(x, y)[3] > 32}
            if a.icon_style == "mono" and len(tones) > 1:
                errors.append(f"icons/{os.path.basename(p)}: {len(tones)} tones, SPRUCE Mono must be one")
            if a.icon_style == "multi" and len(tones) <= 1:
                errors.append(f"icons/{os.path.basename(p)}: single tone, expected a two-tone style")

    # Option -> PyUI key assertions, e.g. --expect systemSelectViewType=GRID --expect showClock=false
    if a.expect:
        cp = os.path.join(T, "config.json")
        data = json.load(open(cp)) if os.path.exists(cp) else {}
        for pair in a.expect:
            k, _, v = pair.partition("=")
            try:
                want = json.loads(v)
            except ValueError:
                want = v
            if k not in data:
                errors.append(f"--expect {k}: absent from config.json")
            elif data[k] != want:
                errors.append(f"--expect {k}: config.json has {data[k]!r}, expected {want!r}")

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
            out = r.stdout.splitlines()
            if r.returncode != 0 and out and "is missing" in out[0] and not prebake_missing(out, res, spec["icons"]):
                print(f"prebake --check {res}: OK (no icons_{res}/: PyUI reads icons/, as for SPRUCE)")
                continue
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
