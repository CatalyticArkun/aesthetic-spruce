# Devices

Aesthetic Spruce targets **aarch64 spruceOS 4.3.x, 4.4.x and 4.5.x**, tracked to 4.5.2 stable /
4.5.5 nightly. The app warns once at start if the card runs anything else, or if PyUI's theme
loader has changed in a way the generator does not understand.

## Verified on hardware

| spruceOS | Devices |
| --- | --- |
| 4.3.6 | TrimUI Smart Pro S, TrimUI Brick Pro, Miyoo Flip, Miniloong Pocket 1, Anbernic RG35XX SP, Anbernic RG40XX-class 720x480 |
| 4.4.0 | Miyoo Flip |
| 4.4.3 | MagicX Zero 28, MagicX Zero 40 |
| 4.5.3 | MagicX Zero 28, MagicX Zero 40 |
| 4.5.5 | MagicX XU Mini M |

The XU Mini M run was the thorough one: on 4.5.5 it built 71 themes covering every option value
and all 34 built-in presets, and each generated theme was checked on the device for correct
gradients, icon tones, PyUI config keys and image formats.

## Expected to work, not yet run

TrimUI Brick and Smart Pro, GKD Pixel2, the rest of the Anbernic RG XX family, RGB30, the MagicX
XU20 and the BatleXP G350. The MagicX boards need spruceOS 4.4.2 or a Development build: 4.4.1
has no MagicX support in its menu.

## Not supported

Miyoo A30 and the Mini family: 32-bit, with no LÖVE runtime.

## Device notes

- **RGB30**: a Full spruce update resets the active theme to SPRUCE, because spruce keeps that
  setting inside `App/PyUI`, which the update replaces. Your theme folder is kept — re-select it
  under ***Settings*** > ***Theme***.
- **MagicX (Zero 28, Zero 40, XU20)**: their platform configs export a positional SDL map, so the
  app swaps A/B and X/Y for them. See `spruce/launch.sh`.
- **BatleXP G350**: untested, but it is the same RK3326 SoC, 640x480 panel, dArkMoss base and pad
  codes as the XU Mini M, so it is expected to behave the same.
