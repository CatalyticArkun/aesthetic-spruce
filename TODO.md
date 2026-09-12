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
- [ ] **Rotation direction** on the Miniloong follows PyUI's own convention, which PyUI marks unverified; confirm on the device that the app is not upside down, and check RG28XX (270).
- [ ] **Miniloong: activation needs a PyUI restart.** On the Miniloong PyUI runs apps as a child (`subprocess.run`) instead of exiting through `cmd_to_run.sh`, so after "Activate Now" PyUI keeps the old theme in memory. Proposed: `activateTheme` drops a `userdata/.theme_activated` marker and `spruce/launch.sh`, as its very last command, runs `killall MainUI` when the marker exists (PyUI's SIGTERM handler raises inside `subprocess.run`, which kills launch.sh, so nothing may follow it). Needs a Miniloong run from the Apps menu.
- [ ] **Stickless Anbernic XX d-pad swap** (spruce 4.4.0 `_xx_dpad_swap`, `nds_pwrkey`): mupen and ScummVM set it to 2 (d-pad reported as the left stick) and back to 0; if an emulator is killed hard the value could stay at 2 when the app starts. Not seen; no stickless unit has run the app since 4.4.0.

## Performance (Mali handhelds)

- [ ] Per-frame `love.graphics.newMesh` for focused-item gradients (`component.lua`, `button.lua` x2, `tab_bar.lua`); cache one mesh per component and `setVertices`.
- [ ] `hex.lua` builds ~54 `Header` objects per frame through `getManualContentArea()`; compute the grid once in `onEnter`/`updateLayout` (partly mitigated: the measuring header is now a module-level instance).
- [ ] `input_manager.lua` still copies `prevActionStates` and allocates the `actions` table every frame.
- [ ] `colors.lua` `adjustColor` duplicates `utils/color.lua` HSL helpers (different ranges); unify.
- [ ] `theme_creator`: generating icons for 81 systems takes ~8 s on the TSPS and ~15 s on the Miniloong (glyph + label per tile, PNG encode each). Options: encode in a worker thread, or skip `sel/` when PyUI can derive it.

## Product

- [ ] **System families** in `src/spruce/system_glyphs.lua`: check the handheld/console/arcade/computer membership for systems added to spruce later (unknown ids fall back to the controller glyph; systems SPRUCE has no icon for need an `EXTRA_SYSTEM_ICONS` entry in `icon_renderer.lua`); a per-system override in presets is not offered.
- [ ] **Volume indicator**: PyUI shows `icon-volume-00`..`icon-volume-20` (an f-string, so the asset grep missed it) plus the level number in the top bar; generated themes have no volume icons and do not set `displayVolumeNumbers` (every SPRUCE config sets it true). Add the 21 pictograms to `pyui_assets.lua` (dims are already in `skin_spec.lua`) and the key to `pyui_config.lua`.
- [ ] **Screensaver dim** (`screensaver.dimBacklight`, new in spruce 4.4.0, default true): generated themes leave it unset, which matches SPRUCE. A toggle would need a `THEME_FIELDS` entry, a `spruce_options` row (and a generalised bool mapping: today only "Shown" maps to true) and the config key.
- [ ] **Theme sounds**: the muOS sound set was dropped; generated themes have no `sound/change.wav`. Decide whether to ship a CC0 click.
- [ ] **Pixel2 loading screen**: spruce composites `skin/app_loading_bg.png` + `app_loading_0*.png` (or uses `app_loading_merged.png`) from the active theme at boot and on theme change, falling back to SPRUCE's art. Generated themes have none, so the Pixel2 shows SPRUCE's loading screen. Decide whether to render them (dims are in `skin_spec.lua`).
- [ ] **Game Nursery** copies the active theme's `icons/` (640x480 set, never `icons_<W>x<H>`) into `Saves/GameNursery/Imgs` at download time; check whether those images are shown and whether generated tiles look right there.
- [ ] **All-resolutions build** (`state.allResolutions`) exists but has no UI toggle; add one under Settings if sharing themes between devices is wanted.
- [ ] **Box art width preview** (`box_art_width.lua`): the animated preview still shows a text/box-art split from the muOS layout; PyUI's `TEXT_AND_IMAGE` view differs. Re-draw with `ui/theme_preview.lua`.
- [ ] **Compat check coverage** (`src/spruce/compat.lua`): warns when the card is not on a `SUPPORTED_FAMILIES` release (4.3.x, 4.4.x) and on missing loader sentinels. Add a family only after diffing PyUI's `themes/theme.py` and `theme_patcher.py` between releases; add the tested version to `TESTED_VERSIONS` after each release verification. PyUI still has no version of its own to read (4.4.1).
- [ ] **Zero28**: spruce 4.4.1 has a `Zero28` platform but PyUI has no `MAGICX_ZERO28` device (`mainui.py` `initialize_device` raises), so spruce's menu does not start there; the A/B and X/Y swap in `spruce/launch.sh` is an unverified assumption. Revisit if spruce adds the device.
- [ ] **RGB30 theme after a Full update**: spruce keeps the RGB30 system json at `App/PyUI/config/rgb30-system.json`, which a Full update deletes (`App/-Updater/delete_files.sh` removes `App/PyUI`), so the active theme falls back to SPRUCE. Report to spruce (back the file up in `spruceBackup.sh`, or keep it under `Saves/`).
- [ ] **Other devices**: Brick, Smart Pro, Pixel2, RGB30 and the Anbernic stick variants have not run the app (Brick Pro, Flip, RG35XX SP and a 720x480 Anbernic passed the tour on 2026-09-09); `DEVELOPMENT.md` §8 lists expectations and the per-platform SDL environment to verify.
- [ ] **Validator coverage** (`utils/validate_theme.py`): it checks the ids in `skin_spec.lua` only; with a spruce tree it could also read every `Emu/*/config.json` and `App/*/config.json` and warn about tiles PyUI will look for but the theme lacks. Recommend a pinned `git archive` tree for `--spruce`: the default is a working tree.
- [ ] **Unused assets**: `ic-retroarch-n` / `ic-retroarch-f` in `pyui_assets.lua` have no reader in PyUI (4.3.4 to 4.4.1); drop them.
- [ ] **`DEPLOY_HOST` deploy** in `build.sh` runs `rsync --delete`, which wipes the card's `userdata/` (settings, presets, logs); exclude `/userdata/` and `/theme_working/`.
- [ ] **Upstream screenshots** in `.github/` still show the muOS app; replace with spruce captures (`AESTHETIC_SCREENSHOT=path ./dev_launch.sh`).
- [ ] **`.github/` wiki links** in README point at the original project's wiki, which documents the muOS build.
