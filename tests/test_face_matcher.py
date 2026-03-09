from vision.embeddings import serialize_face_descriptor
from vision.matcher import MatchResult, best_match_for_embedding


class _User:
    def __init__(self, user_id: int, emb):
        self.id = user_id
        self.face_embedding = emb


def test_matcher_finds_best_within_threshold():
    users = [
        _User(1, serialize_face_descriptor([0.0, 0.0, 0.0])),
        _User(2, serialize_face_descriptor([0.1, 0.1, 0.1])),
    ]
    candidate = [0.1, 0.1, 0.1]
    result = best_match_for_embedding(candidate, users, threshold=0.5, metric="l2")
    assert isinstance(result, MatchResult)
    assert result.user_id == 2
    assert result.distance is not None


def test_matcher_returns_none_when_over_threshold():
    users = [_User(1, serialize_face_descriptor([1.0, 1.0, 1.0]))]
    candidate = [0.0, 0.0, 0.0]
    result = best_match_for_embedding(candidate, users, threshold=0.1, metric="l2")
    assert result is None


def test_matcher_supports_cosine_metric_within_threshold():
    users = [_User(1, serialize_face_descriptor([1.0, 0.0]))]
    candidate = [1.0, 0.0]
    result = best_match_for_embedding(candidate, users, threshold=0.1, metric="cosine")
    assert isinstance(result, MatchResult)
    assert result.user_id == 1
    assert result.distance is not None and result.distance <= 0.1


def test_matcher_cosine_over_threshold_returns_none():
    users = [_User(1, serialize_face_descriptor([1.0, 0.0]))]
    candidate = [0.0, 1.0]
    result = best_match_for_embedding(candidate, users, threshold=0.1, metric="cosine")
    assert result is None
