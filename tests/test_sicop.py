import json
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from nexolicitcr.sicop import SicopClient, SourceError, amount, normalize, source_date


@pytest.fixture
def sample():
    return json.loads((Path(__file__).parent / "fixtures/tender.json").read_text())


def test_normalization_is_exact_and_conservative(sample):
    tender = normalize(sample["listing"], sample["detail"], sample["lines"], "servicios")
    assert tender.lines[0].budget_unit_price == Decimal("125.35")
    assert tender.lines[0].unit is None
    assert tender.deadline.raw == "2026-10-15T16:00:00"
    assert tender.deadline.utc is None
    assert not tender.requirements_complete
    assert "<p>" not in tender.conditions["generalCondsCont"]
    copy = tender.model_copy(update={"source_version": "another-observation"})
    assert copy.fingerprint() == tender.fingerprint()
    assert tender.model_copy(update={"title": "Modificación"}).fingerprint() != tender.fingerprint()


def test_dates_missing_and_configured_timezone(sample):
    assert source_date(None, "").utc is None
    assert source_date("2026-10-15T16:00:00", "America/Costa_Rica").utc.hour == 22
    assert source_date("2026-10-15T16:00:00-06:00", "").utc.hour == 22
    sample["detail"]["biddocEndDt"] = None
    sample["detail"]["openbidDt"] = "2026-10-15T16:00:00"
    assert (
        normalize(sample["listing"], sample["detail"], sample["lines"], "servicios").deadline.raw
        is None
    )


@pytest.mark.parametrize("value", [True, "NaN", "Infinity", "-1", "not-money"])
def test_invalid_money_rejected(value):
    with pytest.raises(SourceError):
        amount(value)


def test_mismatched_and_duplicate_lines_rejected(sample):
    bad = deepcopy(sample["lines"])
    bad[0]["id"]["cartelNo"] = "999"
    with pytest.raises(SourceError):
        normalize(sample["listing"], sample["detail"], bad, "servicios")
    with pytest.raises(SourceError):
        normalize(sample["listing"], sample["detail"], sample["lines"] * 2, "servicios")


def api(handler):
    return SicopClient(httpx.Client(transport=httpx.MockTransport(handler)), sleep=lambda _: None)


def test_all_pages_and_decimal_json():
    requested = []

    def handler(request):
        payload = json.loads(request.content)
        requested.append(payload["pageNumber"])
        return httpx.Response(
            200,
            json={
                "content": [{"value": "line" + str(payload["pageNumber"])}],
                "last": payload["pageNumber"] == 2,
            },
        )

    client = api(handler)
    assert len(list(client.pages("/test", {}))) == 3
    assert requested == [0, 1, 2]
    client = api(
        lambda r: httpx.Response(
            200,
            content='{"price":0.1234567890123456789}',
            headers={"content-type": "application/json"},
        )
    )
    assert client.post("/test", {})["price"] == Decimal("0.1234567890123456789")


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, text="<html>Acceso bloqueado</html>"),
        httpx.Response(200, content="broken", headers={"content-type": "application/json"}),
        httpx.Response(403),
        httpx.Response(302, headers={"location": "https://example.com"}),
    ],
)
def test_blocked_or_invalid_is_not_empty(response):
    with pytest.raises(SourceError):
        api(lambda r: response).post("/test", {})


def test_valid_empty_and_repeated_page():
    assert (
        list(api(lambda r: httpx.Response(200, json={"content": [], "last": True})).pages("/x", {}))
        == []
    )
    with pytest.raises(SourceError, match="repitió"):
        list(
            api(lambda r: httpx.Response(200, json={"content": [{"x": 1}], "last": False})).pages(
                "/x", {}
            )
        )


def test_retries_are_bounded():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(503)

    with pytest.raises(SourceError):
        api(handler).post("/test", {})
    assert len(calls) == 3


@pytest.mark.parametrize(
    "header,expected",
    [("180", 180), ("0", 60), ("invalid", 300), (None, 300), ("999999999", 86400)],
)
def test_rate_limit_stops_requests_and_preserves_retry_after(header, expected):
    from nexolicitcr.sicop import SourceRateLimited

    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(429, headers={"Retry-After": header} if header else {})

    with pytest.raises(SourceRateLimited) as error:
        api(handler).post("/test", {})
    assert error.value.retry_after == expected
    assert len(calls) == 1


def test_retry_after_http_date():
    from datetime import UTC, datetime, timedelta
    from email.utils import format_datetime

    from nexolicitcr.sicop import retry_after_seconds

    value = format_datetime(datetime.now(UTC) + timedelta(seconds=180), usegmt=True)
    assert 179 <= retry_after_seconds(value) <= 180
