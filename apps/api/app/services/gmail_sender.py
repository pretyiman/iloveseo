import base64
from email.mime.text import MIMEText

import httpx

from app.core.config import get_settings

GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
GMAIL_SEND_ENDPOINT = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"


class GmailNotConnectedError(Exception):
    """Raised when the user hasn't connected Google at all, or connected it
    without granting the gmail.send scope -- surfaced to the frontend as a
    "Connect Gmail" prompt rather than a generic error."""


async def get_google_access_token(clerk_user_id: str) -> str:
    """Clerk stores and refreshes the underlying Google OAuth token for us
    -- this just asks for a current one. Requesting the gmail.send scope
    itself happens client-side via Clerk's reauthorize()/additionalScopes;
    this only reads whatever was already granted."""
    settings = get_settings()
    url = f"https://api.clerk.com/v1/users/{clerk_user_id}/oauth_access_tokens/google"

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, headers={"Authorization": f"Bearer {settings.clerk_secret_key}"})
    resp.raise_for_status()
    body = resp.json()
    tokens = body.get("data", body) if isinstance(body, dict) else body

    for entry in tokens:
        if GMAIL_SEND_SCOPE in entry.get("scopes", []):
            return entry["token"]

    raise GmailNotConnectedError("Connect Gmail (with mail-sending permission) before sending a report.")


async def send_email(access_token: str, to: str, subject: str, html_body: str) -> None:
    message = MIMEText(html_body, "html")
    message["To"] = to
    message["Subject"] = subject
    # Deliberately no "From" -- Gmail fills it in with the authenticated
    # account's own address, which is the whole point of this integration.
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            GMAIL_SEND_ENDPOINT,
            headers={"Authorization": f"Bearer {access_token}"},
            json={"raw": raw},
        )
    resp.raise_for_status()
