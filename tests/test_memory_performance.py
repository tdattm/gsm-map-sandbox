from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from backend.app.simulation import SimulationConfig
from backend.app.simulation_cache import IdleResultCache
from backend.app.simulation_jobs import JobStore, create_router
from backend.app.simulation_resources import resource_decision

GIB = 1024**3


def state(physical=1.8, commit=3.):
    return {'availablePhysicalBytes': int(physical*GIB), 'systemCommitAvailableBytes': int(commit*GIB)}


@pytest.mark.parametrize('changes', [{'bookingCount': 5001}, {'horizonSeconds': 3601}, {'maxCandidates': 256},
    {'onlineSchedule': [{'timeSeconds': i, 'onlineFraction': .5} for i in range(9)]}])
def test_ordinary_admission_has_bounded_workload_and_preserves_extended_guard(changes):
    base = dict(fleetSize=100, carCount=40, bookingCount=20)
    assert resource_decision(SimulationConfig(**base), state())['allowed']
    base.update(changes)
    decision = resource_decision(SimulationConfig(**base), state())
    assert not decision['allowed'] and decision['minimumAvailableGiB'] == 2.


@pytest.mark.parametrize('fleet,bookings,floor,commit,kind', [
    (100, 20, .5, 1., 'light'), (1000, 250, .5, 1., 'light'),
    (1000, 1000, .5, 1., 'light'), (1001, 250, .75, 1.5, 'routine'),
    (5000, 1250, .75, 1.5, 'routine'), (100, 1001, .75, 1.5, 'routine'),
    (5000, 5000, .75, 1.5, 'routine')])
def test_sub_gib_admission_depends_on_workload_and_exact_boundary(fleet,bookings,floor,commit,kind):
    config = SimulationConfig(fleetSize=fleet,carCount=round(fleet*.4),bookingCount=bookings)
    decision = resource_decision(config,state(floor,commit))
    assert decision['allowed'] and decision['workloadClass']==kind
    assert decision['minimumAvailableGiB']==floor
    assert not resource_decision(config,state(floor-.01,commit))['allowed']
    assert not resource_decision(config,state(floor,commit-.01))['allowed']


def test_commit_and_physical_are_independent_not_pagefile_permission_to_stress():
    config = SimulationConfig()
    assert not resource_decision(config, state(.49, 10))['allowed']
    assert not resource_decision(config, state(3, .5))['allowed']
    assert resource_decision(config, state(.5, 1))['allowed']
    assert not resource_decision(config, state(.49, 1))['allowed']


@pytest.mark.parametrize('fleet,bookings,floor',[(1000,250,.5),(5000,1250,.75)])
def test_rejection_does_not_enqueue_repeated_failed_jobs(tmp_path, monkeypatch,fleet,bookings,floor):
    monkeypatch.setattr('backend.app.simulation_resources.memory', lambda: state(floor-.01))
    store = JobStore(tmp_path)
    app = FastAPI();app.include_router(create_router(store))
    with TestClient(app) as client:
        for _ in range(3):
            response = client.post('/api/v3/simulation/jobs', json=SimulationConfig(fleetSize=fleet,carCount=round(fleet*.4),bookingCount=bookings).model_dump())
            assert response.status_code == 507
            assert response.json()['detail']['code'] == 'RESOURCE_PRESSURE'
    assert store.statuses() == []
    assert not list(tmp_path.glob('*/input.json'))


def test_idle_cache_release_keeps_reader_immutable_and_evicts_old_run():
    now = [0.]
    cache = IdleResultCache(idle_seconds=1000, clock=lambda: now[0])
    # Avoid background timing in a deterministic test of the actual expiry callback.
    cache._schedule = lambda _: None
    old = cache.get('first', lambda: {'route': [[1, 2], [3, 4]]})
    assert cache.get('first', lambda: pytest.fail('must reuse immutable cached result')) is old
    now[0] = 1001
    cache.expire()
    assert cache.status()['entries'] == 0
    assert old['route'] == [[1, 2], [3, 4]]
    cache.get('second', lambda: {'new': True})
    assert cache.status()['entries'] == 1
    cache.close()
