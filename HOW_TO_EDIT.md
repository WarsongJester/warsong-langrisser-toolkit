# Warsong / Langrisser graphics editor — how to use

Requires `warsong_tool.py`, Python 3, and Pillow (`pip install pillow`). Works on
BOTH Warsong (USA) and Langrisser (Japan) — auto-detected. Your original ROM is
never modified; every command that writes always produces a new file.

## Quick start
```
python3 warsong_tool.py list ROM.bin            # see every graphics block
python3 warsong_tool.py chars ROM.bin           # see roster with in-game names
python3 warsong_tool.py export ROM.bin 132 garett.png   # extract block as PNG
#   ...edit garett.png in any pixel editor, keep size + 16 colors...
python3 warsong_tool.py import ROM.bin 132 garett.png out.bin   # write it back
```

## Command reference

### Viewing / exporting
| Command | What it does |
|---|---|
| `list ROM.bin` | List every graphics block (id, tile count, mode). |
| `chars ROM.bin` | Character roster with in-game display name and palette. |
| `names ROM.bin [IDX]` | List or show per-unit display names (Geryon, Malvese, etc.). |
| `classes ROM.bin [ID]` | List or show class names (Fighter, Serpent Knight, etc.). |
| `export ROM.bin BLOCK out.png [PAL]` | Save block as an editable PNG. Auto-detects the true palette for known characters. For live in-game colors use `--cram`. |
| `exportall ROM.bin DIR [--auto]` | Export every block to a folder. |
| `faces ROM.bin DIR [PAL]` | Export just the portrait blocks (132-160). |
| `palettes ROM.bin BLOCK` | Render one block in all 64 stored palettes. |
| `sheetmap ROM.bin` | Battle-scene matchup table (the backdrop/arena blocks). |
| `unitmap ROM.bin` | Battle-troop sprite table (91 entries). |

### Editing / importing
| Command | What it does |
|---|---|
| `import ROM.bin BLOCK in.png out.bin [PAL] [--writepal]` | Replace a block. `--writepal` also writes the PNG's colors into the ROM palette. |
| `newportrait ROM.bin CHAR_ID art.png out.bin` | Give one character a new portrait + custom palette without affecting others sharing the original art. Use the index from `chars`. |
| `names ROM.bin IDX "NewName" out.bin` | Change a unit's in-game display name (e.g. Geryon → Lord Doom). Max 15 ASCII chars. |
| `classes ROM.bin CLS_ID "NewName" out.bin` | Change a class name (e.g. Shaman → Witchking). Max 15 ASCII chars. |
| `setcolor ROM.bin out.bin PAL SLOT #RRGGBB [SLOT COLOR ...]` | Edit palette colors directly. |
| `expandblock ROM.bin BLOCK out.bin` | Duplicate a block to a new slot for independent editing. |
| `mapdup ROM.bin IDX out.bin` | Give one battle-troop table entry its own copy (de-dup battle-scene troops only). |

### Live palettes from emulator
| Command | What it does |
|---|---|
| `cram dump.bin` | Read exact palettes from a CRAM dump (.bin from Exodus/BlastEm). |
| `cram shot.png [L,T,R,B]` | Read palettes from a CRAM debugger screenshot. |
| `export ... --cram=dump.bin:LINE` | Use a CRAM palette line for the export. |

## Editing rules
- Keep the PNG the same pixel size (same tile count).
- Use only the 16 palette colors of that block. Keep PNGs in indexed (P) mode.
- Slot 0 is transparent/background.
- Use the same BLOCK id for export and import.

## Workflow: full custom character
This is the complete workflow used to build PROOF_malvese_makeover.bin:
```
# 1. Find the target
python3 warsong_tool.py chars Warsong.bin           # Malvese = idx 75, block 149

# 2. Export her current portrait (optional, for reference)
python3 warsong_tool.py export Warsong.bin 149 malvese_old.png

# 3. Design a new 48x48 indexed PNG with 16 colors (any pixel editor)
#    or programmatically with Pillow

# 4. Give her the new portrait + custom palette
python3 warsong_tool.py newportrait Warsong.bin 75 new.png step1.bin

# 5. Change her display name
python3 warsong_tool.py names step1.bin 75 "Mal-kor" step2.bin

# 6. Change her class name (class 61 = Shaman)
python3 warsong_tool.py classes step2.bin 61 "Witchking" final.bin
```

## Always test in an emulator
Data edits can be correct while in-game effects differ from expectations (this
happened repeatedly during development). PROOF_malvese_makeover.bin demonstrates
every capability working end-to-end. For your own mods, test each major change.
