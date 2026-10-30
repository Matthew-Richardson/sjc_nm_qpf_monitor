from shapely.geometry import box
import qpf_monitor
from qpf_monitor import GAUGE_CATCHMENTS, gauge_catchment_geometries, summarize

def test_uniform():
    region=box(-108,37,-107,38)
    fs=[{"properties":{"qpf":1.5,"units":"inches","issue_time":"2026","start_time":"a","end_time":"b"},"geometry":region.__geo_interface__}]
    out=summarize(region,fs)
    assert out["average_in"]==1.5
    assert out["coverage_pct"]==100

def test_unmapped_area_counted_as_zero():
    region=box(-108,37,-107,38)
    partial=box(-108,37,-107.9,38)
    fs=[{"properties":{"qpf":1,"units":"inches"},"geometry":partial.__geo_interface__}]
    result=summarize(region,fs)
    assert result["coverage_pct"] < 15
    assert 0 < result["average_in"] < 0.15
    assert result["min_in"] == 0.0

def test_gauge_catchments_use_usgs_nldi(monkeypatch):
    calls=[]
    def fake_fetch(url,params):
        calls.append((url,params))
        return {"type":"FeatureCollection","features":[{"geometry":box(-108,37,-107,38).__geo_interface__}]}
    monkeypatch.setattr(qpf_monitor,"fetch",fake_fetch)
    result=gauge_catchment_geometries()
    assert set(result)==set(GAUGE_CATCHMENTS)
    assert all(row["source"].endswith("/basin") for row in result.values())
    assert all(params=={"f":"json"} for _,params in calls)


def test_run_writes_all_divided_periods_and_nbm_regions(tmp_path, monkeypatch):
    import json
    from tests.test_divided_catchments import regions
    upper, animas, navajo, farm, ship = regions()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(qpf_monitor, 'county', lambda: farm)
    monkeypatch.setattr(qpf_monitor, 'watershed_geometries', lambda g: {})
    monkeypatch.setattr(qpf_monitor, 'fine_watershed_geometries', lambda g, b: {})
    shapes = {'09365000': farm, '09368000': ship, '09367500': upper,
              '09364500': animas, '09364010': animas}
    monkeypatch.setattr(qpf_monitor, 'gauge_catchment_geometries', lambda: {
        site: {**GAUGE_CATCHMENTS[site], 'geometry': geom, 'source': 'fixture'}
        for site, geom in shapes.items()})
    def fetch(url, params):
        geom = upper if '09361500' in url else navajo
        return {'type': 'FeatureCollection', 'features': [{'geometry': geom.__geo_interface__}]}
    monkeypatch.setattr(qpf_monitor, 'fetch', fetch)
    monkeypatch.setattr(qpf_monitor, 'features', lambda *args: [{
        'geometry': ship.__geo_interface__, 'properties': {
            'qpf': 2, 'units': 'inches', 'issue_time': '2026-10-30 10:30:11',
            'start_time': '2026-10-30 12:00:00', 'end_time': '2026-11-06 12:00:00'}}])
    def nbm(regions):
        assert {'split_animas_upper', 'split_animas_lower', 'split_navajo',
                'split_san_juan_local', 'split_shiprock_local'} <= regions.keys()
        return {'status': 'complete', 'cycle_utc': '2026-10-30T12:00:00Z',
                'totals': {key: {'average_in': 1, 'grid_points': 10} for key in regions}}
    monkeypatch.setattr(qpf_monitor, 'calculate_nbm', nbm)
    qpf_monitor.run()
    result = json.loads((tmp_path/'data/latest.json').read_text())
    assert result['area_schema'] == 'sjc-divided-catchments-v1'
    for row in result['divided_catchments'].values():
        assert set(row['periods']) == set(qpf_monitor.LAYERS)
        assert all(period['average_in'] == 2 for period in row['periods'].values())
        assert row['area_sq_mi'] > 0 and 'geometry' not in row
    md = (tmp_path/'data/latest.md').read_text()
    assert 'Divided catchment precipitation' in md and 'Days 6–7' in md

