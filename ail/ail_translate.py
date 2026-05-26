"""Ail Soft engine translator — engine-safe Japanese -> English for kouhouDL etc.

Pipeline (12 steps):
  1.  Locate game files in cwd or ancestor (sall.snl + .exe)
  2.  Create <game>_ENG_ver/ copy of full game
  3.  Wait for / start Sugoi server, poll until ready
  4.  Read sall.snl
  5.  Decompress each LZSS-packed entry
  6.  For each entry: find the dense strings region (heuristic) and
       extract only strings INSIDE that cluster — strings detected in
       the bytecode region are false positives and patching them
       corrupts opcodes (engine raises "Scenario Code decode error").
  7.  Parse ruby annotations [reading]base — skip readings, translate
       base text only.
  8.  Strip control chars (\\r \\n) from translation input.
  9.  Batch-translate via Sugoi (batch_size = 1024).
  10. Encode English as full-width Latin in Shift-JIS (2 bytes/char,
       0xFF01-0xFF5E unicode range maps cleanly to SJIS double-byte).
       Pad with full-width space (\\x81\\x40) to JP byte length, drop
       brackets [ ] that would re-trigger ruby parser.
  11. Replace in-place — preserves all offset references.
  12. Re-compress with ALL-LITERAL LZSS (engine-safe) and write back.
"""
from __future__ import annotations
import os
import sys
import json
import time
import shutil
import struct
import socket
import subprocess
import urllib.request
from pathlib import Path
from typing import List, Tuple, Dict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ail_lzss import (
    read_archive, write_archive, decode_entry, lzss_pack_all_literal,
)

# --------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------
BATCH_SIZE = 1024
SUGOI_URL = "http://localhost:14366/"
SUGOI_START_BAT = r"D:\game_install\501Translate\tools\sugoi\startServer-CUDA.bat"
SUGOI_BOOT_TIMEOUT = 180

# Strings region detection
MIN_STRING_BYTES = 4       # min length of an SJIS run to be considered a string
REGION_MAX_GAP   = 16      # max byte-gap between strings inside a region

# Encoding mode: 'fullwidth' is engine-safe (every char = 2 SJIS bytes).
# 'ascii' attempts half-width (single byte per char) but the engine may
# fail to render it — leave 'fullwidth' on for safety.
ENCODING_MODE = "fullwidth"


# --------------------------------------------------------------------
# Sugoi client
# --------------------------------------------------------------------

def sugoi_is_up() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 14366), timeout=1.5):
            return True
    except OSError:
        return False


def sugoi_ensure_running() -> None:
    if sugoi_is_up():
        return
    if not os.path.isfile(SUGOI_START_BAT):
        print(f"[!] Sugoi start bat not found: {SUGOI_START_BAT}")
        sys.exit(1)
    print(f"[+] Launching Sugoi ...")
    subprocess.Popen(
        ["cmd", "/c", "start", "", "/MIN", SUGOI_START_BAT],
        cwd=os.path.dirname(SUGOI_START_BAT),
        close_fds=True,
    )
    t0 = time.time()
    while time.time() - t0 < SUGOI_BOOT_TIMEOUT:
        if sugoi_is_up():
            try:
                sugoi_translate(["test"])
                print(f"[+] Sugoi ready ({int(time.time()-t0)}s)")
                return
            except Exception:
                pass
        time.sleep(2)
    print("[!] Sugoi failed to start"); sys.exit(1)


