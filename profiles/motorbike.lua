-- Hanoi electric MOTORCYCLE pilot v1: design 70 km/h, assumed 6 kW.
-- Independent access, dimensional and speed rules; pinned upstream handlers only.
-- Model estimates, not calibrated traffic/GSM ETA. See profiles/motorbike.json.
api_version = 4
local upstream = dofile('/opt/car.lua')
local Set = require('lib/set')
local Sequence = require('lib/sequence')
local access = require('lib/access').find_access_tag
local allowed = Set {'yes','designated','permissive'}
local roads = Set {'trunk','trunk_link','primary','primary_link','secondary','secondary_link',
  'tertiary','tertiary_link','unclassified','residential','living_street','service'}
local explicit_roads = Set {'track','path','pedestrian','cycleway'}
local hierarchy = Sequence {'motorcycle','motor_vehicle','vehicle','access'}
local conditional = {'access:conditional','vehicle:conditional','motor_vehicle:conditional',
  'motorcycle:conditional','oneway:conditional','oneway:motorcycle:conditional'}
function setup()
  local p = upstream.setup()
  p.access_tags_hierarchy = hierarchy
  p.restrictions = Sequence {'motorcycle','motor_vehicle','vehicle'}
  p.access_tag_whitelist = allowed
  p.restricted_access_tag_list = Set {}
  p.vehicle_height=1.7; p.vehicle_width=0.8; p.vehicle_length=2.1; p.vehicle_weight=250
  p.speeds.highway = {trunk=30,trunk_link=20,primary=35,primary_link=20,
    secondary=30,secondary_link=20,tertiary=25,tertiary_link=15,
    unclassified=20,residential=20,living_street=10,service=15,
    track=10,path=10,pedestrian=10,cycleway=10}
  p.properties.weight_name='duration'
  p.properties.max_speed_for_map_matching=70/3.6
  return p
end
function process_way(p,way,result,relations)
  local h=way:get_value_by_key('highway')
  if h=='motorway' or h=='motorway_link' or way:get_value_by_key('motorroad')=='yes' then return end
  local a=access(way,hierarchy)
  if a and a~='' and not allowed[a] then return end
  if not roads[h] and not (explicit_roads[h] and allowed[way:get_value_by_key('motorcycle')]) then return end
  for _,key in ipairs(conditional) do
    local v=way:get_value_by_key(key); if v and v~='' then return end
  end
  local o=way:get_value_by_key('oneway:motorcycle') or way:get_value_by_key('oneway')
  if o and o~='' and o~='yes' and o~='no' and o~='1' and o~='-1' and o~='true' and o~='false' and o~='0' then return end
  upstream.process_way(p,way,result,relations)
end
function process_node(p,node,result,relations)
  upstream.process_node(p,node,result,relations)
  local a=access(node,hierarchy)
  local b=node:get_value_by_key('barrier')
  if a and a~='' and not allowed[a] then result.barrier=true end
  -- Unknown/physical barriers cannot be made traversable by an access=yes tag.
  if b and b~='' and b~='no' and b~='entrance' and b~='toll_booth' and b~='border_control' then result.barrier=true end
end
return {setup=setup,process_way=process_way,process_node=process_node,process_turn=upstream.process_turn}
