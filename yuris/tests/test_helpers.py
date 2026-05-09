import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from yuris_translate import is_japanese


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
