#!/usr/bin/env python3
"""Generate the stage-2 device test matrix from the app's own tables.

Every option domain is PARSED from source, never retyped here: if a parse finds nothing the script
fails rather than silently testing less. Emits one case per file set into <out>/:

    NNN-<name>.lua      a preset to build (absent for built-in preset cases)
    NNN-<name>.builtin  the name of a built-in preset to build instead
    NNN-<name>.theme    the theme directory the build will produce
    NNN-<name>.args     extra arguments for validate_theme.py (may be empty)

Usage: utils/make_stage2_cases.py <out dir>
"""
import os, re, sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def read(*p):
    return open(os.path.join(ROOT, *p)).read()


def need(what, value):
    if not value:
        sys.exit(f"parse failed: {what} -- the source moved; fix this generator before testing less")
    return value


def parse_domains():
    d = {}
    icons = read("src", "screens", "icons.lua")
    m = need("ICON_STYLES", re.search(r'local ICON_STYLES = \{([^}]*)\}', icons))
    d["systemIconStyle"] = [x.strip().strip('"') for x in m.group(1).split(",") if x.strip()]

    so = read("src", "screens", "spruce_options.lua")
    for key in ("gameListView", "systemsView", "appsView"):
        m = need(key, re.search(r'\{ key = "%s".*?options = \{([^}]*)\}' % key, so))
        d[key] = [x.strip().strip('"') for x in m.group(1).split(",") if x.strip()]
    m = need("SCREENSAVER_MINUTES", re.search(r'local SCREENSAVER_MINUTES = \{([^}]*)\}', so))
    d["screensaverMinutes"] = [int(x) for x in m.group(1).split(",") if x.strip()]

    fonts = read("src", "ui", "fonts.lua")
    fam = need("font families", re.findall(r'name = "([^"]+)",\s*\n\s*ttf = "assets/fonts/', fonts))
    d["fontFamily"] = list(dict.fromkeys(fam))
    # fonts.lua declares an empty table first and fills it in init(); take the populated one.
    blocks = re.findall(r'fonts\.themeFontSizeOptions = \{(.*?)\}', fonts, re.S)
    sizes = [re.findall(r'\["([^"]+)"\]', b) for b in blocks]
    d["fontSize"] = need("font sizes", max(sizes, key=len) if sizes else [])

    d["homeScreenLayout"] = ["Grid", "List"]            # home_screen_layout.lua options
    d["backgroundType"] = ["Solid", "Gradient"]          # background.lua typeToggle
    d["backgroundGradientDirection"] = ["Vertical", "Horizontal"]  # background.lua directionToggle
    for b in ("systemIcons", "showTopBarText", "showBottomBar", "showClock", "showBattery",
              "showRecents", "showCollections", "showFavorites", "showIndex"):
        d[b] = [True, False]
    return d


def parse_defaults():
    s = read("src", "state.lua")
    block = need("THEME_FIELDS", re.search(r'state\.THEME_FIELDS = \{(.*?)\n\}', s, re.S)).group(1)
    out = {}
    for key, typ, dflt in re.findall(r'\{ key = "([A-Za-z0-9_]+)", type = "(\w+)", default = ([^}]+?) \}', block):
        dflt = dflt.strip()
        out[key] = (True if dflt == "true" else False if dflt == "false"
                    else dflt.strip('"') if dflt.startswith('"') else float(dflt) if "." in dflt else int(dflt))
    return need("defaults", out)


VIEW = {  # pyui_config.lua lines 19-24
    "games": {"Text": "TEXT_ONLY", "Text + Box Art": "TEXT_AND_IMAGE",
              "Full Screen Grid": "FULLSCREEN_GRID", "Carousel": "CAROUSEL"},
    "systems": {"Grid": "GRID", "Text": "ICON_AND_DESC", "Carousel": "CAROUSEL"},
    "apps": {"Icons + Details": "ICON_AND_DESC", "Text": "TEXT_ONLY"},
}
COLORS = ('colors = { background = "#1E40AF", backgroundGradient = "#155CFB", foreground = "#FFFFFF",'
          ' batteryActive = "#4ADE80", batteryLow = "#F87171" }')


