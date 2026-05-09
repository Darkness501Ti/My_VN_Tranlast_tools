#!/usr/bin/env python3
"""YU-RIS VN Auto-Translation Tool (yuri + ypf-repacker.exe + Sugoi)."""

import os
import sys

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
