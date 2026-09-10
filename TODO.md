# TODO

Items that need more than a local fix: design decisions, behaviour changes, or device testing.
Trivial findings from the 2026-09-08 audit were fixed in place; these remain.

## Correctness (needs scrutiny)

- [ ] **Option screens read state back from buttons** (`home_screen_layout`, `icons`, `bars`, `box_art_width`): `List:handleInput` hands left/right to the focused `Button`, which cycles its own option and returns handled, so the list's `onItemOptionCycle` callback never fires; every option screen polls `getCurrentOption()` each frame instead (upstream did the same). Make the cycle callback the single path and drop the polling.
- [ ] **Button:handleInput contract** (`src/ui/components/button.lua`): takes `(input)` while `Component`, `List`, `Container` and `FocusManager` pass `(direction, input)`; CONFIRM uses `isActionPressed` (held) so a held A can re-fire `onClick` on repeat ticks under `FocusManager`. Align the signature and switch to `isActionJustPressed`; verify every caller.
- [ ] **Palette tab uses the legacy poller** (`src/screens/color_picker/palette.lua`, `src/input.lua`): `isGamepadPressedWithDelay` has no edge detection, so A held for >0.3 s after entering the picker selects the nearest colour immediately. Port palette (and `debug.lua`) to `InputManager`, then delete `src/input.lua` (its L1+R1 quit combo in `input.update` is never called anyway; decide whether a quit combo is wanted at all).
- [ ] **HSV geometry on square panels** (`hsv.lua`): cursor maths mixes `contentHeight` and `squareSize`; identical on 4:3/16:9 but off on 720x720 (RGB30, RG CubeXX). Use `squareSize` everywhere; verify on a 720x720 device.
- [ ] **FocusManager fallback** (`focus_manager.lua:findNextFocusableComponent`): now skips hidden components (was returning on the first one); the wider focus model (one shared manager, screens clearing focus around modals) has not been reviewed.
- [ ] **Shared gradient preview** (`button.lua` `gradientPreviewInstance`): one mesh for every GRADIENT button; two visible with different colours would rebuild it every frame. Only one such button exists today (main menu Background).
- [ ] **Modal layout duplicated** (`modal.lua`): `handleInput` re-implements `draw`'s layout arithmetic to find `isScrollable`; extract one `computeLayout()`.
- [ ] **Hex confirm "wobble"** (`hex.lua`): the tween animates fields no draw code reads. Wire it into `drawKey` or delete the tween.
- [ ] **`commands.executeCommand`** assumes Lua 5.1 `os.execute` numeric return. Verified numeric on the device LÖVE (the `mv` step would have failed otherwise); keep an eye on it if the runtime changes.
- [ ] **Rotation direction** on the Miniloong follows PyUI's own convention, which PyUI marks unverified; confirm on the device that the app is not upside down, and check Zero28 (90) and RG28XX (270).

## Performance (Mali handhelds)

- [ ] Per-frame `love.graphics.newMesh` for focused-item gradients (`component.lua`, `button.lua` x2, `tab_bar.lua`); cache one mesh per component and `setVertices`.
- [ ] `hex.lua` builds ~54 `Header` objects per frame through `getManualContentArea()`; compute the grid once in `onEnter`/`updateLayout` (partly mitigated: the measuring header is now a module-level instance).
- [ ] `input_manager.lua` still copies `prevActionStates` and allocates the `actions` table every frame.
- [ ] `colors.lua` `adjustColor` duplicates `utils/color.lua` HSL helpers (different ranges); unify.
- [ ] `theme_creator`: generating icons for 77 systems takes ~8 s on the TSPS and ~15 s on the Miniloong (glyph + label per tile, PNG encode each). Options: encode in a worker thread, or skip `sel/` when PyUI can derive it.

## Product

- [ ] **System families** in `src/spruce/system_glyphs.lua`: check the handheld/console/arcade/computer membership for systems added to spruce later (unknown ids fall back to the controller glyph); a per-system override in presets is not offered.
- [ ] **Theme sounds**: the muOS sound set was dropped; generated themes have no `sound/change.wav`. Decide whether to ship a CC0 click.
- [ ] **All-resolutions build** (`state.allResolutions`) exists but has no UI toggle; add one under Settings if sharing themes between devices is wanted.
- [ ] **Box art width preview** (`box_art_width.lua`): the animated preview still shows a text/box-art split from the muOS layout; PyUI's `TEXT_AND_IMAGE` view differs. Re-draw with `ui/theme_preview.lua`.
- [ ] **Compat check coverage** (`src/spruce/compat.lua`): warns on family mismatch (4.3.x) and on missing loader sentinels. Add the tested version to `TESTED_VERSIONS` after each release verification; consider reading PyUI's own version if one appears.
- [ ] **Zero28 button layout** is assumed TrimUI-like (A/B and X/Y swapped) in `spruce/launch.sh`; verify against PyUI's device table for `MAGICX_ZERO28` or on hardware.
- [ ] **Other devices**: Brick, Smart Pro, Zero28, Pixel2, RGB30 and the Anbernic stick variants have not run the app (Brick Pro, Flip, RG35XX SP and a 720x480 Anbernic passed the tour on 2026-09-09); `DEVELOPMENT.md` §8 lists expectations and the per-platform SDL environment to verify.
- [ ] **Upstream screenshots** in `.github/` still show the muOS app; replace with spruce captures (`AESTHETIC_SCREENSHOT=path ./dev_launch.sh`).
- [ ] **`.github/` wiki links** in README point at the original project's wiki, which documents the muOS build.
