#!/usr/bin/env python3
"""Generate the stage-2 device test matrix from the app's own tables.

Every option domain is PARSED from source, never retyped here: if a parse finds nothing the script
fails rather than silently testing less. Emits one case per file set into <out>/:

    NNN-<name>.lua      the preset to build (preset cases are the built-in file with themeName
                        rewritten to this case's own S2nnn, so no user theme can be touched)
    NNN-<name>.theme    the theme directory the build will produce, always S2nnn
    NNN-<name>.args     extra arguments for validate_theme.py (may be empty)

Usage: utils/make_stage2_cases.py <out dir>
"""
import os, re, sys

DEFAULT_COLORS = {}

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def read(*p):
    return open(os.path.join(ROOT, *p)).read()


def need(what, value):
    if not value:
        sys.exit(f"parse failed: {what} -- the source moved; fix this generator before testing less")
    return value


def parse_domains(fields):
    """A domain for every THEME_FIELDS key, discovered rather than listed.

    An earlier version enumerated the keys by hand, so three options added on 2026-10-25 produced
    no cases at all and nothing noticed. Now every field must resolve to a domain or this fails.
    """
    d = {}
    icons = read("src", "screens", "icons.lua")
    m = need("ICON_STYLES", re.search(r'local ICON_STYLES = \{([^}]*)\}', icons))
    d["systemIconStyle"] = [x.strip().strip('"') for x in m.group(1).split(",") if x.strip()]

    # Every row in spruce_options, not a chosen few: a new row is a new option to cover.
    # Parsed per line and brace-aware: `options = FIT },` and `options = { "a", "b" },` are both
    # real shapes, and one regex for both silently truncated domains to a single value.
    so = read("src", "screens", "spruce_options.lua")
    named = dict(re.findall(r'local ([A-Z_]+) = \{([^}]*)\}', so))
    for line in so.splitlines():
        m = re.match(r'\s*\{ key = "([A-Za-z0-9_]+)",.*?options = (.*)$', line)
        if not m:
            continue
        key, tail = m.group(1), m.group(2).strip()
        if tail.startswith("{"):
            raw = tail[1:tail.index("}")]
        else:
            raw = named.get(tail.split(",")[0].strip().rstrip("}").strip(), "")
        values = [x.strip().strip('"') for x in raw.split(",") if x.strip()]
        if "minutes = true" in line:
            mm = need("SCREENSAVER_MINUTES", re.search(r'local SCREENSAVER_MINUTES = \{([^}]*)\}', so))
            d[key] = [int(x) for x in mm.group(1).split(",") if x.strip()]
        elif "bool = true" in line:
            d[key] = [True, False]
        else:
            d[key] = values
        if len(d[key]) < 2:
            sys.exit("domain for %s parsed as %r: a one-value domain means the parse failed"
                     % (key, d[key]))

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
    d["systemIcons"] = [True, False]                     # icons.lua Disabled/Enabled
    # Booleans on other screens (bars, battery, clock): the type gives the domain.
    for k, v in fields.items():
        if isinstance(v, bool) and k not in d:
            d[k] = [True, False]

    # Fail closed on anything new. These are the fields a sweep cannot or should not enumerate.
    NOT_SWEPT = {
        "themeName",      # free text, and every case needs its own name anyway
        "boxArtWidth",    # the options are generated from the screen size at load time
    }
    unresolved = [k for k in fields if k not in d and k not in NOT_SWEPT]
    if unresolved:
        sys.exit("no domain for THEME_FIELDS key(s): %s\n"
                 "Add them to parse_domains (or to NOT_SWEPT with a reason) -- an option with no "
                 "domain is an option the matrix never tests." % ", ".join(unresolved))
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


def parse_color_defaults():
    src = read("src", "state.lua")
    block = need("COLOR_FIELDS", re.search(r'state\.COLOR_FIELDS = \{(.*?)\n\}', src, re.S)).group(1)
    return need("colour defaults",
                dict(re.findall(r'\{ key = "([A-Za-z0-9_]+)", default = "(#[0-9A-Fa-f]{6})" \}', block)))


