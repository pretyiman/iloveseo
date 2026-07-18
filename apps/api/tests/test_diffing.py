from types import SimpleNamespace

from app.services.diffing import diff_result


def _result(score, codes):
    return SimpleNamespace(score=score, findings=[{"code": c} for c in codes])


def test_diff_result_none_when_no_previous():
    current = _result(80, ["a"])
    assert diff_result(current, None) is None


def test_diff_result_computes_score_delta():
    current = _result(90, [])
    previous = _result(70, [])
    diff = diff_result(current, previous)
    assert diff["score_delta"] == 20
    assert diff["previous_score"] == 70


def test_diff_result_detects_new_and_resolved_findings():
    current = _result(80, ["a", "b"])
    previous = _result(80, ["b", "c"])
    diff = diff_result(current, previous)
    assert diff["new_finding_codes"] == ["a"]
    assert diff["resolved_finding_codes"] == ["c"]


def test_diff_result_handles_none_scores():
    current = _result(None, [])
    previous = _result(80, [])
    diff = diff_result(current, previous)
    assert diff["score_delta"] is None
