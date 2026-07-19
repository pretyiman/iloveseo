from app.core.share_tokens import generate_share_token


def test_generate_share_token_is_nonempty_and_url_safe():
    token = generate_share_token()
    assert len(token) > 16
    assert all(c.isalnum() or c in "-_" for c in token)


def test_generate_share_token_is_unique_per_call():
    assert generate_share_token() != generate_share_token()
