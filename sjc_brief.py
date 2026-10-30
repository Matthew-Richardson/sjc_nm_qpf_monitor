"""Compact SJC OEM texts with explicit forecast periods and source times."""
from collections import defaultdict
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

LOCAL = ZoneInfo('America/Denver')
PERIODS = ('Days 1-7', 'Day 1', 'Day 2', 'Day 3', 'Days 4-5', 'Days 6-7')
RIVERS = {'arfn5': 'Animas/Farmington', 'frmn5': 'San Juan/Farmington',
          'shrn5': 'San Juan/Shiprock', 'lpfn5': 'La Plata/Farmington'}
LEVELS = {1: 'Marginal', 2: 'Slight', 3: 'Moderate', 4: 'High'}


def local(value):
    if isinstance(value, (int, float)):
        value = datetime.fromtimestamp(value / (1000 if value > 1e11 else 1), timezone.utc)
    elif not isinstance(value, datetime):
        value = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(LOCAL)


def issued(value):
    return local(value).strftime('%a %-m/%-d %-I:%M %p %Z') if value else 'unavailable'


def span(period, times=False):
    if not period.get('valid_period') or any(x is None for x in period['valid_period']):
        return 'unavailable'
    start, end = map(local, period['valid_period'])
    fmt = '%-m/%-d %-I %p %Z' if times else '%-m/%-d'
    return start.strftime(fmt) + '–' + end.strftime(fmt)


def amounts(row):
    periods = row.get('periods', {})
    return ' | '.join(f"{periods[key]['average_in']:.2f}" if key in periods else 'n/a' for key in PERIODS)


def rain_core(report, reason, now):
    periods = report['periods']
    lines = [now.strftime('SJC OEM | Rain — %a %-m/%-d')]
    if reason == 'No material changes':
        lines.append('No material change.')
    elif reason.startswith('Material change —'):
        direction = reason.split('forecast ', 1)[-1].split(':', 1)[0]
        lines.append('WPC forecast ' + direction + ' since last sent.')
    elif reason.startswith('Returned to dry') or reason.startswith('Snow guidance'):
        lines.append(reason)
    lines.extend(['WPC averages (in): 7d | D1 | D2 | D3 | D4–5 | D6–7',
                  'County: ' + amounts({'periods': periods})])
    divided = report.get('divided_catchments', {})
    labels = [('animas_upper', 'Animas above Durango'),
              ('animas_lower', 'Animas Durango–Farmington only'),
              ('san_juan_local', 'Navajo–Farmington excl. Animas'),
              ('shiprock_local', 'Farmington–Shiprock only')]
    for key, label in labels[:2]:
        lines.append(label + ': ' + amounts(divided.get(key, {})))
    lines.append('La Plata above Farmington: ' + amounts(report.get('gauge_catchments', {}).get('09367500', {})))
    for key, label in labels[2:]:
        lines.append(label + ': ' + amounts(divided.get(key, {})))
    combined = report.get('gauge_catchments', {}).get('09364500', {}).get('periods', {}).get('Days 1-7', {}).get('average_in')
    lines.append('Divided catchment averages; do not add.')
    if combined is not None:
        lines.append(f'Combined Animas above Farmington, 7d: {combined:.2f}".')
    codes = ('D1', 'D2', 'D3', 'D4–5', 'D6–7')
    lines.append('Periods: ' + '; '.join(code + ' ' + span(periods[key]) for code, key in zip(codes, PERIODS[1:])))
    valid = periods['Days 1-7'].get('valid_period')
    if valid:
        start, end = map(local, valid)
        hours = start.strftime('%-I %p %Z')
        if start.utcoffset() != end.utcoffset():
            hours += '; ' + end.strftime('%-I %p %Z') + ' after DST ends'
        lines.append('Periods start/end ' + hours + ', not midnight.')
    lines.append('WPC issued ' + issued(periods['Days 1-7'].get('issue_time')))
    return '\n'.join(lines)


