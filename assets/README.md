# Assets

- **fonts/** TTF families offered as theme fonts (each with its OFL/licence file). The chosen
  family is copied into the generated theme and referenced by PyUI's `config.json`.
- **icons/lucide/**, **icons/kenney_input_prompts/**, **icons/material_symbols/** SVG sources.
  `utils/generate_ui_icon_pngs.py` rasterises them into `icons/png/` (gitignored, 128 px white
  masks) which the app tints at runtime and bakes into theme skins and system icons.
- **images/** the Ko-fi QR code shown on the About screen (original author's).
