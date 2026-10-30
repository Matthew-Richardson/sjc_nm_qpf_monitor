from nbm_monitor import FORECAST_HOURS, forecast_messages


def test_prefetch_preserves_all_accumulation_fields_in_order(monkeypatch):
    monkeypatch.setattr('nbm_monitor.fetch_apcp_message', lambda cycle, hour: str(hour).encode())
    rows = list(forecast_messages(None))
    assert [hour for hour, message in rows] == list(FORECAST_HOURS)
    assert all(message == str(hour).encode() for hour, message in rows)


def test_prefetch_failure_propagates_instead_of_returning_partial_total(monkeypatch):
    import pytest
    def fetch(cycle, hour):
        if hour == 3:
            raise RuntimeError('missing field')
        return b'field'
    monkeypatch.setattr('nbm_monitor.fetch_apcp_message', fetch)
    with pytest.raises(RuntimeError, match='missing field'):
        list(forecast_messages(None))
