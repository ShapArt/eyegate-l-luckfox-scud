from __future__ import annotations

from types import SimpleNamespace

from vision.service import _label_for_user_id


def test_label_prefers_name_then_login():
    user = SimpleNamespace(name="Alice", login="alice-login")

    label, known = _label_for_user_id(1, lambda _: user)

    assert label == "Alice"
    assert known is True


def test_label_unknown_when_missing_or_empty():
    label, known = _label_for_user_id(1, lambda _: None)
    assert label == "UNKNOWN"
    assert known is False

    user_no_name = SimpleNamespace(name="", login="")
    label2, known2 = _label_for_user_id(2, lambda _: user_no_name)
    assert label2 == "UNKNOWN"
    assert known2 is False

    label3, known3 = _label_for_user_id(None, lambda _: user_no_name)
    assert label3 == "UNKNOWN"
    assert known3 is False
