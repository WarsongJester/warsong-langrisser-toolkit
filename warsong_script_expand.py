#!/usr/bin/env python3
"""
warsong_script_expand.py — expand Warsong / Langrisser dialog to ANY length.

How the script really works
---------------------------
The game does NOT read its script through one relocatable base pointer. It has
~298 hard-coded absolute pointers across the code, each aimed at a dialog line.
Many lines have NO pointer at all: the engine enters a conversation at a "door"
(a line-start with an incoming pointer) and reads the following lines
sequentially until the next door. So you cannot relocate the whole block, and
you cannot move a single mid-conversation line on its own.

Strategy: VERBATIM RUN RELOCATION
---------------------------------
For each edited line, this tool finds the conversation "run" that contains it
(door -> next door), copies that run's ORIGINAL BYTES VERBATIM into free ROM,
splices ONLY the edited line's bytes (header preserved, new text substituted),
repoints the run's door to the copy, and leaves the original block untouched.

Crucially, unedited lines, separators, and inter-entry padding are copied as
raw bytes — never re-encoded — so the relocated run is byte-identical to the
original except for the edited line. (An earlier version re-encoded the run and
drifted padding by a byte, which desynced speakers; this version cannot.)

Usage
-----
  python3 warsong_script_expand.py list   ROM.bin
  python3 warsong_script_expand.py one    ROM.bin INDEX "New text" OUT.bin
  python3 warsong_script_expand.py expand ROM.bin edited_script.txt OUT.bin

Indices match `warsong_tool.py script export`. Text escapes: \n = paragraph
break, {HH} = raw control byte. Original ROM is never modified.
"""

import sys, struct, importlib.util, os

def _load_wt():
    here = os.path.dirname(os.path.abspath(__file__))
    spec = importlib.util.spec_from_file_location(
        'warsong_tool', os.path.join(here, 'warsong_tool.py'))
    mod = importlib.util.module_from_spec(spec)
    saved = sys.argv; sys.argv = ['warsong_tool']
    try: spec.loader.exec_module(mod)
    finally: sys.argv = saved
    return mod
WT = _load_wt()


def _entry_byte_span(rom, off):
    """For a dialog entry starting at `off` (byte==0x00), return
       (text_start, text_end, header_bytes). text_end is the index of the
       terminating 0xFF. Works for box (00 SPK FF ...) and non-box (00 SPK ...)."""
    assert rom[off] == 0x00
    box = (rom[off + 2] == 0xFF)
    text_start = off + 3 if box else off + 2
    e = text_start
    while rom[e] != 0xFF:
        e += 1
    return text_start, e, bytes(rom[off:text_start])


def _structure(rom, block_start):
    items = WT._parse_script(rom, block_start)
    end = block_start
    for e in items:
        k = e[0]
        if k == 'dialog':
            _, off, spk, box, raw = e
            end = max(end, off + (3 if box else 2) + len(raw) + 1)
        elif k == 'raw':
            end = max(end, e[1] + len(e[2]) + 1)
        elif k == 'sep':
            end = max(end, e[1] + 2)
        elif k == 'ff':
            end = max(end, e[1] + 1)
    return items, end


def _dialog_index_map(items):
    m = {}; idx = 0
    for e in items:
        if e[0] in ('dialog', 'raw'):
            m[idx] = e; idx += 1
    return m


def _pointer_sites(rom, lo, hi):
    sites = {}
    for off in range(0, len(rom) - 4):
        v = (rom[off]<<24)|(rom[off+1]<<16)|(rom[off+2]<<8)|rom[off+3]
        if lo <= v < hi:
            sites.setdefault(v, []).append(off)
    return sites


def _finalize(rom_ba):
    while len(rom_ba) % 0x100:
        rom_ba.append(0xFF)
    struct.pack_into('>I', rom_ba, 0x1A4, len(rom_ba) - 1)
    return bytearray(WT.fix_checksum(bytes(rom_ba)))


