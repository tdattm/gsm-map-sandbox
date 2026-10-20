"""Versioned adapter: shared v1 dispatcher, explicit mode partitions, no voucher changes."""
import hashlib
import json
from pydantic import Field, model_validator
from .booking import PrepareRequest, demand_inputs, build_plan
from .fleet import candidate_catalog
from .modes import VehicleType, routing_identity


class MixedRequest(PrepareRequest):
    vehicleTypes: list[VehicleType] = Field(min_length=1, max_length=10)
    serviceTypes: list[VehicleType] = Field(min_length=10, max_length=30)

    @model_validator(mode='after')
    def counts_match(self):
        if len(self.vehicleTypes) != self.fleetSize or len(self.serviceTypes) != self.bookingCount:
            raise ValueError('Types must correspond exactly to fleet and request counts')
        return self


def mode_catalog(context):
    catalog = candidate_catalog(context.base if hasattr(context,'base') else context)
    identity = routing_identity(context)
    # The new contract uses content identity, not a legacy CAR runtime URL.
    provenance={k:v for k,v in catalog['provenance'].items() if k not in ('router_url','image_digest')}
    catalog['provenance'] = {**provenance, 'region_id':context.id, 'profile':identity['profile'],
        'profile_sha256':identity['profileSha256'],'graph_manifest_sha256':identity['graphManifestSha256'],
        'vehicle_type': identity['vehicleType'], 'routingIdentity': identity}
    catalog['datasetFingerprint'] = hashlib.sha256(json.dumps(catalog['provenance'], sort_keys=True).encode()).hexdigest()
    catalog['routingSource'] = f"OSRM local / {identity['profile']} / MLD"
    catalog['candidateSource'] = f"Local OSM vertices; {identity['vehicleType']} snaps checked during preparation; separate static pilot audit"
    return catalog


async def prepare_mixed(config, contexts, travels, cancelled=None):
    core = PrepareRequest.model_validate({k:v for k,v in config.model_dump().items() if k not in ('vehicleTypes','serviceTypes')})
    identities = {m:routing_identity(c) for m,c in contexts.items()}
    # The common potential draw is tied to all pinned graphs and the explicit new contract.
    first_context=next(iter(contexts.values()))
    catalog = candidate_catalog(getattr(first_context,'base',first_context))
    common={k:v for k,v in catalog['provenance'].items() if k not in
            ('router_url','profile','profile_sha256','graph_manifest_sha256','image_digest')}
    catalog['provenance'] = {**common, 'region_id':first_context.id, 'routingIdentities': identities, 'modelVersion': 'dispatch-multimodal/v1'}
    catalog['datasetFingerprint'] = hashlib.sha256(json.dumps(catalog['provenance'],sort_keys=True).encode()).hexdigest()
    initial,demand = demand_inputs(catalog,core)
    vehicles = {v.id:m for v,m in zip(initial,config.vehicleTypes)}
    # demand_inputs returns chronological order; pin service to stable booking ID, not response completion order.
    services = {f'BK-{i+1:03}':m for i,m in enumerate(config.serviceTypes)}
    plan = await build_plan(catalog,core,next(iter(travels.values())),cancelled,inputs=demand,initial=initial,
                            vehicle_modes=vehicles,booking_modes=services,mode_travel=travels)
    if any(routing_identity(c)!=identities[m] for m,c in contexts.items()):
        from fastapi import HTTPException
        raise HTTPException(503,{'code':'ROUTING_IDENTITY_CHANGED','message':'Graph đã đổi trong khi chuẩn bị.'})
    raw = plan.model_dump(mode='json')
    raw['routingSource']='OSRM local / ' + ' + '.join(sorted(contexts)) + ' / MLD'
    raw['assumptions']={**raw['assumptions'],'dispatchVersion':'dispatch-multimodal/v1',
        'compatibleVehicles':'Exact requested service type only; no automatic substitution',
        'serviceOutage':'Preparation fails explicitly; no partial/fabricated plan returned'}
    for v in raw['vehicles']: v['vehicleType']=vehicles[v['id']]
    for b in raw['demand']: b['serviceType']=services[b['id']]
    for a in raw['assignments']:
        if vehicles[a['vehicleId']] != services[a['bookingId']]: raise ValueError('Cross-mode assignment')
        a['vehicleType']=vehicles[a['vehicleId']]
        a['routingIdentity']=identities[a['vehicleType']]
    raw['id']=hashlib.sha256(json.dumps({'config':config.model_dump(),'fingerprint':catalog['datasetFingerprint'],'version':'dispatch-multimodal/v1'},sort_keys=True).encode()).hexdigest()
    raw['routingRequests']={f'{m}.{name}':count for m,t in travels.items() for name,count in t.counts.items()}
    return {'schemaVersion':'gsm-multimodal-scenario/v1','regionId':next(iter(contexts.values())).id,
            'config':config.model_dump(),'routingIdentities':identities,'plan':raw,
            'assumptions':{'vehicleClass':'electric motorcycle 70 km/h design, assumed 6 kW; not moped',
                'eta':'OSRM static model-based estimates, not measured GSM traffic',
                'voucher':'No multimodal choice or voucher behavior in this contract'}}
