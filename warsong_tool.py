#!/usr/bin/env python3
"""
warsong_tool.py -- all-in-one graphics editor for Warsong (USA) AND
                   Langrisser (Japan) on the Sega Genesis / Mega Drive.

The tool auto-detects which ROM you give it (from the cartridge header) and uses
the right internal offsets, so the SAME commands work on either version:
   Warsong (USA)      GM T-24046   table @0x3BA00   palettes @0x2AE5A
   Langrisser (Japan) GM T-25103   table @0x3A400   palettes @0x2A984
Both share the identical decompression engine; only the data tables moved.
(A header-independent fallback also recovers the table/palette addresses, so
mildly-modified dumps usually still work.)

You only need THIS file (it has the codec, palette, encoder, and patcher built in)
and Python 3 with Pillow:   pip install pillow

In the examples below, "ROM.bin" means EITHER Warsong.bin OR Langrisser.bin.
------------------------------------------------------------------ COMMANDS
  python3 warsong_tool.py list   ROM.bin
        -> show the detected version and every graphics block (id, mode, tiles).

  python3 warsong_tool.py export ROM.bin 16 tile16.png [PAL]
        -> save block 16 as an editable PNG. Optional PAL = palette number
           (0-63) for true colors; default 0. For units/sprites whose real colors
           aren't a stored palette, use a LIVE palette captured from an emulator:
             export ROM.bin 104 soldier.png --cram=shot.png:LINE[:L,T,R,B]
           where shot.png is a VDP CRAM debugger screenshot, LINE is which palette
           line (0,1,2...), and the optional L,T,R,B box restricts the search.

  python3 warsong_tool.py cram shot.png [L,T,R,B]
        -> extract & print the live palette lines from a VDP CRAM debugger
           screenshot (BlastEm/Gens). Crop to the swatch grid, or pass a box, if
           auto-detection grabs the wrong area. Use the colors with export --cram.

  python3 warsong_tool.py exportall ROM.bin OUTDIR [--auto]
        -> export EVERY graphics block to OUTDIR at once (skips non-graphics
           blocks, writes an index.txt). Default palette 0; add --auto to let
           the tool guess a sensible palette per block.

  python3 warsong_tool.py faces ROM.bin OUTDIR [PAL]
        -> export just the character portraits (blocks 132-160) to OUTDIR.
           Guesses a palette per face unless you pass a fixed PAL number.

  python3 warsong_tool.py palettes ROM.bin 135
        -> render block 135 in all 64 palettes onto one sheet so you can pick
           the right palette number by eye.

  python3 warsong_tool.py import ROM.bin 16 tile16.png ROM_edited.bin [PAL] [--writepal]
        -> read your edited PNG back in, recompress it, write it into a COPY of
           the ROM (auto-expands the ROM, repoints the block, fixes checksum).
           Your original ROM is never modified.
           Add --writepal to ALSO write the PNG's own colors into the ROM palette,
           so you can paint with new colors and have them appear in-game.

  python3 warsong_tool.py chars   ROM.bin
        -> list the character roster: in-game display name (from the name table),
           graphics block, palette. Use this to find which index is which character
           (e.g. Geryon = 26, Malvese = 75).

  python3 warsong_tool.py names ROM.bin [INDEX [NEW_NAME OUT.bin]]
        -> view or set per-unit display names (e.g. change "Geryon" to anything).
           No args: list all 77. With INDEX: show that one. With INDEX NEW_NAME
           OUT.bin: change it. Name must be <= 15 ASCII chars.

  python3 warsong_tool.py classes ROM.bin [CLASS_ID [NEW_NAME OUT.bin]]
        -> view or set class names (e.g. "Shaman" -> "Witchking"). Indexed by the
           unit's class byte (e.g. 43 = Serpent Knight, 61 = Shaman). USA only.

  python3 warsong_tool.py newportrait ROM.bin CHAR_ID newart.png OUT.bin
        -> give one character a BRAND-NEW portrait image + its own palette, without
           changing any character that shared the original art. CHAR_ID is the
           roster number from "chars" (e.g. Stone Dragon = 65). newart.png is an
           indexed PNG the same size as the original portrait. This expands the ROM
           and relocates the graphics pointer table; TEST the result in an emulator.

  python3 warsong_tool.py expandblock ROM.bin BLOCK_ID OUT.bin
        -> duplicate any graphics block into a NEW block slot so you can edit the
           copy independently (de-duplication / expansion). Prints the new block id.
           NOTE: for unit sprites, this makes an editable copy, but pointing a
           specific in-game unit at the copy is not yet automated (the unit->sprite
           mapping is still being mapped). Editing a unit block IN PLACE already
           works via export/import.

  python3 warsong_tool.py sheetmap ROM.bin
        -> show how battle sprites are shared across fight matchups, so you know
           which units an edit will affect. See UNIT_SPRITE_MAP.md for the full
           explanation.

  python3 warsong_tool.py unitmap ROM.bin
        -> show the BATTLE-SCENE TROOP table (91 entries -> sprite blocks). Edits
           via "mapdup" affect troops drawn during BATTLE SCENES, not map sprites.

  python3 warsong_tool.py mapdup ROM.bin INDEX OUT.bin
        -> give one battle-troop entry its own copy of its block, so editing the
           copy changes that troop only in battle scenes. CONFIRMED in-game (TEST7).
           For the small overworld map units, edit the block IN PLACE via
           export/import - that's the path the map view actually reads (e.g.
           block 104 = enemy soldier, 119 = troop elemental, 30 = Garett).

  python3 warsong_tool.py battledup ROM.bin MATCHUP SLOT OUT.bin
        -> give ONE battle matchup (1-9) its own copy of a scene block. NOTE: testing
           showed these blocks are the battle-scene BACKDROP/ARENA graphics (terrain),
           NOT the troop sprites. SLOT is attacker, defender, attacker_bg, defender_bg
           (positions in the matchup record). Use "sheetmap" to view sharing. The copy
           + repoint is correct, but its in-game visual effect is the battle backdrop.

  python3 warsong_tool.py showpal  ROM.bin 12
        -> print palette 12's 16 colors as hex.

  python3 warsong_tool.py setcolor ROM.bin OUT.bin 12 5 #FF8800 [SLOT COLOR ...]
        -> change color slot 5 of palette 12 to orange and save OUT.bin. You can
           list several SLOT COLOR pairs. COLOR is #RRGGBB or r,g,b.
           (Colors snap to the Genesis 3-bit-per-channel hardware levels.)

NOTE ON SHARED PALETTES: there are 64 palettes but ~180 graphics blocks, so a
palette may be used by more than one sprite. Editing a palette changes the colors
of EVERY block that uses it. To see what's affected, edit a palette, load the ROM
in an emulator, and look. Your original ROM is never modified, so this is safe.

------------------------------------------------------------------ EDITING RULES
  * Edit the PNG in any pixel editor (Aseprite, GIMP, Photoshop, Paint.NET...).
  * Keep the image the SAME size (don't add/remove tiles).
  * Use ONLY the 16 colors already in the image's palette. Keep it an indexed
    PNG. (Slot 0 = transparent/background.)
  * Save as PNG.  Use the SAME block id + palette number for export and import.
------------------------------------------------------------------------------
"""
import sys, struct

_LUT      = [0,36,73,109,146,182,219,255]   # Genesis 3-bit channel -> 8-bit

# ---------------------------------------------------------------------------
# ROM version auto-detection.
# Both Warsong (USA) and Langrisser (Japan) share the SAME decompressor engine
# at 0x54AC, but their graphics pointer table and palette bank live at different
# ROM offsets. We detect the version from the cartridge header product code and
# pick the right offsets automatically, so every command works on either ROM.
# The pointer-table address is also self-verified at runtime (lea $XXXXXX in the
# routine at 0x58E2), so unknown revisions still work if that instruction is intact.
# ---------------------------------------------------------------------------
_VERSIONS = {
    'GM T-24046'  : dict(name='Warsong (USA)',        gfx_table=0x3BA00, pal_base=0x2AE5A),
    'GM T-25103'  : dict(name='Langrisser (Japan)',   gfx_table=0x3A400, pal_base=0x2A984),
}

def detect_rom(rom):
    """Return a dict with name, gfx_table, pal_base for this ROM."""
    code = rom[0x180:0x18A].decode('ascii','replace').strip()
    info = None
    for k,v in _VERSIONS.items():
        if rom[0x180:0x180+len(k)] == k.encode():
            info = dict(v); break
    if info is None:
        info = dict(name='Unknown (%s)'%code, gfx_table=None, pal_base=None)
    # Self-verify / recover the gfx table address from the lookup routine at 0x58E2:
    #   41 F9 xx xx xx xx  = lea.l $xxxxxx, a0
    if rom[0x58E2]==0x41 and rom[0x58E3]==0xF9:
        tbl = struct.unpack('>I', rom[0x58E4:0x58E8])[0]
        if 0x10000 <= tbl < len(rom):
            info['gfx_table'] = tbl
    if info['gfx_table'] is None:
        raise SystemExit('Could not locate the graphics table in this ROM. '
                         'It may be a different game or a modified dump.')
    if info['pal_base'] is None:
        info['pal_base'] = _find_palette_bank(rom)
    return info