def _apply(rom, edits, out_path):
    """edits: {dialog_index: new_text_bytes}."""
    WT._use(rom)
    block_start, _ = WT._find_script_block(rom)
    items, block_end = _structure(rom, block_start)
    dmap = _dialog_index_map(items)
    sites = _pointer_sites(rom, block_start, block_end)
    entry_starts = set(it[1] for it in items if it[0] in ('dialog', 'raw'))
    real_doors = sorted(d for d in sites if d in entry_starts)

    # Resolve edits to offsets
    edited_off = {}
    problems = []
    for index, new_text in edits.items():
        if index not in dmap:
            problems.append((index, 'no such dialog index')); continue
        e = dmap[index]
        if e[0] != 'dialog':
            problems.append((index, 'headerless line — edit it in place instead')); continue
        edited_off[e[1]] = (index, new_text)

    def door_of(off):
        c = [d for d in real_doors if d <= off]
        return max(c) if c else None
    def next_door(d):
        c = [x for x in real_doors if x > d]
        return min(c) if c else block_end

    # Group edited offsets by their run's door
    runs = {}
    for off in edited_off:
        d = door_of(off)
        if d is None:
            problems.append((edited_off[off][0], 'no entry-point pointer reaches this line'))
            continue
        runs.setdefault(d, []).append(off)

    rom_ba = bytearray(rom)
    done = []

    for d in sorted(runs):
        e1 = next_door(d)
        run_bytes = bytearray(rom[d:e1])          # VERBATIM copy of the run

        # Splice edited lines, applying from the LAST offset backwards so earlier
        # splice offsets stay valid as lengths change.
        edited_here = sorted(runs[d], reverse=True)
        per_line = []
        for off in edited_here:
            ts, te, header = _entry_byte_span(rom, off)
            index, new_text = edited_off[off]
            rel_ts = ts - d
            rel_te = te - d
            oldlen = te - ts
            run_bytes[rel_ts:rel_te] = new_text   # header + terminating FF untouched
            per_line.append((index, off, oldlen, len(new_text)))

        base = (len(rom_ba) + 1) & ~1             # word-align
        rom_ba += b'\xFF' * (base - len(rom_ba))
        run_start_in_rom = len(rom_ba)
        rom_ba += run_bytes

        # Repoint ONLY this run's door (a line-start). Mid-string pointers and
        # any other line-start doors keep pointing at the intact original.
        repointed = 0
        for site in sites[d]:
            struct.pack_into('>I', rom_ba, site, run_start_in_rom)
            repointed += 1

        mids = sum(len(locs) for t, locs in sites.items() if d < t < e1)

        for (index, off, oldlen, newlen) in sorted(per_line):
            done.append((index, off, oldlen, newlen, e1 - d, len(run_bytes),
                         repointed, mids, d, run_start_in_rom))

    rom_ba = _finalize(rom_ba)
    open(out_path, 'wb').write(rom_ba)

    print('Verbatim run relocation complete.')
    print('  ROM: %d -> %d bytes   block @0x%06X left intact' % (
        len(rom), len(rom_ba), block_start))
    seen = set()
    for (index, off, oldlen, newlen, runlen, newrun, rep, mids, d, nb) in done:
        flag = ('  [EXPANDED +%d]' % (newlen-oldlen)) if newlen > oldlen else (
               ('  [shortened %d]' % (oldlen-newlen)) if newlen < oldlen else '')
        print('  idx %-3d @0x%06X -> 0x%06X   text %d->%d bytes%s' % (
            index, off, nb + (off - d), oldlen, newlen, flag))
        if d not in seen:
            seen.add(d)
            w = ('  [WARN %d mid-string ref(s) stay on original]' % mids) if mids else ''
            print('     run 0x%06X len %d->%d, door repointed%s' % (d, runlen, newrun, w))
    for (k, why) in problems:
        print('  SKIPPED idx %s: %s' % (k, why))
    print('  Checksum + ROM-end updated. Wrote %s. Test in an emulator.' % out_path)


def cmd_list(rom):
    WT._use(rom)
    bs, _ = WT._find_script_block(rom)
    items, end = _structure(rom, bs)
    sites = _pointer_sites(rom, bs, end)
    dmap = _dialog_index_map(items)
    entry_starts = set(it[1] for it in items if it[0] in ('dialog', 'raw'))
    doors = set(d for d in sites if d in entry_starts)
    print('idx  offset    spk box door  text')
    for idx in sorted(dmap):
        e = dmap[idx]; off = e[1]
        if e[0] == 'dialog':
            spk = '%02X' % e[2]; box = 'Y' if e[3] else 'N'; raw = e[4]
        else:
            spk = '--'; box = '-'; raw = e[2]
        d = 'DOOR' if off in doors else ' .  '
        print('%-4d 0x%06X  %s   %s  %s  %s' % (
            idx, off, spk, box, d,
            WT._encode_text_for_file(raw).replace('\\n', ' | ')[:46]))


def _parse_edited(path, rom):
    WT._use(rom)
    bs, _ = WT._find_script_block(rom)
    items, _ = _structure(rom, bs)
    dmap = _dialog_index_map(items)
    edits = {}
    for line in open(path, encoding='utf-8', errors='replace'):
        line = line.rstrip('\r\n')
        if not line or line.startswith('#'):
            continue
        p = line.split('|', 3)
        if len(p) != 4:
            continue
        try: idx = int(p[0].strip())
        except ValueError: continue
        if idx not in dmap:
            continue
        e = dmap[idx]
        if e[0] != 'dialog':
            continue
        new_text = WT._decode_text_from_file(p[3])
        if new_text != e[4]:
            edits[idx] = new_text
    return edits


# ===========================================================================
#  ADD-BOX  — insert a brand-new dialog box into a scenario's event table
# ===========================================================================
#
#  Game model (reverse-engineered, validated in-game):
#    * Scenario number is in RAM $AEAC.
#    * Pointer array @0x33198 (USA): 20 entries x 4 bytes, indexed by scenario#.
#      Each entry -> that scenario's EVENT TABLE.
#    * Event table = (condition_ptr, action_ptr) pairs, terminated by FFFFFFFF.
#      The engine walks the whole table every frame-ish; for each pair it calls
#      the condition; if it returns D0!=0 it calls the action (which shows a box).
#      => inserting a pair is ADDITIVE; it never removes an existing box.
#    * Action routine (one box):
#         clr.w  $E8D6
#         move.l #textptr,$E8CE
#         move.l #$15456,D0          ; standard box-render callback
#         jsr    $485E               ; queue it
#         rts
#    * Text entry: 00 SPK <text> FF   (2-byte header; 0x0D = newline).
#      SPK 0x00-0x9F = global roster index (name table @0x2B33A).
#    * Fire-once: conditions set a bit in $E8D4 so a box shows only once.
#    * Turn counter = $AEB2 (incremented end-of-turn; "Turn N" = $AEB2).