def weather_context(report, operational, now):
    lines = []
    active = [row for row in operational.get('outlooks', {}).values()
              if row.get('level', 0) > 0 and local(row['end']) > now]
    for row in active:
        period = {'valid_period': [row['start'], row['end']]}
        lines.append(f"{LEVELS[row['level']]} excessive-rain risk in part of SJC: {span(period, times=True)}.")
        lines.append('ERO issued ' + issued(row.get('issued')))
    grouped = defaultdict(list)
    for town, row in operational.get('timing', {}).items():
        if row.get('issued'):
            grouped[row['issued']].append(town)
    for value, towns in grouped.items():
        lines.append('NWS ABQ hourly (' + '/'.join(towns) + ') issued ' + issued(value))
    if not grouped:
        lines.append('NWS ABQ hourly forecast unavailable.')
    snow = report.get('snow', {})
    for day, rows in snow.get('periods', {}).items():
        if not rows:
            continue
        strongest = {}
        for row in rows:
            threshold = row['threshold_in']
            strongest[threshold] = max(strongest.get(threshold, 0), row['minimum_probability_pct'])
        # County-only signal; do not infer rain/snow partition for upstream basins.
        summary = '; '.join(f'{pct}%+ for {threshold}+"' for threshold, pct in sorted(strongest.items()))
        lines.append(f'SJC snow {day}: {summary} in part of county.')
        issues = snow.get('issued_by_day', {}).get(day, [])
        lines.append('Snow issued ' + ('; '.join(issued(value) for value in issues) if issues else 'unavailable'))
    if operational.get('errors'):
        lines.append('Some sources unavailable; see run log. Missing data do not mean lower risk.')
    return '\n'.join(lines)


def river_core(operational, now):
    lines = [now.strftime('SJC OEM | Rivers — %a %-m/%-d')]
    issues = defaultdict(list)
    for gauge, name in RIVERS.items():
        row = operational.get('rivers', {}).get(gauge)
        if not row:
            lines.append(name + ': unavailable.')
            continue
        time = local(row['time']).strftime('%a %-m/%-d %-I:%M %p %Z')
        category = row.get('category', 'undefined')
        label = {'below action': 'below action', 'undefined': 'stage category undefined',
                 'action': 'ACTION STAGE', 'minor': 'MINOR FLOOD STAGE',
                 'moderate': 'MODERATE FLOOD STAGE', 'major': 'MAJOR FLOOD STAGE'}[category]
        stage = f" / {row['stage_ft']:.2f} ft" if category in ('action', 'minor', 'moderate', 'major') and row.get('stage_ft') is not None else ''
        if row.get('observed'):
            lines.append(f"{name}: {row['cfs']:,} cfs observed {time}; {label}; no current NWS forecast.")
        else:
            kind = 'max through' if row.get('at_horizon') else 'peak'
            lines.append(f"{name}: {row['cfs']:,} cfs{stage}, {kind} {time}; {label}.")
            issues[row.get('issued')].append(name)
    for value, names in issues.items():
        lines.append('NWS issued ' + '/'.join(names) + ': ' + issued(value))
    lines.append('Local flash flooding remains possible below mainstem action stages.')
    return '\n'.join(lines)


def navajo_section(report, operational):
    lines = ['Navajo:']
    row = report.get('divided_catchments', {}).get('navajo')
    if row:
        lines.extend(['Upstream basin (in), 7d | D1 | D2 | D3 | D4–5 | D6–7:', amounts(row),
                      'WPC issued ' + issued(row['periods']['Days 1-7'].get('issue_time'))])
    else:
        lines.append('Upstream basin forecast unavailable.')
    ops = operational.get('reservoirs', {}).get('navajo')
    if ops:
        date = datetime.fromisoformat(ops['date']).strftime('%a %-m/%-d')
        lines.append(f"{date} daily avg: inflow {ops['inflow_cfs']:,.0f}; total release {ops['release_cfs']:,.0f} cfs.")
        change = ops.get('storage_change_af')
        storage = f"Storage {ops['storage_af']:,.0f} acre-ft"
        if change is not None:
            storage += f" ({change:+,.0f}/day)"
        lines.append(storage + '.')
        lines.append('Report issuance time unavailable. Future release changes unverified.')
    else:
        lines.append('Daily operations unavailable. Future release changes unverified.')
    return '\n'.join(lines)


def build_messages(report, operational, reason, now, include_rivers=True, limit=1000):
    """Use two texts normally; one overflow text at most, without dropping sources."""
    rain = rain_core(report, reason, now)
    context = weather_context(report, operational, now)
    overflow = []
    if len(rain + '\n' + context) <= limit:
        rain += '\n' + context
    elif context:
        overflow.append('SJC OEM | Local outlook\n' + context)
    texts = [rain]
    if include_rivers:
        rivers = river_core(operational, now)
        navajo = navajo_section(report, operational)
        if len(rivers + '\n\n' + navajo) <= limit:
            rivers += '\n\n' + navajo
        else:
            overflow.append('SJC OEM | ' + navajo)
        texts.append(rivers)
    if overflow:
        texts.append('\n\n'.join(overflow))
    if len(texts) > 3 or any(len(text) > limit for text in texts):
        raise ValueError('SJC briefing exceeds three GroupMe texts; delivery state retained')
    return texts
