# YU-RIS Engine Translation Research Brief

## TL;DR — Recommended Strategy

**Primary path:** Repack translated `.ybn` scripts into a fresh **`update<N>.ypf`** archive (next-highest-numbered update slot) and drop it into the game's archive folder. Sidesteps original-key problem entirely — community-confirmed working trick used by Clock Up themselves for official patches.

**Fallback path:** Use the engine's "auto-open all packages in game directory" behavior to drop a brand-new YPF (e.g. `zzz_eng.ypf`) containing only modified `.ybn` files. If that fails, repack the entire `sn.ypf` / `ysbin.ypf` and replace the original (requires per-game encryption key, much harder).

**Loose-file override (bare `.ybn` on disk) is NOT a confirmed YU-RIS feature.** Do NOT rely on it as your primary mechanism — the original architectural assumption was wrong. The right primitive is "drop a higher-priority YPF", not "drop a loose file".

**Toolchain to bundle:**
1. **Extractor + Repacker:** `dreamsavior/ypf-repacker.exe` — single .NET .exe, MIT, handles extract + create with `-c <folder> -v <version>`, with `update<N>.ypf` workflow proven in fan community.
2. **YBN handler (preferred):** `shimamura-sakura/yuri` — pure Python lib, byte-exact recompilation verified for v0.488/v0.494, handles both YPF and YBN. Last updated Jan 2026.
3. **YBN handler (fallback):** `regomne/chinesize/yuris/extYbn` — Go binary, well-tested for v2xx–v4xx games; older but battle-proven for Euphoria-era Clock Up titles.

---

## A. YPF Archive Format

### Header layout (from GARbro `ArcYPF.cs` source)
```
0x00  "YPF\0"  (magic 0x00465059 LE)
0x04  uint32 version
0x08  int32  entry_count
0x0C  uint32 dir_size
0x10  ...    extra_header  (4 bytes if version >= 0x1D9 / 473; 8 bytes if version == 0xDE / 222; else 0)
0x20  per-entry records
```

### Per-entry record (32-bit-offset variant)
```
uint32 name_hash (CRC32)
byte   name_len  (XOR-decrypted via per-version SwapTable)
byte[] index_name (Shift-JIS, swap-table decrypted)
byte   file_type  (0=ybn, 1=bmp, 2=png, 3=jpg, 4=gif, 5=wav, 6=ogg, 7=psd, 8=ycg, 9=psb)
byte   is_packed  (0/1, deflate)
uint32 unpacked_size
uint32 packed_size
uint32 offset       <-- 32-bit
uint32 data_crc     (Adler32)
```

