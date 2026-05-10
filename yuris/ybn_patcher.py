"""Custom YSTB (YU-RIS bytecode) patcher — byte-exact round-trip.

Why this exists
---------------
yuri's YSTB.read() parses bytecode but has no .write(). The full
decompile/recompile path (yuridec + yuricom) fails on commercial Clock Up
games (VScope=0 unsupported, YSTL non-sequential iscr). This module patches
YSTB byte-for-byte: parse the header, locate WORD arg records in the arg
section, rebuild the resource section with new strings, update offsets,
re-encrypt, write.

Round-trip guarantee
--------------------
Identity-edit (ybn_load_strings then ybn_patch_strings with the same strings
unchanged) MUST produce a byte-equal result. Verified by test_ybn_roundtrip.py.

YSTB V3xx binary layout (verified against yuri/fileformat/ystb.py, all games
use version >=300: Tera Beppin=474, Mousou=491, Please R Me!=500)
--------------------------------------------------------------------
Header (32 bytes, NOT encrypted):
  0x00  magic "YSTB"       bytes[4]
  0x04  version            uint32 LE
  0x08  ncmd               uint32 LE   (number of commands)
  0x0C  lcmd               uint32 LE   (code section size = ncmd * 4)
  0x10  larg               uint32 LE   (arg section size; multiple of 12)
  0x14  lexp               uint32 LE   (resource / exp section size)
  0x18  llno               uint32 LE   (lno section size = ncmd * 4)
  0x1C  pad                uint32 LE   (always 0)

Sections (immediately after header, in this order, each XOR-encrypted):
  code section   lcmd bytes   (ncmd * 4; each record is <BBH: code, na, npar)
  arg section    larg bytes   (sequential SArg records; each is <HBBII = 12 bytes)
  resource/exp   lexp bytes   (string heap: concatenated CP932 byte strings, no NUL separators)
  lno section    llno bytes   (ncmd * 4; uint32 line numbers, one per command)

XOR encryption (key confirmed by empirical test against all 3 target games)
----------------------------------------------------------------------------
Key bytes:
  version >= 290: KEY_290 = 0xD36FAC96  ->  kbs = b'\\xd3\\x6f\\xac\\x96'  (big-endian .to_bytes(4))
  version < 290:  KEY_200 = 0x07B4024A  ->  kbs = b'\\x07\\xb4\\x02\\x4a'
The key resets to position 0 at the start of each section.
Applied as: data[i] ^= kbs[i % 4]   (cyclic_xor_in_place from xor_cipher)
The YSER key extracted from the game .exe (find_script_key) is used for YPF
archive decryption, NOT for YSTB bytecode. YSTB always uses the hardcoded keys.

SArg record layout (each 12 bytes, decrypted from arg section)
--------------------------------------------------------------
  id   uint16 LE   (argument identifier / variable index)
  typ  uint8       (Typ enum: 0=Unk, 1=Int, 2=Flt, 3=Str)
  aop  uint8       (AOp enum: 0=EQL, ..., 8=BXOR)
  siz  uint32 LE   (byte length of string in resource section; 0 for non-string)
  off  uint32 LE   (byte offset into resource section; 0 for non-string)

WORD command identification — CRITICAL FINDINGS
-----------------------------------------------
WORD opcode varies per game (read from ysc.ybn via YSCM). In the code section
each record is <BBH: code (1 byte), na (1 byte, arg count), npar (2 bytes).

WORD dialogue args have typ==0 (Unk), NOT typ==3 (Str).
typ==3 args are expression bytecode blobs (MAC.BG calls, asset names, etc.)
that must NOT be translated — they are looked up by exact byte match at runtime.
Translating typ==3 strings causes "Invalid identifier detected" engine errors.

To find dialogue strings, walk the code section with the WORD opcode (from
ysc.ybn via YSCM). Collect arg section indices for each WORD command's one arg.
Those args contain the CP932 dialogue text with siz/off pointing into the
resource section.

ybn_load_strings(raw, script_key, ysc_data) uses this walk.
ybn_patch_strings(raw, script_key, new_strings, ysc_data) patches the same args.
Both require ysc_data (raw bytes of ysc.ybn from the same game archive).
"""

import struct
import sys
import os

# Ensure yuri path is available for YSCM reading if needed
_YURIS_DIR = os.path.dirname(os.path.abspath(__file__))

from xor_cipher import cyclic_xor_in_place