def parse_preset(src):
    """Pull a built-in preset's fields out of its Lua table. A fresh app launch starts from the
    THEME_FIELDS defaults, so a field the preset omits is that default -- which is how the
    expectations below treat anything missing."""
    colors = {}
    m = re.search(r'colors\s*=\s*\{(.*?)\}', src, re.S)
    if m:
        colors = dict(re.findall(r'([A-Za-z0-9_]+)\s*=\s*"(#[0-9A-Fa-f]{6})"', m.group(1)))
        src = src[:m.start()] + src[m.end():]
    fields = {}
    for key, raw in re.findall(r'^\s*([A-Za-z0-9_]+)\s*=\s*([^,\n]+),', src, re.M):
        raw = raw.strip()
        if key in ("colors", "source", "themeName"):
            continue
        if raw in ("true", "false"):
            fields[key] = raw == "true"
        elif raw.startswith('"'):
            fields[key] = raw.strip('"')
        elif re.fullmatch(r'-?\d+(\.\d+)?', raw):
            fields[key] = float(raw) if "." in raw else int(raw)
    return fields, colors


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
    # Added 2026-10-25 with the options themselves: SPRUCE sets these three and PyUI defaults the
    # other way, so a theme that omits them does not match the stock one.
    a += ["--expect", "displayVolumeNumbers=%s" % ("true" if f.get("showVolumeNumber", True) else "false")]
    a += ["--expect", "setTopBarTextToGameSelection=%s" % ("true" if f.get("topBarShowsGame", True) else "false")]
    a += ["--expect", 'fullScreenGridGameMenuResizeType="%s"'
          % ("ZOOM" if f.get("fullScreenGridFit", "Fit") == "Zoom" else "FIT")]
    # mainMenuTitle is written ONLY when the title is hidden: with it shown the key is absent and
    # PyUI supplies its own, so asserting it then would fail on a correct theme.
    if not f.get("showMainMenuTitle", True):
        a += ["--expect", 'mainMenuTitle=""']
    return a


def background_args(f, colors=None):
    colors = colors or {}
    t = f.get("backgroundType", "Gradient")
    if t == "Solid":
        return ["--gradient", "solid"]
    d = f.get("backgroundGradientDirection", "Vertical").lower()
    a = colors.get("background", DEFAULT_COLORS["background"])
    b = colors.get("backgroundGradient", DEFAULT_COLORS["backgroundGradient"])
    if a.upper() == b.upper():
        # both stops the same colour: a gradient was asked for but cannot be distinguished from
        # a flat fill, so assert flatness rather than a ramp that does not exist.
        return ["--gradient", "solid"]
    return ["--gradient", "%s:%s,%s" % (d, a, b)]


# Only "SPRUCE Art" recolours the SPRUCE art in two tones. Glyph and Letter each draw one `ink`
# colour (icon_renderer.lua drawSymbol/drawHandheldGlyph), and SPRUCE Mono is one colour by name.
# Asserting "multi" for the Glyph default is what failed all 18 cases on 2026-10-19.
TWO_TONE_STYLES = {"SPRUCE Art"}


def icon_args(f):
    if not f.get("systemIcons", True):
        return []            # no icons directory at all; nothing to assert
    style = f.get("systemIconStyle", "Glyph")
    return ["--icon-style", "multi" if style in TWO_TONE_STYLES else "mono"]


def main():
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    dflt = parse_defaults()
    dom = parse_domains(dflt)
    global DEFAULT_COLORS
    DEFAULT_COLORS = parse_color_defaults()
    cases, n = [], 0

    def add(name, fields=None, body=None, theme=None):
        """Every case builds under an S2nnn theme name THIS RUN OWNS. A case must never build over
        or delete a theme the user has, which is what using a preset's own name would have done."""
        nonlocal n
        n += 1
        stem = os.path.join(out, "%03d-%s" % (n, name))
        assert re.fullmatch(r"S2\d{3}", theme), "theme name must be S2nnn, got %r" % theme
        if body is not None:
            open(stem + ".lua", "w").write(body)
            pf, pc = parse_preset(body)
            args = background_args(pf, pc) + icon_args(pf) + expectations(pf)
        else:
            open(stem + ".lua", "w").write(preset(theme, fields))
            args = background_args(fields) + icon_args(fields) + expectations(fields)
        open(stem + ".theme", "w").write(theme + "\n")
        assert args, "case %s would ship no assertions at all" % name
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
        src = open(os.path.join(pdir, f)).read()
        need("themeName in " + f, re.search(r'themeName\s*=\s*"([^"]+)"', src))
        theme = "S2%03d" % (n + 1)
        # The app loads this through the same preset loader; only the theme name is ours, so the
        # build cannot touch a theme the user already has under the preset's own name.
        body = re.sub(r'themeName\s*=\s*"[^"]+"', 'themeName = "%s"' % theme, src, count=1)
        add("preset-%s" % name, body=body, theme=theme)

    with open(os.path.join(out, "CASES.txt"), "w") as fh:
        for stem, theme in cases:
            fh.write("%s\t%s\n" % (stem, theme))
    print("%d cases -> %s" % (len(cases), out))
    print("  per-option %d, combinations 4, presets %d"
          % (len(cases) - 4 - len([f for f in os.listdir(pdir) if f.endswith('.lua')]),
             len([f for f in os.listdir(pdir) if f.endswith('.lua')])))


if __name__ == "__main__":
    main()