def _find_palette_bank(rom):
    """Fallback: locate the largest run of valid 16-colour CRAM palettes."""
    def is_color(w): return (w & 0xF111)==0
    def looks(o):
        ws=[struct.unpack('>H',rom[o+i*2:o+i*2+2])[0] for i in range(16)]
        if not all(is_color(w) for w in ws): return False
        nz=[w for w in ws if w!=0]
        return len(nz)>=6 and len(set(ws))>=7
    hits=[]; o=0; N=len(rom)
    while o<N-32:
        if looks(o): hits.append(o); o+=32
        else: o+=2
    if not hits: raise SystemExit('Could not locate palette data in this ROM.')
    # biggest contiguous cluster
    best=(0,hits[0]); start=prev=hits[0]
    for h in hits[1:]:
        if h-prev<=0x20: prev=h
        else:
            if prev-start>best[0]-best[1]: best=(prev,start)
            start=prev=h
    if prev-start>best[0]-best[1]: best=(prev,start)
    return best[1]

# Module-level offsets, set per-ROM by _use(rom). Default to Warsong for back-compat.
GFX_TABLE = 0x3BA00
PAL_BASE  = 0x2AE5A
CHAR_TABLE = 0x2AC8C
ROM_NAME  = 'Warsong (USA)'

# Character roster names, in table order (from community research + ROM verification).
_CHAR_NAMES = ["Garett","Baldarov","Calais","Mina","Sabra","Tiberon","Thorne","Bayard",
"Carleon","Lance","Priest","Soldier","Soldier","Alfador","Efreet",
"1st Commander","2nd Commander","3rd Commander","Momus",
"1st Commander","2nd Commander","3rd Commander","4th Commander",
"Commander","Chief Commander","Chief Commander","Geryon","Emperor Pythion",
"1st Commander","2nd Commander","3rd Commander","4th Commander",
"5th Commander","6th Commander","7th Commander","8th Commander",
"Chief Commander","Lance","The Guards",
"1st Commander","2nd Commander","3rd Commander","4th Commander",
"5th Commander","6th Commander","7th Commander","8th Commander",
"1st Commander","2nd Commander","3rd Commander","4th Commander",
"5th Commander","6th Commander","7th Commander","8th Commander",
"Magician","Spell User","High Priest","Soldier","Soldier","Spell User",
"Naxos","Mortimus","The guards","Ganelon","Monster","Monster","Chaos",
"Monster","Monster","Monster","Monster","Monster","Monster",
"Spell User","Malvese","Stone Monument"]

def _find_char_table(rom):
    """Locate the character table (entries of portrait_code(2) + palette_ptr(4)).
    The table is at a FIXED address per ROM version; we key off the detected version
    so that editing entries (which changes their codes/pointers) can't shift detection.
    Falls back to a content scan only for unknown ROMs, and that scan tolerates already-
    edited leading entries by requiring a long run of valid entries rather than the
    first few."""
    # Known fixed locations by product code.
    code=rom[0x180:0x18A]
    if code[:10]==b'GM T-24046': return 0x2AC8C   # Warsong (USA)
    if code[:10]==b'GM T-25103': return 0x2A7B6   # Langrisser (Japan)
    # Fallback for unknown/modified ROMs: find the offset that maximizes the number of
    # consecutive "original-looking" entries (code 0x80-0xA0, palptr near PAL_BASE).
    best=(0,None)
    for o in range(0x20000, 0x30000, 2):
        run=0
        for i in range(60):
            c=struct.unpack('>H',rom[o+i*6:o+i*6+2])[0]
            pp=struct.unpack('>I',rom[o+i*6+2:o+i*6+6])[0]
            if 0x80<=c<=0xA0 and PAL_BASE-0x100<=pp<=PAL_BASE+0x800: run+=1
            else: break
        if run>best[0]: best=(run,o)
    return best[1]

def _find_name_table(rom):
    """Find the per-unit display name table. 77 records, 16 bytes each, FF-terminated.
    Records hold the in-game story name shown in the unit info panel (e.g. 'Geryon',
    'Malvese'). Indexed by the same byte[1] used for the portrait."""
    code=rom[0x180:0x18A]
    if code[:10]==b'GM T-24046': return 0x2B33A   # Warsong (USA)
    if code[:10]==b'GM T-25103': return 0x2B01B   # Langrisser (Japan)
    # fallback: find longest run of FF every 16 bytes
    best=(0,None)
    for o in range(0x28000,0x2D000,1):
        n=0; p=o
        while p+15<len(rom) and rom[p+15]==0xFF and n<200: n+=1; p+=16
        if n>best[0]: best=(n,o)
    return best[1]

def _find_class_table(rom):
    """Find the class name table (e.g. 'Fighter', 'Serpent Knight'). 16-byte records.
    Indexed by the unit's class byte (byte[0])."""
    code=rom[0x180:0x18A]
    if code[:10]==b'GM T-24046': return 0x2B80A   # Warsong (USA)
    # JP not yet located; return None for unknown
    return None

def read_name(rom, index, table_base=None):
    """Read the display name string for a roster index."""
    if table_base is None: table_base=_find_name_table(rom)
    if table_base is None: return ''
    o=table_base + index*16
    raw=bytes(rom[o:o+16])
    ff=raw.find(0xFF)
    if ff<0: return raw.decode('ascii','replace').rstrip()
    return raw[:ff].decode('ascii','replace').rstrip()

def read_class_name(rom, class_id, table_base=None):
    """Read the class name string for a class id."""
    if table_base is None: table_base=_find_class_table(rom)
    if table_base is None: return ''
    o=table_base + class_id*16
    raw=bytes(rom[o:o+16])
    ff=raw.find(0xFF)
    if ff<0: return raw.decode('ascii','replace').rstrip()
    return raw[:ff].decode('ascii','replace').rstrip()

def char_entries(rom, count=77):
    """Return list of (index, name, block_id, palette_index) from the ROM's char table."""
    out=[]
    if CHAR_TABLE is None: return out
    for i in range(count):
        o=CHAR_TABLE+i*6
        code=struct.unpack('>H',rom[o:o+2])[0]
        pp=struct.unpack('>I',rom[o+2:o+6])[0]
        # Original portrait codes are 0x80..0xA0. Custom blocks added by this tool may
        # be higher. Stop only if the entry looks like neither (i.e. table ended).
        if not (0x80<=code<=0x3FF):
            break
        block=code           # portrait code == graphics block id
        palidx=(pp-PAL_BASE)//32 if pp>=PAL_BASE else -1
        name=_CHAR_NAMES[i] if i<len(_CHAR_NAMES) else '?'
        out.append((i,name,block,palidx))
    return out

