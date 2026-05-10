import sys, os, tempfile, shutil
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from yuris_translate import next_patch_slot


def _touch(path):
    with open(path, "wb") as f:
        f.write(b"x")


def test_next_slot_empty_dir():
    d = tempfile.mkdtemp()
    try:
        assert next_patch_slot(d) == "update1.ypf"
    finally:
        shutil.rmtree(d)


def test_next_slot_after_three():
    d = tempfile.mkdtemp()
    try:
        for i in (1, 2, 3):
            _touch(os.path.join(d, f"update{i}.ypf"))
        assert next_patch_slot(d) == "update4.ypf"
    finally:
        shutil.rmtree(d)


def test_next_slot_skips_gaps():
    """If update1 + update3 exist, next slot is update4 (don't reuse the gap)."""
    d = tempfile.mkdtemp()
    try:
        _touch(os.path.join(d, "update1.ypf"))
        _touch(os.path.join(d, "update3.ypf"))
        assert next_patch_slot(d) == "update4.ypf"
    finally:
        shutil.rmtree(d)


def test_next_slot_ignores_other_ypfs():
    d = tempfile.mkdtemp()
    try:
        _touch(os.path.join(d, "sn.ypf"))
        _touch(os.path.join(d, "cg.ypf"))
        assert next_patch_slot(d) == "update1.ypf"
    finally:
        shutil.rmtree(d)
