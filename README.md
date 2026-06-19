# Warsong / Langrisser graphics toolkit

A single-file Python tool for editing graphics, palettes, names, and classes in the
Sega Genesis games Warsong (USA) and Langrisser (Japan). Plus reference docs and a
proof ROM demonstrating every editing capability working end-to-end in-game.

## Credits & Acknowledgments
- Developed in collaboration with **Claude 3.5 Sonnet** (Anthropic), which generated the `warsong_tool.py` script, reverse-engineered the file headers, and formatted the technical documentation.

## Files
- **warsong_tool.py** — the tool. Run with no args for full help.
- **HOW_TO_EDIT.md** — usage guide and command reference.
- **FORMAT.md** — technical reference: ROM addresses, data structures, traced findings.
- **NAME_TABLE.md** — the in-game name + class name system (how Geryon, Malvese,
  "Serpent Knight", etc. are stored and selected).
- **SCENARIO_UNITS.md** — per-scenario commander portrait indices, so you can target
  specific named enemies (e.g. Malvese = idx 75).
- **catalog/** — visual reference: every block rendered as a thumbnail.
- **exports_faces/**, **exports_units/** — pre-exported PNGs of all portraits and units.
- **test_roms_archive/** — diagnostic ROMs from earlier investigation steps.

## Requirements
Python 3 and Pillow: `pip install pillow`

## Start here
```
python3 warsong_tool.py            # full help
python3 warsong_tool.py list ROM.bin
python3 warsong_tool.py chars ROM.bin   # roster with in-game names
```
See HOW_TO_EDIT.md for the workflow.

## Confirmed-working capabilities
All validated in-game on real ROMs through emulator testing:
- Edit any graphics block in place (portraits, unit sprites, backgrounds)
- Give a character a unique portrait + custom palette via `newportrait`
- Rename any unit's display name via `names` (e.g. "Geryon" → "Dark Lord")
- Rename any class via `classes` (e.g. "Serpent Knight" → "Sea Dragon")
- De-duplicate battle-scene troop sprites via `mapdup` (TEST7-verified)
- Read live in-game palettes from CRAM dumps for accurate color editing
- ROM auto-expansion + checksum + table relocation, all automatic
- Works identically on Warsong (USA) and Langrisser (Japan)

## What NOT to use
- `battledup` edits battle-scene backdrops/terrain, NOT troop sprites. Use `mapdup`
  for troop sprite de-dup. `battledup` is left in the tool for completeness.

## Quick example — make a custom enemy
```
python3 warsong_tool.py chars Warsong.bin           # find your target (e.g. Malvese = idx 75)
python3 warsong_tool.py newportrait Warsong.bin 75 myface.png out.bin
python3 warsong_tool.py names out.bin 75 "Mal-kor" out.bin
python3 warsong_tool.py classes out.bin 61 "Witchking" out.bin
```