def palette_for_block(rom, block_id):
    """Return the game-correct palette for a character's graphics block. Returns:
       - (idx, None) if the palette is a stored-bank index 0..63
       - (None, abs_offset) if it's a custom palette pointer outside the bank
       - None if the block isn't a character portrait."""
    if CHAR_TABLE is None: return None
    for i in range(77):
        o=CHAR_TABLE+i*6
        code=struct.unpack('>H',rom[o:o+2])[0]
        pp=struct.unpack('>I',rom[o+2:o+6])[0]
        if not (0x80<=code<=0x3FF): break
        if code==block_id:
            if PAL_BASE<=pp<PAL_BASE+64*32:
                return ((pp-PAL_BASE)//32, None)
            else:
                return (None, pp)   # custom palette outside the bank
    return None

def resolve_palette(rom, paldata):
    """paldata is either an int (bank index) OR a tuple (idx_or_None, abs_or_None) from
    palette_for_block. Returns 16-color RGB list."""
    if isinstance(paldata, tuple):
        idx, abs_off = paldata
        if abs_off is not None:
            return [cram_to_rgb(struct.unpack('>H',rom[abs_off+c*2:abs_off+c*2+2])[0]) for c in range(16)]
        return read_palette(rom, idx)
    return read_palette(rom, paldata)

def char_entry_offset(char_index):
    """ROM offset of a character table entry (6 bytes each)."""
    return CHAR_TABLE + char_index*6

def set_char_portrait(rom, char_index, block_id):
    """Point a character entry at a different graphics block id (the 'portrait code')."""
    struct.pack_into('>H', rom, char_entry_offset(char_index), block_id)

def set_char_palette_ptr(rom, char_index, abs_addr):
    """Point a character entry's palette at an absolute ROM address (custom palette)."""
    struct.pack_into('>I', rom, char_entry_offset(char_index)+2, abs_addr)

def append_aligned(rom, data, align=0x100):
    """Append data to the ROM tail at an `align`-aligned offset; return that offset.
    rom must be a bytearray. Also updates the header ROM-end field."""
    off=(len(rom)+align-1)&~(align-1)
    rom += b'\xFF'*(off-len(rom))
    rom += data
    while len(rom)%align: rom.append(0xFF)
    struct.pack_into('>I', rom, 0x1A4, len(rom)-1)   # ROM end address in header
    return off

def add_gfx_block(rom, block_bytes):
    """Append a compressed graphics block to the ROM and add a NEW entry to the gfx
    pointer table (relocating the table to expanded space the first time, since the
    original table has data packed right after it). Returns the new block id.
    rom must be a bytearray."""
    global GFX_TABLE
    tab=gfx_table(rom)
    n=len(tab)
    # write the block data to the tail
    blkoff=append_aligned(rom, block_bytes)
    # We need room for one more table entry. The original table can't grow in place,
    # so on first use we copy the whole table to the tail and patch the lookup
    # instruction at 0x58E2 (lea $TABLE,a0) to point at the new location.
    # Detect whether the table already lives in expanded space (>= original ROM end).
    relocated = GFX_TABLE >= 0x80000
    if not relocated:
        # copy existing table + one new entry into expanded space
        newtab=bytearray()
        for v in tab: newtab += struct.pack('>I', v)
        newtab += struct.pack('>I', blkoff)         # the new block's pointer
        newtab += b'\xFF'*16                          # a little slack for future adds
        newoff=append_aligned(rom, bytes(newtab))
        # patch the lookup instruction operand (bytes at 0x58E4..0x58E8)
        struct.pack_into('>I', rom, 0x58E4, newoff)
        GFX_TABLE=newoff
    else:
        # table already relocated: just write the new pointer into the next slot
        struct.pack_into('>I', rom, GFX_TABLE+n*4, blkoff)
    return n  # new block id (index)

def find_matchup_table(rom):
    """Locate the battle matchup table: 9 entries of 18 bytes, keys 1..9. Returns offset or None."""
    for o in range(0x22000, 0x26000, 2):
        keys=[struct.unpack('>H',rom[o+i*18:o+i*18+2])[0] for i in range(9)]
        if keys==list(range(1,10)): return o
    return None

def find_mapsprite_table(rom):
    """Locate the BATTLE-SCENE TROOP sprite table at 0xFD74 (Warsong) / 0xFCEE (JP).
    Despite the historical name "map sprite", in-game testing (TEST7) showed this
    table controls the troop sprites shown in BATTLE SCENES (the rows of soldiers
    drawn during a fight), NOT the small unit sprites on the strategy map. The map
    view and the VS-icon in the info bar load their sprites by hard-coded block id,
    so they're not affected by edits to this table.
    Table is 91 word entries (block ids), starting 0000 001E 001F 0020 0021..."""
    for o in range(0x8000, 0x20000, 2):
        vals=[struct.unpack('>H',rom[o+i*2:o+i*2+2])[0] for i in range(6)]
        if vals==[0,0x1E,0x1F,0x20,0x21,0x22]:
            return o
    return None

def mapsprite_entries(rom, base=None, maxn=91):
    """Return list of (index, block_id) from the battle-troop table at 0xFD74."""
    if base is None: base=find_mapsprite_table(rom)
    if base is None: return []
    tabn=len(gfx_table(rom))
    out=[]
    for i in range(maxn):
        w=struct.unpack('>H',rom[base+i*2:base+i*2+2])[0]
        if w>=tabn: break
        out.append((i,w))
    return out

# matchup entry slot offsets: +2 attacker char, +4 defender char, +6 attacker bg, +8 defender bg
_MATCHUP_SLOTS={'attacker':2,'defender':4,'attacker_bg':6,'defender_bg':8}

def _use(rom):
    """Configure module offsets for the given ROM (call once after loading)."""
    global GFX_TABLE, PAL_BASE, ROM_NAME, CHAR_TABLE
    info = detect_rom(rom)
    GFX_TABLE = info['gfx_table']; PAL_BASE = info['pal_base']; ROM_NAME = info['name']
    CHAR_TABLE = _find_char_table(rom)
    return info

# ----- palette -----
def cram_to_rgb(w):
    r=(w&0x00E)>>1; g=(w&0x0E0)>>5; b=(w&0xE00)>>9
    return (_LUT[r],_LUT[g],_LUT[b])

def read_palette(rom, idx):
    o=PAL_BASE+idx*32
    return [cram_to_rgb(struct.unpack('>H',rom[o+c*2:o+c*2+2])[0]) for c in range(16)]

def rgb_to_cram(r,g,b):
    """8-bit RGB -> Genesis CRAM word (0000 BBB0 GGG0 RRR0), snapping each channel
    to the nearest of the 8 hardware levels in _LUT."""
    def q(v): return min(range(8), key=lambda i: abs(_LUT[i]-v))
    return (q(b)<<9)|(q(g)<<5)|(q(r)<<1)

def write_color(rom, pal_idx, slot, rgb):
    """Write one color (r,g,b 0-255) into palette pal_idx, slot 0-15. rom = bytearray."""
    w=rgb_to_cram(*rgb)
    o=PAL_BASE+pal_idx*32+slot*2
    rom[o]=(w>>8)&0xFF; rom[o+1]=w&0xFF

def write_palette(rom, pal_idx, colors):
    """Write a full 16-color palette (list of (r,g,b)) into palette pal_idx."""
    for s,c in enumerate(colors[:16]):
        write_color(rom, pal_idx, s, c)

def parse_color(s):
    """Accept '#RRGGBB', 'RRGGBB', or 'r,g,b'."""
    s=s.strip()
    if ',' in s:
        parts=[int(x) for x in s.split(',')]
        return tuple(parts[:3])
    s=s.lstrip('#')
    return (int(s[0:2],16), int(s[2:4],16), int(s[4:6],16))

def extract_cram_from_image(path, rows=None, region=None):
    """Read live palette colours from a VDP CRAM debugger screenshot (BlastEm, Gens,
    etc.). Returns a list of palette rows, each a list of 16 (r,g,b) tuples snapped to
    the Genesis 3-bit-per-channel hardware grid.

    A palette swatch panel is a grid of flat, uniform colour cells. We locate it by
    finding rows of the image made up of ~16 long flat-colour runs, group those into
    horizontal bands (one per palette line), and sample each cell centre.

    region = optional (left, top, right, bottom) box (pixels) to restrict the search
    to just the swatch grid. Crop your screenshot to the swatches, or pass region, if
    auto-detection picks the wrong area. rows = expected number of palette lines
    (auto-detected if None)."""
    from PIL import Image
    img=Image.open(path).convert('RGB')
    if region:
        img=img.crop(region)
    px=img.load(); W,H=img.size

    def close(a,b,tol=14): return all(abs(a[i]-b[i])<=tol for i in range(3))

    # For each scanline, count "swatch runs": maximal runs of near-constant colour at
    # least min_run px long. A palette row scanline yields ~16 such runs.
    min_run=max(6, W//40)
    def runs_on(y):
        runs=[]; startx=0; cur=px[0,y]
        for x in range(1,W):
            c=px[x,y]
            if not close(c,cur):
                if x-startx>=min_run: runs.append((startx,x-1,cur))
                startx=x; cur=c
        if W-startx>=min_run: runs.append((startx,W-1,cur))
        return runs
    rowruns=[len(runs_on(y)) for y in range(H)]

    # bands = contiguous y-ranges where rows look like swatch rows (>=8 runs)
    bands=[]; in_b=False; s=0
    for y in range(H):
        if rowruns[y]>=8:
            if not in_b: s=y; in_b=True
        else:
            if in_b and y-s>=4: bands.append((s,y-1))
            in_b=False
    if in_b and H-s>=4: bands.append((s,H-1))
    if not bands:
        raise SystemExit('Could not find palette swatches. Crop the image to just the '
                         'CRAM swatch grid, or pass an explicit region=(l,t,r,b).')

    # If the swatch rows are touching (one big band but several palette lines), split a
    # tall band into equal sub-rows. Decide row count from band height vs cell width.
    def band_extent(b):
        top,bot=b; mid=(top+bot)//2
        rs=runs_on(mid)
        return (rs[0][0], rs[-1][1]) if rs else None
    extents=[(b,band_extent(b)) for b in bands]
    extents=[(b,e) for b,e in extents if e]
    if not extents:
        raise SystemExit('Could not measure swatch extent.')
    from collections import Counter
    Lref=Counter(round(e[0]/10)*10 for _,e in extents).most_common(1)[0][0]
    panel=[(b,e) for b,e in extents if abs(e[0]-Lref)<=max(12,W//30)]
    panel.sort(key=lambda be: be[0][0])
    L=min(e[0] for _,e in panel); R=max(e[1] for _,e in panel)
    cellw=(R-L+1)/16
    # Build the list of palette-line y-centres. If one band is much taller than a cell,
    # it contains multiple touching lines -> split it into rows of ~cellw height.
    line_centres=[]
    for (top,bot),_ in panel:
        h=bot-top+1
        nsub=max(1, round(h/cellw))
        for k in range(nsub):
            line_centres.append(int(top + (k+0.5)*h/nsub))
    if rows: line_centres=line_centres[:rows]
    out=[]
    for cy in line_centres:
        rowcols=[]
        for c in range(16):
            cx=int(L + c*cellw + cellw/2)
            samples=[px[min(W-1,max(0,cx+dx)), min(H-1,max(0,cy+dy))]
                     for dy in (-2,0,2) for dx in (-2,0,2)]
            rgb=tuple(int(sum(s[i] for s in samples)/len(samples)) for i in range(3))
            rgb=cram_to_rgb(rgb_to_cram(*rgb))   # snap to Genesis hardware grid
            rowcols.append(rgb)
        out.append(rowcols)
    return out

def read_cram_dump(path):
    """Read a raw VDP CRAM dump (128 bytes = 64 colour words = 4 palette lines of 16),
    as produced by emulator 'dump CRAM' features (Exodus, BlastEm, etc.). Returns a list
    of 4 palette lines, each 16 (r,g,b) tuples. This is exact (no screenshot sampling)."""
    data=open(path,'rb').read()
    if len(data)<128:
        raise SystemExit('CRAM dump should be at least 128 bytes (got %d).'%len(data))
    out=[]
    for p in range(4):
        row=[]
        for c in range(16):
            w=struct.unpack('>H',data[p*32+c*2:p*32+c*2+2])[0]
            row.append(cram_to_rgb(w))
        out.append(row)
    return out

# ----- gfx pointer table -----
def gfx_table(rom, count=256):
    t=[]
    # Graphics blocks live below the pointer table; accept any offset that points
    # into ROM at/after the palette bank and before the table itself.
    lo = min(PAL_BASE, GFX_TABLE) - 0x200
    for i in range(count):
        o = GFX_TABLE + i*4
        if o+4 > len(rom): break
        v=struct.unpack('>I', rom[o:o+4])[0]
        if not (lo <= v < len(rom)): break
        t.append(v)
    return t

# ----- transpose (decode) and its inverse (encode) -----
def _xpose_direct(buf):
    words=[(buf[i*2]<<8)|buf[i*2+1] for i in range(16)]
    res=bytearray(); a4=0
    for _g in range(4):
        for _w in range(4):
            d3=0
            for _ in range(4):
                for off in (0x18,0x08,0x10,0x00):
                    idx=(a4+off)//2; v=words[idx]; c=(v>>15)&1
                    words[idx]=(v<<1)&0xFFFF; d3=((d3<<1)|c)&0xFFFF
            res+=struct.pack('>H',d3)
        a4+=2
    return res

def _xpose_nibble(buf, nibtab):
    words=[(buf[i*2]<<8)|buf[i*2+1] for i in range(16)]
    res=bytearray(); a4=0
    for _g in range(4):
        for _w in range(4):
            d7=0
            for _ in range(4):
                d3=0
                for off in (0x18,0x08,0x10,0x00):
                    idx=(a4+off)//2; v=words[idx]; c=(v>>15)&1
                    words[idx]=(v<<1)&0xFFFF; d3=((d3<<1)|c)&0xF
                d7=((d7<<4)|nibtab[d3])&0xFFFF
            res+=struct.pack('>H',d7)
        a4+=2
    return res

# build inverse-transpose permutation (source bit -> output bit position)
def _build_inv():
    src=[[(wi,bi) for bi in range(16)] for wi in range(16)]
    out=[]; a4=0
    for _g in range(4):
        for _w in range(4):
            for _ in range(4):
                for off in (0x18,0x08,0x10,0x00):
                    idx=(a4+off)//2; out.append(src[idx].pop(0)); src[idx].append(None)
        a4+=2
    inv={}
    for k,prov in enumerate(out): inv[prov]=k
    return inv
_INV=_build_inv()

def _untranspose(tile32):
    ow=[(tile32[i*2]<<8)|tile32[i*2+1] for i in range(16)]
    def ob(k): w=k//16; b=k%16; return (ow[w]>>(15-b))&1
    src=[0]*16
    for (wi,bi),k in _INV.items(): src[wi]|=ob(k)<<(15-bi)
    r=bytearray()
    for w in src: r+=struct.pack('>H',w)
    return r

# ----- decompress -----
def decompress(rom, off):
    a0=off
    sel=(rom[a0]<<8)|rom[a0+1]; a0+=2
    if sel==1: return None,'tilemap'
    flag=rom[a0]; a0+=1
    nibble=bool(flag&0x80)
    R=rom[a0]; a0+=1
    nibtab=None
    if nibble: nibtab=list(rom[a0:a0+16]); a0+=16
    d5=(rom[a0]<<8); a0+=1; d5|=rom[a0]; a0+=1
    if d5>=0x8000: d5-=0x10000
    a1=a0+d5; a2=a1
    d5v=R
    if d5v!=2: d5v^=5
    loops=d5v-1
    out=bytearray(); guard=0
    while a0<a2 and a0<len(rom) and guard<2_000_000:
        guard+=1
        plane=bytearray(32); a4=0
        for _ in range(loops+1):
            mask=rom[a0] if a0<len(rom) else 0; a0+=1
            for _ in range(8):
                carry=(mask>>7)&1; mask=(mask<<1)&0xFF
                rng=R
                if carry:
                    for _ in range(rng):
                        if a4<32: plane[a4]=rom[a1] if a1<len(rom) else 0
                        a1+=1; a4+=1
                else:
                    for _ in range(rng):
                        if a4<32: plane[a4]=0
                        a4+=1
        out += _xpose_nibble(plane,nibtab) if nibble else _xpose_direct(plane)
    return bytes(out),('nibble' if nibble else 'direct')

# ----- encode (DIRECT mode, R=1; verified byte-exact round-trip) -----
def encode(tiles_4bpp, R=1):
    assert len(tiles_4bpp)%32==0
    groups = 2 if R==2 else (R^5)
    assert groups*8*R==32
    ps=bytearray()
    for t in range(len(tiles_4bpp)//32):
        ps += _untranspose(tiles_4bpp[t*32:t*32+32])
    masks=bytearray(); lits=bytearray(); cur=0; nb=0; i=0
    while i<len(ps):
        run=ps[i:i+R]; i+=R
        bit=0 if all(b==0 for b in run) else 1
        if bit: lits+=run
        cur=(cur<<1)|bit; nb+=1
        if nb==8: masks.append(cur); cur=0; nb=0
    if nb: masks.append((cur<<(8-nb))&0xFF)
    blk=bytearray()
    blk+=struct.pack('>H',0x0002)   # selector (!=1)
    blk.append(0x00)                # DIRECT mode
    blk.append(R)
    blk+=struct.pack('>H',len(masks))
    blk+=masks; blk+=lits
    return bytes(blk)

# ----- PNG <-> 4bpp tiles -----
def grid_cols(n):
    """Tiles-per-row layout for a block of n tiles, so it assembles like in-game.
    Faces (36) are 6 wide; unit sprites (22/37) 11 wide; backgrounds (16/64) 8;
    small icons (9) 3; big maps (225) 16. Anything else falls back to 16 wide.
    The SAME function is used for export and import, so round-trips line up."""
    return {36:6, 22:11, 37:11, 9:3, 16:8, 64:8, 225:16}.get(n, 16)

def tiles_to_png(data, path, pal, cols=16, scale=1):
    from PIL import Image
    n=len(data)//32; rows=(n+cols-1)//cols
    img=Image.new('P',(cols*8,rows*8))
    flat=[]
    for c in pal: flat+=list(c)
    flat+=[0,0,0]*(256-len(pal))
    img.putpalette(flat)
    px=img.load()
    for t in range(n):
        tx=(t%cols)*8; ty=(t//cols)*8
        for r in range(8):
            for h in range(4):
                b=data[t*32+r*4+h]
                px[tx+h*2,ty+r]=b>>4
                px[tx+h*2+1,ty+r]=b&0xF
    if scale>1: img=img.resize((img.width*scale,img.height*scale),Image.NEAREST)
    img.save(path)
    return n

def png_to_tiles(path, pal, ntiles, cols=16):
    from PIL import Image
    img=Image.open(path)
    # Preferred path: the image is still in palette/index mode (mode 'P').
    # Then each pixel value IS the 0-15 color index -- exact, no matching needed.
    if img.mode=='P':
        w,h=img.size
        scale=max(1, w//(cols*8))
        if scale>1: img=img.resize((cols*8, h//scale), Image.NEAREST)
        px=img.load()
        data=bytearray()
        for t in range(ntiles):
            tx=(t%cols)*8; ty=(t//cols)*8
            for r in range(8):
                for hbyte in range(4):
                    hi=px[tx+hbyte*2,   ty+r] & 0xF
                    lo=px[tx+hbyte*2+1, ty+r] & 0xF
                    data.append((hi<<4)|lo)
        return bytes(data)
    # Fallback: RGB image (editor flattened it). Match each pixel to nearest
    # palette slot, but prefer the LOWEST slot index on exact ties so duplicate
    # colors stay deterministic.
    img=img.convert('RGB'); w,h=img.size
    scale=max(1, w//(cols*8))
    if scale>1: img=img.resize((cols*8, h//scale), Image.NEAREST)
    px=img.load()
    def nearest(rgb):
        best=0; bd=1e9
        for i,c in enumerate(pal):
            d=(c[0]-rgb[0])**2+(c[1]-rgb[1])**2+(c[2]-rgb[2])**2
            if d<bd: bd=d; best=i
        return best
    data=bytearray()
    for t in range(ntiles):
        tx=(t%cols)*8; ty=(t//cols)*8
        for r in range(8):
            for hbyte in range(4):
                hi=nearest(px[tx+hbyte*2,   ty+r])
                lo=nearest(px[tx+hbyte*2+1, ty+r])
                data.append((hi<<4)|lo)
    return bytes(data)

def png_to_tiles_with_palette(path, ntiles, cols=16):
    """'Paint freely' import: derive the 16-color palette from the edited PNG itself
    and map pixels to it. Returns (palette_list_of_16_rgb, tile_bytes).
    - Indexed PNG ('P' mode): use its embedded palette and pixel indices directly
      (exact; slot positions preserved, so slot 0 stays the background).
    - RGB PNG: collect up to 16 distinct colors. The color at the top-left pixel is
      forced to slot 0 (background), the rest fill slots 1..15 by frequency.
    If the image has more than 16 colors, the 16 most common are kept and others are
    snapped to the nearest kept color (with a warning)."""
    from PIL import Image
    img=Image.open(path)
    w,h=img.size
    scale=max(1, w//(cols*8))
    if img.mode=='P':
        # embedded palette -> 16 rgb entries; indices are exact
        rawpal=img.getpalette() or []
        pal=[(rawpal[i*3] if i*3<len(rawpal) else 0,
              rawpal[i*3+1] if i*3+1<len(rawpal) else 0,
              rawpal[i*3+2] if i*3+2<len(rawpal) else 0) for i in range(16)]
        if scale>1: img=img.resize((cols*8, h//scale), Image.NEAREST)
        px=img.load()
        data=bytearray()
        for t in range(ntiles):
            tx=(t%cols)*8; ty=(t//cols)*8
            for r in range(8):
                for hbyte in range(4):
                    hi=px[tx+hbyte*2,   ty+r]&0xF
                    lo=px[tx+hbyte*2+1, ty+r]&0xF
                    data.append((hi<<4)|lo)
        return pal, bytes(data)
    # RGB image: build a 16-color palette from the pixels
    img=img.convert('RGB')
    if scale>1: img=img.resize((cols*8, h//scale), Image.NEAREST)
    px=img.load()
    from collections import Counter
    cnt=Counter()
    for y in range(img.height):
        for x in range(img.width):
            cnt[px[x,y]]+=1
    bg=px[0,0]  # top-left -> slot 0 (background/transparent)
    ordered=[bg]+[c for c,_ in cnt.most_common() if c!=bg]
    pal=ordered[:16]
    while len(pal)<16: pal.append((0,0,0))
    idx={c:i for i,c in enumerate(pal)}
    def nearest(rgb):
        if rgb in idx: return idx[rgb]
        best=0; bd=1e9
        for i,c in enumerate(pal):
            d=(c[0]-rgb[0])**2+(c[1]-rgb[1])**2+(c[2]-rgb[2])**2
            if d<bd: bd=d; best=i
        return best
    if len(ordered)>16:
        print('  note: PNG had %d colors; kept the 16 most common, snapped the rest.'%len(ordered))
    data=bytearray()
    for t in range(ntiles):
        tx=(t%cols)*8; ty=(t//cols)*8
        for r in range(8):
            for hbyte in range(4):
                hi=nearest(px[tx+hbyte*2,   ty+r])
                lo=nearest(px[tx+hbyte*2+1, ty+r])
                data.append((hi<<4)|lo)
    return pal, bytes(data)

# ----- checksum -----
def fix_checksum(rom):
    rom=bytearray(rom)
    s=0
    for i in range(0x200,len(rom),2):
        s=(s+((rom[i]<<8)|rom[i+1]))&0xFFFF
    rom[0x18E]=(s>>8)&0xFF; rom[0x18F]=s&0xFF
    return bytes(rom)

# ----- CLI -----
def main():
    if len(sys.argv)<2:
        print(__doc__); return
    cmd=sys.argv[1]

    if cmd=='list':
        rom=open(sys.argv[2],'rb').read(); info=_use(rom); tab=gfx_table(rom)
        print('ROM: %s   (table @0x%X, palettes @0x%X)'%(ROM_NAME,GFX_TABLE,PAL_BASE))
        print(' id   offset   mode      tiles   grid')
        for i,off in enumerate(tab):
            d,m=decompress(rom,off)
            if d is None:
                print('%3d  %06X  %-8s     -'%(i,off,m)); continue
            n=len(d)//32
            print('%3d  %06X  %-8s %5d   %dx%d'%(i,off,m,n,16,(n+15)//16))
        return

    if cmd=='export':
        rom=open(sys.argv[2],'rb').read(); _use(rom)
        gid=int(sys.argv[3]); out=sys.argv[4]
        # Optional: --cram IMG[:LINE[:L,T,R,B]] uses a live palette from a VDP CRAM
        # debugger screenshot instead of a stored ROM palette. LINE picks which of the
        # extracted palette lines (default 0); the optional box restricts the search.
        cram_pal=None; pal_src=None
        args=sys.argv[5:]
        for a in list(args):
            if a.startswith('--cram'):
                spec=a.split('=',1)[1] if '=' in a else (args[args.index(a)+1] if args.index(a)+1<len(args) else '')
                parts=spec.split(':')
                imgpath=parts[0]; line=int(parts[1]) if len(parts)>1 and parts[1] else 0
                if imgpath.lower().endswith('.bin') or imgpath.lower().endswith('.cram'):
                    pals=read_cram_dump(imgpath)
                else:
                    region=None
                    if len(parts)>2 and parts[2]:
                        region=tuple(int(x) for x in parts[2].split(','))
                    pals=extract_cram_from_image(imgpath, region=region)
                if line>=len(pals):
                    print('CRAM image only had %d palette lines.'%len(pals)); return
                cram_pal=pals[line]; pal_src='live CRAM line %d from %s'%(line,imgpath)
        # If the user gives a numeric palette, use it. Else if a CRAM palette was given,
        # use that. Else if it's a known character portrait, use its true palette; else 0.
        numeric=[a for a in args if a.lstrip('-').isdigit()]
        custom_pal=None  # for portraits with palettes outside the stored bank
        if numeric:
            palidx=int(numeric[0]); pal_src='you specified'
        elif cram_pal is not None:
            palidx=None
        else:
            pdata=palette_for_block(rom,gid)
            if pdata is not None:
                idx_part, abs_part = pdata
                if abs_part is not None:
                    custom_pal=[cram_to_rgb(struct.unpack('>H',rom[abs_part+c*2:abs_part+c*2+2])[0]) for c in range(16)]
                    palidx=None; pal_src='auto: this character\'s custom palette @0x%X'%abs_part
                else:
                    palidx=idx_part; pal_src='auto: this character\'s in-game palette'
            else:
                palidx=0; pal_src='default'
        tab=gfx_table(rom); d,m=decompress(rom,tab[gid])
        if d is None: print('Block %d is a %s block (not editable here).'%(gid,m)); return
        if cram_pal is not None: pal=cram_pal
        elif custom_pal is not None: pal=custom_pal
        else: pal=read_palette(rom,palidx)
        n=len(d)//32
        cols=grid_cols(n)
        # Export at native 1x size (no upscaling); layout uses the correct
        # tiles-per-row so the image is assembled the way it appears in-game.
        tiles_to_png(d,out,pal,cols=cols,scale=1)
        pdesc=('palette %d, %s'%(palidx,pal_src)) if palidx is not None else pal_src
        print('Exported block %d (%s, %d tiles, %d wide -> %dx%d px) -> %s  [%s]'
              %(gid,m,n,cols,cols*8,((n+cols-1)//cols)*8,out,pdesc))
        print('Edit it keeping the same size and the same 16 colors, then use "import".')
        return

    if cmd=='import':
        src=sys.argv[2]; gid=int(sys.argv[3]); png=sys.argv[4]; dst=sys.argv[5]
        palidx=int(sys.argv[6]) if (len(sys.argv)>6 and sys.argv[6].lstrip('-').isdigit()) else 0
        writepal = '--writepal' in sys.argv[5:]   # also write the PNG's colors into the ROM palette
        rom=bytearray(open(src,'rb').read())
        _use(bytes(rom))
        tab=gfx_table(rom)
        d,m=decompress(bytes(rom),tab[gid])
        if d is None: print('Block %d is not an editable graphics block.'%gid); return
        ntiles=len(d)//32
        cols=grid_cols(ntiles)
        if writepal:
            # "Paint freely" mode: take the 16 colors straight from the edited PNG,
            # write them into the ROM palette, and map pixels by index position.
            new_pal, tiles = png_to_tiles_with_palette(png, ntiles, cols=cols)
            write_palette(rom, palidx, new_pal)
        else:
            pal=read_palette(bytes(rom),palidx)
            tiles=png_to_tiles(png,pal,ntiles,cols=cols)
        block=encode(tiles,R=1)
        # expand ROM to a 0x100-aligned tail and append the new block
        newoff=(len(rom)+0xFF)&~0xFF
        rom += b'\xFF'*(newoff-len(rom))
        rom += block
        # pad to power-of-two-ish 0x100 boundary
        while len(rom)%0x100: rom.append(0xFF)
        # repoint table entry
        struct.pack_into('>I', rom, GFX_TABLE+gid*4, newoff)
        # update ROM end address in header
        struct.pack_into('>I', rom, 0x1A4, len(rom)-1)
        rom=bytearray(fix_checksum(bytes(rom)))
        open(dst,'wb').write(rom)
        print('Imported %s into block %d.'%(png,gid))
        print('  new block at 0x%X (%d bytes), table repointed, checksum fixed.'%(newoff,len(block)))
        if writepal:
            print('  palette %d updated from the PNG colors (snapped to Genesis 3-bit levels).'%palidx)
        print('  wrote %s  (%d bytes, was %d)'%(dst,len(rom),len(open(src,'rb').read())))
        return

    if cmd=='unitmap':
        # Show the battle-scene troop table: which block each battle-troop entry uses.
        # NOTE: confirmed by TEST7 - this controls BATTLE SCENE troops, not map sprites.
        #   python3 warsong_tool.py unitmap ROM.bin
        rom=open(sys.argv[2],'rb').read(); _use(rom)
        base=find_mapsprite_table(rom)
        if base is None: print('Could not find the battle-troop table.'); return
        ents=mapsprite_entries(rom, base)
        print('ROM: %s   (battle-scene troop table @0x%X, %d entries)'%(ROM_NAME,base,len(ents)))
        print('NOTE: This table drives troop sprites shown during BATTLE SCENES.')
        print('Map view, info-bar icons, and VS-icon load sprites by hardcoded block id.')
        from collections import Counter
        blockcount=Counter(b for _,b in ents)
        print('\n index  block   note')
        for i,b in ents:
            note=''
            if blockcount[b]>1:
                shared=[str(j) for j,bb in ents if bb==b and j!=i]
                note='shares block %d with entry %s'%(b,', '.join(shared))
            print('  %3d    %3d    %s'%(i,b,note))
        print('\nUse "mapdup ROM.bin INDEX OUT.bin" to give one entry its own copy.')
        return

    if cmd=='mapdup':
        # Give ONE battle-troop table entry its own copy of its block, so editing it
        # won't affect other entries sharing it. Confirmed in-game by TEST7.
        #   python3 warsong_tool.py mapdup ROM.bin INDEX OUT.bin
        # (Command name is historical - it actually controls battle-scene troops, not
        # the small overworld map sprites. Edit those in place via export/import.)
        src=sys.argv[2]; index=int(sys.argv[3]); dst=sys.argv[4]
        rom=bytearray(open(src,'rb').read()); _use(bytes(rom))
        base=find_mapsprite_table(bytes(rom))
        if base is None: print('Could not find the battle-troop table.'); return
        ents=dict(mapsprite_entries(bytes(rom), base))
        if index not in ents:
            print('Index %d not in the battle-troop table (valid 0..%d).'%(index,max(ents))); return
        old_block=ents[index]
        tab=gfx_table(rom)
        others=[j for j,b in ents.items() if b==old_block and j!=index]
        d,m=decompress(bytes(rom),tab[old_block])
        if d is None: print('Block %d is not a graphics block.'%old_block); return
        new_block=add_gfx_block(rom, encode(d,R=1))
        struct.pack_into('>H', rom, base+index*2, new_block)
        rom=bytearray(fix_checksum(bytes(rom)))
        open(dst,'wb').write(rom)
        print('Battle-troop entry %d:'%index)
        print('  was block %d -> now its OWN copy, NEW block %d (%d tiles).'%(old_block,new_block,len(d)//32))
        if others:
            print('  original block %d still used by entry/entries: %s (now unaffected).'%(old_block,others))
        print('  edit the copy with:  export %s %d art.png   (then import into block %d)'%(dst,new_block,new_block))
        print('  wrote %s (%d bytes).'%(dst,len(rom)))
        return

    if cmd=='battledup':
        # Give ONE battle matchup its own copy of a sprite block, so editing it won't
        # affect the other matchups that shared the original.
        #   python3 warsong_tool.py battledup ROM.bin MATCHUP SLOT OUT.bin
        # MATCHUP = 1..9 (see "sheetmap"). SLOT = attacker | defender | attacker_bg | defender_bg
        # Copies the block that matchup currently uses for that slot into a NEW block,
        # and repoints just this matchup at the copy. Then edit the new block normally.
        src=sys.argv[2]; matchup=int(sys.argv[3]); slot=sys.argv[4]; dst=sys.argv[5]
        rom=bytearray(open(src,'rb').read()); _use(bytes(rom))
        base=find_matchup_table(bytes(rom))
        if base is None: print('Could not find the battle matchup table.'); return
        if not (1<=matchup<=9): print('MATCHUP must be 1..9.'); return
        if slot not in _MATCHUP_SLOTS:
            print('SLOT must be one of: %s'%', '.join(_MATCHUP_SLOTS)); return
        entry=base+(matchup-1)*18
        field=entry+_MATCHUP_SLOTS[slot]
        old_block=struct.unpack('>H',rom[field:field+2])[0]
        tab=gfx_table(rom)
        if old_block>=len(tab):
            print('Matchup %d slot %s uses block %d which is out of range.'%(matchup,slot,old_block)); return
        # who else uses this block? (warn the user what they're separating from)
        others=[]
        for m in range(9):
            for sname,soff in _MATCHUP_SLOTS.items():
                b=struct.unpack('>H',rom[base+m*18+soff:base+m*18+soff+2])[0]
                if b==old_block and not (m==matchup-1 and sname==slot):
                    others.append((m+1,sname))
        # copy the block
        d,mname=decompress(bytes(rom),tab[old_block])
        if d is None: print('Block %d is not a graphics block.'%old_block); return
        new_block=add_gfx_block(rom, encode(d,R=1))
        struct.pack_into('>H', rom, field, new_block)
        rom=bytearray(fix_checksum(bytes(rom)))
        open(dst,'wb').write(rom)
        print('Matchup %d, slot "%s":'%(matchup,slot))
        print('  was block %d -> now its OWN copy, NEW block %d (%d tiles).'%(old_block,new_block,len(d)//32))
        if others:
            print('  the original block %d is still used by: %s'%(old_block,
                  ', '.join('matchup %d/%s'%(m,s) for m,s in others)))
            print('  those are now UNAFFECTED by edits to the new block.')
        print('  edit the new sprite with:')
        print('     python3 warsong_tool.py export %s %d art.png'%(dst,new_block))
        print('     (then import into block %d of %s)'%(new_block,dst))
        print('  wrote %s (%d bytes).'%(dst,len(rom)))
        return

    if cmd=='sheetmap':
        # Show how battle sprites are shared across matchups (read live from the ROM).
        #   python3 warsong_tool.py sheetmap ROM.bin
        rom=open(sys.argv[2],'rb').read(); _use(rom)
        # battle matchup table: 0x23F10 (USA). Try to locate it: 9 entries of 18 bytes
        # whose keys are 1..9. Scan a window for that signature.
        base=None
        for o in range(0x22000, 0x26000, 2):
            keys=[struct.unpack('>H',rom[o+i*18:o+i*18+2])[0] for i in range(9)]
            if keys==list(range(1,10)): base=o; break
        if base is None:
            print('Could not locate the battle matchup table in this ROM.'); return
        print('ROM: %s   (battle matchup table @0x%X)'%(ROM_NAME,base))
        usage={}
        print('\nmatchup  attacker/defender sprite blocks')
        for i in range(9):
            o=base+i*18
            key=struct.unpack('>H',rom[o:o+2])[0]
            s=[struct.unpack('>H',rom[o+2+k*2:o+4+k*2])[0] for k in range(4)]
            print('   %d      blocks %s'%(key,s))
            for b in s: usage.setdefault(b,[]).append(key)
        print('\nblock  shared by matchups')
        for b in sorted(usage):
            tag=' (SHARED)' if len(usage[b])>1 else ''
            print('  %2d   %s%s'%(b,usage[b],tag))
        print('\nEditing a block changes every matchup listed for it. Use expandblock')
        print('to copy a block first if you want to differentiate one matchup.')
        return

    if cmd=='expandblock':
        # Duplicate an existing graphics block into a NEW block slot, so you can edit
        # the copy independently of the original (de-duplication / expansion).
        #   python3 warsong_tool.py expandblock ROM.bin BLOCK_ID OUT.bin
        # Prints the NEW block id. Nothing that used the original block changes; you
        # then point whatever you want at the new id (or just edit the new id with
        # export/import). Useful for unit sprites that share art.
        src=sys.argv[2]; block_id=int(sys.argv[3]); dst=sys.argv[4]
        rom=bytearray(open(src,'rb').read()); _use(bytes(rom))
        tab=gfx_table(rom)
        if block_id>=len(tab):
            print('No block %d (ROM has %d).'%(block_id,len(tab))); return
        # copy the original block's compressed bytes verbatim (decompress->encode would
        # also work, but verbatim keeps it byte-identical and smaller).
        d,m=decompress(bytes(rom),tab[block_id])
        if d is None:
            print('Block %d is not a graphics block.'%block_id); return
        block_bytes=encode(d, R=1)   # re-encode so it's a self-contained copy
        new_block=add_gfx_block(rom, block_bytes)
        rom=bytearray(fix_checksum(bytes(rom)))
        open(dst,'wb').write(rom)
        print('Duplicated block %d -> NEW block %d (%d tiles).'%(block_id,new_block,len(d)//32))
        print('  Original block %d is unchanged and still used by whatever referenced it.'%block_id)
        print('  Edit the copy with:  export %s %d out.png   (then import into block %d)'%(dst,new_block,new_block))
        print('  wrote %s (%d bytes).'%(dst,len(rom)))
        return

    if cmd=='newportrait':
        # Give a character a BRAND-NEW portrait image (and its own palette), without
        # disturbing any character that shared the original art.
        #   python3 warsong_tool.py newportrait ROM.bin CHAR_ID newart.png OUT.bin
        # CHAR_ID is the roster number from "chars" (e.g. Stone Dragon = 65).
        # newart.png must be an indexed PNG sized like the original portrait
        # (faces: 48x48). The PNG's own 16 colors become the character's new palette.
        src=sys.argv[2]; char_id=int(sys.argv[3]); png=sys.argv[4]; dst=sys.argv[5]
        rom=bytearray(open(src,'rb').read()); _use(bytes(rom))
        ents=char_entries(rom)
        if char_id>=len(ents):
            print('No character %d (roster has %d entries). Use "chars" to list.'%(char_id,len(ents))); return
        _,name,old_block,old_pal=ents[char_id]
        tab=gfx_table(rom)
        # use the old block's tile count to size the new art
        d,_=decompress(bytes(rom),tab[old_block]); ntiles=len(d)//32
        cols=grid_cols(ntiles)
        # read new art + its palette from the PNG
        new_pal, tiles = png_to_tiles_with_palette(png, ntiles, cols=cols)
        if len(tiles)!=ntiles*32:
            print('PNG tile count (%d) does not match the original portrait (%d). '
                  'Keep the same image size.'%(len(tiles)//32,ntiles)); return
        block_bytes=encode(tiles,R=1)
        # 1) add the art as a NEW gfx block (relocates table on first use)
        new_block=add_gfx_block(rom, block_bytes)
        # 2) store the custom palette in the tail and get its address
        palbytes=bytearray()
        for c in new_pal[:16]:
            w=rgb_to_cram(*c); palbytes+=struct.pack('>H',w)
        while len(palbytes)<32: palbytes+=b'\x00\x00'
        paloff=append_aligned(rom, bytes(palbytes), align=2)
        # 3) repoint THIS character's entry: new portrait code + new palette pointer
        set_char_portrait(rom, char_id, new_block)
        set_char_palette_ptr(rom, char_id, paloff)
        rom=bytearray(fix_checksum(bytes(rom)))
        open(dst,'wb').write(rom)
        print('Gave "%s" (char %d) a new portrait:'%(name,char_id))
        print('  was: block %d (shared), palette index %d'%(old_block,old_pal))
        print('  now: NEW block %d @ROM, NEW palette @0x%X'%(new_block,paloff))
        print('  any other character still using old block %d is untouched.'%old_block)
        print('  wrote %s (%d bytes).'%(dst,len(rom)))
        return

    if cmd=='setcolor':
        # Edit a single color in a palette and write a new ROM:
        #   python3 warsong_tool.py setcolor ROM.bin OUT.bin PAL SLOT COLOR
        # PAL = palette 0-63, SLOT = color index 0-15, COLOR = #RRGGBB or r,g,b.
        # You can pass several SLOT COLOR pairs to change multiple colors at once:
        #   setcolor ROM.bin out.bin 12 5 #FF8800 6 #88CCFF
        src=sys.argv[2]; dst=sys.argv[3]; palidx=int(sys.argv[4])
        rom=bytearray(open(src,'rb').read()); _use(bytes(rom))
        before=read_palette(bytes(rom),palidx)
        args=sys.argv[5:]
        changes=[]
        for k in range(0,len(args)-1,2):
            slot=int(args[k]); col=parse_color(args[k+1])
            write_color(rom,palidx,slot,col); changes.append((slot,col))
        rom=bytearray(fix_checksum(bytes(rom)))
        open(dst,'wb').write(rom)
        after=read_palette(bytes(rom),palidx)
        print('Palette %d updated in %s:'%(palidx,dst))
        for slot,col in changes:
            print('  slot %2d: %s -> %s  (stored as Genesis %s)'
                  %(slot, before[slot], after[slot], after[slot]))
        print('Note: colors snap to the Genesis 3-bit-per-channel hardware levels,')
        print('so the stored color may differ slightly from the exact RGB you asked for.')
        return

    if cmd=='cram':
        # Show live palettes from EITHER a raw CRAM dump (.bin, 128 bytes - exact) or a
        # VDP CRAM debugger screenshot (.png - sampled).
        #   python3 warsong_tool.py cram dump.bin
        #   python3 warsong_tool.py cram screenshot.png [L,T,R,B]
        path=sys.argv[2]
        is_bin = path.lower().endswith('.bin') or path.lower().endswith('.cram')
        if is_bin:
            pals=read_cram_dump(path); src_desc='raw CRAM dump (exact)'
        else:
            region=None
            if len(sys.argv)>3 and ',' in sys.argv[3]:
                region=tuple(int(x) for x in sys.argv[3].split(','))
            pals=extract_cram_from_image(path, region=region); src_desc='screenshot (sampled)'
        print('Palette lines from %s [%s]:'%(path,src_desc))
        for i,row in enumerate(pals):
            print('  line %d: %s'%(i, ' '.join('#%02X%02X%02X'%c for c in row)))
        print('\nUse one with export, e.g.:')
        print('   python3 warsong_tool.py export ROM.bin 104 soldier.png --cram=%s:0'%path)
        return

    if cmd=='chars':
        # List the character roster with in-game display names from the name table.
        #   python3 warsong_tool.py chars ROM.bin
        rom=open(sys.argv[2],'rb').read(); _use(rom)
        ents=char_entries(rom)
        if not ents:
            print('No character table found in this ROM.'); return
        name_base=_find_name_table(rom)
        print('ROM: %s   (char table @0x%X, name table @0x%X)'%(
            ROM_NAME,CHAR_TABLE,name_base if name_base else 0))
        print(' #   block  palette  in-game name        roster label')
        seen=set()
        for i,name,block,pi in ents:
            note=''
            if block in seen: note=' (shares art)'
            seen.add(block)
            palshow = '%3d'%pi if 0<=pi<64 else 'custom'
            display = read_name(rom, i, name_base) if name_base else ''
            print('%3d   %3d   %6s    %-19s %s%s'%(i,block,palshow,display[:19],name,note))
        print('\nThe "in-game name" is what appears on screen (e.g. Geryon = idx 26).')
        print('Use that index with newportrait to change a specific unit\'s portrait.')
        return

    if cmd=='names':
        # View OR set the per-unit in-game display names.
        #   python3 warsong_tool.py names ROM.bin                       (list all)
        #   python3 warsong_tool.py names ROM.bin INDEX                 (show one)
        #   python3 warsong_tool.py names ROM.bin INDEX "NewName" out.bin  (set one)
        rom=bytearray(open(sys.argv[2],'rb').read()); _use(bytes(rom))
        base=_find_name_table(bytes(rom))
        if base is None:
            print('No name table located in this ROM.'); return
        if len(sys.argv)==3:
            for i in range(77):
                print('  [%3d] %s'%(i, read_name(bytes(rom),i,base)))
            return
        idx=int(sys.argv[3])
        if len(sys.argv)<5:
            print('idx %d: "%s"'%(idx, read_name(bytes(rom),idx,base))); return
        new=sys.argv[4]; out=sys.argv[5]
        if len(new.encode('ascii','replace'))>15:
            print('Name must be <= 15 ASCII chars.'); return
        o=base+idx*16
        # Build the 16-byte record: name (space padded), then FF, then existing tail
        pad=new.encode('ascii').ljust(15,b' ')[:15] + b'\xff'
        rom[o:o+16]=pad
        # fix checksum
        rom=bytearray(fix_checksum(bytes(rom)))
        open(out,'wb').write(rom)
        print('Set name idx %d to "%s". Wrote %s.'%(idx,new,out))
        return

    if cmd=='classes':
        # View OR set per-class names (e.g. "Shaman", "Serpent Knight"). Indexed by
        # the unit's class byte (byte[0]).
        #   python3 warsong_tool.py classes ROM.bin                           (list all)
        #   python3 warsong_tool.py classes ROM.bin CLASS_ID                  (show one)
        #   python3 warsong_tool.py classes ROM.bin CLASS_ID "NewName" out.bin (set one)
        rom=bytearray(open(sys.argv[2],'rb').read()); _use(bytes(rom))
        base=_find_class_table(bytes(rom))
        if base is None:
            print('Class table not located in this ROM (currently mapped: USA only).'); return
        if len(sys.argv)==3:
            # list classes until we hit clearly-empty entries
            for i in range(80):
                cn=read_class_name(bytes(rom),i,base)
                if not cn: continue
                print('  [%3d] %s'%(i,cn))
            return
        idx=int(sys.argv[3])
        if len(sys.argv)<5:
            print('class %d: "%s"'%(idx, read_class_name(bytes(rom),idx,base))); return
        new=sys.argv[4]; out=sys.argv[5]
        if len(new.encode('ascii','replace'))>15:
            print('Class name must be <= 15 ASCII chars.'); return
        o=base+idx*16
        pad=new.encode('ascii').ljust(15,b' ')[:15] + b'\xff'
        rom[o:o+16]=pad
        rom=bytearray(fix_checksum(bytes(rom)))
        open(out,'wb').write(rom)
        print('Set class %d to "%s". Wrote %s.'%(idx,new,out))
        return

    if cmd=='showpal':
        # Print a palette's 16 colors as hex so you can see what to edit:
        #   python3 warsong_tool.py showpal ROM.bin 12
        rom=open(sys.argv[2],'rb').read(); _use(rom); palidx=int(sys.argv[3])
        pal=read_palette(rom,palidx)
        print('Palette %d (slot: #RRGGBB):'%palidx)
        for i,c in enumerate(pal):
            tag=' (background/transparent)' if i==0 else ''
            print('  %2d: #%02X%02X%02X%s'%(i,c[0],c[1],c[2],tag))
        return

    if cmd=='palettes':
        rom=open(sys.argv[2],'rb').read(); _use(rom); gid=int(sys.argv[3])
        tab=gfx_table(rom); d,m=decompress(rom,tab[gid])
        if d is None: print('Block %d is not graphics.'%gid); return
        from PIL import Image
        n=len(d)//32
        cols={36:6,22:11,37:11,9:3,16:8,64:8}.get(n,16)
        rows=(n+cols-1)//cols
        # render with all 64 palettes into a grid sheet
        scale=2; pad=10
        thumbs=[]
        for p in range(64):
            pal=read_palette(rom,p)
            im=Image.new('RGB',(cols*8,rows*8)); px=im.load()
            for t in range(n):
                tx=(t%cols)*8; ty=(t//cols)*8
                for r in range(8):
                    for h in range(4):
                        b=d[t*32+r*4+h]; px[tx+h*2,ty+r]=pal[b>>4]; px[tx+h*2+1,ty+r]=pal[b&0xF]
            thumbs.append(im.resize((im.width*scale,im.height*scale),Image.NEAREST))
        tw=thumbs[0].width+pad; th=thumbs[0].height+16
        perrow=8
        sheet=Image.new('RGB',(perrow*tw, ((64+perrow-1)//perrow)*th),(28,28,36))
        from PIL import ImageDraw
        dr=ImageDraw.Draw(sheet)
        for p,im in enumerate(thumbs):
            cx=(p%perrow)*tw; cy=(p//perrow)*th
            dr.text((cx+2,cy),'pal %d'%p,fill=(200,220,255))
            sheet.paste(im,(cx,cy+12))
        out='block%d_palettes.png'%gid
        sheet.save(out)
        print('Saved %s — open it, find the palette number that looks right, and use that number with export/import.'%out)
        return

    if cmd=='faces':
        # Export just the character portraits (blocks 132-160) in one go.
        #   python3 warsong_tool.py faces ROM.bin OUTDIR [PAL]
        # Faces are 6 tiles wide (48x48). With no PAL given, the tool guesses a
        # palette per face; pass a number (e.g. 12) to force one palette for all.
        # Use the "palettes" command to find the right number for a specific face.
        import os
        rom=open(sys.argv[2],'rb').read(); _use(rom)
        outdir=sys.argv[3] if len(sys.argv)>3 else 'faces'
        forced=None
        for a in sys.argv[4:]:
            if a.isdigit(): forced=int(a)
        os.makedirs(outdir, exist_ok=True)
        tab=gfx_table(rom)
        FACE_RANGE=range(132,161)   # 132..160 are the portraits; 128-131 are text/UI
        done=0; index=[]
        for i in FACE_RANGE:
            if i>=len(tab): break
            try:
                d,m=decompress(rom,tab[i])
            except Exception:
                index.append((i,None,'error',0)); continue
            if d is None or len(d)==0:
                index.append((i,None,'not a face',0)); continue
            n=len(d)//32
            # Use the character's true in-game palette from the char table; fall
            # back to a guess only if this block isn't in the table.
            if forced is not None:
                pal=read_palette(rom,forced); p=forced
            else:
                tp=palette_for_block(rom,i)
                if tp is not None:
                    idx_part, abs_part = tp
                    if abs_part is not None:
                        pal=[cram_to_rgb(struct.unpack('>H',rom[abs_part+c*2:abs_part+c*2+2])[0]) for c in range(16)]
                        p='custom'
                    else:
                        pal=read_palette(rom,idx_part); p=idx_part
                else:
                    p=best_palette(rom,d); pal=read_palette(rom,p)
            fn=os.path.join(outdir,'face%03d_pal%s.png'%(i,p if p!='custom' else 'XX'))
            # faces are 6 tiles wide; export at native 48x48 (1x)
            tiles_to_png(d, fn, pal, cols=6, scale=1)
            done+=1; index.append((i,p,m,n))
        with open(os.path.join(outdir,'index.txt'),'w') as fh:
            fh.write('ROM: %s  --  character portraits (blocks 132-160)\n\n'%ROM_NAME)
            fh.write(' id  palette  tiles  file\n')
            for i,p,m,n in index:
                if p is None: fh.write('%3d    -        -    (%s)\n'%(i,m))
                else: fh.write('%3d   %2d      %5d   face%03d_pal%02d.png\n'%(i,p,n,i,p))
        print('Exported %d portraits to %s/'%(done,outdir))
        print('See %s/index.txt for the list.'%outdir)
        if forced is None:
            print('Colors are a per-face guess. If one looks wrong, run:')
            print('   python3 warsong_tool.py palettes ROM.bin <id>')
            print('to find its right palette, then: faces ROM.bin %s <thatnumber>'%outdir)
        return

    if cmd=='exportall':
        # Export EVERY graphics block to a folder, in one go.
        #   python3 warsong_tool.py exportall ROM.bin OUTDIR [--auto]
        # By default uses palette 0 for all blocks. Add --auto to let the tool
        # guess a sensible palette per block (better colors, but only a guess --
        # use the "palettes" command to fine-tune any that look wrong).
        import os
        rom=open(sys.argv[2],'rb').read(); _use(rom)
        outdir=sys.argv[3] if len(sys.argv)>3 else 'export_all'
        auto='--auto' in sys.argv[3:]
        os.makedirs(outdir, exist_ok=True)
        tab=gfx_table(rom)
        done=skipped=0
        index=[]
        for i,off in enumerate(tab):
            try:
                d,m=decompress(rom,off)
            except Exception:
                skipped+=1; index.append((i,None,'error',0)); continue
            if d is None or len(d)==0:
                skipped+=1; index.append((i,None,m if d is None else 'empty',0)); continue
            n=len(d)//32
            cols={36:6,22:11,37:11,9:3,16:8,64:8}.get(n,16)
            p=best_palette(rom,d) if auto else 0
            fn=os.path.join(outdir,'blk%03d_pal%02d.png'%(i,p))
            tiles_to_png(d, fn, read_palette(rom,p), cols=cols, scale=1)
            done+=1; index.append((i,p,m,n))
        # write a plain-text index alongside the images
        with open(os.path.join(outdir,'index.txt'),'w') as fh:
            fh.write('ROM: %s\n\n id  palette  mode      tiles  file\n'%ROM_NAME)
            for i,p,m,n in index:
                if p is None: fh.write('%3d    -      %-8s    -    (tilemap, skipped)\n'%(i,m))
                else: fh.write('%3d   %2d      %-8s %5d   blk%03d_pal%02d.png\n'%(i,p,m,n,i,p))
        print('Exported %d blocks to %s/  (%d non-graphics blocks skipped).'%(done,outdir,skipped))
        print('See %s/index.txt for the full list.'%outdir)
        if not auto:
            print('Tip: colors use palette 0. Re-run with --auto for guessed colors,')
            print('     or use "palettes ROM.bin <id>" to find the right palette for a block.')
        return

    print(__doc__)

# ============================================================================
# Catalog / palette helpers (added for bulk editing workflows)
# ============================================================================
def _to3(rgb): return tuple(min(7,round(v/36.43)) for v in rgb)

def best_palette(rom, d, ref3=None):
    """Guess the best display palette (0-63) for a decoded block.
    ref3 = optional set of 3-bit color tuples from reference art to match against.
    NOTE: this is a heuristic for DISPLAY only; it never affects edit accuracy."""
    used=set()
    for b in d: used.add(b>>4); used.add(b&0xF)
    best=(-1,0)
    for p in range(64):
        pal=read_palette(rom,p)
        cols={_to3(pal[i]) for i in used}
        if ref3 is not None:
            score=len(cols & ref3)*100 + len(cols)
        else:
            bright=sum(sum(c) for c in cols)/max(1,len(cols))
            score=len(cols)*100+min(bright,400)
        if score>best[0]: best=(score,p)
    return best[1]

if __name__=='__main__':
    main()
