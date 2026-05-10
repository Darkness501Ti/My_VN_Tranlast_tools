import sys, os, tempfile, shutil
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from yuris_translate import extract_ypf, create_patch_ypf, probe_ypf, find_scripts_archive

JP = r"D:\game_install\501Translate\waiting to Tranlaste\JP"


def _round_trip(game):
    src_ypf = find_scripts_archive(os.path.join(JP, game))
    src_info = probe_ypf(src_ypf)

    extract_dir = tempfile.mkdtemp(prefix=f"extract_{game[:4]}_")
    try:
        extract_ypf(src_ypf, extract_dir)
        new_ypf = tempfile.mktemp(prefix=f"patch_{game[:4]}_", suffix=".ypf")
        try:
            create_patch_ypf(extract_dir, new_ypf, src_info.version)
            assert os.path.isfile(new_ypf)
            assert os.path.getsize(new_ypf) > 0
            new_info = probe_ypf(new_ypf)
            assert new_info.entry_count == src_info.entry_count, (
                f"entry count mismatch for {game}: "
                f"{src_info.entry_count} vs {new_info.entry_count}"
            )
        finally:
            if os.path.exists(new_ypf):
                os.remove(new_ypf)
    finally:
        shutil.rmtree(extract_dir, ignore_errors=True)


def test_create_pleaserme():
    _round_trip("Please R Me!")


def test_create_terabeppin():
    _round_trip("Tera Beppin")


def test_create_mousou():
    _round_trip("Mousou Haruna-san")
