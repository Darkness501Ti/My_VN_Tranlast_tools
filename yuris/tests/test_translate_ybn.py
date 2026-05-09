import sys, os, glob, tempfile, shutil
from unittest import mock
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from yuris_translate import (
    extract_ypf, find_script_key, find_scripts_archive, translate_ybn,
)

JP = r"D:\game_install\501Translate\waiting to Tranlaste\JP"


def _find_smallest_yst_with_text(work_dir, script_key):
    """Find a yst*.ybn that has at least 1 Japanese string."""
    from ybn_patcher import ybn_load_strings
    from yuris_translate import is_japanese
    candidates = sorted(
        glob.glob(os.path.join(work_dir, "**", "yst[0-9]*.ybn"), recursive=True),
        key=os.path.getsize,
    )
    for path in candidates:
        with open(path, "rb") as f:
            raw = f.read()
        strings = ybn_load_strings(raw, script_key)
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
        target = _find_smallest_yst_with_text(work, key)
        assert target is not None, "no yst with Japanese strings found"
        out = target + ".translated"

        # Mock Sugoi: return ASCII placeholder of similar length
        def fake_translate(texts):
            return ["test " + str(i) for i in range(len(texts))]

        with mock.patch("yuris_translate.translate_batch", side_effect=fake_translate):
            n = translate_ybn(target, out, key)

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
            strs = ybn_load_strings(raw, key)
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
        n = translate_ybn(target, out, key)
        assert n == 0
        with open(target, "rb") as f1, open(out, "rb") as f2:
            assert f1.read() == f2.read(), "zero-strings case must be byte-identical"
    finally:
        shutil.rmtree(work, ignore_errors=True)