SCEN_PTR_ARRAY_USA = 0x33198
SCEN_PTR_ARRAY_JP  = 0x32C9E   # best-effort; USA is the tested target
NUM_SCENARIOS = 20
RENDER_CALLBACK = 0x15456
QUEUE_ROUTINE   = 0x485E
TURN_COUNTER    = 0xAEB2       # $FFFFAEB2, accessed as (abs).w 0xAEB2
FLAG_WORD       = 0xE8D4       # $FFFFE8D4 fire-once bits

# name -> roster-slot index. IMPORTANT: the speaker byte is an index into the LIVE
# deployed-unit roster ($FF30DA / $FF517C), not a fixed character ID. A box only renders
# if that roster slot is filled in the current battle. Slot 0x00 is the lead unit
# (Garett), who is present in every scenario -> the reliable default. Other slots depend
# on who is deployed; verify the unit is present in the target scenario or the box will
# silently not appear. The 0xA0+ range is per-scenario story actor slots.
SPEAKER_NAMES = {
    'garett': 0x00, 'lead': 0x00,
    'slot1': 0x01, 'slot2': 0x02, 'slot3': 0x03, 'slot4': 0x04, 'slot5': 0x05,
    'carleon': 0x08,
}


def _scen_array_base(rom):
    # USA only is verified; detect by checking the first pointer looks like a table.
    base = SCEN_PTR_ARRAY_USA
    p = struct.unpack('>I', rom[base:base+4])[0]
    if 0x20000 <= p < 0x40000:
        return base
    raise SystemExit('Could not locate scenario pointer array (is this the USA ROM?)')


def _read_event_table(rom, table_ptr):
    pairs = []; o = table_ptr
    while True:
        c = struct.unpack('>I', rom[o:o+4])[0]
        if c == 0xFFFFFFFF:
            break
        a = struct.unpack('>I', rom[o+4:o+8])[0]
        pairs.append((c, a)); o += 8
    return pairs


def _action_textptr(rom, a):
    chunk = rom[a:a+0x24]
    p = chunk.find(b'\x21\xFC')
    while p >= 0:
        if chunk[p+6:p+8] == b'\xE8\xCE':
            tp = struct.unpack('>I', chunk[p+2:p+6])[0]
            if 0x30000 <= tp < len(rom):
                return tp
        p = chunk.find(b'\x21\xFC', p+1)
    return None


def _used_flag_bits(rom, pairs):
    """Scan a scenario's condition routines for $E8D4 bits already in use."""
    used = set()
    for c, a in pairs:
        if not (0x8000 <= c < 0x40000):
            continue
        chunk = rom[c:c+0x80]
        i = 0
        while i < len(chunk)-3:
            # btst #n,d1 = 0801 000n ; bset #n,d1 = 08C1 000n
            if chunk[i] == 0x08 and chunk[i+1] in (0x01, 0xC1) and chunk[i+2] == 0x00:
                used.add(chunk[i+3]); i += 4; continue
            if chunk[i:i+2] == b'\x4E\x75':
                break
            i += 2
    return used


def _free_flag_bit(rom, pairs):
    used = _used_flag_bits(rom, pairs)
    for b in range(16):
        if b not in used:
            return b
    raise SystemExit('No free $E8D4 flag bit in this scenario (all 16 used).')


def _gen_action(text_ptr):
    return (b'\x42\x78\xE8\xD6'                              # clr.w $E8D6
            + b'\x21\xFC' + struct.pack('>I', text_ptr) + b'\xE8\xCE'  # move.l #txt,$E8CE
            + b'\x20\x3C' + struct.pack('>I', RENDER_CALLBACK)         # move.l #$15456,D0
            + b'\x4E\xB9' + struct.pack('>I', QUEUE_ROUTINE)          # jsr $485E
            + b'\x4E\x75')                                            # rts


def _gen_cond_common(bit, gate_bytes):
    """Build a fire-once condition. gate_bytes is the extra test placed after the
       'already-shown' check; it must `bne` to ret0 when the gate is NOT satisfied
       (or be empty for fire-on-start). We compute branch displacements precisely."""
    movem_in  = b'\x48\xE7\x7F\xFE'
    read_flag = b'\x32\x39\xFF\xFF' + struct.pack('>H', FLAG_WORD)   # move.w $E8D4,d1
    btst      = b'\x08\x01' + struct.pack('>H', bit)                 # btst #bit,d1
    set_show  = (b'\x30\x3C\x00\x01'                                  # move.w #1,d0
                 + b'\x08\xC1' + struct.pack('>H', bit)              # bset #bit,d1
                 + b'\x33\xC1\xFF\xFF' + struct.pack('>H', FLAG_WORD) # move.w d1,$E8D4
                 + b'\x60\x04')                                       # bra +4 -> end
    ret0      = b'\x30\x3C\x00\x00'                                   # move.w #0,d0
    end       = b'\x4C\xDF\x7F\xFE\x4E\x75'                          # movem.l (a7)+,..; rts
    # Layout: movem read_flag btst bne1 [gate] set_show ret0 end
    # bne1 -> ret0.  Each gate test is a cmpi+bne that also -> ret0.
    # Distance from after bne1 to ret0 = len(gate) + len(set_show)
    after_bne1_to_ret0 = len(gate_bytes) + len(set_show)
    bne1 = b'\x66' + bytes([after_bne1_to_ret0])
    return movem_in + read_flag + btst + bne1 + gate_bytes + set_show + ret0 + end


