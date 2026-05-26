"""Test: translate sakurakoDL using FULL-WIDTH Latin SJIS (every char = 2 bytes).

If voice works with fullwidth but breaks with halfwidth, the engine
disables voice when dialogue contains half-width ASCII (some engines do
this — they treat half-width as 'system text' that has no voice).

This re-uses the existing translator but with the fullwidth encoder.
"""
import os, sys, struct
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import ail_translate
# Monkey-patch the encoder to use fullwidth
ORIG = ail_translate.english_to_halfwidth_sjis

def fullwidth_encode(text, slot_bytes):
    """Encode ASCII as full-width Latin SJIS (2 bytes per char)."""
    text = ail_translate.sanitize_english(text)
    def encode(t):
        out = []
        for ch in t:
            c = ord(ch)
            if c == 0x20:
                out.append('　')  # fullwidth space
            elif 0x21 <= c <= 0x7E:
                out.append(chr(c - 0x20 + 0xFF00))
            else:
                out.append('?')
        return ''.join(out).encode('shift_jis', errors='replace')
    raw = encode(text)
    while len(raw) > slot_bytes:
        if ' ' in text[-12:]:
            text = text.rsplit(' ', 1)[0].rstrip()
        else:
            text = text[:-1].rstrip()
        if not text:
            raw = b''
            break
        raw = encode(text)
    if len(raw) < slot_bytes:
        pad = slot_bytes - len(raw)
        fw = pad // 2
        rem = pad - fw * 2
        raw = raw + b'\x81\x40' * fw + b' ' * rem
    return raw

ail_translate.english_to_halfwidth_sjis = fullwidth_encode
print("[+] Patched encoder to fullwidth Latin SJIS")
print("[+] Running translator (uses cached Sugoi)...")
import sys
sys.exit(ail_translate.main())
