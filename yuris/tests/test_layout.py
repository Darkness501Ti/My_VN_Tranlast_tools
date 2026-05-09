import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from yuris_translate import detect_layout, find_scripts_archive, find_game_exe

JP = r"D:\game_install\501Translate\waiting to Tranlaste\JP"


def test_detect_layout_pac_terabeppin():
    assert detect_layout(os.path.join(JP, "Tera Beppin")) == "pac"


def test_detect_layout_pac_pleaserme():
    assert detect_layout(os.path.join(JP, "Please R Me!")) == "pac"


def test_detect_layout_flat_mousou():
    assert detect_layout(os.path.join(JP, "Mousou Haruna-san")) == "flat"


def test_find_scripts_archive_terabeppin():
    p = find_scripts_archive(os.path.join(JP, "Tera Beppin"))
    assert os.path.basename(p) == "sn.ypf"
    assert "pac" in p


def test_find_scripts_archive_pleaserme():
    p = find_scripts_archive(os.path.join(JP, "Please R Me!"))
    assert os.path.basename(p) == "sn.ypf"
    assert "pac" in p


def test_find_scripts_archive_mousou():
    p = find_scripts_archive(os.path.join(JP, "Mousou Haruna-san"))
    assert os.path.basename(p) == "ysbin.ypf"


def test_find_game_exe_terabeppin():
    p = find_game_exe(os.path.join(JP, "Tera Beppin"))
    assert os.path.basename(p).lower() == "terabeppin.exe"


def test_find_game_exe_skips_engine_settings():
    # エンジン設定.exe must NOT be picked as game.exe
    p = find_game_exe(os.path.join(JP, "Mousou Haruna-san"))
    assert os.path.basename(p).lower() == "mousou.exe"