def _gate_turn(N):
    """cmpi.w #N,$AEB2.w ; bne ret0  — but the bne displacement depends on what
       follows (set_show=16, then ret0). After this bne, distance to ret0 = 16."""
    cmpi = b'\x0C\x78' + struct.pack('>H', N) + struct.pack('>H', TURN_COUNTER)
    bne  = b'\x66\x10'   # +0x10 == len(set_show)=16 -> ret0
    return cmpi + bne


def _extract_gate_from_condition(rom, cond_ptr):
    """For 'clone', pull the state-test instructions out of an existing condition,
       i.e. everything between the initial btst/bne block and the 'move.w #1,d0'
       success marker, rewritten so its failure branches go to OUR ret0.
       Returns gate_bytes whose every bne lands `len(set_show)`(16) past its own end,
       i.e. at ret0. We re-emit each cmpi/tst+bcc with corrected short displacements."""
    # Disassemble and capture the comparison/test instructions up to the success store.
    insns = list(_md().disasm(bytes(rom[cond_ptr:cond_ptr+0x80]), cond_ptr))
    # find index of 'move.w #1,d0' (the show marker: 303c 0001)
    show_idx = None
    for k, ins in enumerate(insns):
        if ins.bytes == b'\x30\x3c\x00\x01':
            show_idx = k; break
    if show_idx is None:
        raise SystemExit('clone: could not parse source condition (no success marker).')
    # The gate is the comparison instructions that appear AFTER the initial
    # flag btst/bne and BEFORE the show marker. We keep cmpi/tst and their
    # following conditional branches, but every conditional branch must be made
    # to jump to OUR ret0. Because our ret0 sits immediately after set_show(16),
    # we can recompute: emit the same cmpi/tst bytes, then a bcc with the right
    # displacement. To keep it robust we only support the common shapes:
    #   tst.w (abs).w ; bne X        (4 + 2)
    #   cmpi.w #imm,(abs).w ; beq Y  (6 + 2)  -> invert sense as needed
    # Simpler & safe: re-evaluate the SOURCE semantics by replaying its logic is
    # hard; instead we copy the source's gate VERBATIM and append a tail that maps
    # its internal 'fire' path to set_show and its 'no-fire' path to ret0.
    raise SystemExit('clone mode: see _gen_cond_clone (implemented below).')


def _gen_cond_clone(rom, src_cond_ptr, bit):
    """Clone an existing condition's TRIGGER while giving it a fresh fire-once bit.
       Implementation strategy that avoids fragile re-encoding: we wrap the original
       condition. The new condition:
         1. checks our own fire-once bit; if set -> return 0
         2. otherwise JSR the ORIGINAL condition routine
            - but the original SETS ITS OWN bit and returns 1 only once. To avoid
              consuming the original's single-show, we instead replicate only its
              state test by calling a 'peek' that doesn't set the bit.
       Since the original entangles test+latch, the safe, verified approach is to
       copy the original's bytes and neutralize its latch (its bset/move.w to $E8D4)
       so it becomes a pure predicate, then add our own latch.  We do that here."""
    src = bytearray(rom[src_cond_ptr:src_cond_ptr+0x80])
    insns = list(_md().disasm(bytes(src), src_cond_ptr))
    # Find the original's latch: 'bset #n,d1' (08C1 000n) and the 'move.w d1,$E8D4'
    # and the initial 'btst #n,d1' + its bne. We will:
    #   - remove the initial btst/bne (so it always evaluates the state test)
    #   - turn its bset into nop-equivalent by switching to OUR bit on d1 AND keep
    #     its store, but to OUR flag word (same word) with OUR bit.
    # Because the original already uses 'move.w $E8D4,d1' at top, we keep that, then
    # change the btst bit and bset bit to OUR bit, and keep the rest verbatim. This
    # makes it a faithful clone that fires on the SAME state but latches on OUR bit.
    out = bytearray()
    end_addr = None
    for ins in insns:
        b = bytearray(ins.bytes)
        # retarget btst #n,d1 and bset #n,d1 to our bit
        if len(b) == 4 and b[0] == 0x08 and b[1] in (0x01, 0xC1) and b[2] == 0x00:
            b[3] = bit
        out += b
        if ins.mnemonic == 'rts':
            end_addr = ins.address + 2
            break
    if end_addr is None:
        raise SystemExit('clone: source condition had no rts within range.')
    return bytes(out)


