"""Single-host durable bounded queue; atomic publication and cross-process locks."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import uuid

from fastapi import APIRouter, HTTPException, Query

from .config import PROJECT_ROOT
from .simulation import SimulationConfig, snapshot
from .simulation_details import booking_detail
from .simulation_cache import IdleResultCache
from .simulation_resources import require_simulation_headroom

TERMINAL = {'COMPLETED', 'FAILED', 'CANCELLED', 'INTERRUPTED'}


def default_store():
    return Path(os.environ.get('GSM_SIMULATION_STORE', str(PROJECT_ROOT/'build/m3/jobs'))).resolve()


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, value):
    import time
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f'.{path.name}.{uuid.uuid4().hex}.tmp')
    try:
        with temporary.open('w', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
            stream.flush()
            os.fsync(stream.fileno())
        for attempt in range(20):
            try:
                os.replace(temporary, path)
                break
            except PermissionError:
                if attempt == 19:
                    raise
                time.sleep(.005)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def file_lock(path, blocking=True):
    """OS releases advisory lock even on worker kill; lock file is never unlinked."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as stream:
        stream.seek(0, 2)
        if stream.tell() == 0:
            stream.write(b'0')
            stream.flush()
        stream.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK if blocking else msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def error(code, message, status=409):
    raise HTTPException(status, {'code': code, 'message': message})


class JobStore:
    def __init__(self, root=None, capacity=8):
        self.root = Path(root) if root is not None else default_store()
        self.capacity = capacity

    def path(self, id):
        if not re.fullmatch(r'[a-f0-9]{32}', id):
            error('JOB_NOT_FOUND', 'Unknown simulation job', 404)
        return self.root/id

    def read(self, id):
        import time
        target = self.path(id)/'status.json'
        for attempt in range(20):
            try:
                return json.loads(target.read_text(encoding='utf-8'))
            except FileNotFoundError:
                error('JOB_NOT_FOUND', 'Unknown simulation job', 404)
            except PermissionError:
                if attempt == 19:
                    raise
                time.sleep(.005)

    def statuses(self):
        return [self.read(p.parent.name) for p in sorted(self.root.glob('*/status.json'), key=lambda p: p.parent.name)]

    def create(self, config):
        with file_lock(self.root/'.store.lock'):
            if sum(s['status'] not in TERMINAL for s in self.statuses()) >= self.capacity:
                error('JOB_QUEUE_FULL', 'Bounded simulation queue is full', 429)
            id = uuid.uuid4().hex
            raw = config.model_dump()
            regional = raw.get('schemaVersion') == 'gsm-nvmr-regional-scenario/v1'
            connected = raw.get('schemaVersion') == 'gsm-nvmr-connected-scenario/v1'
            manifest = {'schemaVersion': ('gsm-nvmr-connected-job/v1' if connected else
                'gsm-nvmr-regional-job/v1' if regional else 'gsm-simulation-job/v1'), 'id': id, 'config': raw,
                'inputHash': hashlib.sha256(json.dumps(raw, sort_keys=True).encode()).hexdigest(),
                'createdAt': timestamp(), 'engineVersion': ('heap-grid-connected/v1' if connected else
                    'heap-grid-regional/v1' if regional else 'heap-grid/v1')}
            atomic_json(self.path(id)/'input.json', manifest)
            status = {'id': id, 'runId': id, 'status': 'QUEUED', 'progress': 0.,
                'createdAt': manifest['createdAt'], 'updatedAt': timestamp(), 'config': raw, 'inputHash': manifest['inputHash']}
            atomic_json(self.path(id)/'status.json', status)
            return status

    def claim(self):
        with file_lock(self.root/'.store.lock'):
            queued = sorted((s for s in self.statuses() if s['status'] == 'QUEUED'), key=lambda s: (s['createdAt'], s['id']))
            if not queued:
                return None
            status = queued[0]
            status.update(status='RUNNING', progress=0., updatedAt=timestamp(), workerPid=os.getpid())
            atomic_json(self.path(status['id'])/'status.json', status)
            return status

    def update_progress(self, id, progress):
        with file_lock(self.root/'.store.lock'):
            status = self.read(id)
            if status['status'] == 'RUNNING':
                status.update(progress=max(status['progress'], min(.99, progress)), updatedAt=timestamp())
                atomic_json(self.path(id)/'status.json', status)

    def cancel(self, id):
        with file_lock(self.root/'.store.lock'):
            status = self.read(id)
            if status['status'] not in TERMINAL:
                status.update(status='CANCELLED', updatedAt=timestamp())
                atomic_json(self.path(id)/'status.json', status)
            return status

    def finish(self, id, result=None, failure=None):
        with file_lock(self.root/'.store.lock'):
            status = self.read(id)
            if status['status'] != 'RUNNING':
                return status  # Cancellation is terminal and cannot resurrect.
            if failure is None:
                if result is None or result['runId'] != id:
                    raise ValueError('Final result identity mismatch')
                # Atomic status COMPLETED is published only after a complete result exists.
                atomic_json(self.path(id)/'event-log.json', result['events'])
                atomic_json(self.path(id)/'result.json', result)
                status.update(status='COMPLETED', progress=1., summary={k: result[k] for k in
                    ('simulationDurationSeconds', 'counts', 'routingIdentities')})
            else:
                status.update(status='FAILED', error=failure)
            status.update(updatedAt=timestamp())
            atomic_json(self.path(id)/'status.json', status)
            return status

    def interrupt_abandoned(self):
        # Caller must own .worker.lock, proving no other worker can be running.
        with file_lock(self.root/'.store.lock'):
            for status in self.statuses():
                if status['status'] == 'RUNNING':
                    status.update(status='INTERRUPTED', updatedAt=timestamp(),
                        error={'code': 'WORKER_INTERRUPTED', 'message': 'Worker restarted; create a new job to rerun'})
                    atomic_json(self.path(status['id'])/'status.json', status)

    def result(self, id):
        if self.read(id)['status'] != 'COMPLETED':
            error('RESULT_NOT_FINAL', 'Only a completed job exposes its final result')
        return json.loads((self.path(id)/'result.json').read_text(encoding='utf-8'))

    def runtime(self):
        # Probe the actual lifetime OS lock, including workers launched before S0.
        # A PID file or an old heartbeat would not prove store ownership.
        worker = 'unknown'
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            # A permission-denied OPEN is not evidence of a live worker lock.
            with (self.root/'.worker.lock').open('a+b'):
                pass
        except OSError:
            pass
        else:
            try:
                with file_lock(self.root/'.worker.lock', blocking=False):
                    worker = 'offline'
            except OSError as exc:
                import errno
                if exc.errno in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                    worker = 'locked'
        return {'schemaVersion': 'gsm-dev-runtime/v1', 'application': 'gsm-map-sandbox',
            'workspace': str(PROJECT_ROOT.resolve()), 'store': str(self.root.resolve()),
            'apiPid': os.getpid(), 'worker': worker,
            'workerMeaning': 'locked = OS worker lease held for this exact store; not a progress/health heartbeat'}


