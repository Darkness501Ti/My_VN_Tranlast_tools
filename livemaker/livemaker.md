# LiveMaker Translation Tool

## What It Does

Translates a LiveMaker engine Visual Novel from Japanese to English.
Drop both files into the game folder, run the bat, get a full English copy in `eng_version/`.

## Files

| File | Purpose |
|------|---------|
| `translate_livemaker.bat` | Entry point — starts Sugoi, installs deps, runs Python script |
| `livemaker_translate.py` | Main logic — copy game, extract LSBs, translate, repack |

## pylivemaker Version

Requires **pylivemaker 1.2.1+**. The old `lmcsv` tool no longer exists.
Tools used: `lmar`, `lmlsb`, `lmpatch` (all installed by `pip install pylivemaker`).

## How It Works (step by step)

### 1. BAT file startup
- Checks if Sugoi server is already running: `curl http://localhost:14366`
- If not running: launches `startServer-CUDA.bat` minimized **with `/D %SUGOI_DIR%`** so the bat runs in its own folder (required — it uses relative paths to Python38 and models), polls every 5 seconds until port responds
- Checks if `pylivemaker` is installed (`import livemaker`); runs `pip install pylivemaker` if missing
- Runs `livemaker_translate.py`

### 2. Python script — `livemaker_translate.py`

**[tools] Locate pylivemaker CLI tools**
Searches PATH then Python's `Scripts/` directory for `lmar.exe`, `lmlsb.exe`, `lmpatch.exe`.
Exits with error if any are missing.

**[1/5] Copy game to `<game>_ENG_ver/`**
Uses `shutil.copytree()`. Output folder is named `<game_folder_name>_ENG_ver` (e.g. `Fairy×Cherry_ENG_ver/`).
Excludes `<game>_ENG_ver/` and `_lm_extract/` from the copy.

**[2/5] Detect LiveMaker archive**
Finds the largest `.exe` *or* `.dat` in `eng_version/` that is >5 MB and not `install.exe` / `setup.exe` / `install.dat`. LiveMaker archives can live in either a bundled `.exe` (scripts embedded in the launcher) or a standalone `.dat` (launcher loads it at runtime). pylivemaker treats both the same.

| Game | Archive file | Launcher | Output folder |
|------|--------------|----------|---------------|
| Fairy×Cherry | `Fairy×Cherry.exe` (199 MB — bundled exe) | same as archive | `Fairy×Cherry_ENG_ver/` |
| LoveJ | `loveJ.exe` (484 MB — bundled exe) | same as archive | `LoveJ_ENG_ver/` |
| KAZEHIME | `game.dat` (355 MB — standalone archive) | `kznohm.exe` (1.9 MB launcher) | `KAZEHIME_ENG_ver/` |

**[3/5] Extract LSB scripts**
Runs: `lmar x <archive> -o _lm_extract/`
Extracts all `.lsb` script files (and images/resources) from the archive (whether wrapped in `.exe` or standalone `.dat`).

**[4/5] Translate each LSB**
For each `.lsb` file in `_lm_extract/`:
1. `lmlsb extractcsv <file.lsb> <file.lsb_raw.csv>` — export text to CSV
2. Skip if "No text data found" (non-script LSBs)
3. Find `Original text` column (contains JP source), `Translated text` column (target)
4. Collect all JP strings, split into chunks of `BATCH_SIZE` (default 1024), send each chunk as a list in one `POST http://localhost:14366/` request → get back list of English strings
5. `lmlsb insertcsv --no-backup <file.lsb> <file.lsb_tl.csv>` — patch LSB in-place

**Translation method: batch_size (preferred over parallel requests)**
Sending a list lets the server call `ctranslate2.translate_batch()` once per chunk — one GPU kernel for 32 strings vs 32 separate GPU calls. Tune `BATCH_SIZE` at the top of `livemaker_translate.py`.

**[5/5] Repack into archive**
Runs: `lmpatch -r --no-backup -f <archive> _lm_extract/`
Replaces every modified LSB inside the archive (the same `.exe` or `.dat` selected in step [2/5]).
Deletes `_lm_extract/` temp directory.

## Sugoi API — Batch Mode