_MD = None
def _md():
    global _MD
    if _MD is None:
        from capstone import Cs, CS_ARCH_M68K, CS_MODE_M68K_000
        _MD = Cs(CS_ARCH_M68K, CS_MODE_M68K_000)
    return _MD


def _validate_routine(code, base_addr):
    """Disassemble; ensure all short branches land on instruction starts and it ends rts."""
    insns = list(_md().disasm(bytes(code), base_addr))
    starts = {i.address for i in insns}
    for i in insns:
        if i.mnemonic in ('bne', 'beq', 'bra', 'bsr') and i.op_str.startswith('$'):
            tgt = int(i.op_str[1:], 16)
            if tgt not in starts:
                return False, 'branch @0x%X -> 0x%X not on instruction boundary' % (i.address, tgt)
    if not insns or insns[-1].mnemonic != 'rts':
        return False, 'routine does not end in rts'
    return True, 'ok'


def cmd_addbox(argv):
    # addbox ROM SCENARIO POSITION SPEAKER "text" OUT [--trigger on-start|on-turn N|clone K]
    rom_path = argv[0]
    scenario = int(argv[1])
    position = argv[2]            # integer index, or 'end'
    speaker  = argv[3]
    text_s   = argv[4]
    out_path = argv[5]
    trigger  = ('on-start',)
    experimental_ok = '--i-understand-experimental' in argv
    if '--trigger' in argv:
        ti = argv.index('--trigger')
        rest = argv[ti+1:]
        if rest and rest[0] == 'on-turn':
            trigger = ('on-turn', int(rest[1]))
        elif rest and rest[0] == 'clone':
            trigger = ('clone', int(rest[1]))
        elif rest and rest[0] == 'on-start':
            trigger = ('on-start',)
        else:
            raise SystemExit('--trigger must be: on-start | on-turn N | clone K')

    if trigger[0] == 'clone' and not experimental_ok:
        raise SystemExit(
            "\n*** 'clone' is EXPERIMENTAL and not yet verified in-game. ***\n"
            "Verified working triggers: on-start, on-turn N.\n"
            "Re-run with --i-understand-experimental to try clone anyway.\n")

    if not (0 <= scenario < NUM_SCENARIOS):
        raise SystemExit('scenario must be 0..%d' % (NUM_SCENARIOS-1))

    # speaker -> index
    if speaker.lower() in SPEAKER_NAMES:
        spk = SPEAKER_NAMES[speaker.lower()]
    else:
        spk = int(speaker, 0)
    if not (0 <= spk <= 0xFF):
        raise SystemExit('speaker index out of range')

    rom = bytearray(open(rom_path, 'rb').read())
    arr = _scen_array_base(rom)
    slot = arr + scenario*4
    table_ptr = struct.unpack('>I', rom[slot:slot+4])[0]
    pairs = _read_event_table(rom, table_ptr)

    # position
    if position == 'end':
        pos = len(pairs)
    else:
        pos = int(position)
        if not (0 <= pos <= len(pairs)):
            raise SystemExit('position must be 0..%d (or "end")' % len(pairs))

    bit = _free_flag_bit(rom, pairs)

    def append(data, align=2):
        while len(rom) % align:
            rom.append(0xFF)
        off = len(rom); rom.extend(data); return off

    # 1) text entry: 00 SPK <text> FF
    text_bytes = WT._decode_text_from_file(text_s)   # handles \n -> 0x0D and {HH}
    entry = bytes([0x00, spk]) + text_bytes + b'\xFF'
    text_ptr = append(entry)

    # 2) action
    action = _gen_action(text_ptr)
    ok, why = _validate_routine(action, len(rom))
    if not ok:
        raise SystemExit('internal: bad action routine: %s' % why)
    action_ptr = append(action)

    # 3) condition
    if trigger[0] == 'on-start':
        cond = _gen_cond_common(bit, b'')                       # fire turn-of-entry, once
    elif trigger[0] == 'on-turn':
        cond = _gen_cond_common(bit, _gate_turn(trigger[1]))    # fire on turn N
    elif trigger[0] == 'clone':
        k = trigger[1]
        if not (0 <= k < len(pairs)):
            raise SystemExit('clone box index must be 0..%d' % (len(pairs)-1))
        src_cond = pairs[k][0]
        cond = _gen_cond_clone(rom, src_cond, bit)
    ok, why = _validate_routine(cond, len(rom))
    if not ok:
        raise SystemExit('internal: bad condition routine: %s' % why)
    cond_ptr = append(cond)

    # 4) rebuild event table with new pair inserted at pos
    new_pairs = pairs[:pos] + [(cond_ptr, action_ptr)] + pairs[pos:]
    newtab = b''.join(struct.pack('>I', c) + struct.pack('>I', a) for c, a in new_pairs)
    newtab += b'\xFF\xFF\xFF\xFF'
    newtab_ptr = append(newtab)

    # 5) repoint scenario slot
    old = struct.unpack('>I', rom[slot:slot+4])[0]
    struct.pack_into('>I', rom, slot, newtab_ptr)

    # finalize
    while len(rom) % 0x100:
        rom.append(0xFF)
    struct.pack_into('>I', rom, 0x1A4, len(rom)-1)
    rom = bytearray(WT.fix_checksum(bytes(rom)))

    # self-check: walk the new table and confirm our box reads back
    chk = _read_event_table(rom, newtab_ptr)
    assert chk[pos] == (cond_ptr, action_ptr), 'table self-check failed'
    tp = _action_textptr(rom, action_ptr)
    assert tp == text_ptr, 'action text pointer self-check failed'

    open(out_path, 'wb').write(rom)

    trg = {'on-start': 'fires turn 1 (once)',
           'on-turn': 'fires on turn %d (once)' % (trigger[1] if trigger[0]=='on-turn' else 0),
           'clone': 'fires when box %d fires (own flag bit)' % (trigger[1] if trigger[0]=='clone' else 0)
           }[trigger[0]]
    print('addbox complete.')
    print('  scenario %d, table @0x%06X -> rebuilt @0x%06X (%d -> %d boxes)' % (
        scenario, table_ptr, newtab_ptr, len(pairs), len(new_pairs)))
    print('  new box at position %d, speaker 0x%02X, trigger: %s, flag bit %d' % (
        pos, spk, trg, bit))
    print('  text @0x%06X, action @0x%06X, condition @0x%06X' % (text_ptr, action_ptr, cond_ptr))
    print('  scenario slot 0x%06X: 0x%06X -> 0x%06X' % (slot, old, newtab_ptr))
    print('  ROM %d bytes, checksum fixed. Wrote %s. Test in an emulator.' % (len(rom), out_path))
    if spk < 0xA0:
        print('  NOTE: speaker 0x%02X is roster slot %d. The box shows the unit deployed in'
              ' that slot,\n        and ONLY appears if that slot is filled this battle.'
              ' Slot 0 (lead/Garett) is\n        always present; other slots depend on who'
              ' is deployed.' % (spk, spk))


