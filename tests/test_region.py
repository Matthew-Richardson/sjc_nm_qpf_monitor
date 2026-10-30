from unittest.mock import patch
from shapely.geometry import mapping, box
from qpf_monitor import county, GAUGE_CATCHMENTS
from groupme_notify import WATCHED
from operational_monitor import RIVERS, TOWNS, OBSERVED_ONLY_RIVERS


def test_new_mexico_county_selection():
    with patch('qpf_monitor.features', return_value=[{'geometry': mapping(box(-109, 36, -107, 37))}]) as query:
        county()
    assert query.call_args.args[1]['where'] == "GEOID='35045'"


def test_regional_sources_agree():
    assert set(WATCHED.values()) == set(GAUGE_CATCHMENTS)
    assert set(RIVERS) == {'frmn5', 'shrn5', 'arfn5', 'azrn5', 'lpfn5'}
    assert 'azrn5' in OBSERVED_ONLY_RIVERS
    assert set(TOWNS) == {'Farmington', 'Aztec', 'Bloomfield', 'Shiprock'}
