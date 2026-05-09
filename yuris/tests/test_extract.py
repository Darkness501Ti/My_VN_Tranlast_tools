import sys, os, tempfile, shutil
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from yuris_translate import extract_ypf, find_scripts_archive

JP = r"D:\game_install\501Translate\waiting to Tranlaste\JP"


def _count_ybn(out_dir):
    n = 0
    for root, _, files in os.walk(out_dir):
        n += sum(1 for f in files if f.lower().endswith(".ybn"))
    return n


def test_extract_pleaserme():
    src = find_scripts_archive(os.path.join(JP, "Please R Me!"))
    out = tempfile.mkdtemp(prefix="ypf_extract_test_")
    try:
        extract_ypf(src, out)
        assert _count_ybn(out) >= 200, f"expected 200+ .ybn, got {_count_ybn(out)}"
    finally:
        shutil.rmtree(out, ignore_errors=True)


def test_extract_terabeppin():
    src = find_scripts_archive(os.path.join(JP, "Tera Beppin"))
    out = tempfile.mkdtemp(prefix="ypf_extract_test_")
    try:
        extract_ypf(src, out)
        assert _count_ybn(out) >= 250, f"expected 250+ .ybn, got {_count_ybn(out)}"
    finally:
        shutil.rmtree(out, ignore_errors=True)


def test_extract_mousou():
    src = find_scripts_archive(os.path.join(JP, "Mousou Haruna-san"))
    out = tempfile.mkdtemp(prefix="ypf_extract_test_")
    try:
        extract_ypf(src, out)
        assert _count_ybn(out) >= 100, f"expected 100+ .ybn, got {_count_ybn(out)}"
    finally:
        shutil.rmtree(out, ignore_errors=True)
