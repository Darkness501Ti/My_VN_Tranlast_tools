import sys, os, glob, tempfile, shutil
from unittest import mock
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from yuris_translate import (
    extract_ypf, find_script_key, find_scripts_archive, translate_ybn,
)

JP = r"D:\game_install\501Translate\waiting to Tranlaste\JP"


def _load_ysc_data(work_dir):
    """Find and load ysc.ybn from an extracted archive directory."""
    for root, _, files in os.walk(work_dir):
        for f in files:
            if f.lower() == "ysc.ybn":
                with open(os.path.join(root, f), "rb") as fh:
                    return fh.read()
    return None


def _find_smallest_yst_with_text(work_dir, script_key, ysc_data):
    """Find a yst*.ybn that has at least 1 Japanese WORD dialogue string."""
    from ybn_patcher import ybn_load_strings
    from yuris_translate import is_japanese
    candidates = sorted(
        glob.glob(os.path.join(work_dir, "**", "yst[0-9]*.ybn"), recursive=True),
        key=os.path.getsize,
    )
    for path in candidates:
        with open(path, "rb") as f:
            raw = f.read()
        strings = ybn_load_strings(raw, script_key, ysc_data)
        for sjis in strings:
            try:
                text = sjis.decode("cp932")
            except UnicodeDecodeError:
                continue
            if is_japanese(text):
                return path
    return None


def test_translate_ybn_writes_modified_output():
    src_ypf = find_scripts_archive(os.path.join(JP, "Please R Me!"))
    exe = os.path.join(JP, "Please R Me!", "prm.exe")
    key = find_script_key(exe)

    work = tempfile.mkdtemp(prefix="tr_ybn_")
    try:
        extract_ypf(src_ypf, work)
        ysc_data = _load_ysc_data(work)
        assert ysc_data is not None, "ysc.ybn not found in extracted archive"

        target = _find_smallest_yst_with_text(work, key, ysc_data)
        assert target is not None, "no yst with Japanese WORD strings found"
        out = target + ".translated"

        # Mock Sugoi: return ASCII placeholder of similar length
        def fake_translate(texts):
            return ["test " + str(i) for i in range(len(texts))]

        with mock.patch("yuris_translate.translate_batch", side_effect=fake_translate):
            n = translate_ybn(target, out, key, ysc_data)

        assert os.path.isfile(out)
        assert n > 0, "expected at least 1 string translated"
        # Output should differ from input (we mutated strings)
        with open(target, "rb") as f1, open(out, "rb") as f2:
            assert f1.read() != f2.read(), "expected mutation when n>0"
    finally:
        shutil.rmtree(work, ignore_errors=True)


def test_translate_ybn_zero_strings_writes_identical_file():
    """If no Japanese strings, output should be byte-equal to input."""
    src_ypf = find_scripts_archive(os.path.join(JP, "Mousou Haruna-san"))
    exe = os.path.join(JP, "Mousou Haruna-san", "Mousou.exe")
    key = find_script_key(exe)

    work = tempfile.mkdtemp(prefix="tr_zero_")
    try:
        extract_ypf(src_ypf, work)
        ysc_data = _load_ysc_data(work)

        # Find a yst with NO Japanese (or smallest yst as proxy)
        candidates = sorted(
            glob.glob(os.path.join(work, "**", "yst[0-9]*.ybn"), recursive=True),
            key=os.path.getsize,
        )
        from ybn_patcher import ybn_load_strings
        from yuris_translate import is_japanese
        target = None
        for path in candidates:
            with open(path, "rb") as f:
                raw = f.read()
            strs = ybn_load_strings(raw, key, ysc_data)
            has_jp = False
            for sjis in strs:
                try:
                    if is_japanese(sjis.decode("cp932")):
                        has_jp = True
                        break
                except UnicodeDecodeError:
                    continue
            if not has_jp:
                target = path
                break
        if target is None:
            # All yst files have JP — skip this test
            import pytest
            pytest.skip("no yst file without Japanese found in Mousou Haruna-san")

        out = target + ".unchanged"
        n = translate_ybn(target, out, key, ysc_data)
        assert n == 0
        with open(target, "rb") as f1, open(out, "rb") as f2:
            assert f1.read() == f2.read(), "zero-strings case must be byte-identical"
    finally:
        shutil.rmtree(work, ignore_errors=True)


