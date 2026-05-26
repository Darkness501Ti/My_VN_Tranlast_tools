# Ail Soft engine reverse engineering — kouhouDL.exe

## Game identity

- VNDB v378 — *Kouhou Yome* / "肛奉嫁" (Ail / ail-soft.com, 2009)
- Engine: Ail proprietary, Windows 2000/XP/Vista era, no installer dependencies
- Files of interest in game directory:
  - `kouhouDL.exe` — main game (target for runtime testing)
  - `mchecker.exe` — music checker (irrelevant)
  - `uninst.exe` — uninstaller (irrelevant)
  - `sall.snl` — **script archive** (translation target)
  - `Gall0..3.dat` — graphics (CGs, sprites)
  - `Pall0..2.dat` — picture/face graphics
  - `vall00..08.dat` — voice
  - `THelp.dat` — help system images
  - `m01..m10.wav` — BGM (PCM WAV, untouched)

## Archive format (`.dat` / `.snl`) — `DatOpener` in GARbro

Ground truth: https://github.com/morkt/GARbro/blob/master/ArcFormats/Ail/ArcAil.cs

```
struct AilArchive {
    u32 count;
    u32 size[count];      // 0 or 0xFFFFFFFF = empty slot
    u8  data[];           // entries concatenated in slot order
};
```

Per-entry layout (6-byte prefix):
```
u16  packed_marker    // == 0x0001 iff LZSS-compressed
u32  unpacked_size    // valid iff packed_marker == 1
u8   payload[];       // either raw, or LZSS stream
```

Decoding rules:
- Read u32 signature at entry start.
- If `(signature & 0xFFFF) == 1`: **LZSS-packed**. `unpacked_size = u32 at offset+2`. Payload at offset+6, length = entry.size − 6.
- Else if `signature == 0` OR `bytes[offset+4..offset+8] == "OggS"`: **raw, extra prefix = 4 bytes**.
- Else: **raw, extra prefix = 6 bytes**.

## LZSS variant (Ail custom)

- 4 KB sliding dictionary (`frame[0x1000]`).
- Frame pre-initialized to 0x20 (space).
- `frame_pos` starts at 0xFEE.
- **Control bit semantics are reversed from classic LZSS** — bit=0 means literal, bit=1 means back-reference (GARbro comment).
- Back-ref format: `[off_lo:u8] [b2:u8]` → `offset = off_lo | ((b2 & 0xF0)<<4)`, `count = (b2 & 0x0F) + 3` (so length range 3..18).

Verified round-trip: see `ail_lzss.py` `lzss_unpack` (port of GARbro's `LzssUnpack`) and matching encoder `lzss_pack`.

## Script entry layout (sall.snl decompressed)

- 167 entries total (151 non-empty in kouhouDL).
- Each entry corresponds to one scene/screen (menus, scenes, system text).
- Decompressed payload structure:
  ```
  [header: 16 bytes — starts with 00 00 00 00, then field-specific]
  [bytecode region: opcodes + jump tables]
  [strings region: SJIS strings, each null-terminated, packed end-to-end]
  ```

### Strings region

- Strings are stored as **null-terminated Shift-JIS**.
- Inter-string separator is almost always `00 00` (one alignment-pad null + one terminator).
- Strings are clustered contiguously starting at a region-start offset that varies per entry (e.g. entry 0 → 0x02DE, entry 50 → 0x0DD0).

### Bytecode → string references

- Most strings appear to be consumed **sequentially** by the engine — no explicit offset reference needed.
- A minority of strings (jump targets, branches, repeated UI strings) are referenced as **u16 LE** in the bytecode region pointing to the string start offset.
- Observed reference rate: entry 50 = 5/189 strings, entry 100 = 4/51 strings.

## Translation strategy

### Mode A — in-place equal-byte-length replacement (initial)

Replace each SJIS string with English of the **same byte length**. Pad with `0x20` (space) if English is shorter; truncate if longer. This preserves all offsets, requires zero bytecode patching.

Trade-off: English translations often exceed the byte budget (esp. since 1 SJIS char = 2 bytes, but ASCII = 1 byte, so usually we have ~2× headroom for half-width Latin). Long dialogue may need abbreviation.

### Mode B — resize-and-rewrite (future, if A produces readable but cramped text)

Append translated strings AT THE END of the strings region. Update all u16 bytecode refs to point to new offsets. For sequentially-consumed strings, just keep them in original order with new lengths.

Will require: full opcode parser that identifies every string-reference site. Currently only u16-LE absolute refs detected; jump-relative refs would need decoding the opcode stream.

### Encoding choice — half-width ASCII vs full-width Latin

Game uses **full-width** Latin (e.g. `Ｗｉｎｄｏｗｓ` = 5 SJIS chars = 10 bytes) for English words in JP UI text. Engine **probably** also accepts half-width ASCII (single byte per char), since SJIS includes ASCII range natively (0x00..0x7E identity-maps). We start with half-width to maximize byte budget — falls back to full-width if game renders garbled.

## Implementation files

- `ail_lzss.py` — LZSS codec, archive reader/writer
- `analyze_dat.py` — archive format hypothesis tester (confirmed simple format)
- `analyze_snl.py` — initial SJIS scanner (now legacy)
- `analyze_decompressed.py` — string structure analyzer
- `find_string_refs.py` — u16 offset reference detector

## Verified facts

- ✅ Archive format identical to GARbro `Ail/DatOpener`
- ✅ LZSS algorithm matches `LzssUnpack` byte-for-byte (decompresses entries 0..166)
- ✅ Decompressed entries contain readable Shift-JIS dialogue
- ✅ String region is contiguous at end of each entry

## Unverified / risks

- ⚠️ Engine may require full-width Latin (test needed in-game)
- ⚠️ Some strings may have **length-prefix** byte we haven't detected (test by patching a single byte)
- ⚠️ LZSS encoder is naive (O(N²) per block) — fine for ~500KB sall.snl but slow on large archives
- ⚠️ Byte-exact recompression NOT required — game decompresses on load, so any valid LZSS stream that decodes to identical payload works
