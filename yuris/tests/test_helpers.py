import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from yuris_translate import is_japanese, ascii_fold


def test_is_japanese_hiragana():
    assert is_japanese("ありがとう") is True


def test_is_japanese_katakana():
    assert is_japanese("カタカナ") is True


def test_is_japanese_kanji():
    assert is_japanese("漢字") is True


def test_is_japanese_ascii():
    assert is_japanese("Hello world") is False


def test_is_japanese_mixed():
    assert is_japanese("Hello 世界") is True


def test_is_japanese_empty():
    assert is_japanese("") is False


def test_is_japanese_numbers():
    assert is_japanese("1234567890") is False


def test_ascii_fold_smart_quotes():
    assert ascii_fold("“Hello”") == '"Hello"'


def test_ascii_fold_em_dash():
    assert ascii_fold("yes—no") == "yes-no"


def test_ascii_fold_en_dash():
    assert ascii_fold("a–b") == "a-b"


def test_ascii_fold_diacritics():
    assert ascii_fold("café naïve") == "cafe naive"


def test_ascii_fold_ellipsis():
    assert ascii_fold("wait…") == "wait..."


def test_ascii_fold_pure_ascii_unchanged():
    assert ascii_fold("Hello, world!") == "Hello, world!"


def test_ascii_fold_japanese_brackets():
    assert ascii_fold("「yes」") == '"yes"'


def test_ascii_fold_japanese_period_comma():
    assert ascii_fold("hi。bye、ok") == "hi.bye,ok"