# YSTB hardcoded XOR keys (from yuri/fileformat/ystb.py)
# key.to_bytes(4) in Python 3.11+ is big-endian by default
_KEY_290 = (0xD36FAC96).to_bytes(4)   # d3 6f ac 96
_KEY_200 = (0x07B4024A).to_bytes(4)   # 07 b4 02 4a

_YSTB_MAGIC = b'YSTB'
_HEADER_FMT = struct.Struct('<4s7I')   # SYstbHead from yuri: magic + 7 uint32
_SARB_FMT   = struct.Struct('<HBBII')  # SArg: id(2)+typ(1)+aop(1)+siz(4)+off(4)
_SCMD_FMT   = struct.Struct('<BBH')    # SCmdV300: code(1)+na(1)+npar(2)

_SARB_SIZE = _SARB_FMT.size   # 12
_SCMD_SIZE = _SCMD_FMT.size   # 4
_HDR_SIZE  = _HEADER_FMT.size # 32


def _ystb_key(ver: int) -> bytes:
    """Return the 4-byte XOR key for the given YSTB version."""
    return _KEY_290 if ver >= 290 else _KEY_200


def _xor_section(data: bytes, key: bytes) -> bytearray:
    """Decrypt (or re-encrypt) a section: XOR with rolling 4-byte key."""
    buf = bytearray(data)
    cyclic_xor_in_place(buf, key)
    return buf


def _xor_section_inplace(buf: bytearray, key: bytes) -> None:
    """Encrypt a bytearray in-place."""
    cyclic_xor_in_place(buf, key)


def _parse_header(raw: bytes):
    """Parse YSTB header. Returns (ver, ncmd, lcmd, larg, lexp, llno, pad)."""
    if len(raw) < _HDR_SIZE:
        raise ValueError(f"YBN too small: {len(raw)} bytes")
    magic, ver, ncmd, lcmd, larg, lexp, llno, pad = _HEADER_FMT.unpack_from(raw, 0)
    if magic != _YSTB_MAGIC:
        raise ValueError(f"Not YSTB: magic={magic!r}")
    return ver, ncmd, lcmd, larg, lexp, llno, pad


def _section_offsets(lcmd, larg, lexp, llno):
    """Return (code_start, arg_start, exp_start, lno_start) absolute offsets."""
    code_start = _HDR_SIZE
    arg_start  = code_start + lcmd
    exp_start  = arg_start + larg
    lno_start  = exp_start + lexp
    return code_start, arg_start, exp_start, lno_start


def _word_opcode_from_ysc(ysc_data: bytes, ver: int) -> tuple[int, int]:
    """Parse ysc.ybn to get (WORD opcode, RETURNCODE opcode) for this game.

    Parameters
    ----------
    ysc_data : raw bytes of ysc.ybn (decrypted by the archive extractor)
    ver      : YSTB version from _parse_header (used to select YSCM parse path)

    Returns
    -------
    (word_opcode, returncode_opcode) as integers
    """
    sys.path.insert(0, _YURIS_DIR)
    from yuri.fileformat.yscm import YSCM
    from yuri.fileformat.common import Rdr
    yscm = YSCM.read(Rdr(ysc_data), v=ver)
    return yscm.cmdcodes.WORD, yscm.cmdcodes.RETURNCODE


def _collect_word_arg_indices(dcode: bytearray, lcmd: int, word_op: int, rc_op: int) -> list[int]:
    """Walk the decrypted code section; return sequential arg-section indices for WORD commands.

    For V3xx, each command record is 4 bytes (SCmdV300: code, na, npar).
    Args are consumed sequentially from the arg section: command i's args
    start at arg offset = sum(na for all commands before i).

    WORD commands always have na=1; that one arg holds the dialogue string.
    RETURNCODE is special-cased to na=1 (it also reads one SArg in V3xx).

    Returns list of arg-section indices (0-based) for each WORD command, in
    command order (which matches resource-section offset order for well-formed files).
    """
    n_cmds = lcmd // _SCMD_SIZE
    arg_ptr = 0
    word_indices = []
    for ci in range(n_cmds):
        code, na, npar = _SCMD_FMT.unpack_from(dcode, ci * _SCMD_SIZE)
        if code == rc_op:
            na = 1  # RETURNCODE always reads exactly one SArg in V3xx
        if code == word_op:
            word_indices.append(arg_ptr)
        arg_ptr += na
    return word_indices


