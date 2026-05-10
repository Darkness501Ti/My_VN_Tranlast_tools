# YU-RIS Engine Learnings

Hard-won facts discovered while building the YU-RIS translator. Saves you time on the next YU-RIS game.

## Archive layer (YPF)

- **`bn.ypf` is the scripts archive for Clock Up `pac/` layout games**, NOT `sn.ypf`. `sn.ypf` is ~21 .ogg audio files (system sounds). `bn.ypf` is hundreds of `.ybn` bytecode files. The `find_scripts_archive()` heuristic must check `bn.ypf` first.
- **Mousou Haruna-san** uses flat layout with `ysbin.ypf` at root (no `pac/`). Different developer than Clock Up.
- **YPF version detection is unreliable** — yuri's `ypf_read(f)` auto-detect fails on Clock Up `bn.ypf`. Try version hints in this order: `[None, 265, 491, 500, 474, 400, 300]`. v265 unlocks Clock Up; v491 auto-works for Mousou.
- **`ypf-repacker.exe` rejects Clock Up YPFs** ("Invalid Name Checksum") even though yuri can read them. .exe is fallback only — works for Mousou v491 but useless for Clock Up.
- **Loose-file override is NOT a YU-RIS feature** despite forum claims. The real override mechanism is dropping a higher-numbered `update<N>.ypf` into the same folder. Clock Up themselves ship official patches as `update1/2/3.ypf` (Tera Beppin already has empty 16-byte placeholders for these slots).
- **YPF entries store path with backslashes**: `ysbin\yst00000.ybn`. Strip-and-replace when going to/from filesystem paths.

## Bytecode layer (YBN / YSTB)

- **YSTB uses hardcoded encryption keys, NOT the YSER key from `.exe`.** `KEY_290 = 0xD36FAC96` works for all v>=290 games. The YSER key from `.exe` is for YPF filename obfuscation, not YBN bytecode. `find_script_key()` is mostly cosmetic — YSTB ignores the parameter.
- **XOR is cyclic rolling per-section** (resets to key[0] at each section boundary). Use `xor_cipher.cyclic_xor_in_place(section_bytes, key)`. NOT a continuous stream across sections.
- **YSTB layout (v3xx-v5xx)**: header(32) + code section + arg section + resource section + lno (line numbers) section. All 4 sections encrypted independently with the same key.
- **WORD command opcode varies per game** — discover at runtime via `YSCM.read(ysc.ybn).codes`. Observed values:
  - Clock Up (v474/v500 YSTB): opcode = 90
  - Mousou Haruna-san (v491 YSTB): opcode = 106
- **WORD args are `typ==0` (Unk type)**, with `.dat` parsed as the dialogue string. **NOT `typ==3`.**
- **`typ==3` args are expression bytecode** (e.g. `M\x08\x00"MAC.BG"`, `W\x02\x00\xc8\x00`) — engine resolves them by exact byte match. Translating these strings = "Invalid identifier detected" runtime error. **Never translate typ==3.**

## yuri library (shimamura-sakura/yuri)

- **`yuri.YSTB.read()` works** but `YSTB.write()` does NOT exist. Library is read-heavy.
- **`yuri.yuridec.run()` + `yuricom.run()` (full decompile/recompile pipeline) FAILS on YPF v500 commercial games** with `ValueError: 0 is not a valid VScope` and `AssertionError: iscr(30) != i1`. Author acknowledged this on Fuwanovel: "this thing might need a rewrite". Use a custom YSTB byte patcher instead — see `ybn_patcher.py`.
- **Actual YPF API (not what GitHub readme suggests)**:
  ```python
  from yuri.fileformat import ypf_read, ypf_make
  ents, version = ypf_read(f, v=265)  # v=None for auto-detect
  # ents = [(name, k, c, data, ul), ...]
  # k = unknown int (use 0), c = compression code (1=compressed), ul = uncompressed length
  ypf_make(ents, version, f, enc='cp932')
  ```

## Encoding

- All YBN strings are CP932 (Shift-JIS). ASCII English encodes safely as a CP932 subset.
- Sugoi may emit smart quotes (`"` `"`), em-dashes (`—`), accented chars (`café`) — these break CP932 encoding. ASCII-fold before write: smart quote → straight, em-dash → hyphen, NFKD strip diacritics.
- Default in-game font is fullwidth MS Gothic — English ASCII renders fullwidth. Acceptable for v1; v2 could swap font via `yscfg.dat` patch or SJIS-tunneling DLL.

## Windows batch trap

- **`setlocal enabledelayedexpansion` eats `!` in folder names** like "Please R Me!". Drop it unless you actually use `!var!` syntax. Use plain `setlocal`.

## Patcher strategy that worked

`ybn_patcher.py` mode = "WORD-only patch":
1. Use yuri's `YSTB.read()` to parse the bytecode.
2. Find WORD opcode from `YSCM.read(ysc.ybn).codes`.
3. Walk commands; collect `(arg.off, arg.siz)` for every WORD arg.
4. Build new resource section: append translated strings AFTER the original heap (don't rewrite existing strings — preserves all non-WORD pointers).
5. Rewrite ONLY the WORD args' `.off` to point to new positions in the appended region.
6. Re-encrypt + reassemble + write.

Round-trip identity edit must be byte-equal — that's the safety net (`tests/test_ybn_roundtrip.py`).

## Per-game data discovered

| Game | YPF ver | YSTB ver | WORD opcode | Scripts archive | Layout |
|------|---------|----------|-------------|-----------------|--------|
| Tera Beppin | 265 | 474 | 90 | `pac/bn.ypf` | pac |
| Please R Me! | 265 | 500 | 90 | `pac/bn.ypf` | pac |
| Mousou Haruna-san | 491 | 491 | 106 | `ysbin.ypf` | flat |

## References

- Research brief: `yuris_research.md` (deep-dive that informed initial design — some claims later revised)
- Design spec: `../../docs/superpowers/specs/2026-05-09-yuris-translator-design.md`
- Implementation plan: `../../docs/superpowers/plans/2026-05-09-yuris-translator.md`
- Upstream yuri: https://github.com/shimamura-sakura/yuri
- Upstream ypf-repacker: https://github.com/dreamsavior/ypf-repacker
