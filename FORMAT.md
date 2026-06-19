# Warsong / Langrisser — technical format reference

Confirmed findings from reverse-engineering + in-game testing. Addresses are for
Warsong (USA) unless noted; Langrisser (JP) equivalents are listed where known.

## ROM versions
Both share the SAME decompressor (code identical for 1082 bytes from 0x54AC) and
the same data structures; only table addresses differ.

| Item | Warsong (USA) GM T-24046 | Langrisser (JP) GM T-25103 |
|---|---|---|
| GFX pointer table | 0x3BA00 | 0x3A400 |
| Palette bank (64 palettes) | 0x2AE5A | 0x2A984 |
| Character roster table | 0x2AC8C | 0x2A7B6 |
| Unit name table | 0x2B33A | 0x2B01B |
| Class name table | 0x2B80A | (not yet located) |
| Battle matchup table | 0x23F10 | 0x23A3A |
| Battle-troop sprite table | 0xFD74 | 0xFCEE |
| GFX lookup routine | 0x58E2 (lea $TABLE,a0) — single-point patch for relocation |

## Graphics compression
Custom mask-RLE codec, decompressor dispatch at 0x53B4 (calls 0x54AC direct /
0x55B2 nibble-LUT). Per block: u16 selector (!=1 for gfx), u8 flag (bit7=nibble),
u8 count R, optional 16-byte nibble table, u16 literal pointer, mask bytes, then
literals. Tiles are standard Genesis 4bpp after a bit-transpose. Round-trips are
byte-exact. The tool's encoder uses direct mode R=1 (always valid).

## GFX pointer table
188 entries, 4 bytes each (absolute ROM offset). The lookup routine at 0x58E2 is
`lea $3BA00,a0; ... (table + id*4)` with no bounds check, so the table can be
relocated to expanded ROM by copying it and patching the lea operand at 0x58E4 —
this is how the tool adds new blocks. CONFIRMED working in-game.

## Block ranges (by content)
- Battle-scene sheets (combatant + arena), 100-tile: blocks 4,6,8,10,12,14
- Battle backgrounds, 225-tile: blocks 5,7,9,11,13,15
- Battle backdrops, 64-tile: blocks 16-24
- Map unit sprites, 22-tile and 37-tile: blocks 30-119
  - 30-38: commander/hero map sprites (block 30 = Garett, CONFIRMED)
  - block 104 = soldier (CONFIRMED in-game), 119 = troop elemental
- Portraits, 36-tile (48x48, 6 wide): blocks 128-160

## Character roster table (0x2AC8C) — portrait + palette
77 entries, 6 bytes each: portrait_code(2) + palette_pointer(4, absolute).
- portrait_code = the graphics block id for that character's face.
- palette_pointer points into the palette bank; palette index = (ptr-PAL_BASE)/32.
- The pointer is a full 32-bit address, so it can point at NEW palette data in
  expanded ROM (custom palettes), and the portrait code can point at a NEW block.
- 39 generic-commander entries share block 146 (the generic helmet portrait).
- Unique story characters (Ledin=0/block132, Stone Dragon=65, etc.) have their own.

### How a unit's portrait is chosen (CONFIRMED via savestate + code trace)
Info-panel code at 0xFF5E: `d4 = unit.byte[1]`, then portrait = `roster[d4]`
(loader at 0xBF4C: `lea $2AC8C,a0; d0=d4*6; d1=(a0,d0); jsr $53B4`).
So a unit's portrait is roster entry number `byte[1]` of its unit struct. To give
a specific enemy commander a unique face, edit the roster entry equal to its
byte[1]. Example CONFIRMED: the level-1 "1st Commander Serpent Knight" has
byte[1]=47, so editing roster entry 47 changes its portrait in-game.

## Unit display name tables (parallel to the roster)

A unit's info-panel display is built as:
- **Display name** = `name_table[ byte[1] ]` (the SAME byte[1] that picks the portrait)
- **Class name** = `class_table[ byte[0] ]` (the unit's class field)

Each name-table record is 16 bytes: ASCII text (space-padded) terminated by FF,
max 15 chars usable. So a unit at byte[0]=43, byte[1]=47 displays as
"1st Commander Serpent Knight" because name[47]="1st Commander" and class[43]=
"Serpent Knight". See NAME_TABLE.md for the full mapping including the boss
indices (Geryon=26, Momus=18, Malvese=75, etc.).

The Warsong English names (Garett, Baldarov, Calais, ...) are read from the ROM's
name table directly; the labels in the tool's `_CHAR_NAMES` list (legacy, from
forum data) should not be trusted for in-game names — use `chars` or `names`
which read live from the ROM.

## Battle matchup table (0x23F10)
9 clean entries, 18 bytes each: key(2) + four block words(+2,+4,+6,+8) + two
pointers(+A,+E, animation/frame data). The four blocks are the battle-SCENE
graphics (combatant+arena sheets and backgrounds) in a 3x3 terrain grid — they
are the backdrop/arena, NOT the small troop sprites. Editing them changes the
battle scene visuals.

## Battle-scene troop sprite table (0xFD74 USA / 0xFCEE JP)
91 word entries, each a graphics block id. CONFIRMED by in-game test (TEST7):
this table drives the troop sprites shown during BATTLE SCENES (the rows of
soldiers visible during a fight). The map view and the small VS-icon in the
info bar load their sprites via different code paths (hardcoded block ids).

So:
- To change a unit's MAP sprite -> edit its block in place (e.g. block 104 =
  enemy soldier; editing block 104 directly is the confirmed working route).
- To change a unit's BATTLE-SCENE troop sprite independently -> use `mapdup` on
  the table entry that maps to that block (or edit the block in place if you
  want both contexts to change together).

The map sprite system per-class (what block each unit class uses on the map)
is NOT a single table; it's looked up via per-scenario state and class. Editing
sprite blocks in place is the practical way to change map appearances.

## Palettes
64 stored 16-color palettes at the palette bank (CRAM format: 0000 BBB0 GGG0 RRR0,
3 bits/channel, 8 levels). IMPORTANT: in-game battle palettes are assembled at
runtime (per-faction + terrain), so the live colors often match NO single stored
palette. For true colors when editing units, capture a CRAM dump from an emulator
and use it via the tool's `cram` / `export --cram` features.

## Confirmed-working edits (validated in-game)
- Character portraits including enemy commanders (`newportrait` after indexing fix)
- Editing any sprite block in place (`export`/`import`): block 30 = Garett, 104 = soldier
- ROM/table relocation for adding new blocks and custom palettes
- Per-unit display name changes (`names`): name table at 0x2B33A
- Per-class name changes (`classes`): class table at 0x2B80A
- Battle-scene troop sprite de-dup (`mapdup`): table at 0xFD74
- CRAM dump / screenshot palette extraction for accurate color editing
- Full-stack character makeover (portrait + palette + name + class), demonstrated
  in PROOF_malvese_makeover.bin