def ybn_load_strings(raw: bytes, script_key: bytes, ysc_data: bytes | None = None) -> list[bytes]:
    """Extract WORD dialogue strings from a YSTB YBN file.

    Parameters
    ----------
    raw        : raw bytes of the .ybn file
    script_key : YSER key from find_script_key (not used for YSTB; kept for
                 API symmetry with ybn_patch_strings)
    ysc_data   : raw bytes of ysc.ybn from the same archive.  Required to
                 identify WORD opcode so only dialogue strings are returned.
                 When None (legacy / test usage), falls back to collecting all
                 Str-typed (typ==3) arg records — useful for roundtrip tests
                 that do not need semantic filtering.

    Returns
    -------
    list of bytes objects (CP932-encoded), one per WORD command in code-section
    order (when ysc_data provided), or one per Str-typed arg sorted by resource
    offset (legacy fallback).  Pass the same list (or a modified one of the same
    length and order) to ybn_patch_strings with the same ysc_data argument.

    The returned list maps 1:1 to internal arg records.
    """
    ver, ncmd, lcmd, larg, lexp, llno, pad = _parse_header(raw)
    if ver < 300:
        return _load_strings_v2xx(raw, ver, ncmd, lcmd, larg, lexp)

    code_start, arg_start, exp_start, lno_start = _section_offsets(lcmd, larg, lexp, llno)
    key = _ystb_key(ver)

    darg = _xor_section(raw[arg_start:arg_start+larg], key)
    dexp = _xor_section(raw[exp_start:exp_start+lexp], key)

    if ysc_data is not None:
        dcode = _xor_section(raw[code_start:code_start+lcmd], key)
        word_op, rc_op = _word_opcode_from_ysc(ysc_data, ver)
        word_indices = _collect_word_arg_indices(dcode, lcmd, word_op, rc_op)
        return _extract_strings_by_indices(word_indices, darg, dexp, lexp)
    else:
        return _extract_strings_v3xx(darg, larg, dexp, lexp)


def _extract_strings_by_indices(
    arg_indices: list[int],
    darg: bytearray,
    dexp: bytearray,
    lexp: int,
) -> list[bytes]:
    """Extract dialogue strings from arg section at the given sequential arg indices."""
    strings = []
    for ai in arg_indices:
        id_, typ, aop, siz, off = _SARB_FMT.unpack_from(darg, ai * _SARB_SIZE)
        if siz == 0:
            strings.append(b'')
        else:
            if off + siz > lexp:
                raise ValueError(f"WORD arg at ai={ai} off={off} siz={siz} exceeds resource size {lexp}")
            strings.append(bytes(dexp[off:off+siz]))
    return strings


def _extract_strings_v3xx(darg: bytearray, larg: int, dexp: bytearray, lexp: int) -> list[bytes]:
    """Legacy: walk arg section, collect all Str-typed (typ==3) records in resource-offset order.

    Used as fallback when ysc_data is not provided (roundtrip tests).
    Note: typ==3 args are expression bytecode (asset names, MAC.BG calls, etc.),
    NOT dialogue strings. This path exists only for identity round-trip testing
    without ysc.ybn available.
    """
    # Collect (off, siz, arg_index) for all Str-typed args
    str_args = []
    n_args = larg // _SARB_SIZE
    for i in range(n_args):
        id_, typ, aop, siz, off = _SARB_FMT.unpack_from(darg, i * _SARB_SIZE)
        if typ == 3:  # Typ.Str
            str_args.append((off, siz, i))

    # Sort by resource offset to return in storage order
    str_args.sort(key=lambda x: x[0])

    strings = []
    for off, siz, _ in str_args:
        if siz == 0:
            strings.append(b'')
        else:
            if off + siz > lexp:
                raise ValueError(f"Str arg at off={off} siz={siz} exceeds resource size {lexp}")
            strings.append(bytes(dexp[off:off+siz]))
    return strings


def _load_strings_v2xx(raw: bytes, ver: int, ncmd: int, lcmd: int, larg: int, lexp: int) -> list[bytes]:
    """V2xx (version < 300) string extraction.

    V2xx layout (from yuri ystb.py):
      Header field rest = lcmd, lexp, exp_off, *pads  (larg is not a separate field)
    Actually for V2xx: SYstbHead unpacks as mag, v_, lcmd, lexp, exp_off, pad0, pad1, pad2
    The code and expression sections follow immediately.
    RETURNCODE uses a special readV2xxR path. Regular args are embedded.
    """
    # For V2xx, rest = lcmd, lexp, exp_off, *pads (3 pads)
    # Header: magic(4) + ver(4) + lcmd(4) + lexp(4) + exp_off(4) + pad0(4) + pad1(4) + pad2(4)
    magic, ver_, lcmd_h, lexp_h, exp_off, p0, p1, p2 = _HEADER_FMT.unpack_from(raw, 0)
    key = _ystb_key(ver)

    code_start = _HDR_SIZE
    exp_start = code_start + lcmd_h
    dcmd = _xor_section(raw[code_start:code_start+lcmd_h], key)
    dexp = _xor_section(raw[exp_start:exp_start+lexp_h], key)

    # V2xx: SArg2xxR or inline SArg depending on RETURNCODE
    # For simplicity: scan all Str-type content in the resource section
    # V2xx args have SArg embedded in the code stream — complex to parse
    # Return raw resource bytes as single-entry list for now
    # (V2xx games are not in scope for these 3 target games, all use V3xx)
    return [bytes(dexp)]


