import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from yuris_translate import probe_ypf

JP = r"D:\game_install\501Translate\waiting to Tranlaste\JP"


def test_probe_terabeppin_sn():
    info = probe_ypf(os.path.join(JP, "Tera Beppin", "pac", "sn.ypf"))
    assert info.version > 0
    assert info.entry_count > 0
    assert info.tool in ("yuri", "ypf-repacker.exe", "raw-header")


def test_probe_pleaserme_sn():
    info = probe_ypf(os.path.join(JP, "Please R Me!", "pac", "sn.ypf"))
    assert info.version > 0
    assert info.entry_count > 0


def test_probe_mousou_ysbin():
    info = probe_ypf(os.path.join(JP, "Mousou Haruna-san", "ysbin.ypf"))
    assert info.version > 0
    assert info.entry_count > 0
