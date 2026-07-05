"""Provider error classification tests."""

from app.utils.provider_errors import classify_provider_exception


def test_classify_provider_exception_quota_message() -> None:
    status, message = classify_provider_exception("Tavily", RuntimeError("HTTP 429 Too Many Requests"))
    assert status == "budget_exceeded"
    assert "quota/rate limit" in message


def test_classify_provider_exception_credit_message() -> None:
    status, message = classify_provider_exception(
        "Firecrawl",
        RuntimeError("insufficient credits for this operation"),
    )
    assert status == "budget_exceeded"
    assert "Firecrawl" in message


def test_classify_provider_exception_non_quota_error() -> None:
    status, message = classify_provider_exception("Serper", RuntimeError("Connection refused"))
    assert status == "error"
    assert message == "Connection refused"

