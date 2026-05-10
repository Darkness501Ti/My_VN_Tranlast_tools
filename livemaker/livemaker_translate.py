#!/usr/bin/env python3
"""
LiveMaker VN Auto-Translation Tool (pylivemaker 1.2.1+)
Workflow: lmar x → lmlsb extractcsv → Sugoi batch-translate → lmlsb insertcsv → lmpatch -r

Place livemaker_translate.py and translate_livemaker.bat in the game folder.
Run translate_livemaker.bat to get a translated English copy in eng_version/.
"""

import os
import sys
import shutil
import glob
import subprocess
import csv
import requests

SUGOI_URL   = "http://localhost:14366/"
GAME_DIR    = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.join(os.path.dirname(sys.executable), "Scripts")
BATCH_SIZE  = 1024  # strings per Sugoi request — tune down if GPU OOMs


def is_japanese(text):
    for ch in str(text):
        cp = ord(ch)
        if (0x3040 <= cp <= 0x30FF or
                0x4E00 <= cp <= 0x9FFF or
                0xFF00 <= cp <= 0xFFEF):
            return True
    return False


def translate_batch(texts):
    """Send a list of JP strings to Sugoi in one request. Returns list of EN strings.
    The Sugoi server passes the whole list to ctranslate2.translate_batch() in one GPU pass."""
    try:
        resp = requests.post(
            SUGOI_URL,
            json={"message": "translate sentences", "content": texts},
            timeout=120
        )
        resp.raise_for_status()
        result = resp.json()
        if isinstance(result, list) and len(result) == len(texts):
            return result
        # Server returned a single string (shouldn't happen for list input, but handle it)
        return [str(result)] * len(texts)
    except Exception as exc:
        print(f"    [warn] batch error: {exc}")
        return texts   # return originals on failure


def find_tool(name):
    """Find a pylivemaker CLI tool in PATH or the Python Scripts directory."""
    try:
        subprocess.run([name, "--help"], capture_output=True, timeout=5)
        return name
    except Exception:
        pass
    exe_path = os.path.join(SCRIPTS_DIR, f"{name}.exe")
    if os.path.isfile(exe_path):
        return exe_path
    return None


