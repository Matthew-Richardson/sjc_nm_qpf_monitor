"""USBR provisional daily Navajo operations; never a future release schedule."""
from datetime import datetime, timedelta
from html.parser import HTMLParser
from zoneinfo import ZoneInfo
import math
import requests

SOURCE = 'https://www.usbr.gov/rsvrWater/rsv40Day.html?reservoirtype=Reservoir&siteid=920'


class TableRows(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.row = []
        self.cell = None

    def handle_starttag(self, tag, attrs):
        if tag == 'tr':
            self.row = []
        elif tag in ('td', 'th'):
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self.cell is not None:
            self.row.append(''.join(self.cell).strip())
            self.cell = None
        elif tag == 'tr' and self.row:
            self.rows.append(self.row)


def parse(html, now):
    parser = TableRows()
    parser.feed(html)
    today = now.astimezone(ZoneInfo('America/Denver')).date()
    headers = [cells for cells in parser.rows if cells and cells[0].strip().lower() == 'date']
    expected = ('date', 'elevation', 'storage', 'inflow', 'total release')
    if not any(len(cells) == 5 and all(word in cell.lower() for word, cell in zip(expected, cells))
               for cells in headers):
        raise ValueError('Unexpected USBR Navajo daily table header')
    records = {}
    for cells in parser.rows:
        if not cells:
            continue
        try:
            day = datetime.strptime(cells[0], '%d-%b-%Y').date()
        except ValueError:
            continue
        if len(cells) != 5:
            raise ValueError('Unexpected USBR Navajo daily table columns')
        if day > today:
            continue
        try:
            vals = [float(x.replace(',', '')) for x in cells[1:]]
        except ValueError as exc:
            raise ValueError('Missing USBR Navajo daily value') from exc
        if not all(math.isfinite(x) and x >= 0 for x in vals):
            raise ValueError('Invalid USBR Navajo daily value')
        records[day] = dict(zip(('elevation_ft', 'storage_af', 'inflow_cfs', 'release_cfs'), vals))
    if not records:
        raise ValueError('No USBR Navajo daily records')
    day = max(records)
    if today - day > timedelta(days=3):
        raise ValueError('Stale USBR Navajo daily operations')
    latest = records[day]
    before = records.get(day - timedelta(days=1))
    return {**latest, 'date': day.isoformat(), 'source': SOURCE,
            'storage_change_af': latest['storage_af'] - before['storage_af'] if before else None,
            'issued': None, 'future_release_verified': False,
            'note': 'Daily average total release and computed inflow; not instantaneous flow or a future release schedule.'}


def collect(now):
    response = requests.get(SOURCE, timeout=30,
                            headers={'User-Agent': 'SanJuanNM-QPF-Monitor/1.0'})
    response.raise_for_status()
    return parse(response.text, now)
