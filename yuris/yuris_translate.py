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

    Heuristic: in pac/ layout look for sn.ypf or ysbin.ypf (in that order).
    In flat layout look for ysbin.ypf at root. Falls back to the largest
    non-asset YPF (excludes cg/bgm/voice/se/cgsys/op/ed/bn/st/vo).
    """
    layout = detect_layout(game_dir)
    search_dir = os.path.join(game_dir, "pac") if layout == "pac" else game_dir
    for name in ("sn.ypf", "ysbin.ypf"):
        p = os.path.join(search_dir, name)
        if os.path.isfile(p):
            return p
    # Fallback heuristic
    asset_prefixes = ("cg", "bgm", "voice", "vo", "se", "cgsys",
                       "op", "ed", "bn", "st", "update")
    candidates = []
    for ypf in glob.glob(os.path.join(search_dir, "*.ypf")):
        name = os.path.basename(ypf).lower()
        if not any(name.startswith(p) for p in asset_prefixes):
            candidates.append(ypf)
    if candidates:
        candidates.sort(key=os.path.getsize, reverse=True)
        return candidates[0]
    raise FileNotFoundError(f"No script archive (sn.ypf / ysbin.ypf) in {search_dir}")


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
