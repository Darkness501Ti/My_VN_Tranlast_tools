# My_tools — One-Click VN Translator Project

## Goal

Build one-click auto-translation tools for Japanese Visual Novels, organized by game engine.
Each tool folder contains scripts the user copies into a game directory and runs with a single double-click.
The tool produces a fully playable English copy in an `eng_version` subfolder inside the game.

## Translation Backend

**Sugoi Offline Translator** (local AI, no internet required)
- Server bat: `D:\game_install\501Translate\tools\sugoi\startServer-CUDA.bat`
- API endpoint: `POST http://localhost:14366/`
- Request body: `{"message": "translate sentences", "content": ["text1", "text2", ...]}`
- Response: JSON array of translated English strings — one per input string
- GPU mode (CUDA); CPU fallback bat also exists at same location

**Translation approach: batch_size** (preferred)
All tools send strings in batches (default `BATCH_SIZE = 1024`) in a single API request.
The Sugoi server passes the whole list to `ctranslate2.translate_batch()` in one GPU kernel call.
Tune `BATCH_SIZE` at the top of each Python script — drop to 256/512 if GPU OOMs on a large script.
Do NOT use parallel requests (ThreadPoolExecutor) — batch mode is faster and simpler.

The tools auto-start Sugoi if it is not running and poll until the server is ready before translating.

## Folder Structure

```
My_tools/
├── goal.md                  ← this file (project context for Claude Code)
├── livemaker/
│   ├── livemaker.md         ← how the LiveMaker tool works
│   ├── translate_livemaker.bat
│   └── livemaker_translate.py
├── ail/                     ← Ail Soft engine (アイル / ail-soft.com)
│   ├── ail.md               ← user docs
│   ├── translate_ail.bat    ← entry point
│   ├── ail_translate.py     ← orchestrator (12-step pipeline)
│   ├── ail_lzss.py          ← Ail-LZSS codec (custom variant) + archive I/O
│   └── Claude_Ail/          ← dev / RE notes (NOT shipped to game folders)
│       ├── kouhouDL_research.md ← format spec writeup
│       ├── LEARNINGS.md     ← five engine gotchas + fixes
│       └── analyze_*.py / test_*.py / probe_*.py / etc.
└── <engine_name>/           ← future engines go here (e.g. nscripter, rpgmaker)
    ├── <engine>.md
    ├── translate_<engine>.bat
    └── translate_<engine>.py
```

## Workflow (for every engine tool)

1. User copies the engine's tool folder contents into the game root directory
2. User double-clicks `translate_<engine>.bat`
3. The bat: starts Sugoi if needed → installs Python deps if needed → runs the Python script
4. The Python script: creates `<game_name>_ENG_ver/` (full game copy) → extracts JP scripts → translates via Sugoi → repackages
5. User plays from `<game_name>_ENG_ver/<game_exe>`

## Supported Engines (so far)

| Engine | Status | Notes |
|--------|--------|-------|
| LiveMaker | Done | Uses pylivemaker 1.2.1+ (`lmar` + `lmlsb` + `lmpatch`) |
| YU-RIS | Done | Uses shimamura-sakura/yuri (vendored, YPF I/O) + custom Python YSTB patcher (byte-exact). Patch via update<N>.ypf trick. |
| Ail Soft | Done | Ail proprietary engine (アイル / ail-soft.com). Custom LZSS-compressed `sall.snl`. RE'd from GARbro `Ail/DatOpener`. In-place half-width ASCII replacement preserves all offset references. **All-literal LZSS encoding required** (engine validator rejects back-ref encoder). **Multi-cluster string-region detection** (median-gap heuristic) catches scenes with interleaved bytecode + strings. **Voice-safe skip rules** preserve scene tags (after `a04_`-style ASCII prefix) and speaker labels (`【XXX】`) in Japanese — newer engine (2014+) uses these as voice lookup keys. Tested in-game with voice on kouhouDL (VNDB v378) and sakurakoDL. |

## Games Waiting to Translate

Located in `D:\game_install\501Translate\waiting to Tranlaste\JP\`

| Game | Engine | Status |
|------|--------|--------|
| Fairy×Cherry | LiveMaker | Ready |
| KAZEHIME | LiveMaker | Ready (uses game.dat archive) |
| LoveJ | LiveMaker | Ready |
| Tera Beppin | YU-RIS | Ready (pac/ layout, bn.ypf v265) |
| Please R Me! | YU-RIS | Ready (pac/ layout, bn.ypf v265) |
| Mousou Haruna-san | YU-RIS | Ready (flat layout, ysbin.ypf v491) |

Translated output goes to `D:\game_install\501Translate\waiting to Tranlaste\ENG\` (manual move after `eng_version` is produced).

## Python Environment

- Uses system Python (user's installed Python, not Sugoi's bundled Python38)
- Dependencies are auto-installed via pip on first run
- Key packages: `pylivemaker`, `requests`

## When Adding a New Engine Tool

1. Create `My_tools/<engine_name>/` folder
2. Write `translate_<engine>.bat` — same structure as livemaker bat (Sugoi check → pip check → run python)
3. Write `translate_<engine>.py` — game-specific: extract scripts → translate via Sugoi API → repackage
4. Write `<engine>.md` documenting how it works
5. Update the Supported Engines table above