def run_cmd(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        msg = (r.stderr or r.stdout or "").strip()[:400]
        if msg:
            print(f"    stderr: {msg}")
    return r.returncode == 0


def translate_lsb(lsb_path, lmlsb):
    """Extract, batch-translate, and re-insert text for one LSB file.
    Returns True if at least one string was translated."""
    raw_csv = lsb_path + "_raw.csv"
    tl_csv  = lsb_path + "_tl.csv"

    # Extract text from LSB to CSV
    r = subprocess.run(
        [lmlsb, "extractcsv", lsb_path, raw_csv],
        capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if r.returncode != 0:
        combined = (r.stdout + r.stderr).lower()
        if "no text data" in combined:
            return False
        print(f"    extractcsv error: {r.stderr.strip()[:200]}")
        return False

    # Read CSV
    try:
        with open(raw_csv, encoding="utf-8", newline="") as f:
            rows = list(csv.reader(f))
    except Exception as e:
        print(f"    CSV read error: {e}")
        _rm(raw_csv)
        return False

    if len(rows) < 2:
        _rm(raw_csv)
        return False

    header = rows[0]
    data   = rows[1:]
    h_low  = [c.lower().strip() for c in header]

    # pylivemaker 1.2.1 columns: ID, Label, Context, Original text, Translated text
    src_idx = next((i for i, c in enumerate(h_low) if "original" in c), None)
    tgt_idx = next((i for i, c in enumerate(h_low) if "translat" in c), None)

    if src_idx is None:
        print(f"    No source column in {os.path.basename(lsb_path)}, header={header}")
        _rm(raw_csv)
        return False
    if tgt_idx is None:
        tgt_idx = len(header)
        header.append("Translated text")

    to_translate = [
        (i, row) for i, row in enumerate(data)
        if len(row) > src_idx and is_japanese(row[src_idx])
    ]

    if not to_translate:
        _rm(raw_csv)
        return False

    name  = os.path.basename(lsb_path)
    total = len(to_translate)
    jp_texts = [data[i][src_idx] for (i, _) in to_translate]
    print(f"    {name}: {total} strings, batch_size={BATCH_SIZE}")

    # Send to Sugoi in chunks — each chunk is one GPU translate_batch() call
    en_texts = []
    for start in range(0, total, BATCH_SIZE):
        chunk = jp_texts[start : start + BATCH_SIZE]
        en_texts.extend(translate_batch(chunk))
        done = min(start + BATCH_SIZE, total)
        print(f"      {done}/{total}")

    # Write translations back into data rows
    for en, (i, _) in zip(en_texts, to_translate):
        while len(data[i]) <= tgt_idx:
            data[i].append("")
        data[i][tgt_idx] = en

    _rm(raw_csv)

    with open(tl_csv, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(data)

    ok = run_cmd([lmlsb, "insertcsv", "--no-backup", lsb_path, tl_csv])
    _rm(tl_csv)

    if not ok:
        print(f"    insertcsv failed for {name}")
    return ok


def _rm(path):
    try:
        os.remove(path)
    except Exception:
        pass


def main():
    game_dir    = GAME_DIR
    game_name   = os.path.basename(game_dir)
    eng_dir     = os.path.join(game_dir, f"{game_name}_ENG_ver")
    extract_dir = os.path.join(game_dir, "_lm_extract")

    print(f"\n=== LiveMaker Auto-Translation Tool ===")
    print(f"Game folder : {game_dir}")

    # Locate pylivemaker tools
    print("\n[tools] Locating pylivemaker CLI tools...")
    lmar    = find_tool("lmar")
    lmlsb   = find_tool("lmlsb")
    lmpatch = find_tool("lmpatch")
    missing = [n for n, p in [("lmar", lmar), ("lmlsb", lmlsb), ("lmpatch", lmpatch)] if not p]
    if missing:
        print(f"  ERROR: Tools not found: {missing}")
        print("  Run: pip install pylivemaker")
        sys.exit(1)
    print(f"  lmar    : {lmar}")
    print(f"  lmlsb   : {lmlsb}")
    print(f"  lmpatch : {lmpatch}")

    # [1/5] Copy game to eng_version/
    print("\n[1/5] Creating eng_version copy...")
    if os.path.exists(eng_dir):
        print("  Removing old eng_version...")
        shutil.rmtree(eng_dir)
    shutil.copytree(game_dir, eng_dir,
                    ignore=shutil.ignore_patterns(f"{game_name}_ENG_ver", "_lm_extract"))
    print("  Copied.")

    # [2/5] Find LiveMaker archive (bundled .exe or standalone .dat) in eng_version/
    print("\n[2/5] Detecting LiveMaker archive...")
    EXCLUDE = ("install.exe", "setup.exe", "install.dat")
    candidates = sorted(
        [f for f in glob.glob(os.path.join(eng_dir, "*.exe")) + glob.glob(os.path.join(eng_dir, "*.dat"))
         if os.path.basename(f).lower() not in EXCLUDE
         and os.path.getsize(f) > 5 * 1024 * 1024],
        key=os.path.getsize, reverse=True
    )
    if not candidates:
        print("  ERROR: No LiveMaker archive (>5 MB .exe or .dat) found in eng_version/")
        sys.exit(1)
    target_archive = candidates[0]
    print(f"  Target: {os.path.basename(target_archive)} ({os.path.getsize(target_archive)//1024//1024} MB)")

    # [3/5] Extract LSB scripts from archive
    print("\n[3/5] Extracting LSB scripts with lmar...")
    if os.path.exists(extract_dir):
        shutil.rmtree(extract_dir)
    os.makedirs(extract_dir)
    if not run_cmd([lmar, "x", target_archive, "-o", extract_dir]):
        print("  ERROR: lmar extract failed.")
        sys.exit(1)
    lsb_files = sorted(glob.glob(os.path.join(extract_dir, "*.lsb")))
    print(f"  Found {len(lsb_files)} LSB script files.")
    if not lsb_files:
        print("  ERROR: No .lsb files extracted — unsupported archive format?")
        sys.exit(1)

    # [4/5] Translate each LSB via Sugoi batch API
    print(f"\n[4/5] Translating via Sugoi (batch_size={BATCH_SIZE})...")
    translated = sum(translate_lsb(lsb, lmlsb) for lsb in lsb_files)
    print(f"  Translated {translated}/{len(lsb_files)} script files.")

    if translated == 0:
        print("  WARNING: No strings translated. Check Sugoi server and LSB contents.")

    # [5/5] Patch translated LSBs back into archive
    print("\n[5/5] Patching translated LSBs into archive with lmpatch...")
    if not run_cmd([lmpatch, "-r", "--no-backup", "-f", target_archive, extract_dir]):
        print("  ERROR: lmpatch failed.")
        sys.exit(1)
    print("  Patched successfully.")

    # Cleanup temp extract dir
    shutil.rmtree(extract_dir, ignore_errors=True)

    print(f"\n{'='*42}")
    print(f" DONE!")
    print(f" Play from: {os.path.basename(eng_dir)}\\")
    print(f" (launch the game's .exe from there)")
    print(f"{'='*42}\n")


if __name__ == "__main__":
    main()
