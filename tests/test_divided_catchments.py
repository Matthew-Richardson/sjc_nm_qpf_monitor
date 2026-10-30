import pytest
from shapely.geometry import box
from shapely.ops import unary_union
from qpf_monitor import PROJECT, summarize
from divided_catchments import partition


def regions():
    upper = box(-108, 37, -107.8, 37.2)
    animas = box(-108, 36.9, -107.8, 37.2)
    navajo = box(-107.6, 37, -107.4, 37.2)
    farm = box(-108, 36.8, -107.4, 37.2)
    ship = box(-108.1, 36.7, -107.4, 37.2)
    return upper, animas, navajo, farm, ship


def test_splits_partition_downstream_basin_without_double_counting():
    source = regions()
    rows = partition(*source, PROJECT)
    polygons = [g for name, g in rows.values()]
    assert unary_union(polygons).symmetric_difference(source[-1]).area < 1e-12
    for i, a in enumerate(polygons):
        for b in polygons[i + 1:]:
            assert a.intersection(b).area == 0


def test_split_averages_are_recalculated_not_subtracted():
    upper, animas, *rest = regions()
    lower = partition(upper, animas, *rest, PROJECT)['animas_lower'][1]
    features = [{'geometry': g.__geo_interface__, 'properties': {'qpf': q, 'units': 'inches'}}
                for g, q in [(upper, 3), (lower, 1)]]
    assert summarize(upper, features)['average_in'] == 3
    assert summarize(lower, features)['average_in'] == 1
    combined = summarize(animas, features)['average_in']
    assert 1 < combined < 3
    assert combined - 3 != 1


def test_rejects_non_nested_catchments():
    source = list(regions())
    source[0] = box(-109, 37, -108.5, 37.5)
    with pytest.raises(ValueError, match='Non-nested'):
        partition(*source, PROJECT)
