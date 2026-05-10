import pytest

from ntfy_mcp.config import ConfigError, load_settings


def test_topic_is_required() -> None:
    with pytest.raises(ConfigError, match="NTFY_TOPIC is required"):
        load_settings({})


def test_allowed_topics_default_to_topic() -> None:
    settings = load_settings({"NTFY_TOPIC": "long_random_topic_123"})

    assert settings.topic == "long_random_topic_123"
    assert settings.allowed_topics == frozenset({"long_random_topic_123"})
    assert settings.base_url == "https://ntfy.sh"
    assert settings.default_priority == 3
    assert settings.max_message_length == 1800
    assert settings.source == "agent"


def test_custom_allowed_topics_are_parsed() -> None:
    settings = load_settings(
        {
            "NTFY_TOPIC": "primary-topic",
            "NTFY_ALLOWED_TOPICS": "primary-topic, secondary_topic",
        }
    )

    assert settings.allowed_topics == frozenset({"primary-topic", "secondary_topic"})


def test_topic_must_be_inside_allowed_topics() -> None:
    with pytest.raises(ConfigError, match="must be included"):
        load_settings(
            {
                "NTFY_TOPIC": "primary-topic",
                "NTFY_ALLOWED_TOPICS": "secondary-topic",
            }
        )


def test_default_priority_must_be_valid() -> None:
    with pytest.raises(ConfigError, match="NTFY_DEFAULT_PRIORITY"):
        load_settings({"NTFY_TOPIC": "primary-topic", "NTFY_DEFAULT_PRIORITY": "9"})


def test_dry_run_boolean_is_parsed() -> None:
    settings = load_settings({"NTFY_TOPIC": "primary-topic", "NTFY_DRY_RUN": "true"})

    assert settings.dry_run is True


def test_base_url_must_use_https() -> None:
    with pytest.raises(ConfigError, match="must use https"):
        load_settings({"NTFY_TOPIC": "primary-topic", "NTFY_BASE_URL": "http://ntfy.local"})


def test_token_must_not_contain_newlines() -> None:
    with pytest.raises(ConfigError, match="NTFY_TOKEN must not contain newlines"):
        load_settings({"NTFY_TOPIC": "primary-topic", "NTFY_TOKEN": "good\nbad"})
