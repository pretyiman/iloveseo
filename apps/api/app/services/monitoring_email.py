import html as html_lib

from app.models.audit import Audit
from app.models.project import Project

_SCORE_COLORS = [(90, "#16a34a"), (70, "#65a30d"), (50, "#d97706"), (0, "#dc2626")]


def _score_color(score: int | None) -> str:
    if score is None:
        return "#9ca3af"
    for threshold, color in _SCORE_COLORS:
        if score >= threshold:
            return color
    return "#dc2626"


def _score_label(score: int | None) -> str:
    return "--" if score is None else f"{score}/100"


def build_report_email_html(
    project: Project, audit: Audit, share_url: str, personal_message: str | None
) -> str:
    """Plain, inline-styled HTML -- no flexbox/grid, since this goes
    through actual email clients (Gmail's own rendering included), not a
    browser or the PDF pipeline's headless Chrome, both of which are far
    more forgiving of modern CSS. Kept factual and calm throughout, same
    tone constraint as the report pages: this is often a freelancer's
    pitch to a non-technical site owner, not an internal alert."""
    new_count = sum(len(r.diff["new_finding_codes"]) for r in audit.results if r.diff)
    resolved_count = sum(len(r.diff["resolved_finding_codes"]) for r in audit.results if r.diff)
    has_previous = any(r.diff is not None for r in audit.results)

    if not has_previous:
        change_line = "This is the first check on record for this site."
    else:
        parts = []
        if new_count:
            parts.append(f"{new_count} new item{'s' if new_count != 1 else ''} to review")
        if resolved_count:
            parts.append(f"{resolved_count} resolved since the last check")
        change_line = ", ".join(parts) if parts else "No change since the last check."

    rows = "".join(
        f"""
        <tr>
          <td style="padding:6px 10px;border-bottom:1px solid #e5e7eb;font-family:Arial,sans-serif;font-size:13px;color:#374151;">
            {r.tool.replace('_', ' ')}
          </td>
          <td style="padding:6px 10px;border-bottom:1px solid #e5e7eb;font-family:Arial,sans-serif;font-size:13px;font-weight:bold;color:{_score_color(r.score)};text-align:right;">
            {_score_label(r.score)}
          </td>
        </tr>"""
        for r in audit.results
    )

    # Escape anything that ultimately came from user input before it goes
    # into HTML that becomes a real email to a third party -- personal_message
    # is free text the user typed, and domain (though normalized elsewhere)
    # costs nothing to escape defensively too.
    safe_domain = html_lib.escape(project.domain)
    personal_message_html = (
        f'<p style="font-family:Arial,sans-serif;font-size:14px;color:#111827;white-space:pre-wrap;">{html_lib.escape(personal_message)}</p>'
        if personal_message
        else ""
    )

    return f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
      {personal_message_html}
      <p style="font-family:Arial,sans-serif;font-size:14px;color:#374151;">
        Here's a site-health check for <strong>{safe_domain}</strong>. {change_line}
      </p>
      <table style="width:100%;border-collapse:collapse;margin:16px 0;">
        {rows}
      </table>
      <p style="margin:20px 0;">
        <a href="{share_url}" style="background:#111827;color:#ffffff;text-decoration:none;padding:10px 20px;border-radius:6px;font-family:Arial,sans-serif;font-size:14px;display:inline-block;">
          View the full report
        </a>
      </p>
      <p style="font-family:Arial,sans-serif;font-size:11px;color:#9ca3af;">
        Report generated with SEO Repair Kit.
      </p>
    </div>
    """.strip()