def cmd_scenarios(rom):
    """List scenarios with box counts and speakers (quick reference)."""
    arr = _scen_array_base(rom)
    for s in range(NUM_SCENARIOS):
        tp = struct.unpack('>I', rom[arr+s*4:arr+s*4+4])[0]
        pairs = _read_event_table(rom, tp)
        print('scenario %2d: table @0x%06X  %d boxes' % (s, tp, len(pairs)))
        for i, (c, a) in enumerate(pairs):
            txtp = _action_textptr(rom, a)
            if txtp:
                spk = rom[txtp+1]
                ts = txtp+2
                if rom[ts] == 0xFF: ts += 1
                e = ts
                while rom[e] != 0xFF: e += 1
                preview = rom[ts:e].replace(b'\x0d', b' ').decode('latin1', 'replace')[:40]
                print('    box %2d spk=0x%02X  %r' % (i, spk, preview))
            else:
                print('    box %2d (special action)' % i)


# ===========================================================================
#  PROLOGUE PAGING — make a scenario's pre-battle prologue span multiple pages
# ===========================================================================
#
#  Verified in-game. The prologue is a static screen; the game already has a
#  "press to continue" wait at 0x19052 that advances to the battle. We:
#    * install a small engine (once) that hooks that press-wait and the prologue
#      text-draw, driven by a per-scenario PAGE-LIST table;
#    * for a chosen scenario, write its pages as separate FF-terminated strings,
#      build that scenario's page list, and point the table entry at it.
#  A scenario with no page list renders exactly like vanilla. Page index uses
#  RAM $AEFC; a release flag uses $AEF6 (both verified unused by the base game).
#
#  Engine layout addresses are NOT fixed (they sit at the end of the ROM, which
#  grows). To support patching scenarios across multiple runs, the engine writes
#  a signature and a small header so a later run can find the PAGELIST table.

PROL_TABLE   = 0x39EFA      # scenario -> single prologue string (x4), vanilla
PROL_DRAW    = 0x5F60       # text draw: a1=str, d1=col, d2=row, d3,d4,d5
PROL_QUEUE   = 0x485E
PROL_PAGEIDX = 0xFFFFAEFC
PROL_RELFLAG = 0xFFFFAEF6
PROL_NUM_SCEN = 20
PROL_CLEAR_ROWS = 10
PROL_HOOK_DRAW = (0x18E48, 0x18E60)   # prologue text-draw region we replace
PROL_HOOK_WAIT = (0x19052, 0x1906E)   # existing press-to-continue wait we replace
PROL_ORIG_WAIT_ACTION = (0x19070, 0x8AA0)  # (next state, queue id) the wait did
PROL_SIG = b'PGEN'          # engine signature
PROL_SIG_AT = 0x1B0         # header location in ROM (unused area near 0x1A4 footer)


def _lea_abs(addr, areg):
    op = {0: 0x41F9, 1: 0x43F9, 2: 0x45F9}[areg]
    return struct.pack('>H', op) + struct.pack('>I', addr)


def _prologue_engine_present(rom):
    return bytes(rom[PROL_SIG_AT:PROL_SIG_AT + 4]) == PROL_SIG


def _prologue_pagelist_ptr(rom):
    # stored right after the signature
    return struct.unpack('>I', rom[PROL_SIG_AT + 4:PROL_SIG_AT + 8])[0]


