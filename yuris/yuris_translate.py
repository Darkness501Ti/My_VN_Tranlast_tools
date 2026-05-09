#!/usr/bin/env python3
"""YU-RIS VN Auto-Translation Tool (yuri + ypf-repacker.exe + Sugoi)."""

import os
import sys
import unicodedata

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
