import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from yuris_translate import find_script_key

JP = r"D:\game_install\501Translate\waiting to Tranlaste\JP"


def test_find_script_key_terabeppin():
    key = find_script_key(os.path.join(JP, "Tera Beppin", "terabeppin.exe"))
    assert isinstance(key, bytes)
    assert len(key) == 4


def test_find_script_key_pleaserme():
    key = find_script_key(os.path.join(JP, "Please R Me!", "prm.exe"))
    assert isinstance(key, bytes)
    assert len(key) == 4


def test_find_script_key_mousou():
    key = find_script_key(os.path.join(JP, "Mousou Haruna-san", "Mousou.exe"))
    assert isinstance(key, bytes)
    assert len(key) == 4