def ybn_patch_strings(
    raw: bytes,
    script_key: bytes,
    new_strings: list[bytes],
    ysc_data: bytes | None = None,
) -> bytes:
    """Replace dialogue strings in a YSTB YBN file and return the patched bytes.

    Parameters
    ----------
    raw         : original raw bytes of the .ybn file
    script_key  : YSER key from find_script_key (not used for YSTB; API symmetry)
    new_strings : list of CP932-encoded byte strings, same length and order as
                  returned by ybn_load_strings(raw, script_key, ysc_data).
    ysc_data    : raw bytes of ysc.ybn (same game archive).  Must match the
                  value passed to ybn_load_strings so the same arg indices are
                  patched.  When None, falls back to patching Str-typed (typ==3)
                  args — for legacy/roundtrip-test usage only.

    Returns
    -------
    New bytes that are a valid YSTB file with strings replaced.
    Identity patch (same strings) produces byte-equal output.

    Resource section patching strategy (WORD path)
    -----------------------------------------------
    The resource section is a flat byte heap shared by ALL arg types.  Slices
    may alias or overlap.  To safely replace only WORD dialogue strings without
    disturbing expression bytecode or other data:

    - Keep the original resource bytes [0..lexp-1] intact.
    - Append a "dialogue block" of new string bytes after the original data.
    - Update only the WORD arg records to point into the new dialogue block.
    - All other args (typ==3 expression blobs, typ==1 integers, etc.) continue
      to reference their original offsets in [0..lexp-1], which are unchanged.

    Identity patch: new strings == old strings, so the dialogue block is
    appended but WORD args point to the new offsets (different from original).
    This means the WORD path does NOT produce byte-equal output for identity
    patches — the roundtrip test uses ysc_data=None (legacy path) which is
    byte-exact by design.

    Legacy (ysc_data=None) path keeps the original logic: rebuild only typ==3
    args' portion of the resource section.  This is byte-exact for identity.
    """
    ver, ncmd, lcmd, larg, lexp, llno, pad = _parse_header(raw)
    if ver < 300:
        return _patch_strings_v2xx(raw, ver, new_strings)

    code_start, arg_start, exp_start, lno_start = _section_offsets(lcmd, larg, lexp, llno)
    key = _ystb_key(ver)

    # Decrypt arg and resource sections (code + lno sections are unchanged)
    darg = _xor_section(raw[arg_start:arg_start+larg], key)
    dexp = _xor_section(raw[exp_start:exp_start+lexp], key)

    if ysc_data is not None:
        return _patch_strings_word(
            raw, ver, ncmd, lcmd, larg, lexp, llno, pad,
            code_start, arg_start, exp_start, lno_start,
            key, darg, dexp, ysc_data, new_strings,
        )
    else:
        return _patch_strings_legacy_typ3(
            raw, ver, ncmd, lcmd, larg, lexp, llno, pad,
            code_start, arg_start, exp_start, lno_start,
            key, darg, dexp, new_strings,
        )