def create_router(store=None):
    store = store or JobStore()
    router = APIRouter(prefix='/api/v3/simulation/jobs', tags=['NVMR scalable simulation'])
    cache = IdleResultCache()

    def legacy_status(id):
        value = store.read(id)
        if value['config'].get('schemaVersion') in ('gsm-nvmr-regional-scenario/v1', 'gsm-nvmr-connected-scenario/v1'):
            error('JOB_NOT_FOUND', 'No v3 simulation job with this identity', 404)
        return value

    def result(id):
        if legacy_status(id)['status'] != 'COMPLETED':
            error('RESULT_NOT_FINAL', 'Only a completed job exposes its final result')
        return cache.get(id, lambda: store.result(id))

    @router.post('', status_code=202)
    def create(config: SimulationConfig):
        # Refuse before creating input/status files. Worker rechecks queued jobs.
        require_simulation_headroom(config)
        return store.create(config)

    @router.get('/runtime')
    def runtime():
        from scripts.m3_resources import memory
        from .simulation_resources import SMALL_MIN_AVAILABLE_GIB, admission_policy
        current = memory()
        return {**store.runtime(), 'resultCache': cache.status(), 'resources': {
            **{k: current.get(k) for k in ('availablePhysicalBytes', 'systemCommitAvailableBytes', 'systemCommitBytes', 'systemCommitLimitBytes')},
            'smallMinimumAvailableGiB': SMALL_MIN_AVAILABLE_GIB, 'admissionPolicy': admission_policy()}}

    @router.get('/{id}')
    def status(id: str):
        return legacy_status(id)

    @router.post('/{id}/cancel')
    def cancel(id: str):
        legacy_status(id)
        return store.cancel(id)

    @router.get('/{id}/result')
    def final(id: str, summary: bool = False):
        raw = result(id)
        return {k: raw[k] for k in ('schemaVersion', 'runId', 'regionId', 'config', 'simulationDurationSeconds',
            'counts', 'routingIdentities', 'assumptions', 'metrics')} if summary else raw

    @router.get('/{id}/snapshot')
    def current(id: str, timeSeconds: float = Query(default=0, ge=0, allow_inf_nan=False)):
        return snapshot(result(id), timeSeconds)

    @router.get('/{id}/routes/{ref}')
    def route(id: str, ref: str):
        raw = result(id)['routes'].get(ref)
        if raw is None:
            error('ROUTE_UNAVAILABLE', 'No route in this immutable run', 404)
        return {k: v for k, v in raw.items() if k != 'cumulativeMeters'}

    @router.get('/{id}/bookings/{booking_id}')
    def selected_booking(id: str, booking_id: str):
        return booking_detail(result(id), booking_id)

    return router
