from datetime import datetime
from zoneinfo import ZoneInfo
from copy import deepcopy
from sjc_brief import build_messages, river_core
from groupme_notify import decide, totals

NOW = datetime(2026, 10, 30, 10, tzinfo=ZoneInfo('America/Denver'))


def report():
    windows = {
        'Day 1': ['2026-10-30T12:00:00Z', '2026-10-31T12:00:00Z'],
        'Day 2': ['2026-10-31T12:00:00Z', '2026-11-01T12:00:00Z'],
        'Day 3': ['2026-11-01T12:00:00Z', '2026-11-02T12:00:00Z'],
        'Days 4-5': ['2026-11-02T12:00:00Z', '2026-11-04T12:00:00Z'],
        'Days 6-7': ['2026-11-04T12:00:00Z', '2026-11-06T12:00:00Z'],
        'Days 1-7': ['2026-10-30T12:00:00Z', '2026-11-06T12:00:00Z']}
    p = {key: {'average_in': i / 10, 'valid_period': window, 'issue_time': '2026-10-30 10:30:11'}
         for i, (key, window) in enumerate(windows.items(), 1)}
    return {'area_schema': 'sjc-divided-catchments-v1', 'periods': p,
            'divided_catchments': {key: {'name': key, 'periods': deepcopy(p)}
                                  for key in ('animas_upper', 'animas_lower', 'navajo', 'san_juan_local', 'shiprock_local')},
            'gauge_catchments': {site: {'periods': deepcopy(p)} for site in
                                  ('09365000', '09368000', '09367500', '09364500', '09364010')}}


def operational():
    rivers = {key: {'cfs': 5800, 'time': '2026-11-02T23:00:00Z', 'category': 'below action',
                    'issued': issue, 'at_horizon': False, 'observed': False}
              for key, issue in [('arfn5', '2026-10-29T16:25:00Z'), ('frmn5', '2026-10-29T16:25:00Z'),
                                  ('shrn5', '2026-10-29T14:56:00Z'), ('lpfn5', '2026-10-29T14:56:00Z')]}
    return {'rivers': rivers, 'timing': {'Farmington': {'issued': '2026-10-30T12:02:06Z'}},
            'outlooks': {'Sunday': {'level': 3, 'start': '2026-11-01T12:00:00Z',
                                    'end': '2026-11-02T12:00:00Z', 'issued': '2026-10-30T08:19:00Z'}},
            'reservoirs': {'navajo': {'date': '2026-10-29', 'inflow_cfs': 4949, 'release_cfs': 264,
                                     'storage_af': 1143965, 'storage_change_af': 9254}}}


def test_three_text_limit_day_breakdown_dates_and_source_times():
    texts = build_messages(report(), operational(), 'No material changes', NOW)
    assert 2 <= len(texts) <= 3
    assert all(len(text) <= 1000 for text in texts)
    text = '\n'.join(texts)
    assert '7d | D1 | D2 | D3 | D4–5 | D6–7' in text
    assert '0.60 | 0.10 | 0.20 | 0.30 | 0.40 | 0.50' in text
    assert 'do not add' in text and 'Combined Animas' in text
    assert 'D2 10/31–11/1' in text and '5 AM MST after DST ends' in text
    assert 'WPC issued Fri 10/30 4:30 AM MDT' in text
    assert 'ERO issued Fri 10/30 2:19 AM MDT' in text
    assert 'NWS ABQ hourly (Farmington) issued Fri 10/30 6:02 AM MDT' in text
    assert 'Thu 10/29 10:25 AM MDT' in text and 'Thu 10/29 8:56 AM MDT' in text
    assert 'Mon 11/2 4:00 PM MST' in text
    assert 'total release 264 cfs' in text and 'Future release changes unverified' in text


def test_full_catchment_average_cannot_hide_split_change():
    r = report()
    _, state = decide(r, {}, now=NOW)
    changed = deepcopy(r)
    changed['divided_catchments']['animas_lower']['periods']['Days 1-7']['average_in'] += .3
    assert totals(changed)['animas_lower'] - totals(r)['animas_lower'] > .29
    reason, _ = decide(changed, state, now=NOW)
    assert 'animas_lower increased 0.30in' in reason


def test_undefined_and_horizon_forecasts_never_become_confirmed_crests():
    ops = operational()
    ops['rivers']['lpfn5'].update(category='undefined', at_horizon=True)
    text = river_core(ops, NOW)
    assert 'stage category undefined' in text and 'max through' in text


def test_unavailable_sources_stay_explicit():
    text = '\n'.join(build_messages(report(), {}, 'No material changes', NOW))
    assert 'NWS ABQ hourly forecast unavailable' in text
    assert 'Daily operations unavailable' in text
    assert 'La Plata/Farmington: unavailable' in text
