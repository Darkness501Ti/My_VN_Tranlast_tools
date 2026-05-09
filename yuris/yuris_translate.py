#!/usr/bin/env python3
"""YU-RIS VN Auto-Translation Tool (yuri + ypf-repacker.exe + Sugoi)."""

import os
import sys
import unicodedata
import glob

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
