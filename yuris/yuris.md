# YU-RIS Translation Tool

## What It Does

Translates a YU-RIS engine Visual Novel from Japanese to English.
Drop these files into the game folder, run the bat, get a full English copy in `<game>_ENG_ver/`.

## Files

**Runtime (copy these into the game folder):**

| File | Purpose |
|------|---------|
| `translate_yuris.bat` | Entry point — starts Sugoi, installs deps, runs Python script |
| `yuris_translate.py` | Main logic — copy game, extract YBNs, translate, repack |
| `ybn_patcher.py` | Custom YSTB binary patcher (byte-exact round-trip) |
| `ypf-repacker.exe` | Bundled fallback for YPF versions yuri can't handle (1.5 MB, MIT) |
| `DotNetZip.dll` | Required by ypf-repacker.exe (.NET dependency) |
| `ypf-repacker.exe.config` | .NET config for ypf-repacker.exe |
| `yuri/` | Vendored shimamura-sakura/yuri package (YPF read/write + YBN parse) |
| `yuris.md` | This file (user docs) |

**Dev / reference (in `Claude_Yuris/` subfolder, NOT needed in game folder):**

| Path | Purpose |
|------|---------|
| `Claude_Yuris/tests/` | pytest suite (48 tests across 10 files) |
| `Claude_Yuris/LEARNINGS.md` | Hard-won YU-RIS quirks (WORD opcode, typ==3, KEY_290, etc.) |
| `Claude_Yuris/yuris_research.md` | Initial research brief |
| `Claude_Yuris/yuri_VERSION.txt` | Vendored yuri commit SHA |
| `Claude_Yuris/ypf-repacker_VERSION.txt` | ypf-repacker download URL/version |

## Verified games

| Game | Layout | Scripts archive | YPF version | Patch destination | Confidence |
|------|--------|-----------------|-------------|---------------------|------------|
| Tera Beppin | pac/ | pac/bn.ypf | 265 | pac/update<N>.ypf | HIGH |
| Please R Me! | pac/ | pac/bn.ypf | 265 | pac/update1.ypf | HIGH |
| Mousou Haruna-san | flat | ysbin.ypf | 491 | update1.ypf (root) | MEDIUM |

