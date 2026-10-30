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


def weather_context(report, operational, now, reason=None):
    lines = []
    if reason == 'No material changes':
        lines.append('No material change.')
    elif reason and reason.startswith('Material change —'):
        direction = reason.split('forecast ', 1)[-1].split(':', 1)[0]
        lines.append('WPC forecast ' + direction + ' since last sent.')
    elif reason and (reason.startswith('Returned to dry') or reason.startswith('Snow guidance')):
        lines.append(reason)
    categories = defaultdict(list)
    river_issues = defaultdict(list)
    names = {'arfn5': 'Animas at Farmington', 'frmn5': 'San Juan at Farmington',
             'shrn5': 'San Juan at Shiprock', 'lpfn5': 'La Plata near Farmington'}
    labels = {'below action': 'below action', 'undefined': 'stage category undefined',
              'action': 'ACTION STAGE', 'minor': 'MINOR FLOOD STAGE',
              'moderate': 'MODERATE FLOOD STAGE', 'major': 'MAJOR FLOOD STAGE'}
    for gauge, name in names.items():
        row = operational.get('rivers', {}).get(gauge)
        if row and not row.get('observed'):
            categories[labels[row.get('category', 'undefined')]].append(name)
            river_issues[row.get('issued')].append(name)
    for label, gauges in categories.items():
        lines.append('River forecast: ' + '; '.join(gauges) + ' — ' + label + '.')
    for value, gauges in river_issues.items():
        lines.append('NWS river forecasts (' + '; '.join(gauges) + ') issued ' + issued(value))
    active = [row for row in operational.get('outlooks', {}).values()
              if row.get('level', 0) > 0 and local(row['end']) > now]
    for row in active:
        period = {'valid_period': [row['start'], row['end']]}
        lines.append(f"{LEVELS[row['level']]} excessive-rain risk in part of SJC: {span(period, times=True)}.")
        lines.append('WPC excessive-rainfall outlook issued ' + issued(row.get('issued')))
    grouped = defaultdict(list)
    for town, row in operational.get('timing', {}).items():
        if row.get('issued'):
            grouped[row['issued']].append(town)
    for value, towns in grouped.items():
        lines.append('NWS ABQ hourly forecast (' + '/'.join(towns) + ') issued ' + issued(value))
    if not grouped:
        lines.append('NWS ABQ hourly forecast unavailable.')
    lines.append('Future Navajo release changes unverified.')
    if operational.get('errors'):
        lines.append('Some sources unavailable; see run log. Missing data do not mean lower risk.')
    return '\n'.join(lines)


def snow_core(report, now):
    lines = [now.strftime('SJC OEM | Snow — %a %-m/%-d')]
    snow = report.get('snow', {})
    if 'periods' not in snow:
        lines.append('WPC snow guidance unavailable.')
    elif not snow.get('active'):
        lines.append('WPC Days 1–3: no mapped 10%+ chance of 4"+ snow in SJC. Lighter snow remains possible.')
    else:
        for day, rows in snow.get('periods', {}).items():
            if not rows:
                continue
            bands = snow.get('elevation_bands', {}).get(day)
            areas = bands if bands else {'Part of SJC': rows}
            for label, area_rows in areas.items():
                if not area_rows:
                    continue
                strongest = {}
                for row in area_rows:
                    threshold = row['threshold_in']
                    strongest[threshold] = max(strongest.get(threshold, 0), row['minimum_probability_pct'])
                def chance(pct):
                    return '70%+' if pct >= 70 else ('40–69%' if pct >= 40 else '10–39%')
                summary = '; '.join(f'{chance(pct)} for {threshold}+"' for threshold, pct in sorted(strongest.items()))
                lines.append(f'{day}, {label}: {summary}.')
    issues = defaultdict(list)
    for day, values in snow.get('issued_by_day', {}).items():
        for value in values:
            issues[value].append(day)
    for value, days in issues.items():
        lines.append('WPC snow (' + '/'.join(days) + ') issued ' + issued(value))
    if not issues:
        lines.append('WPC snow issuance time unavailable.')
    lines.append('SJC county only; upstream Colorado mountain snow is not assessed here.')
    return '\n'.join(lines)


def river_core(operational, now):
    lines = [now.strftime('SJC OEM | Rivers — %a %-m/%-d')]
    for gauge, name in RIVERS.items():
        row = operational.get('rivers', {}).get(gauge)
        if not row:
            lines.append(name + ': unavailable.')
            continue
        time = local(row['time']).strftime('%a %-m/%-d %-I:%M %p %Z')
        stage = f" / {row['stage_ft']:.2f} ft" if row.get('stage_ft') is not None else ''
        if row.get('observed'):
            lines.append(f"{name}: {row['cfs']:,} cfs{stage} observed {time}; no current NWS forecast.")
        else:
            kind = 'max through' if row.get('at_horizon') else 'peak'
            lines.append(f"{name}: {row['cfs']:,} cfs{stage}, {kind} {time}.")
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
        lines.append('Daily report issuance time unavailable.')
    else:
        lines.append('Daily operations unavailable.')
    return '\n'.join(lines)


def build_messages(report, operational, reason, now, include_rivers=True, limit=1000):
    """Four fixed-purpose texts: rain, snow, rivers/reservoir, discussion."""
    texts = [rain_core(report, reason, now), snow_core(report, now)]
    if include_rivers:
        texts.append(river_core(operational, now) + '\n\n' + navajo_section(report, operational))
    context = weather_context(report, operational, now, reason)
    if operational.get('rivers'):
        context += '\nLocal flash flooding remains possible below mainstem action stages.'
    texts.append('SJC OEM | Forecasts & alerts\n' + context)
    if len(texts) > 4 or any(len(text) > limit for text in texts):
        raise ValueError('SJC briefing exceeds four GroupMe texts; delivery state retained')
    return texts
