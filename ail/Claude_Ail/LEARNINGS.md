# Ail Soft engine — learnings

Tool status: **shipped, playable** on kouhouDL.exe (VNDB v378). Renders
half-width English, some lines truncate (Sugoi-rough text plus the in-place
byte budget). User-confirmed in-game.

## Format

### Archive (.snl / .dat)

```
u32 count
u32 size[count]              # 0 or 0xFFFFFFFF = empty slot
u8  data[]                    # concatenated, in slot order
```

### Per-entry prefix

```
if   u16 at offset 0 == 0x0001  -> LZSS-packed, unpacked_size = u32 at offset 2, body at +6
elif u32 at offset 0 == 0       -> raw, prefix = 4 bytes
elif bytes[+4..+8] == "OggS"    -> raw, prefix = 4 bytes
else                            -> raw, prefix = 6 bytes
```

### LZSS variant

- 4 KB sliding dictionary, pre-init to 0x20, `frame_pos = 0xFEE`
- **Reversed control bits**: 0 = literal, 1 = back-reference
- Back-ref: `[off_lo:u8][b2:u8]` → `offset = off_lo | ((b2 & 0xF0)<<4)`,
  `count = (b2 & 0x0F) + 3` (length 3..18)

## Five things that broke translation

1. **Naive SJIS scanner translates bytecode false positives** → opcode
   corruption → `致命的なエラー[9:0] シナリオCodeの解読エラー`. Fix:
   restrict to dense clusters of consecutive strings (`max_gap=16` bytes).

1a. **Multi-region entries** — some entries have `[bc][strings_1][bc][strings_2]`
   layout, not a single trailing strings region. The "only keep the last
   suffix cluster" version of the heuristic produced **half-English / half-
   Japanese dialogue boxes** in sakurakoDL (entry 51 had 30 missed strings
   at 0x05a2; only the cluster at 0x0ae3 was kept).
   Real fix: find ALL clusters whose **median inter-string gap == 2** (the
   engine's `00 00` separator). Bytecode noise has random gaps with median > 4.
   Retroactive impact: +178 strings on kouhouDL, +3,232 on sakurakoDL (+24%).

1b. **Voice scene tags break voice auto-play** (sakurakoDL only — newer
   engine vs kouhouDL). Pattern: an ASCII run >= 3 chars (`a04_`,
   `e07_ed03`, `vstart(SE_`, ...) precedes a SJIS scene-title string.
   The combined ASCII+SJIS is the engine's voice-mapping key. If we
   translate the SJIS half, the lookup fails — voice still plays via the
   replay button (different code path) but auto-trigger silently dies.
   Fix in `classify_strings_in_region`: any SJIS string with ASCII run
   >= 3 chars within the 16 bytes immediately preceding it is marked
   `voice_tag` and kept JP.

1c. **Character name tags break voice auto-play in newer engines.**
   `【櫻子】` and other `【XXX】` speaker labels (full-width brackets
   `81 79 ... 81 7A`) work fine when translated in kouhouDL (2009).
   In sakurakoDL (2014) the engine uses the speaker name as a voice
   lookup key, so translating breaks auto-voice the same way as 1b.
   Fix: any SJIS string with prefix `81 79` and suffix `81 7A` is
   marked `char_tag` and kept JP. Cosmetic cost: speaker labels stay
   Japanese in dialogue boxes; everything else is English.

   Diagnostic technique that found this: run a "translate but replace
   each string with itself" no-op test → produces byte-identical decoded
   payload to the pure-recompress test which was confirmed voice-safe.
   That proved the LZSS pipeline wasn't the issue, isolating the bug to
   the string CONTENT changes. Then progressive skip rules (voice tags,
   then char tags) narrowed it down.

2. **Ruby annotation `[reading]base_text` brackets get unbalanced** when
   the reading is translated. Fix: detect `[` before and `]` after each
   string; mark those as ruby, don't translate, strip `[` `]` from
   English replacements.

3. **Back-reference LZSS encoder output is rejected** by the engine
   validator even on a pure recompress-no-mods cycle. Both
   `lzss_unpack→lzss_pack→lzss_unpack` and the engine's decoder produce
   identical bytes, so it's not a decode bug — the engine validates the
   compressed stream against some encoder-specific invariant we never
   reverse-engineered. **All-literal LZSS** passes (1.125× source size).

## What worked

- `lzss_pack_all_literal` — emit `0x00` ctl byte + 8 literal bytes, repeat.
- `find_strings_region` — walk strings list backwards from end, include
  strings where gap to next is ≤ 16 bytes.
- `classify_strings_in_region` — `[` `]` adjacency test marks rubies.
- Half-width ASCII encoding — engine renders 0x20-0x7E as normal Latin.

## What's still rough

- Sentences get truncated at word boundary when EN ASCII > JP SJIS bytes.
  Even with 2× budget, ~10% of long lines lose their tail.
- Sugoi translation quality (names, honorifics, idioms). Not in scope here.
- Character names like 「ハルカ」 inside square-bracket dialogue markers
  (`【ハルカ】`) are detected as base text and translated; brackets
  (`【`, `】`) are full-width JIS chars, not the ASCII `[` `]` we treat
  as ruby — so the speaker tag becomes English while the format stays
  intact. This works but the line lengths get tight.

## Mode B (future, not implemented)

To eliminate truncation:
1. Parse the bytecode opcodes per entry, identify every u16/u32 site that
   references a string offset.
2. After translating strings, compute new offsets.
3. Rewrite the bytecode opcodes with updated offset values.
4. Append longer English strings instead of in-place patching.

This requires fully decoding the Ail opcode set, which the GARbro source
doesn't cover. Would need either disassembling kouhouDL.exe or
trial-and-error opcode discovery.

## Files left in `Claude_Ail/` (dev / RE only — not shipped)

- `kouhouDL_research.md` — initial format writeup
- `LEARNINGS.md` — this file
- `inspect_headers.py` — header analyzer
- `analyze_dat.py` — archive hypothesis tester
- `analyze_snl.py`, `analyze_snl2.py`, `analyze_decompressed.py`,
  `dump_dialog.py` — string scanning iterations
- `find_string_refs.py` — bytecode offset reference detector
- `analyze_regions.py` — dense-cluster heuristic prototype
- `inspect_entry48.py` — entry 48 ruby structure dump
- `test_roundtrip.py` — verifies `lzss_unpack(lzss_pack(x)) == x` for all
  151 packed entries (passes; doesn't prove engine acceptance)
- `compare_encoded.py` — byte-level diff of original vs reencoded LZSS
- `test_patch_minimal.py` — Tests A/B/C: pure recompress, single-entry
  recompress, single-string fullwidth patch
- `test_d_no_recompress.py` — identity write (passes byte-equal)
- `test_e_all_literal.py` — Test E: all-literal LZSS (engine accepts)
- `diagnose.py` — confirms kouhouDL.exe has no embedded scripts
- `dry_run_test.py` — mock-translator pipeline test (passes)
- `ail_lzss.py` — devcopy of the production codec (the shipped copy is
  in `My_tools/ail/ail_lzss.py`)
