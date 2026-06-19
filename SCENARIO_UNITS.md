# Per-scenario unit roster (verified portrait indices)

A unit's portrait AND display name are both selected by `byte[1]` of its unit
struct. So `portrait = roster[byte[1]]` and `displayed_name = name_table[byte[1]]`.
See `NAME_TABLE.md` for the full mechanism.

To change a specific named enemy's portrait, run
`newportrait ROM.bin INDEX art.png out.bin` where INDEX is the boss's `byte[1]`.

## Confirmed boss indices

| Scenario | In-game name | byte[1] | Portrait block | Verified |
|---|---|---|---|---|
| 1 | "1st Commander Serpent Knight" | **47** | 146 | YES in-game (TEST6) |
| 1 | "Geryon" (LV5 Lord) | **26** | 146 | savestate |
| 3 | "Malvese" | **75** | 149 | savestate |
| 6 | "Geryon" (LV1 Lord) | **26** | 146 | savestate |
| 7 | "Momus" | **18** | 146 | savestate |

## Notes on shared indices

**Geryon (idx 26) is the same character in scenarios 1, 6, and likely elsewhere**
— that's why both savestates show byte[1]=26 with the displayed name "Geryon".
Editing index 26 affects every appearance of Geryon. (My earlier confusion
calling the scenario-1 unit "Zoldo" was from forum-derived labels; the game
actually calls him Geryon.)

## Full scenario rosters

### Scenario 1
**Enemy commanders:**
- byte[1]=1 → "Baldarov" (Volkoff), Sword Master LV9 — likely pre-deployed cutscene unit
- byte[1]=47 → "1st Commander Serpent Knight" LV9 (block 146 generic)
- byte[1]=57 → "High Priest Bishop" LV9 (block 148)
- byte[1]=25 → "Chief Commander Lord" LV2 (block 146 generic)
- byte[1]=26 → "Geryon" Lord LV5 (block 146 generic)

**Player commanders:** Alfador/King Isaac (13), Calais (2), Sabra (4), Tiberon (5).

### Scenario 3 (Malvese)
**Enemy:**
- byte[1]=1 → "Baldarov" (placeholder/cutscene)
- byte[1]=75 → **"Malvese" Shaman LV9** (block 149)
- byte[1]=74 → "Spell User" Shaman LV1 x6 (her followers, also block 149)

**Player:** Thorne (6), Mina/Chris (3).

### Scenario 6 (Geryon)
**Enemy:**
- byte[1]=1 → "Baldarov" (placeholder/cutscene)
- byte[1]=26 → **"Geryon" Lord LV1** (block 146 generic) — same character as sc1
- byte[1]=31, 32 → Knight commanders (LV2)
- byte[1]=19, 20, 17 → Warrior commanders

### Scenario 7 (Momus)
**Enemy:**
- byte[1]=1 → "Baldarov" (placeholder/cutscene)
- byte[1]=18 → **"Momus" Fighter LV9** (block 146 generic)
- byte[1]=15, 21 → Warrior commanders
- byte[1]=30 → Knight commander
- byte[1]=50, 51 → Serpent Knight commanders

**Player:** Bayard/Albert (PIDX 7).

## Editing example
To give Malvese a unique portrait without affecting anything else:
```
python3 warsong_tool.py newportrait Warsong.bin 75 malvese.png out.bin
```
Index 75 is only used by Malvese (and the "Spell User" followers via byte[1]=74
which is a different index entirely), so this is a clean edit.

Geryon (idx 26) appears in multiple scenarios — editing it changes them all,
which is usually what you want for consistency.
