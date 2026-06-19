[![Built with Claude](https://img.shields.io/badge/Built%20with-Claude-D97706?style=flat-square&logo=anthropic&logoColor=white)](https://anthropic.com)
# Warsong & Langrisser Comprehensive Modding Toolkit

A complete, end-to-end Python toolset for editing graphics, palettes, names, classes, and advanced dialogue scripts in the Sega Genesis games **Warsong (USA)** and **Langrisser (Japan)**. 

This toolkit combines asset modification with a robust script expansion and injection engine, allowing you to rewrite dialogues, insert new events, and customize multi-page game prologues without crashing the base game engine. All capabilities have been validated in-game via emulator testing.

---

## Repository Structure

### 🛠️ Core Tools
* **`warsong_tool.py`** — The foundational backend utility. Handles script parsing, text encoding, ROM checksum correction, graphics extraction, and table relocation.
* **`warsong_script_expand.py`** — The advanced script editor. Handles dialog block expansion, custom text relocation, dynamic box injection (`addbox`), and prologue engine installation.

### 📄 Reference Documentation
* **`HOW_TO_EDIT.md`** — Comprehensive step-by-step workflow guide and graphics command reference.
* **`FORMAT.md`** — Technical reverse-engineering log covering ROM addresses, data structures, and traced findings.
* **`NAME_TABLE.md`** — Comprehensive documentation of the in-game character name and class name storage systems.
* **`SCENARIO_UNITS.md`** — Roster of per-scenario commander portrait indices (crucial for targeting specific enemy assets).
* **`SCENARIO_EVENT_TABLES.txt`** — Scene-by-scene map of all 20 scenarios, outlining every dialogue box, its active speaker, text previews, and pointers.

---

## Requirements

Ensure you have Python 3 installed along with the required image processing and disassembly validation libraries:

```bash
pip install pillow capstone
```
* **Pillow**: Required for extraction, palette mapping, and importing custom character/sprite graphics blocks.
* **Capstone**: Required by the script injector to self-validate generated M68K assembly code on the fly.

---

## 🎨 Module 1: Graphics, Palettes, & Unit Editing (`warsong_tool.py`)

This suite allows you to modify graphics blocks in-place, alter unit structures, and adjust colors directly from emulator CRAM dumps.

### Core Capabilities
* **In-Place Graphics Editing:** Re-draw character portraits, unit sprites, and map backdrops.
* **Custom Character Palettes:** Assign any character a unique portrait and dedicated color palette using the `newportrait` command.
* **Text Overrides:** Swap text out 1:1 for character display names (`names`) and class assignments (`classes`) within the hardcoded tables.
* **Troop Sprite De-duplication:** Clear up and re-map map-scene troop sprites via `mapdup` (verified in testing).

### Quick Examples
```bash
# View the full command-line help
python3 warsong_tool.py

# List general ROM data blocks
python3 warsong_tool.py list ROM.bin

# Output the character roster matched with their in-game text strings
python3 warsong_tool.py chars ROM.bin

# Assign a custom portrait file to an enemy (e.g., Malvese = index 75)
python3 warsong_tool.py newportrait Warsong.bin 75 my_custom_face.png output_rom.bin

# Rename a character string and change a class title
python3 warsong_tool.py names output_rom.bin 75 "Mal-kor" output_rom.bin
python3 warsong_tool.py classes output_rom.bin 61 "Witchking" output_rom.bin
```

> ⚠️ **Note on Battle Assets:** The `battledup` tool is intended for editing battle-scene backdrops and terrain layouts. To de-duplicate or clean up individual troop sprites on the battlefield, use `mapdup` instead.

---

## 💬 Module 2: Dialogue & Story Script Engine (`warsong_script_expand.py`)

This suite allows you to break past original ROM text limits by installing an engine extension into free ROM space to support custom text lengths and new story events.

### Core Capabilities
* **Dialogue Expansion:** If an edited dialogue block exceeds its original length, the toolkit automatically relocates the entire conversation string into free ROM space and safely updates the event run's entry pointer.
* **Dialogue Box Injection (`addbox`):** Seamlessly append entirely new text boxes to any of the game's 20 scenarios, triggered either at the beginning of turn 1 or on a specific turn sequence.
* **Multi-Page Prologues (`editprologue`):** Injects a lightweight text-paging engine that intercepts the pre-battle intro screen. You can pass extended story texts separated by clear breaks (``), enabling modern, multi-page intro scrolls.

### Quick Examples
```bash
# Export the entire game script to a text file for editing
python3 warsong_tool.py script export Warsong.bin script.txt

# Re-import an edited script (automatically handles pointers and expansions)
python3 warsong_script_expand.py expand Warsong.bin script.txt output_rom.bin

# Update a single dialogue string directly via its script index
python3 warsong_script_expand.py one Warsong.bin 7 "This text is now significantly longer\nthan vanilla spacing allows!" output_rom.bin

# Inject a brand-new dialogue box at the start of Scenario 0 (Turn 1)
python3 warsong_script_expand.py addbox Warsong.bin 0 1 garett "Hold the gate!" output_rom.bin --trigger on-start

# Inject a brand-new box at the end of Scenario 4, triggering on Turn 3
python3 warsong_script_expand.py addbox Warsong.bin 4 end garett "Reinforcements soon!" output_rom.bin --trigger on-turn 3

# Create a two-page pre-battle intro narrative for Scenario 0
python3 warsong_script_expand.py editprologue Warsong.bin 0 "The legendary sword... Castle Baltia.\fLong ago, the hero Baldea sealed the dark god Chaos..." output_rom.bin
```

### Text Formatting & Control Keys
* Use `
` to define a standard paragraph break / newline.
* Use `` (or `{PAGE}` / `{FF}`) to dictate page-clearing breaks within pre-battle prologues.
* Use `{HH}` syntax to inject raw control hexadecimal bytes directly into strings.
* Keep standard dialog text strings constrained to roughly **18–22 characters per line** to ensure clean formatting inside UI text boxes.

---

## 🧠 Technical Architecture & Memory Mapping

The script injection engine tracks flags and text positioning using native game patterns alongside designated unmapped memory states:

### Speaker Allocation Mechanics
When using `addbox`, the speaker byte tracks the **live active deployment roster slots**, not a static character ID:
* `0x00` (`garett` / `lead`): The main commander. Safe default as he is present across all scenarios.
* `0x01` to `0x0F` (`slot1` to `slot5`, etc.): Dynamically mapped to whoever you deployed into those slots for that battle. If a slot is empty, the game will silently skip rendering that dialogue box.
* `0xA0+`: Scenario-specific actor slots (temporary NPCs or enemies).

### Critical Memory Targets (Warsong USA ROM)
* **Scenario Event-Table Pointer Array:** `0x33198` (20 scenarios × 4 bytes, indexed via `$AEAC`)
* **Vanilla Script Text Block:** `0x338D0` – `0x39772`
* **Prologue String Pointer Table:** `0x39EFA`
* **Paging Engine RAM Tracking:** Word registers `$AEFC` and `$AEF6` (verified unused by the base game)
* **Fire-Once Event Bitflags:** RAM address `$E8D4` (tracked dynamically by the toolkit to prevent repeating dialogue)

---

## 🚨 Crucial Guidelines for Modding
1. **Always Match Script Data to Its Source ROM:** Game indices and pointer boundaries are strictly calculated relative to your target file structure. Never import a `script.txt` file into a ROM different from the one it was extracted from, or data misalignment will occur.
2. **Emulate & Test Early:** Data blocks may look completely clean under hex inspection but trigger edge cases due to game engine idiosyncrasies. Always verify your compiled `.bin` outputs inside an emulator before pushing final builds.