def _install_prologue_engine(rom):
    """Append the paging engine + an all-zero PAGELIST. Idempotent: returns the
       PAGELIST pointer; if already installed, returns the existing one."""
    if _prologue_engine_present(rom):
        return _prologue_pagelist_ptr(rom)

    def app(data, align=2):
        while len(rom) % align:
            rom.append(0xFF)
        o = len(rom); rom.extend(data); return o

    # PAGELIST: NUM_SCEN x 4 bytes, all zero (no scenario paged yet)
    PAGELIST = app(b'\x00\x00\x00\x00' * PROL_NUM_SCEN)

    def get_pagelist_a0():               # a0 = PAGELIST[$AEAC]; clobbers d0
        return (b'\x30\x39\xFF\xFF\xAE\xAC' + b'\xE5\x48'
                + b'\x41\xF9' + struct.pack('>I', PAGELIST) + b'\x20\x70\x00\x00')

    # DRAWPAGE: a1=string -> draw at col 3, row 5
    dp = (b'\x32\x3C\x00\x03' + b'\x34\x3C\x00\x05' + b'\x36\x3C\xC0\x00'
          + b'\x38\x3C\x80\x00' + b'\x3A\x3C\x00\x02'
          + b'\x4E\xB9' + struct.pack('>I', PROL_DRAW) + b'\x4E\x75')
    DRAWPAGE = app(dp)

    # CLEARBAND: draw blue spaces over the text band
    CLEARSTR = app((b'\x20' * 34 + b'\x0d') * PROL_CLEAR_ROWS + b'\xff')
    cb = (_lea_abs(CLEARSTR, 1) + b'\x32\x3C\x00\x03' + b'\x34\x3C\x00\x05'
          + b'\x36\x3C\xC0\x00' + b'\x38\x3C\x80\x00' + b'\x3A\x3C\x00\x02'
          + b'\x4E\xB9' + struct.pack('>I', PROL_DRAW) + b'\x4E\x75')
    CLEARBAND = app(cb)

    # STATE_DRAW0: page idx=0, rel flag=0; draw page0 (paged) or original string
    sA = bytearray()
    sA += b'\x33\xFC\x00\x00' + struct.pack('>I', PROL_PAGEIDX)
    sA += b'\x33\xFC\x00\x00' + struct.pack('>I', PROL_RELFLAG)
    sA += get_pagelist_a0()
    sA += b'\xB1\xFC\x00\x00\x00\x00'                       # cmpa.l #0,a0
    bne = len(sA); sA += b'\x66\x00'
    sA += b'\x30\x39\xFF\xFF\xAE\xAC' + b'\xE5\x48'         # unpaged: original string
    sA += b'\x43\xF9' + struct.pack('>I', PROL_TABLE) + b'\x22\x71\x00\x00'
    sA += b'\x4E\xB9' + struct.pack('>I', DRAWPAGE) + b'\x4E\x75'
    paged = len(sA)
    sA += b'\x22\x50'                                       # movea.l (a0),a1 (page0)
    sA += b'\x4E\xB9' + struct.pack('>I', DRAWPAGE) + b'\x4E\x75'
    sA[bne + 1] = (paged - (bne + 2)) & 0xFF
    STATE_DRAW0 = app(bytes(sA))

    # HANDLER for the hooked press-wait
    nxt, qid = PROL_ORIG_WAIT_ACTION
    h = bytearray()
    h += get_pagelist_a0()
    h += b'\xB1\xFC\x00\x00\x00\x00'                        # cmpa.l #0,a0
    beq_orig1 = len(h); h += b'\x67\x00'
    h += b'\x4A\x39\xFF\xFF\x80\x95'                        # tst.b $8095
    bne_press = len(h); h += b'\x66\x00'
    h += b'\x33\xFC\x00\x00' + struct.pack('>I', PROL_RELFLAG)  # no press: relflag=0
    h += b'\x4E\x75'
    pressed = len(h)
    h += b'\x4A\x39' + struct.pack('>I', PROL_RELFLAG)      # tst.b relflag
    bne_held = len(h); h += b'\x66\x00'
    h += b'\x33\xFC\x00\x01' + struct.pack('>I', PROL_RELFLAG)  # relflag=1
    h += b'\x30\x39' + struct.pack('>I', PROL_PAGEIDX) + b'\x52\x40' \
        + b'\x33\xC0' + struct.pack('>I', PROL_PAGEIDX)     # ++pageidx
    h += b'\x30\x39' + struct.pack('>I', PROL_PAGEIDX)
    h += b'\x34\x00' + b'\xE5\x42'                          # d2=d0; lsl.w #2,d2
    h += b'\x22\x70\x20\x00'                                # movea.l (a0,d2.w),a1
    h += b'\xB3\xFC\x00\x00\x00\x00'                        # cmpa.l #0,a1
    beq_orig2 = len(h); h += b'\x67\x00'
    h += b'\x2F\x09'                                        # move.l a1,-(a7)
    h += b'\x4E\xB9' + struct.pack('>I', CLEARBAND)
    h += b'\x22\x5F'                                        # movea.l (a7)+,a1
    h += b'\x4E\xB9' + struct.pack('>I', DRAWPAGE)
    h += b'\x4E\x75'
    held = len(h)
    h += b'\x4E\x75'
    do_original = len(h)
    h += b'\x23\xFC' + struct.pack('>I', nxt) + b'\xFF\xFF\x80\x10'
    h += b'\x20\x3C' + struct.pack('>I', qid)
    h += b'\x4E\xB9' + struct.pack('>I', PROL_QUEUE)
    h += b'\x4E\x75'
    h[beq_orig1 + 1] = (do_original - (beq_orig1 + 2)) & 0xFF
    h[bne_press + 1] = (pressed - (bne_press + 2)) & 0xFF
    h[bne_held + 1] = (held - (bne_held + 2)) & 0xFF
    h[beq_orig2 + 1] = (do_original - (beq_orig2 + 2)) & 0xFF
    HANDLER = app(bytes(h))

    # HOOK 1: prologue text-draw -> jsr STATE_DRAW0
    hk = b'\x4E\xB9' + struct.pack('>I', STATE_DRAW0)
    a, b = PROL_HOOK_DRAW
    rom[a:b] = hk + b'\x4E\x71' * ((b - a - len(hk)) // 2)

    # HOOK 2: press-wait body -> jsr HANDLER; rts
    a, b = PROL_HOOK_WAIT
    nb = b'\x4E\xB9' + struct.pack('>I', HANDLER) + b'\x4E\x75'
    nb += b'\x4E\x71' * ((b - a - len(nb)) // 2)
    rom[a:b] = nb

    # signature + PAGELIST pointer header
    rom[PROL_SIG_AT:PROL_SIG_AT + 4] = PROL_SIG
    struct.pack_into('>I', rom, PROL_SIG_AT + 4, PAGELIST)
    return PAGELIST


def cmd_editprologue(argv):
    # editprologue ROM.bin SCENARIO "page1\fpage2\f..." OUT.bin
    if len(argv) < 4:
        print('usage: editprologue ROM.bin SCENARIO "page1\\fpage2\\f..." OUT.bin')
        print('  \\f = page break, \\n = line break, {HH} = raw control byte')
        return
    rom_path, scen_s, text, out_path = argv[0], argv[1], argv[2], argv[3]
    scenario = int(scen_s)
    if not (0 <= scenario < PROL_NUM_SCEN):
        raise SystemExit('scenario must be 0..%d' % (PROL_NUM_SCEN - 1))

    rom = bytearray(open(rom_path, 'rb').read())
    fresh = not _prologue_engine_present(rom)
    PAGELIST = _install_prologue_engine(rom)

    # split into pages on the page-break marker. Accept literal "\f" (two chars),
    # an actual form-feed char (0x0C), or "{FF}"/"{PAGE}" tokens, so it works
    # regardless of how the shell passed the argument.
    norm = text.replace('\\f', '\x0c').replace('{PAGE}', '\x0c').replace('{FF}', '\x0c')
    page_texts = norm.split('\x0c')
    if len(page_texts) < 2:
        print('Note: only one page given (no \\f). This scenario will render as a single'
              ' page (vanilla behavior).')
    pages = [WT._decode_text_from_file(p) for p in page_texts]

    def app(data, align=2):
        while len(rom) % align:
            rom.append(0xFF)
        o = len(rom); rom.extend(data); return o

    # write page strings + this scenario's page list
    sp = [app(p + b'\xFF') for p in pages]
    arr = b''.join(struct.pack('>I', p) for p in sp) + b'\x00\x00\x00\x00'
    listptr = app(arr)
    struct.pack_into('>I', rom, PAGELIST + scenario * 4, listptr)

    rom = bytearray(_finalize(rom))
    open(out_path, 'wb').write(rom)
    print('editprologue complete.')
    print('  engine: %s' % ('installed (first use)' if fresh else 'already present'))
    print('  scenario %d: %d page(s), list @0x%06X' % (scenario, len(pages), listptr))
    for i, p in enumerate(pages):
        preview = p.replace(b'\x0d', b' ').decode('latin1', 'replace')[:48]
        print('    page %d (%d bytes): %r' % (i, len(p), preview))
    print('  wrote %s. Test in an emulator.' % out_path)


def main():
    a = sys.argv[1:]
    if not a or a[0] in ('-h', '--help', 'help'):
        print(__doc__); return
    if a[0] == 'list':
        cmd_list(bytearray(open(a[1], 'rb').read()))
    elif a[0] == 'one':
        rom = bytearray(open(a[1], 'rb').read())
        _apply(rom, {int(a[2]): WT._decode_text_from_file(a[3])}, a[4])
    elif a[0] == 'expand':
        rom = bytearray(open(a[1], 'rb').read())
        edits = _parse_edited(a[2], rom)
        if not edits:
            print('No changed lines found in %s.' % a[2]); return
        _apply(rom, edits, a[3])
    elif a[0] == 'scenarios':
        cmd_scenarios(bytearray(open(a[1], 'rb').read()))
    elif a[0] == 'addbox':
        cmd_addbox(a[1:])
    elif a[0] == 'editprologue':
        cmd_editprologue(a[1:])
    else:
        print('Unknown command:', a[0]); print(__doc__)

if __name__ == '__main__':
    main()
