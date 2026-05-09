#!/usr/bin/env python3
"""YU-RIS VN Auto-Translation Tool (yuri + ypf-repacker.exe + Sugoi)."""

import argparse
import os
import sys
import unicodedata
import glob
import re
import requests

GAME_DIR    = os.path.dirname(os.path.abspath(__file__))
SUGOI_URL   = "http://localhost:14366/"
BATCH_SIZE  = 128


def is_japanese(text):
    """True if any Hiragana/Katakana/CJK/halfwidth-kana char appears in text."""
    for ch in str(text):
        cp = ord(ch)
        if (0x3040 <= cp <= 0x30FF or
                0x4E00 <= cp <= 0x9FFF or
                0xFF00 <= cp <= 0xFFEF):
            return True
    return False


_FOLD_TABLE = {
    '‘': "'", '’': "'",       # smart single quotes
    '“': '"', '”': '"',       # smart double quotes
    '–': "-", '—': "-",       # en/em dash
    '…': "...",                     # ellipsis
    '「': '"', '」': '"',       # Japanese 「」
    '『': '"', '』': '"',       # Japanese 『』
    '、': ",",                       # 、 ideographic comma
    '。': ".",                       # 。 ideographic period
    '！': "!", '？': "?",       # fullwidth ! ?
}


def ascii_fold(text):
    """Replace common non-ASCII chars with ASCII equivalents.
    Required because YBN strings must encode as CP932 — pure ASCII fits cleanly,
    but Sugoi may emit smart quotes / em-dashes / accented chars that break encoding.
    """
    out = []
    for ch in text:
        if ch in _FOLD_TABLE:
            out.append(_FOLD_TABLE[ch])
        elif ord(ch) < 128:
            out.append(ch)
        else:
            # Strip combining marks (NFKD), keep base letter
            decomposed = unicodedata.normalize("NFKD", ch)
            stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
            out.append(stripped if stripped.isascii() else "?")
    return "".join(out)


_EXCLUDE_EXES = ("install.exe", "setup.exe", "inst.exe",
                 "エンジン設定.exe", "セーブファイル設定.exe")


def detect_layout(game_dir):
    """Return 'pac' if game_dir/pac/ exists with .ypf files, else 'flat'."""
    pac = os.path.join(game_dir, "pac")
    if os.path.isdir(pac) and glob.glob(os.path.join(pac, "*.ypf")):
        return "pac"
    return "flat"


def find_scripts_archive(game_dir):
    """Locate the YPF that holds .ybn scenario scripts.

    Heuristic:
    - pac/ layout (Clock Up style): prefer bn.ypf (285 entries in Tera Beppin,
      225 in Please R Me!, all .ybn), then ysbin.ypf, then sn.ypf as last
      named fallback.  sn.ypf in Clock Up pac/ contains only .ogg system audio.
    - flat layout (Mousou Haruna-san style): prefer ysbin.ypf then sn.ypf.
    Falls back to the largest non-asset YPF when none of the named files exist.
    """
    layout = detect_layout(game_dir)
    search_dir = os.path.join(game_dir, "pac") if layout == "pac" else game_dir
    candidates_ordered = (
        ("bn.ypf", "ysbin.ypf", "sn.ypf") if layout == "pac"
        else ("ysbin.ypf", "sn.ypf")
    )
    for name in candidates_ordered:
        p = os.path.join(search_dir, name)
        if os.path.isfile(p):
            return p
    # Fallback heuristic
    asset_prefixes = ("cg", "bgm", "voice", "vo", "se", "cgsys",
                       "op", "ed", "st", "update")
    candidates = []
    for ypf in glob.glob(os.path.join(search_dir, "*.ypf")):
        name = os.path.basename(ypf).lower()
        if not any(name.startswith(p) for p in asset_prefixes):
            candidates.append(ypf)
    if candidates:
        candidates.sort(key=os.path.getsize, reverse=True)
        return candidates[0]
    raise FileNotFoundError(f"No script archive (bn.ypf / ysbin.ypf / sn.ypf) in {search_dir}")


