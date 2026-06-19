# Per-unit display name system

A unit's display in the info panel is built from TWO separate tables, both
indexed by values in the unit's struct:

```
display = name_table[ unit.byte[1] ] + " " + class_table[ unit.byte[0] ]
portrait = roster_table[ unit.byte[1] ]
```

So `byte[1]` selects BOTH the portrait AND the display name; `byte[0]` (class)
selects the class string that gets appended.

## The tables

| Table | USA (Warsong) | JP (Langrisser) | Records | Indexed by |
|---|---|---|---|---|
| Roster (portrait + palette) | 0x2AC8C | 0x2A7B6 | 77 entries x 6 bytes | byte[1] |
| Name table (display name) | 0x2B33A | 0x2B01B | 77 entries x 16 bytes | byte[1] |
| Class name table | 0x2B80A | (not yet located) | 16 bytes each | byte[0] |

Each name-table record is 16 bytes: ASCII text (space-padded) terminated by `FF`,
max 15 chars of name.

## Worked example: scenario 1 "1st Commander Serpent Knight"

The enemy commander has unit struct `byte[0]=43, byte[1]=47`:
- `name_table[47]` = "1st Commander"
- `class_table[43]` = "Serpent Knight"
- Display: **"1st Commander Serpent Knight"** ✓ (matches the in-game info panel)
- `roster_table[47]` selects portrait block 146 (the generic helmet face)

## Key boss indices (confirmed by savestate)

| Boss | byte[1] | Name @ idx | Block | Palette |
|---|---|---|---|---|
| Serpent Knight Cmd 1 (sc1) | 47 | "1st Commander" | 146 | 18 |
| Zoldo (sc1) | 26 | "Geryon" | 146 | 15 |
| Geryon (sc6) | 26 | "Geryon" | 146 | 15 |
| Momus (sc7) | 18 | "Momus" | 146 | 11 |
| Malvese (sc3) | 75 | "Malvese" | 149 | 21 |

**Note: the in-game enemy in scenario 1 that we called "Zoldo" is actually
named "Geryon" by the game.** My earlier roster labels were forum-derived
mistranslations. The unit at byte[1]=26 in scenario 1 IS the same character as
in scenario 6 — the display name is genuinely "Geryon" both times. They share
the index because they're the same character.

## Editing names

Change a name with the `names` command:
```
python3 warsong_tool.py names Warsong.bin 26 "Lord Doom" out.bin
```
This changes every appearance of Geryon (and any other unit that uses idx 26)
to "Lord Doom". Names must be <= 15 ASCII characters.

## Why my roster labels were wrong

The labels in `_CHAR_NAMES` (now corrected) were derived from a Chinese forum
that documented the *Japanese* names. The US version (Warsong) renames most
characters. The actual in-game English names live in this name table, and now
I read them from the ROM directly.

| Old (forum) label | Real Warsong name | Index |
|---|---|---|
| Ledin | Garett | 0 |
| Volkoff | Baldarov | 1 |
| Jessica | Calais | 2 |
| Chris | Mina | 3 |
| Nam | Sabra | 4 |
| Thira | Tiberon | 5 |
| Albert | Bayard | 7 |
| Hawking | Carleon | 8 |
| King Isaac | Alfador | 13 |
| Beruvnoi | Momus | 18 |
| Zoldo | Geryon | 26 |
| Kesiro | Malvese | 75 |