def test_non_word_strings_unchanged_after_translate():
    """Non-WORD strings (typ==3 expression blobs) must remain byte-identical
    in the patched output, even if they contain Japanese-looking bytes."""
    from ybn_patcher import (
        ybn_load_strings, ybn_patch_strings,
        _parse_header, _section_offsets, _ystb_key,
        _xor_section, _SARB_FMT, _SARB_SIZE,
    )
    from yuris_translate import is_japanese

    src_ypf = find_scripts_archive(os.path.join(JP, "Please R Me!"))
    exe = os.path.join(JP, "Please R Me!", "prm.exe")
    key = find_script_key(exe)

    work = tempfile.mkdtemp(prefix="tr_nonword_")
    try:
        extract_ypf(src_ypf, work)
        ysc_data = _load_ysc_data(work)
        assert ysc_data is not None

        # Find any yst file
        yst_files = sorted(
            glob.glob(os.path.join(work, "**", "yst[0-9]*.ybn"), recursive=True),
            key=os.path.getsize,
        )
        assert yst_files, "no yst files found"

        # Find a file that has typ==3 args (non-WORD expression blobs)
        target = None
        for path in yst_files[len(yst_files)//2:]:
            with open(path, "rb") as f:
                raw_orig = f.read()
            ver, ncmd, lcmd, larg, lexp, llno, pad = _parse_header(raw_orig)
            if ver < 300:
                continue
            _, arg_start, exp_start, _ = _section_offsets(lcmd, larg, lexp, llno)
            xkey = _ystb_key(ver)
            darg = _xor_section(raw_orig[arg_start:arg_start+larg], xkey)
            n_args = larg // _SARB_SIZE
            has_typ3 = any(
                _SARB_FMT.unpack_from(darg, i * _SARB_SIZE)[1] == 3
                for i in range(n_args)
            )
            if has_typ3:
                target = path
                break

        if target is None:
            import pytest
            pytest.skip("no yst file with typ==3 args found")

        with open(target, "rb") as f:
            raw_orig = f.read()

        # Translate with mocked Sugoi (only WORD strings should change)
        out = target + ".patched"

        def fake_translate(texts):
            return ["EN_" + str(i) for i in range(len(texts))]

        with mock.patch("yuris_translate.translate_batch", side_effect=fake_translate):
            translate_ybn(target, out, key, ysc_data)

        with open(out, "rb") as f:
            raw_patched = f.read()

        # Verify: typ==3 args in the patched file must have same data as original
        ver, ncmd, lcmd, larg, lexp, llno, pad = _parse_header(raw_orig)
        _, arg_start, exp_start, _ = _section_offsets(lcmd, larg, lexp, llno)
        xkey = _ystb_key(ver)

        darg_orig = _xor_section(raw_orig[arg_start:arg_start+larg], xkey)
        dexp_orig = _xor_section(raw_orig[exp_start:exp_start+lexp], xkey)

        darg_patched = _xor_section(raw_patched[arg_start:arg_start+larg], xkey)
        # Note: exp section in patched may be at a different offset if lexp changed
        _, arg_start_p, exp_start_p, _ = _section_offsets(lcmd, larg, len(raw_patched) - arg_start - larg, llno)
        # Re-derive from patched header
        ver_p, ncmd_p, lcmd_p, larg_p, lexp_p, llno_p, pad_p = _parse_header(raw_patched)
        _, arg_start_p, exp_start_p, _ = _section_offsets(lcmd_p, larg_p, lexp_p, llno_p)
        dexp_patched = _xor_section(raw_patched[exp_start_p:exp_start_p+lexp_p], xkey)

        n_args = larg // _SARB_SIZE
        mismatches = 0
        for i in range(n_args):
            id_, typ, aop, siz, off = _SARB_FMT.unpack_from(darg_orig, i * _SARB_SIZE)
            if typ == 3 and siz > 0:
                orig_blob = bytes(dexp_orig[off:off+siz])
                # Find where this blob is in the patched resource section
                id_p, typ_p, aop_p, siz_p, off_p = _SARB_FMT.unpack_from(darg_patched, i * _SARB_SIZE)
                if siz_p > 0:
                    patched_blob = bytes(dexp_patched[off_p:off_p+siz_p])
                    if orig_blob != patched_blob:
                        mismatches += 1
                        print(f"  MISMATCH ai={i}: orig={orig_blob!r} patched={patched_blob!r}")

        assert mismatches == 0, f"{mismatches} typ==3 (non-WORD) blobs were modified"

    finally:
        shutil.rmtree(work, ignore_errors=True)