def sugoi_translate(texts: List[str]) -> List[str]:
    if not texts:
        return []
    body = json.dumps({"message": "translate sentences", "content": texts}).encode("utf-8")
    req = urllib.request.Request(SUGOI_URL, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        result = json.loads(r.read().decode("utf-8"))
    if not isinstance(result, list) or len(result) != len(texts):
        raise RuntimeError(f"Sugoi length mismatch: {len(result) if hasattr(result,'__len__') else '?'} vs {len(texts)}")
    return [str(x) for x in result]


# --------------------------------------------------------------------
# SJIS string scanner
# --------------------------------------------------------------------

def _is_sjis_lead(b: int) -> bool:
    return 0x81 <= b <= 0x9F or 0xE0 <= b <= 0xFC

def _is_sjis_trail(b: int) -> bool:
    return 0x40 <= b <= 0xFC and b != 0x7F


def extract_sjis_strings(payload: bytes, min_bytes: int = MIN_STRING_BYTES) -> List[Tuple[int, int, str]]:
    """Find maximal runs of valid SJIS double-byte chars."""
    out: List[Tuple[int, int, str]] = []
    i, n = 0, len(payload)
    while i < n:
        b = payload[i]
        if _is_sjis_lead(b) and i + 1 < n and _is_sjis_trail(payload[i + 1]):
            start = i
            while i + 1 < n and _is_sjis_lead(payload[i]) and _is_sjis_trail(payload[i + 1]):
                i += 2
            length = i - start
            if length >= min_bytes:
                try:
                    s = payload[start:i].decode("shift_jis")
                    out.append((start, length, s))
                except UnicodeDecodeError:
                    pass
        else:
            i += 1
    return out


def find_strings_region(strs: List[Tuple[int, int, str]], max_gap: int = REGION_MAX_GAP) -> List[Tuple[int, int, str]]:
    """Return ALL real string clusters (handles entries with multiple regions).

    Real string regions have the engine's `00 00` separator between strings,
    so median inter-string gap == 2. Bytecode false-positives (SJIS-looking
    bytes inside opcode parameters) form clusters with random gaps. Filter:
      - cluster has >= 3 consecutive strings (intra-gap <= max_gap)
      - cluster's median gap <= 4 (allow 2-byte separators + 4-byte ruby)

    This replaced the previous 'last suffix only' heuristic which missed
    early-entry string regions when the bytecode interleaved two clusters
    (e.g. sakurakoDL entry 51 had a missed dialogue cluster at 0x05a2
    before the bytecode-2 section + main cluster at 0x0ae3).
    """
    if not strs:
        return []
    # group adjacent strings into clusters
    clusters = []
    current = [strs[0]]
    for i in range(1, len(strs)):
        gap = strs[i][0] - (current[-1][0] + current[-1][1])
        if gap <= max_gap:
            current.append(strs[i])
        else:
            clusters.append(current)
            current = [strs[i]]
    clusters.append(current)

    out: List[Tuple[int, int, str]] = []
    for c in clusters:
        if len(c) < 3:
            continue
        gaps = [c[i+1][0] - (c[i][0] + c[i][1]) for i in range(len(c) - 1)]
        if not gaps:
            continue
        median_gap = sorted(gaps)[len(gaps) // 2]
        if median_gap > 4:
            continue
        out.extend(c)
    return out


# --------------------------------------------------------------------
# Ruby [reading]base parsing
# --------------------------------------------------------------------

def classify_strings_in_region(payload: bytes, region: List[Tuple[int, int, str]]) -> List[Tuple[int, int, str, str]]:
    """Mark each string as 'base' (translatable), 'ruby', or 'voice_tag' (skip).

    Three skip conditions:

    1. Ruby annotation `[reading]base_text` — `[` (0x5B) before and `]` (0x5D)
       after means this is a furigana reading, not user-visible text. Translating
       it duplicates the base text and breaks the bracket pairing.

    2. Voice/scene tag — when an ASCII run of >= 3 chars (e.g. ``a04_``,
       ``vstart(SE_``, ``rg(N,N) ``) immediately precedes the SJIS string,
       the engine treats the SJIS as a SCENE IDENTIFIER for voice lookup.
       Translating it breaks the engine's voice-file mapping → no voice
       auto-plays. Observed in sakurakoDL but not kouhouDL — engine evolved
       between 2009 and 2014.

    Returns list of (offset, length, decoded, role) where role in
    {"base", "ruby", "voice_tag"}.
    """
    result = []
    for off, ln, text in region:
        b_before = payload[off - 1] if off > 0 else 0
        b_after  = payload[off + ln] if off + ln < len(payload) else 0
        raw = payload[off:off + ln]
        # 1. ruby
        if b_before == 0x5B and b_after == 0x5D:
            result.append((off, ln, text, "ruby"))
            continue
        # 2. voice/scene tag: ASCII run of >=3 chars immediately before
        ascii_run_len = 0
        i = off - 1
        while i >= 0 and ascii_run_len < 16:
            c = payload[i]
            if 0x20 <= c <= 0x7E and c not in (0x5B, 0x5D):
                ascii_run_len += 1
                i -= 1
            else:
                break
        if ascii_run_len >= 3:
            result.append((off, ln, text, "voice_tag"))
            continue
        # 3. character name tag 【XXX】 (full-width brackets)
        # 【 = 0x81 0x79, 】 = 0x81 0x7A in Shift-JIS. Some engines
        # (sakurakoDL, 2014) use the speaker name as a voice lookup key,
        # so translating these breaks voice auto-play.
        if ln >= 4 and raw[:2] == b'\x81\x79' and raw[-2:] == b'\x81\x7A':
            result.append((off, ln, text, "char_tag"))
            continue
        # default
        result.append((off, ln, text, "base"))
    return result


# --------------------------------------------------------------------
# English -> SJIS encoding (full-width Latin)
# --------------------------------------------------------------------

# Sanitize EN text for safety in the ruby parser and SJIS encoder
def sanitize_english(s: str) -> str:
    s = " ".join(s.split())  # collapse whitespace
    # strip characters that could confuse the engine
    s = s.replace("[", "(").replace("]", ")")
    # drop any non-ASCII from Sugoi output (sometimes leaks Japanese)
    s = s.encode("ascii", errors="ignore").decode("ascii")
    return s


def english_to_halfwidth_sjis(text: str, slot_bytes: int) -> bytes:
    """Encode ASCII English as half-width Latin SJIS (1 byte per char).

    ASCII 0x20-0x7E is identity-mapped in Shift-JIS (single-byte chars).
    Gives 2x byte budget vs full-width Latin. Pads with 0x20 (regular space)
    which renders invisibly (no big empty boxes).
    """
    text = sanitize_english(text)
    raw = text.encode("ascii", errors="ignore")

    # truncate at word boundary if too long
    while len(raw) > slot_bytes:
        if b" " in raw[-12:]:
            i = raw.rfind(b" ")
            raw = raw[:i].rstrip()
        else:
            raw = raw[:slot_bytes].rstrip()
            break
    if len(raw) < slot_bytes:
        raw = raw + b" " * (slot_bytes - len(raw))
    elif len(raw) > slot_bytes:
        raw = raw[:slot_bytes]
    assert len(raw) == slot_bytes, f"slot fit failed: {len(raw)} vs {slot_bytes}"
    return raw


# alias kept for back-compat with older mode flag
english_to_fullwidth_sjis = english_to_halfwidth_sjis


# --------------------------------------------------------------------
# Archive translation
# --------------------------------------------------------------------

def translate_snl(snl_path: Path, out_path: Path) -> Dict:
    print(f"[+] Reading {snl_path}")
    count, sizes, blobs = read_archive(str(snl_path))

    print(f"[+] Decompressing {count} entries...")
    entry_data: List[dict] = []
    all_strings: List[str] = []
    all_refs: List[Tuple[int, int]] = []   # (entry_idx, region_idx)

    skipped_false_positives = 0
    skipped_ruby = 0
    skipped_voice_tag = 0
    skipped_char_tag = 0

    for idx, blob in enumerate(blobs):
        if not blob:
            entry_data.append({"empty": True})
            continue
        payload, info = decode_entry(blob)
        if not info.get("packed"):
            entry_data.append({"empty": False, "packed": False, "raw": blob})
            continue
        gross = extract_sjis_strings(payload)
        region = find_strings_region(gross)
        skipped_false_positives += len(gross) - len(region)

        classified = classify_strings_in_region(payload, region)

        translatable_indices: List[int] = []
        for ridx, (off, ln, text, role) in enumerate(classified):
            if role == "ruby":
                skipped_ruby += 1
                continue
            if role == "voice_tag":
                skipped_voice_tag += 1
                continue
            if role == "char_tag":
                skipped_char_tag += 1
                continue
            translatable_indices.append(ridx)
            all_refs.append((idx, ridx))
            all_strings.append(text)

        entry_data.append({
            "empty": False,
            "packed": True,
            "payload": bytearray(payload),
            "classified": classified,
            "translatable_indices": translatable_indices,
        })

    print(f"[+] Extracted {len(all_strings)} translatable strings "
          f"({skipped_false_positives} bytecode false-positives skipped, "
          f"{skipped_ruby} ruby readings skipped, "
          f"{skipped_voice_tag} voice/scene tags skipped, "
          f"{skipped_char_tag} character name tags skipped)")

    sugoi_ensure_running()
    translated: List[str] = []
    t0 = time.time()
    for batch_start in range(0, len(all_strings), BATCH_SIZE):
        batch = all_strings[batch_start: batch_start + BATCH_SIZE]
        print(f"  translating batch {batch_start//BATCH_SIZE+1}/"
              f"{(len(all_strings)+BATCH_SIZE-1)//BATCH_SIZE}  "
              f"({batch_start}/{len(all_strings)})", flush=True)
        try:
            batch_out = sugoi_translate(batch)
        except Exception as e:
            print(f"  [!] batch failed: {e} -- retrying"); time.sleep(2)
            batch_out = sugoi_translate(batch)
        translated.extend(batch_out)
    print(f"[+] Translation done in {int(time.time()-t0)}s")

    assert len(translated) == len(all_strings)

    print(f"[+] Patching entry payloads (in-place, fullwidth SJIS)...")
    ent_to_replacements: Dict[int, List[Tuple[int, int, str]]] = {}
    for (entry_idx, ridx), en_text in zip(all_refs, translated):
        cls = entry_data[entry_idx]["classified"][ridx]
        off, ln, jp, role = cls
        ent_to_replacements.setdefault(entry_idx, []).append((off, ln, en_text))

    for entry_idx, replacements in ent_to_replacements.items():
        e = entry_data[entry_idx]
        payload = e["payload"]
        for off, ln, en in replacements:
            new_bytes = english_to_halfwidth_sjis(en, ln)
            payload[off: off + ln] = new_bytes
        e["payload"] = payload

    print(f"[+] Recompressing entries (all-literal LZSS)...")
    new_blobs: List[bytes] = []
    new_sizes: List[int] = []
    for idx, blob in enumerate(blobs):
        if not blob:
            new_blobs.append(b'')
            new_sizes.append(0)
            continue
        e = entry_data[idx]
        if e.get("packed"):
            payload = bytes(e["payload"])
            packed = lzss_pack_all_literal(payload)
            entry = struct.pack("<HI", 1, len(payload)) + packed
        else:
            entry = e["raw"]
        new_blobs.append(entry)
        new_sizes.append(len(entry))

    print(f"[+] Writing {out_path}")
    write_archive(str(out_path), new_sizes, new_blobs)

    return {
        "entries": count,
        "strings_translated": len(all_strings),
        "false_positives_skipped": skipped_false_positives,
        "ruby_skipped": skipped_ruby,
        "voice_tag_skipped": skipped_voice_tag,
        "char_tag_skipped": skipped_char_tag,
        "input_bytes": snl_path.stat().st_size,
        "output_bytes": out_path.stat().st_size,
    }


# --------------------------------------------------------------------
# Orchestrator
# --------------------------------------------------------------------

def find_game_dir() -> Path:
    cwd = Path(os.getcwd())
    if (cwd / "sall.snl").is_file():
        return cwd
    p = Path(__file__).resolve().parent
    while p != p.parent:
        if (p / "sall.snl").is_file():
            return p
        p = p.parent
    print("[!] No sall.snl found in cwd or ancestors")
    sys.exit(1)


def main() -> int:
    game_dir = find_game_dir()
    game_name = game_dir.name
    eng_dir = game_dir.parent / f"{game_name}_ENG_ver"
    print(f"[+] Game dir : {game_dir}")
    print(f"[+] Output   : {eng_dir}")

    if eng_dir.exists():
        print(f"[+] Output dir exists, skipping full copy (delete to refresh)")
    else:
        print(f"[+] Copying full game directory ...")
        shutil.copytree(str(game_dir), str(eng_dir))

    src_snl = game_dir / "sall.snl"
    dst_snl = eng_dir / "sall.snl"
    stats = translate_snl(src_snl, dst_snl)

    print()
    print("=" * 60)
    print("DONE")
    print(f"  entries          : {stats['entries']}")
    print(f"  strings          : {stats['strings_translated']}")
    print(f"  false-pos skipped: {stats['false_positives_skipped']}")
    print(f"  ruby skipped     : {stats['ruby_skipped']}")
    print(f"  voice tags kept  : {stats['voice_tag_skipped']}")
    print(f"  char tags kept   : {stats['char_tag_skipped']}")
    print(f"  sall.snl bytes   : {stats['input_bytes']:,} -> {stats['output_bytes']:,}")
    print(f"  English version  : {eng_dir}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
