import sys, os
from unittest import mock
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from yuris_translate import translate_batch


def test_translate_batch_returns_list_same_length():
    fake_response = mock.Mock()
    fake_response.json.return_value = ["Hello", "World"]
    fake_response.raise_for_status = mock.Mock()
    with mock.patch("yuris_translate.requests.post", return_value=fake_response):
        out = translate_batch(["こんにちは", "世界"])
    assert out == ["Hello", "World"]


def test_translate_batch_returns_originals_on_error():
    with mock.patch("yuris_translate.requests.post", side_effect=Exception("boom")):
        out = translate_batch(["こんにちは"])
    assert out == ["こんにちは"]


def test_translate_batch_handles_short_response():
    fake_response = mock.Mock()
    fake_response.json.return_value = "single string"
    fake_response.raise_for_status = mock.Mock()
    with mock.patch("yuris_translate.requests.post", return_value=fake_response):
        out = translate_batch(["a", "b"])
    assert len(out) == 2
