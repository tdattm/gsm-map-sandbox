"""Admission policy only. Never changes immutable simulation inputs or dispatch."""
from fastapi import HTTPException
from scripts.m3_resources import memory

GIB = 1024**3
# Operating floors, not process memory limits or reservations. Measurements have
# not stress-tested Windows at these exact physical-availability boundaries.
SMALL_MIN_AVAILABLE_GIB = .5
ROUTINE_MIN_AVAILABLE_GIB = .75


def admission_policy():
    return {'lightMinimumAvailableGiB': SMALL_MIN_AVAILABLE_GIB,
            'routineMinimumAvailableGiB': ROUTINE_MIN_AVAILABLE_GIB,
            'lightMinimumCommitGiB': 1., 'routineMinimumCommitGiB': 1.5,
            'lightMaximumFleet': 1000, 'lightMaximumBookings': 1000,
            'routineMaximumBookings': 5000, 'maximumHorizonSeconds': 3600,
            'maximumSchedulePoints': 8, 'maximumCandidates': 128,
            'extendedMinimumAvailableGiB': 2., 'extendedMinimumCommitGiB': 2.}


def resource_decision(config, current=None):
    current = memory() if current is None else current
    # Fleet size alone is a poor memory estimate: booking history, scheduling and
    # candidate budgets also determine retained data. Never rewrite the config.
    policy = admission_policy()
    routine = (config.bookingCount <= policy['routineMaximumBookings']
               and config.horizonSeconds <= policy['maximumHorizonSeconds']
               and len(config.onlineSchedule) <= policy['maximumSchedulePoints']
               and config.maxCandidates <= policy['maximumCandidates'])
    light = (routine and config.fleetSize <= policy['lightMaximumFleet']
             and config.bookingCount <= policy['lightMaximumBookings'])
    workload = 'light' if light else 'routine' if routine else 'extended'
    minimum = policy[f'{workload}MinimumAvailableGiB']
    minimum_commit = policy[f'{workload}MinimumCommitGiB']
    physical = current['availablePhysicalBytes']/GIB
    commit = current.get('systemCommitAvailableBytes')
    reasons = []
    if physical < minimum:
        reasons.append(f'RAM khả dụng {physical:.2f} GiB < {minimum:.2f} GiB')
    if commit is not None and commit < minimum_commit*GIB:
        reasons.append(f'commit headroom {commit/GIB:.2f} GiB < {minimum_commit:.1f} GiB')
    return {'allowed': not reasons, 'workloadClass': workload,
            'minimumAvailableGiB': minimum, 'minimumCommitHeadroomGiB': minimum_commit,
            'availablePhysicalBytes': current['availablePhysicalBytes'], 'commitHeadroomBytes': commit,
            'message': '; '.join(reasons) or 'Đủ headroom tại thời điểm kiểm tra; không phải reservation hoặc bảo đảm không paging.'}


def require_simulation_headroom(config):
    decision = resource_decision(config)
    if not decision['allowed']:
        raise HTTPException(507, {'code': 'RESOURCE_PRESSURE',
            'message': decision['message']+'; giải phóng bộ nhớ rồi thử lại. Không giảm ngầm quy mô run.',
            'resources': decision})
    return decision
