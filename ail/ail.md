# Ail Soft engine translator

One-click Japanese → English translation for visual novels built on **Ail Soft's
proprietary engine** (developer: アイル / ail-soft.com). Tested on **Kouhou Yome
~Cinnamon Roll~ DL Edition** (kouhouDL.exe, 2009, VNDB v378).

## How to use

1. Copy these three files into the game directory (the folder that contains
   `sall.snl` and the main `.exe`):
   - `translate_ail.bat`
   - `ail_translate.py`
   - `ail_lzss.py`
2. Make sure Sugoi Offline Translator is installed at the path configured in
   `ail_translate.py` (`SUGOI_START_BAT`). The script will auto-launch it.
3. Double-click `translate_ail.bat`.
4. Wait. On a 12-core CPU with a CUDA-capable GPU and Sugoi already warm, a
   500 KB script (~3-5 k strings) finishes in a few minutes.
5. Play from `<game_name>_ENG_ver/<game_name>.exe` (created next to the game
   folder).

## What it does

The tool produces a full copy of the game in `<game_name>_ENG_ver/` with the
script archive `sall.snl` replaced. All other files (`.dat`, `.wav`, `.exe`)
are copied unchanged.

### Steps the script performs

1. Find the game directory (current working dir, or first ancestor containing
   `sall.snl`).
2. Copy the entire game tree to `<game>_ENG_ver/` (skipped if it already exists).
3. Ensure Sugoi is running (boots it via `startServer-CUDA.bat` and polls
   `127.0.0.1:14366` until it responds).
4. Read `sall.snl` — a simple archive of `u32 count + u32 size[] + data[]`.
5. Decompress each LZSS-packed entry (Ail uses a custom LZSS variant with
   pre-init frame and reversed control bit semantics — see `ail_lzss.py`).
6. Extract every Shift-JIS string of ≥4 bytes from every entry.
7. Send strings in batches of `BATCH_SIZE = 1024` to Sugoi's
   `POST http://localhost:14366/`.
8. Replace each JP string in place with English of the **same byte length** —
   pads with spaces if the translation is shorter, truncates at the last word
   boundary if longer.
9. Re-compress each modified entry with the Ail-LZSS encoder.
10. Write the new `sall.snl` to the ENG folder.

## Engine details

The Ail engine has no first-class community tooling — GARbro can read its
archives but not its scripts. This translator was reverse-engineered from
GARbro's `ArcFormats/Ail/ArcAil.cs` (archive + LZSS) and from direct byte-level
analysis of `sall.snl` (script container).

See `Claude_Ail/kouhouDL_research.md` for the full RE writeup including format
specs, opcode hints, and unsolved questions.

### Known limitations

- **In-place byte-budget**: English replacement must fit in the original JP
  byte count. JP chars are 2 bytes (SJIS) and ASCII English is 1 byte, so
  you typically have 2× headroom — but very long monologue lines still
  get truncated mid-sentence. A future "Mode B" would expand the string
  region and re-target u16 references, but that needs a full bytecode-
  opcode parser to find every string reference site.
- **Translation quality** is bottlenecked by Sugoi (offline NMT) — names,
  honorifics, and idioms come out rough. Not fixable in this tool.
- **Graphics with embedded JP text**: untouched. UI labels rendered as
  graphics inside `Gall*.dat` / `Pall*.dat` archives stay Japanese.

### Critical engine gotchas (learned the hard way)

1. **Back-reference LZSS encoder is REJECTED by the engine validator.**
   Even a pure recompress with zero string mods triggers
   `致命的なエラー[9:0] … シナリオCodeの解読エラー`. Solution:
   ``lzss_pack_all_literal`` — emits ctl byte = 0x00 followed by 8
   literal bytes. Output is 1.125× the source size; totally fine for
   ~500 KB script files.

2. **Bytecode region contains byte pairs that LOOK like SJIS strings.**
   A naive SJIS scanner picks up dozens of false positives per entry
   (opcode parameters with 0x82 / 0x83 lead bytes). Patching those
   corrupts opcodes → same scenario-decode error.

   Also, some entries split into MULTIPLE string clusters interleaved
   with bytecode — a "keep only the last cluster" rule produces
   half-English / half-Japanese dialogue boxes.

   Solution: cluster strings by adjacency (max_gap = 16 bytes), then
   keep every cluster whose **median inter-string gap == 2 bytes** (the
   engine's `00 00` string-separator). Bytecode noise has random gaps
   with median > 4, so this filter cleanly separates real text from
   accidental SJIS-looking opcode bytes.

3. **Strings region contains inline ruby/furigana**: pattern
   `[reading]base_text` where `[` = 0x5B and `]` = 0x5D are ASCII
   delimiters. The string between brackets is the pronunciation guide
   — translating it duplicates text and breaks the bracket pairing.
   Solution: detect the surrounding bytes; skip strings preceded by
   `[` and followed by `]`. Strip `[` and `]` from translated text to
   avoid re-triggering the ruby parser.

4. **Engine renders half-width Latin (single-byte ASCII)**. Full-width
   Latin (`Ｓｔａｒｔ`) also renders but looks ugly and halves the
   byte budget. Use half-width.

5. **Voice auto-play breaks if you translate scene tags or speaker
   labels** (sakurakoDL 2014, not kouhouDL 2009 — engine evolved).
   The newer engine uses two things as voice lookup keys:

   - **Voice scene tags**: ASCII run >= 3 chars (e.g. ``a04_``,
     ``e07_ed03``, ``vstart(SE_``) immediately preceding a SJIS scene-
     title string. The ASCII + SJIS pair is the voice mapping key.
   - **Character name tags**: ``【XXX】`` (full-width brackets
     `81 79` / `81 7A`) — the engine uses the speaker name as a voice
     file lookup.

   Translating either silently breaks voice auto-play (text still
   renders, replay button still works, but voice doesn't fire when
   dialogue appears). Solution in `classify_strings_in_region`: mark
   these `voice_tag` / `char_tag` and skip translating. Cost: scene
   titles + speaker labels stay Japanese; dialogue and everything else
   is English. Worth it — voice is essential for VN playback.

## Files

```
ail/
├── ail.md                       ← this file
├── translate_ail.bat            ← entry point (copy to game dir)
├── ail_translate.py             ← orchestrator (10-step pipeline)
├── ail_lzss.py                  ← Ail-LZSS codec + archive I/O
└── Claude_Ail/                  ← dev / RE notes (NOT needed in game dir)
    ├── kouhouDL_research.md     ← reverse-engineering writeup
    ├── ail_lzss.py              ← source of truth for the codec
    ├── analyze_dat.py           ← archive format hypothesis tester
    ├── analyze_snl.py           ← SJIS scanner v1
    ├── analyze_snl2.py          ← SJIS scanner v2
    ├── analyze_decompressed.py  ← string region analyzer
    ├── dump_dialog.py           ← annotated hex dumper
    ├── find_string_refs.py      ← bytecode offset reference hunter
    ├── inspect_headers.py       ← header parser (all .dat / .snl files)
    └── test_roundtrip.py        ← LZSS round-trip verification (151/151 ok)
```
