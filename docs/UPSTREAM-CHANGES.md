# Changes from upstream

This fork started from [joneavila/aesthetic](https://github.com/joneavila/aesthetic) v1.10.1, a
theme creator for muOS. What changed to make it a spruceOS app:

- Theme output is a renderer (`src/utils/skin_renderer.lua`, `icon_renderer.lua`,
  `pyui_config.lua`): PyUI themes are bitmap skins plus a `config.json`, not `.ini` schemes.
- TÖVE (native SVG) is gone; icons are rasterised on the host and tinted at runtime.
- muOS-only parts (launcher, `.muxupd` packaging, LVGL fonts, ImageMagick, RGB, `theme.sh`) are
  replaced by `spruce/launch.sh`, `build.sh`, TTF fonts, LÖVE canvases and a write to the device's
  system json.
- The editor UI, colour pickers, presets and settings are the original code.

**AI disclosure.** This port was written with AI assistance (Claude), directed and tested by the
maintainer on real devices. Throughout, the original author's attribution, credits and Ko-fi have
been kept intact as far as possible; the design and the editor code are Jonathan Avila's work.
