# Developing Aesthetic Spruce

Everything a contributor needs to build, run, change and test the app. Facts here were measured on
spruceOS 4.3.6 (Development nightly of 2026-09-04) and 4.4.0 and the devices listed at the end, and
checked against the 4.4.1 source (PyUI's theme loader reads the same layout from 4.3.0 to 4.4.1);
where something is an assumption it says so.

## 1. What the app is

- A LÖVE 11.5 (LuaJIT, Lua 5.1 semantics) application for aarch64 spruceOS handhelds. The runtime
  ships inside the app: `bin/love`, `lib/liblove-11.5.so`, `lib/libluajit-5.1.so.2` (the same build
  spruce bundles with its Moonlight app), plus `lib/fallback/` media libraries used only when the
  device rootfs lacks one.
- spruce launches apps by writing `cd <dir>; ./launch.sh` to `/tmp/cmd_to_run.sh` and exiting PyUI;
  `principal.sh` runs the file and restarts PyUI when we return. So the app owns the screen for its
  whole life, and "apply theme" is just writing the folder name into the `theme` key of the device's
  system json before exiting. No frontend restart command is needed.
- Output is a PyUI theme folder: `Themes/<name>/config.json` + `skin/` + `icons/` (640x480 base set),
  `config_<W>x<H>.json` + `skin_<W>x<H>/` + `icons_<W>x<H>/` for the device's native size, a `.ttf`,
  `preview.png`, `README.md`.

## 2. Repository map

| path | what |
|---|---|
| `src/main.lua` | LÖVE callbacks, crash handler (logs + returns to PyUI), autobuild/tour/screenshot hooks |
| `src/conf.lua` | window from `WIDTH`/`HEIGHT`/`ROTATION`, fullscreen desktop on device |
| `src/display.lua` | renders the logical frame into a canvas and rotates it on portrait panels (Miniloong, RG28XX, Zero28) and the upside-down XU20 (180) |
| `src/state.lua` | the theme model: `THEME_FIELDS`, `COLOR_FIELDS`, `exportTheme`/`importTheme`, defaults |
| `src/paths.lua` | every path, derived from the environment contract below |
| `src/theme_creator.lua` | the build pipeline (coroutine yielding progress) and `activateTheme` |
| `src/utils/skin_renderer.lua` | draws every `skin/*.png` from `src/spruce/pyui_assets.lua` rules at `src/spruce/skin_spec.lua` sizes |
| `src/utils/icon_renderer.lua` | draws `icons/<system>.png`, `icons/sel/`, `icons/app/` (glyph or letter tiles) |
| `src/utils/pyui_config.lua` | builds `config.json` / `config_<W>x<H>.json` from state |
| `src/utils/image_generator.lua` | canvases, gradient mesh, preview, `encodeCanvas` (alpha post-processing) |
| `src/spruce/` | `compat.lua` (version/loader check), `pyui_assets.lua`, `system_glyphs.lua` (families, names), `skin_spec.lua` (generated) |
| `src/screens/` | one module per screen; `main_menu.lua` is the hub, `spruce_options.lua`, `bars.lua`, `icons.lua`, `home_screen_layout.lua` are option screens |
| `src/ui/` | components (button, list, modal, slider, tab bar, header), controllers (input, focus), `theme_preview.lua` |
| `src/utils/{settings,presets,theme_file}.lua` | auto-restore and presets, one serializer |
| `src/gamepad_layout.lua`, `src/input.lua`, `src/ui/controllers/input_manager.lua` | input; see §6 |
| `src/autobuild.lua`, `src/tour.lua` | headless build and screen tour used for device tests |
| `src/presets/*.lua` | the nine built-in presets (theme-file format, §4) |
| `spruce/` | `launch.sh`, `config.json` (PyUI app manifest), `icon.png` |
| `assets/` | fonts (TTF + licences), Lucide/Kenney/Material SVGs; `assets/icons/png/` is generated and ignored |
| `utils/` | host tools: `generate_ui_icon_pngs.py`, `generate_skin_spec.py`, `check_lua_syntax.py`, `validate_theme.py` |
| `build.sh`, `dev_launch.sh` | package for the card; run on a workstation |
| `lib/fallback/PROVENANCE.md` | where each bundled library came from and its licence |

## 3. Environment contract

`spruce/launch.sh` sources spruce's `helperFunctions.sh` and exports, for `bin/love`:

| variable | meaning |
|---|---|
| `WIDTH`, `HEIGHT` | logical size (`DISPLAY_WIDTH` x `DISPLAY_HEIGHT`); landscape everywhere but the Zero40 (480x800) |
| `ROTATION` | `DISPLAY_ROTATION`; 90/270 makes the physical window portrait, 180 flips it (XU20); `display.lua` rotates |
| `ROOT_DIR` | the app folder; holds `userdata/` (settings, presets, logs, `last_crash.txt`) and `theme_working/` |
| `SOURCE_DIR` | `.aesthetic/`, the Lua tree love runs |
| `THEME_PRESETS_DIR` | built-in presets |
| `SPRUCE_THEMES_DIR` | `/mnt/SDCARD/Themes` |
| `SPRUCE_SYSTEM_JSON` | spruce's `$SYSTEM_JSON`, whose `theme` key names the active theme |
| `SPRUCE_PLATFORM`, `SPRUCE_VERSION`, `SPRUCE_VERSION_COMPLEX` | for the compatibility check |
| `AESTHETIC_SWAP_AB`, `AESTHETIC_SWAP_XY` | button-label remap per platform (§6) |
| `LD_LIBRARY_PATH` | `.aesthetic/lib` first, then the platform's path, then `.aesthetic/lib/fallback` last |
| `SDL_*` | per platform, mirroring `App/PyUI/launch.sh` (kmsdrm+alsa on Miniloong/RGB30; mali SDL and `SDL_JOYSTICK_DISABLE_UDEV=1` on Anbernic) |

Test hooks (any run): `AESTHETIC_AUTOBUILD=1` builds and quits (`AESTHETIC_PRESET=<name>` loads a preset
first, `AESTHETIC_AUTOAPPLY=1` also activates), `AESTHETIC_TOUR=1` visits every screen, presses
Right on the option screens and checks the state changed, `AESTHETIC_SCREENSHOT=/abs/path.png` grabs
the window after a second and quits, `AESTHETIC_COMPAT_WARN=1` makes the compatibility check warn
(the modal a card on an unsupported spruce release sees; a tour then covers that path too). `DEV=true` (set by `dev_launch.sh`) windows the app and points
the card paths at `.dev/`.

## 4. The theme model and how to add an option

`src/state.lua` declares every option once:

```lua
{ key = "showClock", type = "boolean", default = true }, -- in THEME_FIELDS
{ key = "background", default = "#1E40AF" },             -- in COLOR_FIELDS
```

`state.exportTheme()` / `state.importTheme(t)` are the only serialisation path; `utils/theme_file.lua`
writes and reads the Lua-table files used by both the settings file and presets:

```lua
return {
	themeName = "DMG", fontFamily = "Retro Pixel", homeScreenLayout = "Grid", systemIcons = false, ...
	colors = { background = "#9BBC0F", foreground = "#0F380F", ... },
	source = "built-in",
}
```

Unknown fields are ignored and missing ones take the default, so old presets keep loading.

To add an option:

1. Add the field to `THEME_FIELDS` (or `COLOR_FIELDS`).
2. Expose it on a screen. For a list of choices copy a row in `src/screens/spruce_options.lua`
   (`ROWS` table: key, label, option strings, `bool`/`minutes` mapping). Note the List/Button quirk
   in §6: read the value back from the button every frame; the list's cycle callback never fires.
3. Consume it: a config key goes in `utils/pyui_config.lua` (only keys PyUI reads, exact enum
   spellings), a visual change goes in `skin_renderer.lua` / `icon_renderer.lua`.
4. Update the built-in presets if the default is not what a preset should carry.
5. Add a `tour.lua` step (`{ screen = ..., press = "right", field = ... }`) so device runs check it.

## 5. The build pipeline

`theme_creator.createThemeCoroutine()` yields a progress string per step:

1. Clear `theme_working/`.
2. For each resolution (`paths.BASE_RESOLUTION`, plus the native one when different and SPRUCE has a
   set for it; all six when
   `state.allResolutions`): render the skin, render the icons (if `systemIcons`), write the config.
3. Copy the chosen TTF, render `preview.png` (640x480 with the theme name), write `README.md`.
4. `mv` the folder into `Themes/<sanitised name>` (next free `(n)` suffix), `sync`.

Skin: `pyui_assets.lua` lists the ~47 assets PyUI actually reads (grep of every `"<name>.qoi|png"`
literal in `App/PyUI/main-ui`) with a `kind` (background, bar, plate, frame, panel, pictogram,
tile, empty) and options; `skin_spec.lua` gives each asset's size per resolution, generated from
spruce's SPRUCE theme by `utils/generate_skin_spec.py` (regenerate when spruce changes SPRUCE).
Exceptions: `background` is always the full screen (PyUI's patcher rule; SPRUCE's own 1280x720 file
is 960x720), `icon-A-54`/`icon-B-54` are compact buttons (SPRUCE ships transparent 640x54 strips).

Icons: `system_glyphs.lua` groups system ids into families (handheld, console, arcade, computer)
with one glyph each, `overrides` for engines and ports, `apps` for app icons, `names` for the
Letter style. `@handheld`, `@console` and `@tv` are drawn procedurally in `icon_renderer.lua`; every
other name is a PNG under `assets/icons/png/lucide/{glyph,ui}/`. Unknown ids get the controller.
The system tiles rendered are SPRUCE's icon list (`skin_spec.lua`) plus
`icon_renderer.EXTRA_SYSTEM_ICONS`, systems SPRUCE ships no art for (COCO, J2ME, PC-98), at the
common tile size; `EXTRA_APP_ICONS` does the same for apps (ours, Songo#5). Ids are the basename of
the `icon` field in `Emu/<SYS>/config.json` or `App/<name>/config.json`.

The *SPRUCE Art* style (`systemIconStyle = "SPRUCE Art"`) takes each system's art from spruce's own
SPRUCE theme on the card (`paths.SPRUCE_REFERENCE_THEME`, `icons_<W>x<H>/` for the resolution, else
`icons/`; override with `SPRUCE_REFERENCE_THEME=<dir>` on a workstation) and redraws it as a two-tone
gradient map: luminance, stretched per icon, runs from the background colour (held back by
`ART_BG_HOLD` so silhouettes never vanish) to the foreground, flipped on light themes so light parts
stay light. Unselected tiles use SPRUCE's grey art at `ART_DIM` contrast, selected tiles its colour
art at full contrast. Systems without SPRUCE art (COCO, J2ME, PC-98) fall back to glyph tiles.

Composition rules learned from PyUI (`views/grid_view.py`, photos on device):

- PyUI draws the label under main-menu and system tiles at a fixed height, so tile plates occupy
  only the top square of the image and the band below stays transparent.
- Selection is the inverted tile; `bg-game-item-f` / `bg-game-item-single-f` (drawn behind the
  selected cell at 1.05x) are thin frames. Grid labels sit on the background, so
  `grid.selectedcolor` is the foreground; list rows sit on a filled plate, so `list.selectedcolor`
  is the background.
- App icons are filled plates with a background-coloured glyph so they survive on the filled
  selected row.
- `image_generator.encodeCanvas` un-premultiplies canvas pixels and writes the shape's colour into
  fully transparent pixels. Without that, PyUI's bilinear scaling drags black into every edge and
  rounded corner.

Icons are rasterised on the host: `utils/generate_ui_icon_pngs.py` (cairosvg) turns the SVG sets
into 128 px white masks under `assets/icons/png/`; `build.sh` runs it when missing. TÖVE, the
runtime SVG library upstream used, needs glibc 2.38 and is gone.

## 6. Input, display, and two quirks that bite

- **Button labels.** SDL's built-in gamepad maps are positional (bottom = "a"); most spruce
  handhelds print Nintendo labels (right = A). PyUI reads evdev with per-device tables
  (`App/PyUI/main-ui/devices/*mapping_provider*.py`); we export the same facts from `launch.sh` and
  `gamepad_layout.lua` maps "a" to the SDL name to poll. TrimUI, Flip: swap A/B and X/Y.
  Miniloong, Pixel2: swap A/B. Anbernic, RGB30, MagicX (Zero28, Zero40, XU20): none (spruce's own
  map strings are label-based; the MagicX cfgs export `a:b0`, BTN 304, the button labelled A).
  Getting this wrong makes A act as Back, which on the main menu exits the app.
- **Option screens poll their buttons.** `List:handleInput` hands Left/Right to the focused
  `Button`, which cycles its own option and reports handled, so `onItemOptionCycle` never fires.
  Every option screen reads `button:getCurrentOption()` back into state each frame.
- **Rotation.** On the Miniloong LÖVE sees 720x960; `display.lua` draws the 960x720 frame into a
  canvas (`stencil = true`, screens use stencils) and draws it rotated the way PyUI does
  (`display.py:960-1016`). Never call `love.graphics.reset()` inside draw code: it unbinds that canvas.
- The palette tab still uses the older `src/input.lua` poller; everything else uses
  `InputManager`. Both go through `gamepad_layout`.

## 7. Build, run, test

```
python3 -m pip install cairosvg lupa           # rasteriser + LuaJIT parser for the syntax check
python3 utils/check_lua_syntax.py              # every src/*.lua through LuaJIT 2.1's parser
./build.sh                                      # dist/sd-overlay/App/AestheticSpruce, _sd-overlay.zip, .7z
LOVE=/path/to/love ./dev_launch.sh 1280 720     # interactive on a workstation (keyboard map in src/input.lua)
AESTHETIC_AUTOBUILD=1 AESTHETIC_PRESET=dmg ./dev_launch.sh 1280 720
python3 utils/validate_theme.py .dev/Themes/DMG # dims vs SPRUCE, config keys PyUI reads, spruce's prebake --check
AESTHETIC_TOUR=1 ./dev_launch.sh 960 720        # ROTATION=270 in the env emulates the Miniloong
```

A LÖVE 11.5 AppImage works on Linux: extract it and point `LOVE` at `squashfs-root/AppRun`.
`validate_theme.py` runs spruce's `tools/theme/prebake-theme-resolution.py --check` when a spruceOS
checkout is available (`--spruce`, `--prebake`).

The 7z is built with `-mf=off`: spruce's on-device `7zr` cannot extract archives with the ARM64/BCJ
executable filters 7-Zip applies by default.

On a device (over SSH), the honest test is the same path PyUI uses:

```sh
/mnt/SDCARD/spruce/bin64/7zr x -y AestheticSpruce_vX.Y.Z.7z      # absolute path: the Flip's PATH lacks bin64
printf '#!/bin/sh\nexport AESTHETIC_TOUR=1\ncd /mnt/SDCARD/App/AestheticSpruce && ./launch.sh\n' > /tmp/cmd_to_run.sh
chmod +x /tmp/cmd_to_run.sh && killall MainUI                     # principal.sh runs it, then restarts PyUI
grep -E 'TOUR|CRASH|AUTOBUILD|COMPAT' App/AestheticSpruce/userdata/logs/*.log
```

`principal.sh` copies `cmd_to_run.sh` to `spruce/flags/lastgame.lock` (auto-resume); remove or restore
it afterwards. Keep `userdata/` across reinstalls if you want the logs. A crash writes
`userdata/last_crash.txt`, a line in spruce's log, and returns to PyUI on its own.

## 7a. Releases

Two manual GitHub Actions in `.github/workflows/`:

- **Nightly build** (`nightly.yml`): pick a ref; it stamps `version.prerelease` with
  `nightly.<date>.<sha>` (so the About screen and file names carry it), runs `build.sh`, uploads the
  archives as a workflow artifact and, unless `publish` is off, creates a pre-release tagged
  `nightly-<date>-<sha>` with the zip, the 7z and `SHA256SUMS.txt`.
- **Stable release** (`release.yml`): promotes a nightly to a stable release. The tag has to exist
  first, because a workflow token may not create a ref whose workflow files differ from the default
  branch's, which is exactly what pinning an older commit does (both `git push` and the Releases API
  refuse it). So:

  ```
  git fetch origin
  git tag -a v2.1.0 <nightly commit> -m "Aesthetic Spruce v2.1.0"
  git push origin v2.1.0
  ```

  then run the workflow with `version = 2.1.0` and the nightly tag. It checks the tag points at that
  nightly's commit, checks out the commit, sets `src/version.lua` to the clean version, rebuilds and
  publishes the release; `bump_main` also commits the version bump to `main` so later nightlies
  carry the new number. Add a `RELEASE_TOKEN` secret (a PAT with repo and workflow scope) and it
  creates the tag itself.

`build.sh` reads `version.prerelease` and writes `dist/SHA256SUMS.txt`, so local builds name their
files the same way.

## 8. Devices and libraries

Verified on hardware (tour + build, 2026-09-09, spruceOS 4.3.6 nightly): TrimUI Smart Pro S
(1280x720), TrimUI Brick Pro (1024x768), Miyoo Flip (640x480), Miniloong Pocket 1 (960x720
rotated), Anbernic RG35XX SP (`AnbernicXX640480NoStick`), an Anbernic 720x480 unit
(`AnbernicXX720480NoStick`). On spruceOS 4.4.0 (2026-09-12): Miyoo Flip, tour with the real
version check and with `AESTHETIC_COMPAT_WARN=1`, then build + apply against the real
`flip-system.json` (only the theme line changed). Expected: Brick, Smart Pro, Pixel2, other
Anbernic RG XX, RGB30, and the MagicX Zero28, Zero40 and XU20 (spruceOS 4.4.2 / Development;
tours and builds pass on a workstation at their geometries, no board has run the app yet). On the
RGB30 spruce keeps the system json at `App/PyUI/config/rgb30-system.json`, which a Full spruce
update deletes, so the active theme falls back to SPRUCE (the theme folder is kept). Not supported:
A30 and the Mini family (32-bit).

MagicX: PyUI shows an app when its `devices` list names any token the device reports
(`get_device_names()`); the MagicX boards report their own name plus the family token
`MAGICX_A133P`, which `spruce/config.json` lists. The Zero40 runs 480x800 portrait, which SPRUCE has
no set for, so it gets the base set (PyUI's ThemePatcher scales it on the device) and the app lays
itself out portrait. Their rootfs libraries (glibc, the SDL2 in `/usr/magicx/lib`, the LÖVE media
libraries) have not been measured.

liblove links against SDL2, freetype, openal, z, modplug, vorbisfile/vorbis/ogg, theoradec, mpg123,
stdc++, gcc_s, c. Bundled and loaded first: liblove, luajit. Never bundled: SDL2 (each platform's
carries its video driver), libz, libstdc++, libgcc_s, libc. Bundled as a last-resort fallback:
openal (+ libatomic, which the Anbernic BaseOS rootfs lacks), freetype, vorbis, vorbisfile, ogg,
theoradec, mpg123, modplug; all taken from the spruce release tree, see `lib/fallback/PROVENANCE.md`.
Fleet glibc floor for spruce's own binaries is 2.29; measured devices run 2.33 (TrimUI) and 2.38
(Flip, Miniloong).

`src/spruce/compat.lua`: `SUPPORTED_FAMILIES` (4.3, 4.4) and `TESTED_VERSIONS`; it also probes
`App/PyUI/main-ui/themes/theme.py` for the asset and layout names the generator depends on. Add a
family only after `git diff --ignore-cr-at-eol <last supported tag> <new tag> --
App/PyUI/main-ui/themes/theme.py App/PyUI/main-ui/themes/theme_patcher.py` shows no layout change
(without the flag the CRLF churn hides the real diff). Add a tested version in the commit a
verified nightly is built from. `AESTHETIC_COMPAT_WARN=1` forces the warning modal.

## 9. PyUI facts the generator depends on

- A directory under `Themes/` is a theme if it has `config.json`; the picker shows the folder name.
- `config_<W>x<H>.json` + `skin_<W>x<H>/` + `icons_<W>x<H>/` are the per-resolution set; without
  them PyUI rescales the base set on device (`ThemePatcher`) and restarts, which is slow.
- Assets resolve `.qoi` then `.png`; misses are cached.
- Config enums must be spelled exactly (`GRID`, `TEXT_ONLY`, `TEXT_AND_IMAGE`, `ICON_AND_DESC`,
  `FULLSCREEN_GRID`, `CAROUSEL`); anything else silently falls back to PyUI defaults.
- The active theme is the folder name in the `theme` key of `$SYSTEM_JSON`; PyUI applies it live or
  on its next start. `screensaver.screensaverTimeoutSec <= 0` disables the screensaver.
- App icons are keyed by the app's `config.json` `icon` filename: ours is `aestheticspruce.png`.

## 10. Gotchas

- spruce cards can be case-sensitive FAT32; `require` names must match file case exactly (an
  upstream `ui.Component` mismatch was fatal on Linux and on those cards).
- `commands.executeCommand` relies on Lua 5.1 `os.execute` returning a number; verified on the
  device LÖVE build.
- `App/PyUI/` files in the spruceOS repository are CRLF; do not reformat them when reading.
- Keep the original author's attribution, credits and Ko-fi intact in the README, the About screen
  and the generated theme README; this fork is not affiliated with either upstream.
- Open work is tracked in `TODO.md`.