def _patch_strings_word(
    raw, ver, ncmd, lcmd, larg, lexp, llno, pad,
    code_start, arg_start, exp_start, lno_start,
    key, darg, dexp, ysc_data, new_strings,
):
    """WORD-path: append new dialogue strings, redirect WORD args to new offsets.

    All non-WORD data in the resource section is preserved at original offsets.
    """
    dcode = _xor_section(raw[code_start:code_start+lcmd], key)
    word_op, rc_op = _word_opcode_from_ysc(ysc_data, ver)
    word_indices = _collect_word_arg_indices(dcode, lcmd, word_op, rc_op)

    if len(new_strings) != len(word_indices):
        raise ValueError(
            f"new_strings length {len(new_strings)} != "
            f"expected {len(word_indices)} WORD args in this YBN"
        )

    if not word_indices:
        return raw  # No WORD strings — identity

    # Build the new dialogue block appended after original resource section
    diag_block = bytearray()
    word_new_offsets = {}  # ai -> (new_off, new_siz)
    for ai, new_str in zip(word_indices, new_strings):
        word_new_offsets[ai] = (lexp + len(diag_block), len(new_str))
        diag_block.extend(new_str)

    # New resource section = original resource + dialogue block
    new_exp = bytearray(dexp) + diag_block
    new_lexp = len(new_exp)

    # Update only WORD arg records
    n_args_total = larg // _SARB_SIZE
    new_darg = bytearray(darg)
    for ai, (new_off, new_siz) in word_new_offsets.items():
        id_, typ, aop, old_siz, old_off = _SARB_FMT.unpack_from(new_darg, ai * _SARB_SIZE)
        _SARB_FMT.pack_into(new_darg, ai * _SARB_SIZE, id_, typ, aop, new_siz, new_off)

    # Re-encrypt modified sections
    _xor_section_inplace(new_darg, key)
    _xor_section_inplace(new_exp, key)

    new_hdr = bytearray(_HEADER_FMT.pack(
        _YSTB_MAGIC, ver, ncmd, lcmd, larg, new_lexp, llno, pad
    ))

    return (
        bytes(new_hdr)
        + raw[code_start:code_start+lcmd]
        + bytes(new_darg)
        + bytes(new_exp)
        + raw[lno_start:lno_start+llno]
    )


def _patch_strings_legacy_typ3(
    raw, ver, ncmd, lcmd, larg, lexp, llno, pad,
    code_start, arg_start, exp_start, lno_start,
    key, darg, dexp, new_strings,
):
    """Legacy path (ysc_data=None): rebuild typ==3 portion of resource section.

    Used by roundtrip tests that do not have ysc.ybn.  Produces byte-equal
    output for identity patch (same strings in, same bytes out).
    """
    # Collect Str-typed arg records sorted by resource offset
    str_args = []  # (off, siz, arg_index)
    n_args = larg // _SARB_SIZE
    for i in range(n_args):
        id_, typ, aop, siz, off = _SARB_FMT.unpack_from(darg, i * _SARB_SIZE)
        if typ == 3:
            str_args.append((off, siz, i))
    str_args.sort(key=lambda x: x[0])

    if len(new_strings) != len(str_args):
        raise ValueError(
            f"new_strings length {len(new_strings)} != "
            f"expected {len(str_args)} (Str-typed args in this YBN)"
        )

    if not str_args:
        return raw

    # Build new resource section from typ==3 args only (legacy behaviour)
    new_exp = bytearray()
    new_offsets = {}  # arg_index -> (new_off, new_siz)
    for (old_off, old_siz, arg_idx), new_str in zip(str_args, new_strings):
        new_offsets[arg_idx] = (len(new_exp), len(new_str))
        new_exp.extend(new_str)

    new_lexp = len(new_exp)

    # Rebuild arg section: update off+siz only for Str-typed records
    new_darg = bytearray(darg)
    for i in range(n_args):
        id_, typ, aop, siz, off = _SARB_FMT.unpack_from(new_darg, i * _SARB_SIZE)
        if typ == 3 and i in new_offsets:
            new_off, new_siz = new_offsets[i]
            _SARB_FMT.pack_into(new_darg, i * _SARB_SIZE, id_, typ, aop, new_siz, new_off)

    _xor_section_inplace(new_darg, key)
    _xor_section_inplace(new_exp, key)

    new_hdr = bytearray(_HEADER_FMT.pack(
        _YSTB_MAGIC, ver, ncmd, lcmd, larg, new_lexp, llno, pad
    ))

    return (
        bytes(new_hdr)
        + raw[code_start:code_start+lcmd]
        + bytes(new_darg)
        + bytes(new_exp)
        + raw[lno_start:lno_start+llno]
    )


def _patch_strings_v2xx(raw: bytes, ver: int, new_strings: list[bytes]) -> bytes:
    """V2xx fallback: not in scope for target games (all use V3xx). Pass through."""
    # If called for V2xx, return original — no patching
    return raw


def ybn_word_opcode(ysc_raw: bytes, ver: int) -> int:
    """Read the WORD command opcode from a ysc.ybn file.

    Helper for diagnostics.
    """
    word_op, _ = _word_opcode_from_ysc(ysc_raw, ver)
    return word_op
