# Devices

Aesthetic Spruce targets **aarch64 spruceOS 4.3.x, 4.4.x, 4.5.x and 4.6.x**, tracked to 4.6.0 stable /
4.6.1 nightly. The app warns once at start if the card runs anything else, or if PyUI's theme
loader has changed in a way the generator does not understand.

## Verified on hardware

| spruceOS | Devices |
| --- | --- |
| 4.3.6 | TrimUI Smart Pro S, TrimUI Brick Pro, Miyoo Flip, Miniloong Pocket 1, Anbernic RG35XX SP, Anbernic RG40XX-class 720x480 |
| 4.4.0 | Miyoo Flip |
| 4.4.3 | MagicX Zero 28, MagicX Zero 40 |
| 4.5.3 | MagicX Zero 28, MagicX Zero 40 |
| 4.5.5 | MagicX XU Mini M |
| 4.6.1 (nightly 20261109) | TrimUI Smart Pro S, MagicX Zero 40 (oakMOSS), TrimUI Brick on oakMOSS |

The XU Mini M run was the thorough one: on 4.5.5 it built 71 themes covering every option value
and all 34 built-in presets, and each generated theme was checked on the device for correct
gradients, icon tones, PyUI config keys and image formats.

The 4.6.1 runs (2026-11-08) installed the test build, built and applied a theme headless, checked
the main menu on screen (5 tiles on the 16:9 Smart Pro S, SPRUCE's 2x3 grid of six on the Zero 40,
4 tiles on the Brick) and restored the stock theme; on the Zero 40 and the oakMOSS Brick a person
also pressed A, B, X and Y in the app and each acted as labelled.

## Expected to work, not yet run

TrimUI Brick (stock) and Smart Pro, GKD Pixel2, the rest of the Anbernic RG XX
family, RGB30, the MagicX XU20 and the BatleXP G350. The MagicX boards need spruceOS 4.4.2 or a Development build: 4.4.1
has no MagicX support in its menu.

## Not supported

Miyoo A30 and the Mini family: 32-bit, with no LÖVE runtime.

**Accent Color** (spruce's own app) does not work with themes from Aesthetic, and is not meant to.
It recolours themes that ship its template folder; Aesthetic themes do not, so the app says so and
changes nothing. That is the expected result, not a fault. Change colours by rebuilding the theme
in Aesthetic. Forcing Accent Color onto an Aesthetic theme is undefined and unsupported.

## Device notes

- **RGB30**: a Full spruce update resets the active theme to SPRUCE, because spruce keeps that
  setting inside `App/PyUI`, which the update replaces. Your theme folder is kept — re-select it
  under ***Settings*** > ***Theme***.
- **MagicX (Zero 28, Zero 40, XU20)**: their platform configs export a positional SDL map, so the
  app swaps A/B and X/Y for them. See `spruce/launch.sh`.
- **BatleXP G350**: untested, but it is the same RK3326 SoC, 640x480 panel, dArkMoss base and pad
  codes as the XU Mini M, so it is expected to behave the same.
