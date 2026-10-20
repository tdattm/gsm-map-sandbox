import { expect, it } from 'vitest'
import { validateFleetStateSeries, simulationTimestamp, type FleetStateSeries } from '../src/lib/connected-analytics'
const sample=():FleetStateSeries=>({runId:'persisted',fleetSize:2,durationSeconds:60,transitionPointCount:3,sampled:false,points:[
 {timeSeconds:0,OFFLINE:1,IDLE:1,ASSIGNED:0,ON_TRIP:0},
 {timeSeconds:20,OFFLINE:0,IDLE:1,ASSIGNED:1,ON_TRIP:0},
 {timeSeconds:60,OFFLINE:0,IDLE:1,ASSIGNED:0,ON_TRIP:1},
]})
it('accepts conserved real state counts with correct identity',()=>{expect(validateFleetStateSeries(sample(),'persisted',2,60).points).toHaveLength(3)})
it('rejects missing points, wrong totals, wrong identity, duplicate and fabricated endpoint times',()=>{
 const cases=[{...sample(),points:[]},{...sample(),runId:'old'}, {...sample(),durationSeconds:80}]
 const incorrect=sample();incorrect.points[1].IDLE=2;cases.push(incorrect)
 const duplicated=sample();duplicated.points[1].timeSeconds=0;cases.push(duplicated)
 for(const value of cases)expect(()=>validateFleetStateSeries(value,'persisted',2,60)).toThrow()
})
it('formats simulation time including runs longer than one hour',()=>{
 expect(simulationTimestamp(65)).toBe('01:05');expect(simulationTimestamp(19465.5)).toBe('5:24:25')
})

it('accepts fractional time-weighted means only with contiguous declared intervals',()=>{
 const weighted:FleetStateSeries={runId:'persisted',fleetSize:2,durationSeconds:60,transitionPointCount:3,sampled:false,aggregation:'time-weighted-mean/v1',bucketCount:120,
  points:Array.from({length:121},(_,i)=>({timeSeconds:i/2,endSeconds:Math.min(i+1,120)/2,OFFLINE:.25,IDLE:1.5,ASSIGNED:.25,ON_TRIP:0}))}
 expect(validateFleetStateSeries(weighted,'persisted',2,60)).toBe(weighted)
 const gap=structuredClone(weighted);gap.points[20].endSeconds!+=1
 expect(()=>validateFleetStateSeries(gap,'persisted',2,60)).toThrow()
 const negative=structuredClone(weighted);negative.points[3].OFFLINE=-.1
 expect(()=>validateFleetStateSeries(negative,'persisted',2,60)).toThrow()
 const corrupted=structuredClone(weighted);corrupted.points[3].IDLE=1.6
 expect(()=>validateFleetStateSeries(corrupted,'persisted',2,60)).toThrow()
})