(Mousou Haruna-san is MEDIUM confidence because flat-layout patch-archive override behavior is undocumented. F95Zone has a prior MTL patch worth inspecting if `--mode=patch` doesn't surface English in-game.)

## How to run

1. Copy the entire contents of `My_tools/yuris/` (the bat, py files, .exe, .dll, and `yuri/` folder) into the game directory (e.g. `Tera Beppin/`).
2. Double-click `translate_yuris.bat`.
3. Wait. First run installs Python deps (~30s) and the Sugoi model load (~30-60s). Translation itself takes minutes-to-tens-of-minutes per game.
4. Play from `<game>_ENG_ver/<launcher>.exe`.

## Mode flag

| Mode | Behavior | Use when |
|------|----------|----------|
| patch (default) | Drops update<N>.ypf next to the original archive | Default — start here |
| zzz | Drops zzz_eng.ypf (alphabetical-last load order) | If `patch` is ignored |
| replace | Repacks original bn.ypf/ysbin.ypf in-place (backs up to .jp_backup) | Final fallback |

To re-run with a different mode, invoke from the command line in the game folder:
```
translate_yuris.bat --mode=replace
```

## How it works (8 steps)

1. **Locate tools** — verify yuri import, ypf-repacker.exe present, Sugoi reachable.
2. **Detect layout** — `pac/` subfolder vs flat root; find scripts archive (bn.ypf or ysbin.ypf) and game.exe.
3. **Probe** — read YPF version (auto-tries hint list 265/491/500/...) + script_key (4 bytes near YSER magic in game.exe).
4. **Copy** — `<game>_ENG_ver/` is a full game copy; everything subsequent happens here.
5. **Extract** — pull all .ybn files into `_yuris_work/extracted/ysbin/`. yst*.ybn = translatable; ysc/ysv/ysl/yst_list/yst.ybn = system (copy through unchanged).
6. **Translate** — for each yst*.ybn: parse YSTB header, decrypt with hardcoded KEY_290, decode CP932 strings, batch JP-only strings to Sugoi (BATCH_SIZE=1024 per request), ASCII-fold result, encode CP932, recompute resource offsets, re-encrypt sections.
7. **Build patch YPF** — bundle patched + system .ybn files into `update<N>.ypf` (or zzz_eng.ypf, or replace original).
8. **Cleanup** — wipe `_yuris_work/`, print play instructions.

## Translation backend

Sugoi local AI translator at `http://localhost:14366/`. Same as the LiveMaker tool.
- Endpoint: `POST http://localhost:14366/`
- Body: `{"message": "translate sentences", "content": ["jp1", "jp2", ...]}`
- Returns: list of English strings, one per input.
- BATCH_SIZE = 1024 strings per request (one GPU `translate_batch()` call per chunk).
- Tune at the top of `yuris_translate.py`.

## Encoding notes

- All YBN strings are CP932 (Shift-JIS). Input decoded CP932→Unicode, output Unicode→CP932.
- Sugoi may emit smart quotes / em-dashes / accented chars that break CP932 encoding.
- `ascii_fold()` strips them: smart quotes → straight, em-dash → hyphen, café → cafe.
- v1 accepts the default fullwidth font (MS Gothic). English may render clunky. v2 may add font swap.

## Known limitations

- v1 does NOT translate text baked into images (CGs, UI sprites in `cg.ypf`).
- v1 does NOT touch voice or audio archives.
- v1 only handles YPF versions yuri's hint list covers (265, 491, 500, 474, 400, 300). New versions may need extension.
- If `find_script_key` can't find `YSER` magic in game.exe, the tool warns and continues with a placeholder key (yuri uses internal KEY_290 for YBN bytecode anyway).
- v1 does NOT translate the 5 system .ybn files (ysc/ysv/ysl/yst_list/yst) — they pass through unchanged.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `yuri import failed` | Re-vendor `yuri/` from https://github.com/shimamura-sakura/yuri |
| `pip install ... failed` | Run pip install manually as the user with PATH set |
| `ypf-repacker.exe missing` | Re-download from https://github.com/dreamsavior/ypf-repacker/releases (also need DotNetZip.dll) |
| `Sugoi server not reachable` | Check `D:\game_install\501Translate\tools\sugoi\startServer-CUDA.bat` works manually |
| `YSER magic not found` | Tool warns and continues with placeholder; YBN encryption uses yuri's hardcoded KEY_290 anyway |
| YPF version unsupported by both yuri and .exe | Check `yuris_research.md` Open Items |
| Game launches but text is still Japanese | Re-run with `--mode=zzz` then `--mode=replace` |
| English text renders fullwidth/ugly | Known v1 limitation; font swap is a v2 feature |
| Round-trip test failing | Indicates ybn_patcher can't handle that game's YSTB version — escalate before translating |

## Tests

```
cd D:\game_install\501Translate\My_tools\yuris\Claude_Yuris
python -m pytest tests/ -v
```

48 tests covering: pure helpers (is_japanese, ascii_fold), layout detection, YPF probe/extract/create, script_key, YBN round-trip (byte-exact), translate batch (mocked), translate_ybn (with WORD-only filter), patch_slot. Tests use the actual game files at `D:\game_install\501Translate\waiting to Tranlaste\JP\<game>\`.

## References

- Design spec: `../../docs/superpowers/specs/2026-05-09-yuris-translator-design.md`
- Implementation plan: `../../docs/superpowers/plans/2026-05-09-yuris-translator.md`
- Research brief: `Claude_Yuris/yuris_research.md`
- YU-RIS engine learnings: `Claude_Yuris/LEARNINGS.md`
- Reference tool: `../livemaker/`
- Project context: `../goal.md`
