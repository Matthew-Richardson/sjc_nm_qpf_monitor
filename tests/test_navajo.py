from datetime import datetime, timezone
import pytest
from navajo_monitor import parse

NOW = datetime(2026, 10, 30, 16, tzinfo=timezone.utc)
HTML = '''<table><tr><th>Date</th><th>Elevation</th><th>Storage</th><th>Inflow</th><th>Total Release</th></tr>
<tr><td>29-Oct-2026</td><td>6047.63</td><td>1,143,965</td><td>4949</td><td>264</td></tr>
<tr><td>28-Oct-2026</td><td>6046.81</td><td>1,134,711</td><td>5532</td><td>263</td></tr></table>'''


def test_reports_actual_daily_values_and_change_not_future_schedule():
    row = parse(HTML, NOW)
    assert row['storage_af'] == 1143965
    assert row['storage_change_af'] == 9254
    assert row['release_cfs'] == 264 and row['inflow_cfs'] == 4949
    assert row['date'] == '2026-10-29'
    assert row['issued'] is None and row['future_release_verified'] is False


def test_stale_operations_fail_instead_of_appearing_current():
    with pytest.raises(ValueError, match='Stale'):
        parse(HTML, NOW.replace(month=11, day=8))


def test_missing_release_is_not_zero():
    with pytest.raises(ValueError, match='Missing'):
        parse(HTML.replace('<td>264</td>', '<td>M</td>'), NOW)


def test_storage_change_requires_consecutive_dates():
    row = parse(HTML.replace('28-Oct-2026', '27-Oct-2026'), NOW)
    assert row['storage_change_af'] is None


def test_changed_column_order_fails_instead_of_mislabeling_release():
    with pytest.raises(ValueError, match='header'):
        parse(HTML.replace('<th>Inflow</th>', '<th>Discharge</th>'), NOW)
