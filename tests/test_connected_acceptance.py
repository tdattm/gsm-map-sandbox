"""Independent live-audit arithmetic is exercised using explicit domain fixtures."""
from copy import deepcopy

import pytest

from scripts.validate_connected_api import audit
from test_connected_domain import run


@pytest.mark.parametrize('target', ['globalWait', 'zoneNumerator', 'modeRatio', 'modeCount'])
def test_independent_audit_rejects_corrupt_aggregates(target):
    result = run()
    audit(result)
    broken = deepcopy(result)
    if target == 'globalWait':
        broken['kpis']['global']['pickupWait']['meanSeconds'] += 1
    elif target == 'zoneNumerator':
        broken['kpis']['byZone']['hanoi']['utilization']['busyVehicleSeconds'] += 1
    elif target == 'modeRatio':
        broken['kpis']['byMode']['CAR']['utilization']['busyFractionOfOnline'] += .1
    else:
        broken['kpis']['byMode']['CAR']['counts']['completed'] += 1
    with pytest.raises(ValueError, match='Independent'):
        audit(broken)
