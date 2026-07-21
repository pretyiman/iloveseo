from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.services.monitoring import compute_next_run_at
from app.services.monitoring_email import build_report_email_html


def _project(domain="example.com"):
    return SimpleNamespace(domain=domain, brand_name=None)


def _result(tool, score, diff=None):
    return SimpleNamespace(tool=tool, score=score, diff=diff)


def _audit(results):
    return SimpleNamespace(results=results)


def test_compute_next_run_at_daily_is_about_one_day_out():
    next_run = compute_next_run_at("daily")
    delta = next_run - datetime.now(UTC)
    assert timedelta(hours=23, minutes=59) < delta < timedelta(hours=24, minutes=1)


def test_compute_next_run_at_weekly_is_about_seven_days_out():
    next_run = compute_next_run_at("weekly")
    delta = next_run - datetime.now(UTC)
    assert timedelta(days=6, hours=23) < delta < timedelta(days=7, hours=1)


def test_build_report_email_html_first_check_has_no_change_line():
    audit = _audit([_result("meta_tags", 80, diff=None)])
    html = build_report_email_html(_project(), audit, "https://example.com/report/tok", None)

    assert "first check on record" in html
    assert "example.com" in html
    assert "meta_tags".replace("_", " ") in html or "meta tags" in html


def test_build_report_email_html_summarizes_new_and_resolved_findings():
    diff = {"previous_score": 70, "score_delta": 10, "new_finding_codes": ["a", "b"], "resolved_finding_codes": ["c"]}
    audit = _audit([_result("meta_tags", 80, diff=diff)])
    html = build_report_email_html(_project(), audit, "https://example.com/report/tok", None)

    assert "2 new items to review" in html
    assert "1 resolved since the last check" in html


def test_build_report_email_html_includes_personal_message():
    audit = _audit([_result("meta_tags", 80, diff=None)])
    html = build_report_email_html(_project(), audit, "https://example.com/report/tok", "Hi there")

    assert "Hi there" in html


def test_build_report_email_html_escapes_personal_message():
    audit = _audit([_result("meta_tags", 80, diff=None)])
    html = build_report_email_html(_project(), audit, "https://example.com/report/tok", "<script>evil()</script>")

    assert "<script>" not in html
    assert "&lt;script&gt;" in html
