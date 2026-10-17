"""Selected immutable booking adapter; never calls OSRM or modifies run results."""
from fastapi import HTTPException


def booking_detail(result, booking_id):
    def unavailable(code, message, status=404):
        raise HTTPException(status, {'code': code, 'message': message})
    required = ('bookings', 'assignments', 'routes', 'routingIdentities', 'timelines')
    if any(key not in result for key in required):
        unavailable('HISTORICAL_DETAIL_UNAVAILABLE', 'This historical run did not store selected-booking evidence', 409)
    booking = next((b for b in result['bookings'] if b['id']==booking_id), None)
    if booking is None:
        unavailable('BOOKING_NOT_FOUND', 'No such booking in this immutable run')
    assignment = next((a for a in result['assignments'] if a['bookingId']==booking_id), None)
    if assignment is None:
        unavailable('BOOKING_NOT_ASSIGNED', 'This booking has no assigned vehicle/routes', 409)
    vid = assignment['vehicleId']
    checkpoint = next((s for s in result['timelines'].get(vid, [])
                       if s['state']=='ASSIGNED' and s['bookingId']==booking_id), None)
    trip = result['routes'].get(assignment['tripRouteRef'])
    pickup = result['routes'].get(assignment['pickupRouteRef'])
    if checkpoint is None or trip is None or (assignment['pickupRouteRef'] and pickup is None):
        unavailable('HISTORICAL_DETAIL_UNAVAILABLE', 'Stored assignment/route evidence is incomplete', 409)
    mode = assignment['vehicleType']
    identity = result['routingIdentities'][mode]
    for route in (pickup, trip):
        if route and (route['runId']!=result['runId'] or route['routingIdentity']!=identity):
            unavailable('DETAIL_IDENTITY_MISMATCH', 'Stored route identity differs from assignment', 409)
    def leg(name, route, start, end):
        return {'phase': name, 'routeRef': route['routeRef'] if route else None,
                'startTimeSeconds': start, 'endTimeSeconds': end,
                'distance': route['distance'] if route else 0., 'duration': route['duration'] if route else 0.}
    return {'schemaVersion': 'gsm-simulation-booking-detail/v1', 'runId': result['runId'],
        'regionId': result['regionId'], 'bookingId': booking_id, 'vehicleId': vid, 'vehicleType': mode,
        'serviceType': booking['serviceType'], 'routingIdentity': identity,
        'requestTimeSeconds': booking['requestTimeSeconds'],
        'pickupDeadlineSeconds': booking['requestTimeSeconds']+result['config']['maxWaitSeconds'],
        'requestedPickup': booking['pickup'], 'requestedDropoff': booking['dropoff'],
        'pickup': trip['coordinates'][0], 'dropoff': trip['coordinates'][-1],
        'assignmentPosition': checkpoint['position'],
        'pickupLeg': leg('pickup', pickup, assignment['assignedAtSeconds'], assignment['pickupAtSeconds']),
        'tripLeg': leg('trip', trip, assignment['pickupAtSeconds'], assignment['dropoffAtSeconds']),
        'provenance': 'Immutable completed-run inputs, assignment and stored route references; snapped endpoints'}
