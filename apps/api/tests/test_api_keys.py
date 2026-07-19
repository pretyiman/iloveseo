from app.core.api_keys import KEY_PREFIX, generate_api_key, hash_api_key


def test_generate_api_key_has_expected_prefix():
    raw_key, key_prefix, key_hash = generate_api_key()
    assert raw_key.startswith(KEY_PREFIX)
    assert key_prefix == raw_key[: len(KEY_PREFIX) + 8]
    assert key_hash == hash_api_key(raw_key)


def test_generate_api_key_is_unique_per_call():
    first_raw, _, first_hash = generate_api_key()
    second_raw, _, second_hash = generate_api_key()
    assert first_raw != second_raw
    assert first_hash != second_hash


def test_hash_api_key_is_deterministic_and_not_the_raw_key():
    raw_key = f"{KEY_PREFIX}some-fixed-value"
    assert hash_api_key(raw_key) == hash_api_key(raw_key)
    assert hash_api_key(raw_key) != raw_key
