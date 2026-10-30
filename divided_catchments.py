"""Non-overlapping drainage areas for SJC OEM precipitation briefings."""
from shapely import transform
from shapely.geometry import shape
from shapely.ops import unary_union

NAVAJO_COMID = '17040463'
SCHEMA = 'sjc-divided-catchments-v1'


def _basin(fetch, url):
    doc = fetch(url, {'f': 'json'})
    rows = doc.get('features', [])
    if doc.get('type') != 'FeatureCollection' or len(rows) != 1:
        raise ValueError('Expected one NLDI basin: ' + url)
    geom = shape(rows[0]['geometry'])
    if not geom.is_valid:
        geom = geom.buffer(0)
    if geom.is_empty:
        raise ValueError('Empty NLDI basin: ' + url)
    return geom


def partition(upper_animas, animas, navajo, farmington, shiprock, project):
    """Subtract actual polygons, checking nesting before accepting a split."""
    for label, inner, outer in (
        ('Durango/Animas', upper_animas, animas),
        ('Navajo/Farmington', navajo, farmington),
        ('Animas/Farmington', animas, farmington),
        ('Farmington/Shiprock', farmington, shiprock),
    ):
        area = transform(inner, project, interleaved=False).area
        outside = transform(inner.difference(outer), project, interleaved=False).area
        if not area or outside / area > .002:
            raise ValueError('Non-nested NLDI basin: ' + label)
    # Clip tiny inconsistencies between independently delineated NLDI boundaries.
    upper_animas = upper_animas.intersection(animas)
    navajo = navajo.intersection(farmington)
    return {
        'animas_upper': ('Animas above Durango', upper_animas),
        'animas_lower': ('Animas Durango–Farmington only', animas.difference(upper_animas)),
        'navajo': ('Navajo upstream basin', navajo),
        'san_juan_local': ('Navajo–Farmington excluding Animas',
                           farmington.difference(unary_union([navajo, animas]))),
        'shiprock_local': ('Farmington–Shiprock only', shiprock.difference(farmington)),
    }


def geometries(catchments, fetch, nldi, project):
    durango_url = f'{nldi}/linked-data/nwissite/USGS-09361500/basin'
    navajo_url = f'{nldi}/linked-data/comid/{NAVAJO_COMID}/basin'
    result = partition(
        _basin(fetch, durango_url), catchments['09364500']['geometry'],
        _basin(fetch, navajo_url), catchments['09365000']['geometry'],
        catchments['09368000']['geometry'], project)
    return {key: {'name': name, 'geometry': geom,
                  'area_sq_mi': round(transform(geom, project, interleaved=False).area / 2589988.110336, 1),
                  'periods': {}}
            for key, (name, geom) in result.items()}