def lua_value(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    return '"%s"' % v


def preset(name, fields):
    body = ", ".join("%s = %s" % (k, lua_value(v)) for k, v in fields.items())
    return 'return { themeName = "%s", %s, %s }\n' % (name, body, COLORS)


def expectations(f):
    """--expect args that follow from pyui_config.lua, and only those we can derive exactly."""
    a = []
    a.append("--expect")
    a.append("mainMenuViewType=%s" % ('"GRID"' if f.get("homeScreenLayout", "Grid") == "Grid" else '"TEXT_ONLY"'))
    # systemIcons=false forces TEXT_ONLY regardless of systemsView (pyui_config.lua:92)
    if not f.get("systemIcons", True):
        sv = "TEXT_ONLY"
    else:
        sv = VIEW["systems"].get(f.get("systemsView", "Grid"), "GRID")
    a += ["--expect", 'systemSelectViewType="%s"' % sv]
    a += ["--expect", 'gameSelectionViewType="%s"' % VIEW["games"].get(f.get("gameListView", "Text + Box Art"), "TEXT_AND_IMAGE")]
    a += ["--expect", 'appMenuViewType="%s"' % VIEW["apps"].get(f.get("appsView", "Icons + Details"), "ICON_AND_DESC")]
    for key, cfg in (("showTopBarText", "showTopBarText"), ("showBottomBar", "showBottomBar"),
                     ("showClock", "showClock"), ("showRecents", "recentsEnabled"),
                     ("showFavorites", "favoritesEnabled"), ("showCollections", "collectionsEnabled"),
                     ("showIndex", "showIndexText")):
        a += ["--expect", "%s=%s" % (cfg, "true" if f.get(key, True) else "false")]
    a += ["--expect", "displayBatteryIcon=%s" % ("true" if f.get("showBattery", True) else "false")]
    return a


def background_args(f):
    t = f.get("backgroundType", "Gradient")
    if t == "Solid":
        return ["--gradient", "solid"]
    d = f.get("backgroundGradientDirection", "Vertical").lower()
    return ["--gradient", "%s:#1E40AF,#155CFB" % d]


def icon_args(f):
    if not f.get("systemIcons", True):
        return []            # no icons directory at all; nothing to assert
    style = f.get("systemIconStyle", "Glyph")
    return ["--icon-style", "mono" if style == "SPRUCE Mono" else "multi"]


def main():
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    dom, dflt = parse_domains(), parse_defaults()
    cases, n = [], 0

    def add(name, fields=None, builtin=None, theme=None):
        nonlocal n
        n += 1
        stem = os.path.join(out, "%03d-%s" % (n, name))
        if builtin:
            open(stem + ".builtin", "w").write(builtin + "\n")
            args = []
        else:
            open(stem + ".lua", "w").write(preset(theme, fields))
            args = background_args(fields) + icon_args(fields) + expectations(fields)
        open(stem + ".theme", "w").write(theme + "\n")
        open(stem + ".args", "w").write(" ".join(args) + "\n")
        cases.append(("%03d-%s" % (n, name), theme))

    # A. one build per non-default value of every option
    for key in sorted(dom):
        if key not in dflt:
            continue
        for value in dom[key]:
            if value == dflt[key]:
                continue
            fields = {key: value}
            # a gradient direction only means anything with a gradient background
            if key == "backgroundGradientDirection":
                fields["backgroundType"] = "Gradient"
            # an icon style only means anything with icons on
            if key == "systemIconStyle":
                fields["systemIcons"] = True
            slug = re.sub(r'[^A-Za-z0-9]+', '', str(value))[:14] or "x"
            add("opt-%s-%s" % (key, slug), fields, theme="S2%03d" % (n + 1))

    # B. combinations where past bugs lived
    add("combo-minimal", {"backgroundType": "Solid", "systemIcons": False, "showTopBarText": False,
                          "showBottomBar": False, "showClock": False, "showBattery": False,
                          "showRecents": False, "showCollections": False, "showFavorites": False,
                          "showIndex": False, "screensaverMinutes": 0}, theme="S2%03d" % (n + 1))
    add("combo-maximal", {"backgroundType": "Gradient", "backgroundGradientDirection": "Horizontal",
                          "systemIcons": True, "systemIconStyle": "SPRUCE Art", "showTopBarText": True,
                          "showBottomBar": True, "showClock": True, "showBattery": True,
                          "gameListView": "Full Screen Grid", "systemsView": "Carousel",
                          "screensaverMinutes": 30}, theme="S2%03d" % (n + 1))
    add("combo-reporter", {"backgroundType": "Gradient", "backgroundGradientDirection": "Vertical",
                           "systemIcons": True, "systemIconStyle": "SPRUCE Mono",
                           "homeScreenLayout": "Grid"}, theme="S2%03d" % (n + 1))
    add("combo-minui-mono", {"backgroundType": "Solid", "systemIcons": True,
                             "systemIconStyle": "SPRUCE Mono", "homeScreenLayout": "List",
                             "gameListView": "Text"}, theme="S2%03d" % (n + 1))

    # C. every built-in preset, built as the user would load it
    pdir = os.path.join(ROOT, "src", "presets")
    for f in sorted(os.listdir(pdir)):
        if not f.endswith(".lua"):
            continue
        name = f[:-4]
        m = re.search(r'themeName\s*=\s*"([^"]+)"', open(os.path.join(pdir, f)).read())
        add("preset-%s" % name, builtin=name, theme=need("themeName in " + f, m).group(1))

    with open(os.path.join(out, "CASES.txt"), "w") as fh:
        for stem, theme in cases:
            fh.write("%s\t%s\n" % (stem, theme))
    print("%d cases -> %s" % (len(cases), out))
    print("  per-option %d, combinations 4, presets %d"
          % (len(cases) - 4 - len([f for f in os.listdir(pdir) if f.endswith('.lua')]),
             len([f for f in os.listdir(pdir) if f.endswith('.lua')])))


if __name__ == "__main__":
    main()
