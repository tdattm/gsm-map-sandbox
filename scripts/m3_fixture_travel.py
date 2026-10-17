"""Explicit deterministic domain-only recorded travel fixture, never runtime fallback."""
import hashlib
import json
from pathlib import Path

from backend.app.schemas import RouteResponse
from backend.app.simulation import meters

FIXTURE = Path(__file__).resolve().parents[1]/'tests/fixtures/m3/travel-matrix.json'


def load_fixture():
    return json.loads(FIXTURE.read_text(encoding='utf-8'))


def fixture_identities():
    digest = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    return {m: {'regionId': 'nvmr-hanoi-core', 'vehicleType': m, 'profile': 'synthetic-directed-ring',
        'profileSha256': hashlib.sha256(m.encode()).hexdigest(), 'graphManifestSha256': digest,
        'sourceSha256': digest, 'extractSha256': digest, 'algorithm': 'recorded-fixture'} for m in ('CAR', 'MOTORBIKE')}


class RecordedTravel:
    distance = staticmethod(meters)

    def __init__(self, mode):
        fixture = load_fixture()
        self.anchors = fixture['anchors']
        self.indices = {tuple(p): i for i, p in enumerate(self.anchors)}
        self.matrix = fixture['durationMatrices'][mode]
        self.counts = {'nearest': 0, 'table': 0, 'route': 0, 'routeCacheHits': 0, 'tableCacheHits': 0}
        self.mode = mode

    def eta(self, start, end):
        return self.matrix[self.indices[tuple(start)]][self.indices[tuple(end)]]

    async def nearest(self, point):
        self.counts['nearest'] += 1
        self.indices[tuple(point)]
        return tuple(point)

    async def table(self, positions, pickup):
        self.counts['table'] += 1
        return [self.eta(p, pickup) for p in positions]

    async def route(self, start, end):
        self.counts['route'] += 1
        eta = self.eta(start, end)
        if eta <= 0:
            raise ValueError('Stationary pickup must not request an invented route')
        return RouteResponse(coordinates=[start, end], duration=eta, distance=max(.1, meters(start, end)),
            snap_points=[{'location': start, 'distance': 0}, {'location': end, 'distance': 0}],
            duration_source=f'Recorded synthetic {self.mode} ring graph fixture; not OSRM')