**v474+ uses 64-bit offsets** (`uint64 offset`), which breaks naive extractors. GARbro hardcodes 32-bit and explicitly fails — see [morkt/GARbro#452](https://github.com/morkt/GARbro/issues/452): Trap Shrine Steam version is YPF v479 with 64-bit offsets, and CRC algorithms also differ in those.

### Versions encountered
| Version | Notes |
|---|---|
| 0xDE (222) | Older, +8 byte extra header |
| 0xF7 (247) | File-type table includes `avi` |
| 0x100..0x12B | `SwapTable04` / `SwapTable00` |
| 0x12C..0x195 (300..405) | `SwapTable10` |
| 0x196..0x1D8 (406..472) | `SwapTable00` |
| 0x1D9 (473)+ | Adds 4-byte extra header |
| 0x1F4 (500) | Custom swap table per game (e.g. Unionism Quartet) |
| 479..500+ | **64-bit offsets become common** — GARbro fails |
| ~v555 | EXE reports 555 but YPF identifies as v500 (per FuwaBoard MrPalloncini) |

### Encryption
- **Filename length & bytes** XOR'd by per-version swap table.
- **File data** is deflate-compressed; no per-asset XOR.
- **YBN entries** additionally get a 4-byte rolling XOR using `script_key` (4 bytes) found embedded in game.exe near `"YSER"` magic. GARbro `FindYser()` locates it.

### Extractor comparison

| Tool | Lang | Extract | Repack | Single .exe | v473+ | URL |
|------|------|---------|--------|-------------|-------|-----|
| **dreamsavior/ypf-repacker** | C# | YES | **YES** | YES (v0.1.0.1, Aug 2023) | YES | https://github.com/dreamsavior/ypf-repacker |
| GARbro | C# WPF | YES | GUI only | NO (large GUI) | Partial — fails 64-bit | https://github.com/morkt/GARbro |
| arc_unpacker | C++ | YES | NO | YES | Partial | https://github.com/vn-tools/arc_unpacker |
| crskycode/YPF_Tool | C# | YES | **YES** | YES (v1.0, Nov 2021) | Partial | https://github.com/crskycode/YPF_Tool |
| fengberd/YuRISTools | C# | YES | YES | NO releases | Partial | https://github.com/fengberd/YuRISTools |
| mwzzhang Python | Py + Kaitai | YES | NO | NO | Partial | https://github.com/mwzzhang/python-YU-RIS-package-file-unpacker |
| **shimamura-sakura/yuri** | Python 3.13 | YES | YES | NO (lib) | YES — byte-exact | https://github.com/shimamura-sakura/yuri |
| ZQF-ReVN/RxYuris | C++ | YES | YES | needs build | Active 2024+ | https://github.com/ZQF-ReVN/RxYuris |
| jyxjyx1234/YURIS_TOOLS | Py (CN) | YES | YES | NO | YES — used for v0.5xx CN TLs | https://github.com/jyxjyx1234/YURIS_TOOLS |

**Bundle:** `ypf-repacker.exe` (~1.5 MB, MIT). Usage:
```
ypf-repacker.exe -e C:\Some\YU-RIS\pac\ysbin.ypf       # extract
ypf-repacker.exe -c C:\Some\YU-RIS\folder -v 0.479     # create
ypf-repacker.exe -p C:\Some\YU-RIS\pac\ysbin.ypf       # info / version probe
```

UNVERIFIED — needs testing: whether ypf-repacker handles 64-bit-offset variants in v500+ for Tera Beppin / Please R Me builds. Backup tools: crskycode/YPF_Tool, jyxjyx1234/YURIS_TOOLS.

---

## B. YBN Script Format

### Structure
```
header (32 bytes; magic="YSTB", version, code_size, inst_cnt, arg_size, resource_size, off_size, reserved)
code section       (instructions, fixed 4-byte opcodes)
arg section        (per-instruction argument descriptors)
resource section   (string heap — Shift-JIS bytes)
offset section     (per-resource offsets)
```
Validity check: `header.CodeSize == header.InstCnt * 4` and total = sum of section sizes + 32. From `regomne/chinesize/yuris/extYbn` Go source.

### Encryption (separate from YPF)
- 4-byte rolling XOR key applied **independently to each section** (code, arg, resource, off).
- Key embedded in game.exe near `"YSER"` magic. Same key for every `.ybn` in a game.
- A null key (`00 00 00 00`) means unencrypted (rare in retail).

### Text encoding
- Strings are Shift-JIS / CP932. Universal across v2xx–v5xx. UTF-8 not observed in retail YU-RIS.
- Filenames inside YPF: also CP932. Repacking from a folder whose path contains non-SJIS chars breaks repacking — keep working dirs ASCII (FuwaBoard MrPalloncini comment).

### Can we translate in-place?
**No, not safely.** The offset section explicitly stores per-string offsets. Replacing with a different-length string requires rewriting the offset table. The correct approach is parse → split sections → replace strings → recompute offsets → reassemble → re-encrypt. Both `regomne/chinesize/yuris/extYbn` and `shimamura-sakura/yuri` do this correctly.

### YST↔YBN toolchain comparison

| Tool | Maturity | Notes |
|------|----------|-------|
| **shimamura-sakura/yuri** (Python) | Strong, newest | Full decompiler+compiler. Byte-exact recompile verified for v0.488, v0.494, Natsuzora Asterism (v15213). Reads+writes YPF too. Posted Dec 2025, updated Jan 2026. **Best modern open-source option.** Deps: `murmurhash2 xor-cipher deflate`. |
| **regomne/chinesize/yuris/extYbn** (Go) | Mature, older | JSON+TXT extraction + repack. Long battle-tested for Euphoria-era games. Single Go binary. **Most proven for v2xx–v4xx.** |
| CodeSpoof/extYuRis | Active | Strings + partial code, key+opcode guessing, repack. |
| zhengxiaoyao0716/yu-ris-ext-ybn | Lightly maintained | Go, last commit Oct 2024. |
| arcusmaximus/VNTextPatch | Mature | C# extractor/inserter for 20+ engines including YU-RIS. Bonus: SJIS tunneling DLL for non-SJIS chars. |
| dreamsavior/Translator++ w/ YU-RIS plugin | Mature, GUI | Since v5.8.20 handles YPF→YBN→text→inject without manual extraction. Closed-ish, not CLI-friendly. |
| jyxjyx1234/YURIS_TOOLS | Active CN | Includes `GBK.py` that patches EXE for GBK rendering — same trick reusable for ASCII handling. |
| progvian text replacer v6 | Abandoned | 2014, fails on v412+. Historical reference only. |

**Practical recommendation:** `shimamura-sakura/yuri` for v0.4xx games (tested byte-exact for v0.488/v0.494 — likely covers all 3 target games). Fallback to `regomne/chinesize/yuris` for older versions. Both produce byte-identical reproductions when given unmodified text — round-trip is mathematically validatable.

---

## C. Loose-File Override — KEY ARCHITECTURAL FINDING

**The original architectural assumption is half-wrong.**

- Bare loose `.ybn` files outside YPF are NOT a documented YU-RIS engine feature. We found zero sources confirming this works.
- BUT the engine **does automatically open every YPF it finds in the game/`pac` directory**, with later/numbered ones taking precedence. This is the canonical override mechanism.

### Confirmed evidence
- FuwaBoard guide (`Sisulizer` 2022-02, `alina996` 2023-06): "why don't you guys repack to update1.ypf, update2.ypf — it should work if you keep update1>[folder name like ysbin, cgsys]>all the files." → Confirmed working without needing the original encryption key. [thread](https://forums.fuwanovel.moe/topic/24704-a-complete-guide-to-unpack-and-repack-yu-ris-engine-files/)
- Clock Up themselves use `update1.ypf`, `update2.ypf`, `update3.ypf` as official patch archives (as in your Tera Beppin folder).
- shimamura-sakura/yuri README: "usually, paths inside the YPF are like `ysbin\yst00000.ybn`" — the patch YPF must contain entries with the exact internal path including backslash.
- Dreamsavior YU-RIS docs: confirm `pac/` folder is the standard package container; engine auto-loads.

### What this means for our 3 games

**Tera Beppin** (`pac/` w/ existing `update1..3.ypf`):
- Build `pac/update4.ypf` containing `ysbin\<scripts>.ybn`. **HIGH confidence** — this is exactly what Clock Up does.

**Please R Me!** (`pac/` clean, no updates yet):
- Build `pac/update1.ypf`. Same pattern. **HIGH confidence**.

**Mousou Haruna-san** (flat root, no `pac/`):
- Try `update1.ypf` in root first; fall back to `zzz_eng.ypf`; final fallback = repack `ysbin.ypf` directly. **MEDIUM confidence** — engine load-order behavior for non-`pac/` layouts is UNVERIFIED.
- **Critical prior art exists:** F95Zone has an unofficial MTL patch dated 2023-12-04 ([VNDB r117258](https://vndb.org/r117258)). **Download and inspect this patch first** to learn what override mechanism the engine version honors.

### `yscfg.dat` / `yssfs.dat`
- `yscfg.dat`: per-project compiled config (font, window size, system flags). No known runtime flag toggles loose-file override.
- `yssfs.dat`: SJIS-fallback font data. Likely safe to leave alone.

---

## D. Encoding Pitfalls

1. **Filenames inside YPF are Shift-JIS** (length-prefixed, swap-table-XOR'd). Decode/encode as CP932 explicitly.
2. **Script strings are CP932.** Decode CP932→Unicode for Sugoi; encode Unicode→CP932 for write-back.
3. **Pure ASCII English encodes safely as a CP932 subset.** Risk: non-ASCII English (`café`, `naïve`, em-dashes `—`, smart quotes `" "`) — CP932 encoding will fail.
   - Mitigation A (simple): ASCII-fold all translations: `unicodedata.normalize('NFKD').encode('ascii', 'ignore')` + smart-quote replacement table.
   - Mitigation B (advanced): SJIS tunneling via `arcusmaximus/VNTranslationTools` proxy DLL + `sjis_ext.bin`. Defer to v2.
4. **Font rendering.** Default font `ＭＳ ゴシック` (full-width MS Gothic) renders ASCII as full-width — looks bad in English. UNVERIFIED whether `yscfg.dat` font field can be patched. progvian blog: "Currently only characters in this font will be shown correctly."
5. **Line wrapping** is character-count-based, not pixel-width — English under-fills lines. Acceptable for v1.
6. **Halfwidth/fullwidth.** Map full-width brackets `「」` and punctuation `。、` to ASCII `""`, `.,` in pre/post-translation pipeline.

### Reference fan-TLs (toolchain prior art)
- **Euphoria** (Clock Up) — TL'd by Translation Spectrum 2014–2017; private toolchain by RusAnon and dsp2003. Conceptual ancestor of modern open-source tools. [Fuwanovel YU-RIS megathread](https://forums.fuwanovel.moe/topic/757-yu-ris-engine/)
- **NEKO-NIN exHeart** — public BMS extractor by aluigi: [ZenHAX 11061](https://www.zenhax.com/viewtopic.php@t=11061.html)
- **Trap Shrine** — official localization, but reported as YPF v479 + 64-bit offsets, useful data point
- **Natsuzora Asterism** — confirmed byte-exact recompile via `shimamura-sakura/yuri` (v15213)
- **No fan-TL or technical writeup found for Tera Beppin or Please R Me!**
- **Mousou Haruna-san has F95Zone MTL patch from 2023-12-04** — must inspect first

---

## E. The Three Specific Games

### Tera Beppin (テラべっぴん)
- VNDB: [v11068](https://vndb.org/v11068). Developer: [CLOCKUP](https://vndb.org/p200). Released 2012-10-25.
- Standard Clock Up YU-RIS pipeline: `pac/sn.ypf` (scripts), `pac/update1..3.ypf` (official patches), separate ypfs per asset type, `yscfg.dat` + `yssfs.dat` in root.
- Likely YPF v0x1C0–0x1F2 (~448–498) range, possibly 64-bit offsets given 2012 date and Clock Up history. UNVERIFIED — must probe with `ypf-repacker.exe -p`.
- No fan translation found.
- **Recommended:** repack into `pac/update4.ypf`.

### Please R Me! (プリーズ・レ○プ・ミー！, `prm.exe`)
- VNDB: [v7805](https://vndb.org/v7805). Developer: CLOCKUP. Released 2011-10-28.
- Same Clock Up pattern, no existing update slots.
- Earlier release → probably YPF v0x1A0–0x1D0 (~416–464), likely 32-bit offsets. **Smoothest of the three.**
- No fan translation found.
- **Recommended:** repack into `pac/update1.ypf`.

### Mousou Haruna-san (full title likely *Mousou ga Tomaranai Hentai Jukujo no Haruna-san*)
- VNDB: [v47871](https://vndb.org/v47871). Producer NOT Clock Up — different (smaller) developer. Hence flat layout.
- **Existing F95Zone unofficial MTL patch:** [VNDB r117258](https://vndb.org/r117258), dated 2023-12-04. **MUST DOWNLOAD AND INSPECT BEFORE BUILDING.**
- Flat layout (no `pac/`) likely older/simpler YU-RIS SDK, probably v0x1C0–0x1F0.
- Override mechanism for flat layout uncertain — see Section C.

---

## F. Recommended Toolchain & Order of Operations

### Bundle in `My_tools/yuris/`
| Asset | Purpose | Source |
|-------|---------|--------|
| `ypf-repacker.exe` (~1.5 MB, MIT) | Extract + create YPF (single .exe) | https://github.com/dreamsavior/ypf-repacker/releases/tag/0.1.0.1 |
| `yuri/` Python package | YBN extract + recompile, also reads/writes YPF, byte-exact | https://github.com/shimamura-sakura/yuri |
| `extYbn.exe` (Go, optional fallback) | YBN string ops for v2xx–v4xx | https://github.com/regomne/chinesize/tree/master/yuris |
| `translate_yuris.bat` + `yuris_translate.py` | Orchestrator (to be written) | — |
| `yuris.md` | User docs (to be written) | — |

**Strong preference: shimamura-sakura/yuri.** Pure Python (already in your stack), byte-exact recompilation guarantees a validatable round trip, MIT-style license, actively maintained Jan 2026, supports v0.488/v0.494 (Clock Up's typical era). Bundle the `yuri/` folder directly — no compile step.

### One-click pipeline order
```
1. Detect game
   - find エンジン設定.exe + game.exe
   - detect layout: pac/ subfolder vs flat root
   - locate scripts archive: pac/sn.ypf | pac/ysbin.ypf | root ysbin.ypf

2. Probe scripts archive
   - ypf-repacker.exe -p <scripts.ypf>  → record version, key, offset width
   - if extraction fails: try crskycode/YPF_Tool, jyxjyx1234/YURIS_TOOLS, GARbro headless

3. Extract
   - dump every .ybn into working dir, PRESERVING the internal path prefix (ysbin\, sn\, etc.)
   - find YBN script_key by parsing game.exe near "YSER" magic
     (fallback: known-plaintext attack on first bytes of yst00000.ybn)

4. Per-script: extract strings
   - parse YSTB header (magic/sizes), decrypt sections with script_key
   - parse resource section + offset table → list of (offset, length, sjis_bytes)
   - decode CP932 → Unicode

5. Translate (Sugoi)
   - filter is_japanese() to skip already-English / numeric / control strings
   - batch BATCH_SIZE=128, POST localhost:14366
   - pre/post fixes: full-width brackets → ASCII, smart quotes → ASCII

6. Per-script: rebuild YBN
   - encode Unicode → CP932 (errors='replace' or ASCII-fold)
   - rebuild resource section + recompute offset table
   - re-encrypt sections with same script_key
   - write to parallel patched_dir

7. Build patch YPF
   - ypf-repacker.exe -c <patched_dir> -v <detected_version>
   - rename to update<N+1>.ypf
     (Tera Beppin: update4 / Please R Me: update1 / Mousou: update1 OR zzz_eng.ypf)
   - For Mousou: also produce backup of original ysbin.ypf + offer "replace originals" fallback

8. Place patch into ENG copy
   - copy entire game folder to <game>_ENG_ver/
   - drop new update<N>.ypf into <game>_ENG_ver/pac/  (or root for Mousou)

9. (v2 deferred) Font replacement step if ASCII renders ugly
```

### Per-game risk register
| Game | Layout | Override mechanism | Confidence | Top risks |
|------|--------|--------------------|------------|-----------|
| Tera Beppin | `pac/` w/ updates | `pac/update4.ypf` | **HIGH** | YPF v500+ may need 64-bit offset support; script_key recovery; internal path prefix unknown until extract |
| Please R Me! | `pac/` clean | `pac/update1.ypf` | **HIGH** | Same as Tera Beppin, lower 64-bit-offset probability given 2011 date |
| Mousou Haruna | flat root | `update1.ypf` or `zzz_eng.ypf` | **MEDIUM** | Override may not work without `pac/`; F95 MTL must be reverse-engineered first |

---

## Open Items / UNVERIFIED — Needs Testing

1. Whether `ypf-repacker.exe` handles 64-bit-offset YPF (v479+) cleanly. Probe with `-p` on each game.
2. Internal path prefix in each game's scripts archive (`ysbin\`, `sn\`, or empty). Discoverable in 1 minute by extracting.
3. Whether YU-RIS engine respects `update<N>.ypf` override on flat-layout (no `pac/`) games. Mousou Haruna-san is the test; F95Zone MTL is direct prior art.
4. Whether YU-RIS displays ASCII text legibly out of the box, or whether font swap / `yscfg.dat` patch is needed.
5. Whether YBN script_key location via `"YSER"` magic still works in v500+ executables. Fallback: known-plaintext attack on first 4 bytes of `yst00000.ybn`.
6. SDK version mismatch impact for full AST decompile/recompile via shimamura/yuri. **Mitigation:** stick to in-place string patching, do not regenerate YBN from AST source.

---

## Confidence Summary
- Format spec (A, B): **HIGH** — multiple independent open-source implementations agree
- Loose-file override (C): **MEDIUM** — `update<N>.ypf` confirmed for `pac/`, less certain for flat
- Encoding (D): **HIGH** — universally Shift-JIS, well-documented pitfalls
- The 3 games (E): **LOW-MEDIUM** — VNDB metadata only; no per-game RE reports except F95 MTL of Mousou
- Recommended toolchain (F): **HIGH** — proven, permissive, current

---

## Source Index

**YPF format & extractors**
- GARbro source (canonical reference): https://github.com/morkt/GARbro/blob/master/ArcFormats/YuRis/ArcYPF.cs
- GARbro 64-bit offset issue: https://github.com/morkt/GARbro/issues/452
- GARbro repack issue: https://github.com/morkt/GARbro/issues/508
- arc_unpacker source: https://github.com/vn-tools/arc_unpacker/blob/master/src/dec/yuris/ypf_archive_decoder.cc
- **dreamsavior/ypf-repacker** (single-exe, recommended): https://github.com/dreamsavior/ypf-repacker
- crskycode/YPF_Tool: https://github.com/crskycode/YPF_Tool
- fengberd/YuRISTools: https://github.com/fengberd/YuRISTools
- mwzzhang Python: https://github.com/mwzzhang/python-YU-RIS-package-file-unpacker
- ZQF-ReVN/RxYuris: https://github.com/ZQF-ReVN/RxYuris
- ZenHAX NEKO-NIN reverse-eng: https://www.zenhax.com/viewtopic.php@t=11061.html
- GitHub yu-ris topic: https://github.com/topics/yu-ris

**YBN script & translation**
- **shimamura-sakura/yuri** (modern decompiler+compiler, recommended): https://github.com/shimamura-sakura/yuri
- regomne/chinesize/yuris/extYbn: https://github.com/regomne/chinesize/tree/master/yuris
- regomne YBN format issue: https://github.com/regomne/chinesize/issues/21
- CodeSpoof/extYuRis: https://github.com/CodeSpoof/extYuRis
- zhengxiaoyao0716/yu-ris-ext-ybn: https://github.com/zhengxiaoyao0716/yu-ris-ext-ybn
- arcusmaximus/VNTranslationTools (VNTextPatch + SJIS tunneling): https://github.com/arcusmaximus/VNTranslationTools
- VNTextPatch YU-RIS issue: https://github.com/arcusmaximus/VNTranslationTools/issues/121
- jyxjyx1234/YURIS_TOOLS (CN, GBK font patch): https://github.com/jyxjyx1234/YURIS_TOOLS
- progvian text replacer v6 (historical): https://progvian.wordpress.com/2014/07/31/yu-ris-text-replacer-v6/
- yu-ris hacking doc 2013: https://pastebin.com/YRaBLZHe

**Workflows & community**
- **FuwaBoard guide w/ update<N>.ypf trick:** https://forums.fuwanovel.moe/topic/24704-a-complete-guide-to-unpack-and-repack-yu-ris-engine-files/
- FuwaBoard YU-RIS megathread: https://forums.fuwanovel.moe/topic/757-yu-ris-engine/
- FuwaBoard help w/ unpacking: https://forums.fuwanovel.moe/topic/24072-help-with-yu-ris-unpacking-toolset-18-game/
- FuwaBoard shimamura compiler announcement: https://forums.fuwanovel.moe/topic/35091-a-decompiler-for-yu-ris-engine-now-also-a-compiler/
- Translator++ YU-RIS docs: https://dreamsavior.net/docs/translator/yu-ris-engine/
- Translator++ blog: https://dreamsavior.net/translator-ver-5-7-28-yu-ris-engine-translator/

**Game references**
- VNDB Tera Beppin: https://vndb.org/v11068
- VNDB Please R❤pe Me!: https://vndb.org/v7805
- VNDB Mousou Haruna: https://vndb.org/v47871
- VNDB F95 MTL Mousou patch: https://vndb.org/r117258
- VNDB YU-RIS engine filter: https://vndb.org/v?fil=engine-yu-ris