def find_game_exe(game_dir):
    """Largest .exe in game_dir excluding installer/setup/engine-config."""
    exes = []
    for exe in glob.glob(os.path.join(game_dir, "*.exe")):
        name = os.path.basename(exe).lower()
        if name in (e.lower() for e in _EXCLUDE_EXES):
            continue
        exes.append(exe)
    if not exes:
        raise FileNotFoundError(f"No launcher exe in {game_dir}")
    exes.sort(key=os.path.getsize, reverse=True)
    return exes[0]


# ---------------------------------------------------------------------------
# YPF probing
# ---------------------------------------------------------------------------

import re
import shutil
import subprocess
from collections import namedtuple

YPFInfo = namedtuple("YPFInfo", "version entry_count tool")

YPF_REPACKER = os.path.join(GAME_DIR, "ypf-repacker.exe")


def probe_ypf(ypf_path):
    """Return YPFInfo for a YPF archive.

    Strategy (in order):
    1. vendored yuri -- tries auto-detect first, then common version overrides
       (265 for Clock Up bn.ypf, 491 for Mousou, etc.).  Auto-detect fails on
       Clock Up archives; passing v=265 explicitly works.
    2. ypf-repacker.exe -p -- fallback when yuri exhausts all version hints.
    3. raw header parse -- reads 32-byte YPF header directly; last resort.
       Yields version and entry count without any hash validation.
    """
    # Primary: yuri with auto-detect then common version overrides
    sys.path.insert(0, GAME_DIR)
    try:
        from yuri.fileformat import ypf_read
        VERSION_HINTS = [None, 265, 491, 500, 474, 400, 300]
        last_exc = None
        for v in VERSION_HINTS:
            try:
                with open(ypf_path, "rb") as f:
                    ents, real_v = ypf_read(f, v=v) if v is not None else ypf_read(f)
                return YPFInfo(version=real_v, entry_count=len(ents), tool="yuri")
            except Exception as exc:
                last_exc = exc
        print(f"  [probe] yuri exhausted all version hints; last error: {last_exc}; trying ypf-repacker.exe")
    except ImportError as exc:
        print(f"  [probe] yuri not importable: {exc}; trying ypf-repacker.exe fallback")

    # Fallback 1: ypf-repacker.exe -p
    if os.path.isfile(YPF_REPACKER):
        r = subprocess.run(
            [YPF_REPACKER, "-p", ypf_path],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        version, count = _parse_ypf_repacker_probe(r.stdout)
        if version > 0 and count > 0:
            return YPFInfo(version=version, entry_count=count, tool="ypf-repacker.exe")
        print(f"  [probe] ypf-repacker.exe gave no usable data (rc={r.returncode}); trying raw header")

    # Fallback 2: raw 32-byte YPF header (no hash validation)
    # Layout (little-endian): magic[4] version[4] entry_count[4] hdr_size[4] pad[16]
    import struct as _struct
    with open(ypf_path, "rb") as f:
        raw = f.read(32)
    if len(raw) < 32 or raw[:4] != b"YPF\x00":
        raise RuntimeError(f"Not a YPF archive or file too small: {ypf_path}")
    _, version, entry_count, _, _ = _struct.unpack("<4s3I16s", raw)
    return YPFInfo(version=version, entry_count=entry_count, tool="raw-header")


# ---------------------------------------------------------------------------
# YPF version hints (shared by probe_ypf and extract_ypf)
# ---------------------------------------------------------------------------

_YPF_VERSION_HINTS = [None, 265, 491, 500, 474, 400, 300]


def extract_ypf(ypf_path, out_dir):
    """Extract every entry from ypf_path into out_dir, preserving internal paths.

    Tries vendored yuri first (with version-hint loop); falls back to
    ypf-repacker.exe if all yuri attempts fail. Returns the tool name used.
    Raises RuntimeError if both fail.
    """
    os.makedirs(out_dir, exist_ok=True)

    # Primary: yuri with version-hint loop
    sys.path.insert(0, GAME_DIR)
    try:
        from yuri.fileformat import ypf_read
    except ImportError as exc:
        print(f"  [extract] yuri import failed: {exc}; trying .exe fallback")
        ypf_read = None

    if ypf_read is not None:
        last_exc = None
        for v in _YPF_VERSION_HINTS:
            try:
                with open(ypf_path, "rb") as f:
                    ents, _real_v = (ypf_read(f, v=v) if v is not None
                                     else ypf_read(f))
                # ents = [(name, k, c, data, ul), ...]
                for name, _k, _c, data, _ul in ents:
                    dest = os.path.join(out_dir, name.replace("\\", os.sep))
                    os.makedirs(os.path.dirname(dest) or out_dir, exist_ok=True)
                    with open(dest, "wb") as g:
                        g.write(data)
                return "yuri"
            except Exception as exc:
                last_exc = exc
        print(f"  [extract] yuri exhausted version hints; last error: {last_exc}; trying .exe fallback")

    # Fallback: ypf-repacker.exe -e <file>
    # The exe creates a folder named after the archive stem NEXT TO the .ypf file.
    # We run it from out_dir but the exe ignores cwd and writes next to the .ypf.
    # So we find that folder and move/merge its contents into out_dir.
    if not os.path.isfile(YPF_REPACKER):
        raise RuntimeError(f"both yuri and ypf-repacker.exe unavailable for {ypf_path}")

    r = subprocess.run(
        [YPF_REPACKER, "-e", ypf_path],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if r.returncode != 0:
        raise RuntimeError(
            f"both extractors failed for {ypf_path}: "
            f"{(r.stderr or r.stdout).strip()[:300]}"
        )

    # Locate the folder the exe created (stem of ypf_path, sibling directory)
    stem = os.path.splitext(os.path.basename(ypf_path))[0]
    exe_out = os.path.join(os.path.dirname(ypf_path), stem)
    if os.path.isdir(exe_out):
        # Move all files from exe_out into out_dir, preserving sub-structure
        for root, dirs, files in os.walk(exe_out):
            rel = os.path.relpath(root, exe_out)
            dest_root = os.path.join(out_dir, rel) if rel != "." else out_dir
            os.makedirs(dest_root, exist_ok=True)
            for fname in files:
                src_file = os.path.join(root, fname)
                dst_file = os.path.join(dest_root, fname)
                shutil.move(src_file, dst_file)
        shutil.rmtree(exe_out, ignore_errors=True)
    return "ypf-repacker.exe"


def _parse_ypf_repacker_probe(stdout):
    """Extract (version, entry_count) from ypf-repacker.exe -p stdout.

    Observed format (v0.1.0.1):
        Version: 491
        Files Count: 149

    Patterns are matched by keyword to be robust against line-order changes.
    """
    version = 0
    count = 0

    # "Version: 491"  (not "v491" — the header line says "YPF-Repacker v0.1.0.1")
    m = re.search(r"^\s*Version:\s*(\d+)", stdout, re.MULTILINE | re.IGNORECASE)
    if m:
        version = int(m.group(1))

    # "Files Count: 149"
    m = re.search(r"Files\s+Count:\s*(\d+)", stdout, re.IGNORECASE)
    if m:
        count = int(m.group(1))
    else:
        # Broader fallback: "149 files" / "Entries: 149"
        m = re.search(r"(\d+)\s*(?:files?|entries|entry)", stdout, re.IGNORECASE)
        if m:
            count = int(m.group(1))

    return version, count


def find_script_key(exe_path):
    """Find the 4-byte YBN script_key embedded in game.exe near the b'YSER' magic.

    Pattern (from GARbro FindYser): the 4 bytes immediately following YSER are
    the script_key for all .ybn entries in the game's archives.

    Note: yuri's defaults (KEY_200=0x07B4024A, KEY_290=0xD36FAC96) often work
    without YSER lookup, but extracting from .exe is more reliable when present.
    """
    with open(exe_path, "rb") as f:
        blob = f.read()
    idx = blob.find(b"YSER")
    if idx == -1:
        raise RuntimeError(
            f"YSER magic not found in {exe_path}. "
            "v500+ exes may relocate it; known-plaintext attack on yst00000.ybn "
            "is not implemented in v1."
        )
    key = blob[idx + 4 : idx + 8]
    if len(key) != 4:
        raise RuntimeError(f"Truncated YSER region at offset {idx} in {exe_path}")
    return key


# ---------------------------------------------------------------------------
# YBN string ops (re-exported from ybn_patcher)
# ---------------------------------------------------------------------------

sys.path.insert(0, GAME_DIR)
from ybn_patcher import ybn_load_strings, ybn_patch_strings  # noqa: E402


# ---------------------------------------------------------------------------
# YPF archive creation
# ---------------------------------------------------------------------------

def create_patch_ypf(src_dir, out_ypf, version):
    """Build a YPF archive from src_dir at the given version.

    Tries vendored yuri first; falls back to ypf-repacker.exe.
    src_dir contents are added as YPF entries with paths relative to src_dir,
    using backslash separators (YPF convention).
    """
    # Try yuri (API: ypf_make(ents, v, f) where ents = list of (name, k, c, data, ul))
    sys.path.insert(0, GAME_DIR)
    try:
        from yuri.fileformat import ypf_make
        entries = []
        for root, _, files in os.walk(src_dir):
            for fname in sorted(files):
                full = os.path.join(root, fname)
                rel = os.path.relpath(full, src_dir).replace(os.sep, "\\")
                with open(full, "rb") as f:
                    data = f.read()
                # (name, k=0, c=1=compress-on-write, data, ul=uncompressed_len)
                entries.append((rel, 0, 1, data, len(data)))
        with open(out_ypf, "wb") as f:
            ypf_make(entries, version, f)
        return "yuri"
    except Exception as exc:
        print(f"  [create] yuri failed: {exc}; trying ypf-repacker.exe fallback")

    # Fallback: ypf-repacker.exe -c <folder> -v <version_str>
    # The repacker uses float notation: version 491 -> "0.491"
    if not os.path.isfile(YPF_REPACKER):
        raise RuntimeError("both yuri and ypf-repacker.exe unavailable")
    version_str = f"0.{version}"
    r = subprocess.run(
        [YPF_REPACKER, "-c", src_dir, "-v", version_str],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if r.returncode != 0:
        raise RuntimeError(
            f"both creators failed: {(r.stderr or r.stdout).strip()[:300]}"
        )
    # ypf-repacker.exe -c writes <src_dir>.ypf next to src_dir; rename to out_ypf
    default_out = src_dir.rstrip(os.sep) + ".ypf"
    if os.path.isfile(default_out) and os.path.abspath(default_out) != os.path.abspath(out_ypf):
        if os.path.exists(out_ypf):
            os.remove(out_ypf)
        shutil.move(default_out, out_ypf)
    return "ypf-repacker.exe"


# ---------------------------------------------------------------------------
# Sugoi translation (batch HTTP client)
# ---------------------------------------------------------------------------

def translate_batch(texts):
    """Send a list of JP strings to Sugoi in one request. Returns list of EN strings.
    On failure returns the originals so the pipeline can keep going."""
    try:
        resp = requests.post(
            SUGOI_URL,
            json={"message": "translate sentences", "content": texts},
            timeout=120,
        )
        resp.raise_for_status()
        result = resp.json()
        if isinstance(result, list) and len(result) == len(texts):
            return result
        return [str(result)] * len(texts)
    except Exception as exc:
        print(f"    [warn] batch error: {exc}")
        return texts


# ---------------------------------------------------------------------------
# Per-file YBN translation pipeline
# ---------------------------------------------------------------------------

def translate_ybn(ybn_in, ybn_out, script_key):
    """Translate JP strings in one YBN file. Returns count of strings translated.

    Reads ybn_in, decodes CP932 strings, filters Japanese, batches via Sugoi,
    ASCII-folds the English, encodes back to CP932, writes byte-correct YBN to
    ybn_out.  Files with zero Japanese strings produce byte-identical output.

    ybn_load_strings returns list[bytes] (flat, position-indexed).
    ybn_patch_strings takes list[bytes] of the same length and order.
    """
    with open(ybn_in, "rb") as f:
        raw = f.read()
    strings = ybn_load_strings(raw, script_key)  # list[bytes], position = index

    # Identify Japanese-bearing positions
    jp_positions = []   # indices into strings[]
    jp_texts = []       # decoded text for those positions
    for i, sjis in enumerate(strings):
        try:
            text = sjis.decode("cp932")
        except UnicodeDecodeError:
            continue
        if is_japanese(text):
            jp_positions.append(i)
            jp_texts.append(text)

    if not jp_texts:
        # No-op: identity patch produces byte-identical output
        rebuilt = ybn_patch_strings(raw, script_key, strings)
        with open(ybn_out, "wb") as f:
            f.write(rebuilt)
        return 0

    # Batch translate via Sugoi in BATCH_SIZE chunks
    en_texts = []
    for start in range(0, len(jp_texts), BATCH_SIZE):
        chunk = jp_texts[start : start + BATCH_SIZE]
        en_texts.extend(translate_batch(chunk))
        done = min(start + BATCH_SIZE, len(jp_texts))
        print(f"      {done}/{len(jp_texts)}")

    # Build new_strings: copy of strings with JP slots replaced by EN CP932
    new_strings = list(strings)
    for j, en in enumerate(en_texts):
        pos = jp_positions[j]
        folded = ascii_fold(en)
        try:
            sjis = folded.encode("cp932")
        except UnicodeEncodeError:
            sjis = folded.encode("cp932", errors="replace")
        new_strings[pos] = sjis

    rebuilt = ybn_patch_strings(raw, script_key, new_strings)
    with open(ybn_out, "wb") as f:
        f.write(rebuilt)
    return len(jp_texts)


_UPDATE_RE = re.compile(r"^update(\d+)\.ypf$", re.IGNORECASE)


def next_patch_slot(directory):
    """Return 'update<N>.ypf' where N is one greater than the highest existing slot.

    Skips gaps intentionally — never reuses a deleted slot to avoid load-order surprises.
    Returns 'update1.ypf' if no update slots exist.
    """
    highest = 0
    if os.path.isdir(directory):
        for name in os.listdir(directory):
            m = _UPDATE_RE.match(name)
            if m:
                n = int(m.group(1))
                if n > highest:
                    highest = n
    return f"update{highest + 1}.ypf"


def main():
    parser = argparse.ArgumentParser(
        description="One-click YU-RIS VN translator. Run from inside the game folder.",
    )
    parser.add_argument(
        "--mode",
        choices=("patch", "zzz", "replace"),
        default="patch",
        help=(
            "patch (default) = drop update<N>.ypf alongside originals. "
            "zzz = drop zzz_eng.ypf (alphabetical-last load order). "
            "replace = repack original archive in-place (backs up to .jp_backup)."
        ),
    )
    args = parser.parse_args()

    game_dir    = GAME_DIR
    game_name   = os.path.basename(game_dir)
    eng_dir     = os.path.join(game_dir, f"{game_name}_ENG_ver")
    work_dir    = os.path.join(game_dir, "_yuris_work")

    print(f"\n=== YU-RIS Auto-Translation Tool ===")
    print(f"Game folder : {game_dir}")
    print(f"Mode        : {args.mode}")

    # [1/8] Locate tools
    print("\n[1/8] Locating tools...")
    sys.path.insert(0, GAME_DIR)
    try:
        import yuri  # noqa: F401
        print("  yuri          : OK (vendored)")
    except Exception as exc:
        print(f"  ERROR: yuri import failed: {exc}")
        sys.exit(1)
    if not os.path.isfile(YPF_REPACKER):
        print(f"  WARN: ypf-repacker.exe missing at {YPF_REPACKER} (fallback unavailable)")
    else:
        print(f"  ypf-repacker  : OK")
    try:
        requests.get(SUGOI_URL, timeout=3)
        print(f"  Sugoi server  : OK")
    except Exception:
        print(f"  ERROR: Sugoi server not reachable at {SUGOI_URL}")
        sys.exit(1)

    # [2/8] Detect game layout
    print("\n[2/8] Detecting game layout...")
    layout = detect_layout(game_dir)
    try:
        scripts_archive = find_scripts_archive(game_dir)
        game_exe = find_game_exe(game_dir)
    except FileNotFoundError as exc:
        print(f"  ERROR: {exc}")
        sys.exit(1)
    print(f"  layout        : {layout}")
    print(f"  scripts       : {scripts_archive}")
    print(f"  game.exe      : {game_exe}")

    # [3/8] Probe + script_key
    print("\n[3/8] Probing scripts archive and script_key...")
    info = probe_ypf(scripts_archive)
    print(f"  YPF version   : {info.version} (entries={info.entry_count}, tool={info.tool})")
    try:
        script_key = find_script_key(game_exe)
        print(f"  script_key    : {script_key.hex()}")
    except RuntimeError as exc:
        print(f"  WARN: {exc}")
        print(f"  Continuing with default key (yuri's hardcoded KEY_290 is used internally)")
        script_key = b"\x00\x00\x00\x00"  # placeholder — patcher uses internal key

    # [4/8] Copy game to ENG_ver
    print(f"\n[4/8] Copying game to {os.path.basename(eng_dir)}/...")
    if os.path.exists(eng_dir):
        print("  removing old ENG copy...")
        shutil.rmtree(eng_dir)
    shutil.copytree(
        game_dir, eng_dir,
        ignore=shutil.ignore_patterns(f"{game_name}_ENG_ver", "_yuris_work"),
    )
    print("  copied.")

    # [5/8] Extract YBNs to work_dir/extracted
    print("\n[5/8] Extracting YBN scripts...")
    if os.path.exists(work_dir):
        shutil.rmtree(work_dir)
    extracted = os.path.join(work_dir, "extracted")
    patched   = os.path.join(work_dir, "patched")
    extract_ypf(scripts_archive, extracted)

    yst_files = []   # translatable yst*.ybn
    sys_files = []   # system .ybn (ysc/ysv/ysl/yst_list/yst.ybn) — copy through
    for root, _, files in os.walk(extracted):
        for f in files:
            full = os.path.join(root, f)
            low = f.lower()
            if low.endswith(".ybn"):
                if low.startswith("yst") and low[3:4].isdigit():
                    yst_files.append(full)
                else:
                    sys_files.append(full)
    print(f"  extracted {len(yst_files)} yst*.ybn (translatable)")
    print(f"  + {len(sys_files)} system .ybn (copy-through)")
    if not yst_files:
        print("  ERROR: no yst*.ybn extracted. Wrong archive selected?")
        sys.exit(1)

    # [6/8] Translate each yst*.ybn; copy system files through
    print(f"\n[6/8] Translating via Sugoi (BATCH_SIZE={BATCH_SIZE})...")
    fail_count = 0
    total_strings = 0
    for ybn in yst_files:
        rel = os.path.relpath(ybn, extracted)
        out_path = os.path.join(patched, rel)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        try:
            n = translate_ybn(ybn, out_path, script_key)
            total_strings += n
            print(f"  {rel}: {n} strings")
        except Exception as exc:
            fail_count += 1
            print(f"  [warn] {rel}: {exc}")
            shutil.copy2(ybn, out_path)

    # Copy system files unchanged
    for sf in sys_files:
        rel = os.path.relpath(sf, extracted)
        out_path = os.path.join(patched, rel)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        shutil.copy2(sf, out_path)

    print(f"  total: {total_strings} strings translated, {fail_count} files failed")

    # [7/8] Build patch YPF and place it
    print(f"\n[7/8] Building patch archive (mode={args.mode})...")
    patch_dest_dir = (
        os.path.join(eng_dir, "pac") if layout == "pac" else eng_dir
    )
    os.makedirs(patch_dest_dir, exist_ok=True)

    if args.mode == "patch":
        slot_name = next_patch_slot(patch_dest_dir)
        out_ypf = os.path.join(patch_dest_dir, slot_name)
    elif args.mode == "zzz":
        out_ypf = os.path.join(patch_dest_dir, "zzz_eng.ypf")
    else:  # replace
        original_name = os.path.basename(scripts_archive)
        out_ypf = os.path.join(patch_dest_dir, original_name)
        backup = out_ypf + ".jp_backup"
        if os.path.exists(out_ypf) and not os.path.exists(backup):
            shutil.move(out_ypf, backup)
            print(f"  backed up original to {os.path.basename(backup)}")

    create_patch_ypf(patched, out_ypf, info.version)
    print(f"  wrote {os.path.basename(out_ypf)} ({os.path.getsize(out_ypf)//1024} KB)")

    # [8/8] Cleanup
    print("\n[8/8] Cleanup...")
    shutil.rmtree(work_dir, ignore_errors=True)
    launcher = os.path.basename(game_exe)
    rel_patch = os.path.relpath(out_ypf, eng_dir)
    print(f"\n{'='*42}")
    print(f" DONE!")
    print(f" Play from : {os.path.basename(eng_dir)}\\{launcher}")
    print(f" Patch     : {rel_patch}")
    if args.mode == "patch":
        print(f" If English doesn't appear in-game, re-run with: --mode=zzz then --mode=replace")
    print(f"{'='*42}\n")


if __name__ == "__main__":
    main()