```python
# Send a list of strings → get back a list of translations in one GPU pass
requests.post(
    "http://localhost:14366/",
    json={"message": "translate sentences", "content": ["JP string 1", "JP string 2", ...]},
    timeout=120
)
# response.json() returns ["EN string 1", "EN string 2", ...]
```

The server's `tokenizeBatch()` accepts a list, runs `ctranslate2.translate_batch()` on the whole batch at once, and returns a JSON array. This is the preferred approach — one GPU kernel per batch instead of one per string.

`BATCH_SIZE = 1024` is set at the top of `livemaker_translate.py`. Drop to 256/512 if GPU OOMs.

Only strings where `is_japanese(text)` is True are included (Hiragana 0x3040–0x30FF, Katakana, CJK 0x4E00–0x9FFF).

## pylivemaker Tools Reference

| Tool | Command | Purpose |
|------|---------|---------|
| `lmar` | `lmar l <archive>` | List archive contents (`.exe` or `.dat`) |
| `lmar` | `lmar x <archive> -o <dir>` | Extract all files from archive |
| `lmlsb` | `lmlsb extractcsv <file.lsb> <out.csv>` | Export text to CSV |
| `lmlsb` | `lmlsb insertcsv --no-backup <file.lsb> <in.csv>` | Patch text back into LSB |
| `lmpatch` | `lmpatch -r --no-backup -f <archive> <dir>` | Repack modified files into archive |

## CSV Format (lmlsb extractcsv output)

```
ID,Label,Context,Original text,Translated text
pylm:text:00000023.lsb:8:0,00000025,,"Japanese text here",
```

- `ID` — unique key used by `insertcsv` to map translations back
- `Original text` — Japanese source (read-only for the script)
- `Translated text` — fill this column with English translations

## Tool Discovery

The script looks for `lmar`, `lmlsb`, `lmpatch` in:
1. System PATH
2. `<python_executable_dir>/Scripts/` (e.g. `C:\...\pythoncore-3.14-64\Scripts\`)

Python 3.14 on this machine installs to `C:\Users\Don_n\AppData\Local\Python\pythoncore-3.14-64\`.

## Known Limitations

- Does not translate text baked into image files (CGs, UI sprites)
- `lmlsb extractcsv` loses rich formatting tags (bold, ruby, etc.) — acceptable for dialogue
- First run is slower: Sugoi model load (~30–60 sec) + pip install (~30 sec)
- Very old LiveMaker versions may use formats not supported by pylivemaker 1.2.1

## How to Test

1. Copy `translate_livemaker.bat` + `livemaker_translate.py` into a game folder (e.g. `Fairy×Cherry/`)
2. Double-click `translate_livemaker.bat`
3. Confirm console shows: server ready → pylivemaker ready → 5 steps complete
4. Confirm `<game>_ENG_ver/` exists with full game files
5. Run the game's launcher exe from `<game>_ENG_ver/` — dialogue should be in English
   - **Bundled-exe games** (Fairy×Cherry, LoveJ): launch the same exe that was patched
   - **Separate-archive games** (KAZEHIME): launch the small launcher exe (`kznohm.exe`) — it reads the patched `game.dat` next to it

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `lmar/lmlsb/lmpatch not found` | `pip install pylivemaker`; check Python Scripts dir is in PATH |
| `lmar x` fails | Unsupported archive version — try a newer pylivemaker release |
| `lmlsb extractcsv` returns "No text data found" for all LSBs | Wrong game type; game may not use standard LiveMaker text format |
| `lmpatch` fails | Check that the archive is a valid LiveMaker container (`lmar l <archive>`) |
| `No LiveMaker archive (>5 MB .exe or .dat) found` | Game stores scripts somewhere unusual. Check folder for `.exe` or `.dat` files >5 MB; if installer-only setup, run the installer first |
| `pip install pylivemaker` fails | Ensure Python and pip are installed and in PATH |
| "The system cannot find the path specified" on Sugoi start | Fixed by `/D %SUGOI_DIR%` in bat — Sugoi's bat uses relative paths and must run from its own folder |
| Server never becomes ready | Check if `startServer-CUDA.bat` needs CUDA drivers; try CPU version instead |
| Translation column is wrong | Script auto-detects columns named "original" (source) and "translat" (target) |
