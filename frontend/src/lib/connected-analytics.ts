export const fleetStates = ['OFFLINE','IDLE','ASSIGNED','ON_TRIP'] as const
export type FleetStatePoint = {timeSeconds:number} & Record<typeof fleetStates[number],number>
export interface FleetStateSeries {runId:string;fleetSize:number;durationSeconds:number;transitionPointCount:number;sampled:boolean;points:FleetStatePoint[]}
export function validateFleetStateSeries(value:FleetStateSeries,runId:string,fleetSize:number,duration:number) {
  if(!value || value.runId!==runId || value.fleetSize!==fleetSize || value.durationSeconds!==duration ||
    !Number.isInteger(value.transitionPointCount) || value.transitionPointCount<1 || typeof value.sampled!=='boolean' ||
    !Array.isArray(value.points) || !value.points.length || value.points.length>120 ||
    value.points[0].timeSeconds!==0 || value.points.at(-1)!.timeSeconds!==duration ||
    value.transitionPointCount<value.points.length || value.sampled!==(value.transitionPointCount>value.points.length)) throw new Error('Chuỗi trạng thái chưa hợp lệ.')
  let previous=-1
  for(const point of value.points) {
    if(!Number.isFinite(point.timeSeconds)||point.timeSeconds<0||point.timeSeconds>duration||point.timeSeconds<=previous||
      fleetStates.some(state=>!Number.isInteger(point[state])||point[state]<0)||
      fleetStates.reduce((sum,state)=>sum+point[state],0)!==fleetSize) throw new Error('Chuỗi trạng thái không bảo toàn đội xe.')
    previous=point.timeSeconds
  }
  return value
}
export function simulationTimestamp(seconds:number) {
  const whole=Math.floor(seconds),hours=Math.floor(whole/3600),minutes=Math.floor(whole%3600/60),rest=whole%60
  return `${hours?`${hours}:`:''}${String(minutes).padStart(2,'0')}:${String(rest).padStart(2,'0')}`
}
