import { useEffect, useRef, useState } from 'react'
import type { GeoJSONSource, MapMouseEvent } from 'maplibre-gl'
import { useMap } from './ui/map'
import { vehicleFeatures, type SelectedJourney, type SimulationSnapshot, type SimulationRoute } from '@/lib/simulation'
import { registerMobilityIcons, iconKinds } from '@/lib/simulation-map-icons'

export interface MapTelemetry {setDataMs:number[];sourceLagMs:number[];selectionMs:number[];snapshotReceivedWall:number;mapReady:boolean;sourceCount:number;layerCount:number;zoom:number;renderedClusters:number;renderedVehicles:number;clusterRepresented:number;webglRenderer:string;measure:(seconds?:number,freeze?:()=>number|void,options?:{pan?:boolean})=>Promise<Record<string,unknown>>;focus:(id:string)=>void;focusTrip:()=>void;zoomTo:(zoom:number,inspectVehicle?:boolean)=>void}
export function emptyTelemetry():MapTelemetry {return {setDataMs:[],sourceLagMs:[],selectionMs:[],snapshotReceivedWall:0,mapReady:false,sourceCount:0,layerCount:0,zoom:0,renderedClusters:0,renderedVehicles:0,clusterRepresented:0,webglRenderer:'unknown',measure:async()=>({error:'Map chưa sẵn sàng'}),focus:()=>{},focusTrip:()=>{},zoomTo:()=>{}}}
const ids=['m4-clusters','m4-cluster-count','m4-vehicles','m4-state','m4-selected','m4-route','s1-pickup-route','s1-trip-route','s1-stops','s1-stop-labels','s1-selected-icon']
const empty:GeoJSON.FeatureCollection={type:'FeatureCollection',features:[]}
const quantile=(values:number[],p:number)=>values.length?[...values].sort((a,b)=>a-b)[Math.min(values.length-1,Math.floor(values.length*p))]:null
export function SimulationMap({snapshot,selectedId,route,journey=null,onSelect,onCandidates,telemetry}:{snapshot:SimulationSnapshot|null;selectedId:string|null;route:SimulationRoute|null;journey?:SelectedJourney|null;onSelect:(id:string)=>void;onCandidates?:(ids:string[])=>void;telemetry:React.RefObject<MapTelemetry>}) {
  const {map,isLoaded}=useMap(),snapshotRef=useRef(snapshot),selectRef=useRef(onSelect),candidateRef=useRef(onCandidates),journeyRef=useRef(journey),submitted=useRef(0)
  const [iconStatus,setIconStatus]=useState('Đang tải biểu tượng phương tiện…')
  snapshotRef.current=snapshot;selectRef.current=onSelect;candidateRef.current=onCandidates;journeyRef.current=journey
  useEffect(()=>{
    if(!map||!isLoaded)return
    const t=telemetry.current
    const icons=new AbortController()
    setIconStatus('Đang tải biểu tượng phương tiện…')
    void registerMobilityIcons(map,icons.signal).then(()=>{if(!icons.signal.aborted)setIconStatus('')}).catch(e=>{if(!icons.signal.aborted)setIconStatus(String(e))})
    map.addSource('m4-fleet',{type:'geojson',data:empty,promoteId:'id',cluster:true,clusterMaxZoom:13,clusterRadius:45,clusterProperties:{carCount:['+',['case',['==',['get','vehicleType'],'CAR'],1,0]],bikeCount:['+',['case',['==',['get','vehicleType'],'MOTORBIKE'],1,0]]}})
    map.addSource('m4-selected-route',{type:'geojson',data:empty})
    map.addSource('m4-selection',{type:'geojson',data:empty,promoteId:'id'})
    map.addSource('s1-journey',{type:'geojson',data:empty})
    map.addSource('s1-stops',{type:'geojson',data:empty})
    // Routes below symbols, so pickup/vehicle silhouettes stay legible.
    map.addLayer({id:ids[6],type:'line',source:'s1-journey',filter:['==',['get','phase'],'pickup'],paint:{'line-color':'#a9670b','line-width':['case',['get','active'],6,3],'line-dasharray':[2,1.5],'line-opacity':['case',['get','active'],1,.55]}})
    map.addLayer({id:ids[7],type:'line',source:'s1-journey',filter:['==',['get','phase'],'trip'],paint:{'line-color':'#176c75','line-width':['case',['get','active'],6,3],'line-opacity':['case',['get','active'],1,.55]}})
    map.addLayer({id:ids[5],type:'line',source:'m4-selected-route',paint:{'line-color':'#dc7034','line-width':3,'line-opacity':.9}})
    map.addLayer({id:ids[0],type:'circle',source:'m4-fleet',filter:['has','point_count'],paint:{'circle-radius':['step',['get','point_count'],17,100,23,1000,31],'circle-color':['case',['>', ['get','carCount'],['get','bikeCount']],'#2779a7','#8b56a5'],'circle-stroke-width':2,'circle-stroke-color':'#fff'}})
    map.addLayer({id:ids[1],type:'symbol',source:'m4-fleet',filter:['has','point_count'],layout:{'text-field':['to-string',['get','point_count_abbreviated']],'text-font':['Geist'],'text-size':12,'text-allow-overlap':true},paint:{'text-color':'#fff'}})
    map.addLayer({id:ids[2],type:'symbol',source:'m4-fleet',filter:['!', ['has','point_count']],layout:{'icon-image':['match',['get','vehicleType'],'CAR','gsm-car','gsm-motorbike'],'icon-size':['interpolate',['linear'],['zoom'],10,.65,16,1],'icon-allow-overlap':true,'icon-ignore-placement':true},paint:{'icon-opacity':['case',['==',['get','state'],'OFFLINE'],.4,1]}})
    // ASCII state letters stay inside the packaged Geist Latin unicode ranges.
    map.addLayer({id:ids[3],type:'symbol',source:'m4-fleet',filter:['!', ['has','point_count']],layout:{'text-field':['match',['get','state'],'OFFLINE','×','ASSIGNED','P','ON_TRIP','T','R'],'text-font':['Geist'],'text-size':12,'text-offset':[1.15,-1.05],'text-allow-overlap':true,'text-ignore-placement':true},paint:{'text-color':'#173d36','text-halo-color':'#fff','text-halo-width':2}})
    map.addLayer({id:ids[4],type:'circle',source:'m4-selection',paint:{'circle-radius':21,'circle-color':'rgba(0,0,0,0)','circle-stroke-color':'#ee6637','circle-stroke-width':3}})
    // Keep the one selected silhouette visible even when the rest of its depot is clustered.
    map.addLayer({id:ids[10],type:'symbol',source:'m4-selection',layout:{'icon-image':['match',['get','vehicleType'],'CAR','gsm-car','gsm-motorbike'],'icon-size':1.1,'icon-allow-overlap':true,'icon-ignore-placement':true}})
    map.addLayer({id:ids[8],type:'symbol',source:'s1-stops',layout:{'icon-image':['concat','gsm-',['get','kind']],'icon-size':1.2,'icon-anchor':'bottom','icon-allow-overlap':true,'icon-ignore-placement':true}})
    map.addLayer({id:ids[9],type:'symbol',source:'s1-stops',layout:{'text-field':['get','label'],'text-font':['Geist'],'text-size':12,'text-anchor':'top','text-offset':[0,.2],'text-allow-overlap':true},paint:{'text-color':'#173d36','text-halo-color':'#fff','text-halo-width':2}})
    const clicked=(e:MapMouseEvent)=>{
      const hits=map.queryRenderedFeatures(e.point,{layers:[ids[0],ids[2],ids[10]]}),hit=hits[0];if(!hit)return
      if(hit.properties.cluster_id!==undefined) {
        const source=map.getSource('m4-fleet') as GeoJSONSource
        void source.getClusterExpansionZoom(Number(hit.properties.cluster_id)).then(zoom=>{if(map.getSource('m4-fleet')===source && hit.geometry.type==='Point')map.easeTo({center:hit.geometry.coordinates as [number,number],zoom,duration:300})}).catch(()=>{})
      }else {
        const started=performance.now(),vehicleIds=new Set(snapshotRef.current?.vehicles.map(v=>v.id))
        // Rendered feature IDs may be numeric tile IDs, including on the selected overlay.
        // Business identity comes from properties and must belong to this snapshot.
        const keys=[...new Set(hits.filter(h=>h.properties.cluster_id===undefined).map(h=>h.properties.id??h.id).filter((id):id is string=>typeof id==='string'&&vehicleIds.has(id)))].slice(0,30)
        candidateRef.current?.(keys)
        if(keys.length){selectRef.current(keys[0]);requestAnimationFrame(()=>t.selectionMs.push(performance.now()-started))}
      }
    }
    const settled=(e:{sourceId?:string;isSourceLoaded?:boolean})=>{if(e.sourceId==='m4-fleet'&&e.isSourceLoaded&&submitted.current){t.sourceLagMs.push(performance.now()-submitted.current);submitted.current=0}}
    map.on('click',clicked);map.on('sourcedata',settled)
    t.mapReady=true
    t.zoomTo=(zoom,inspectVehicle)=>{const vehicle=inspectVehicle?(snapshotRef.current?.vehicles.find(v=>v.serviceState==='ASSIGNED'||v.serviceState==='ON_TRIP')??snapshotRef.current?.vehicles[0]):null;map.jumpTo(vehicle?{zoom,center:vehicle.position}:{zoom})}
    t.focus=id=>{const v=snapshotRef.current?.vehicles.find(v=>v.id===id);if(v)map.easeTo({center:v.position,zoom:16,duration:300})}
    t.focusTrip=()=>{const j=journeyRef.current;if(!j)return;const points=[...(j.pickupRoute?.coordinates??[]),...j.tripRoute.coordinates],xs=points.map(p=>p[0]),ys=points.map(p=>p[1]);map.fitBounds([[Math.min(...xs),Math.min(...ys)],[Math.max(...xs),Math.max(...ys)]],{padding:65,maxZoom:17,duration:300})}
    t.measure=async(seconds=5,freeze,options)=>{
      if(document.hidden)return {error:'Tab phải ở foreground'}
      const samples:number[]=[],longTasks:number[]=[],started=performance.now(),updatesStart=t.setDataMs.length,lagStart=t.sourceLagMs.length,selectionStart=t.selectionMs.length,visibilityAtStart=document.visibilityState,focusAtStart=document.hasFocus()
      let hiddenFrames=0
      let observer:PerformanceObserver|null=null
      try {observer=new PerformanceObserver(list=>list.getEntries().forEach(e=>longTasks.push(e.duration)));observer.observe({type:'longtask',buffered:false})}catch{/* Not all browsers expose longtask. */}
      const camera=map.getCenter(),original={lng:camera.lng,lat:camera.lat},zoom=map.getZoom()
      await new Promise<void>(resolve=>{let last=performance.now(),frame=0;const finish=()=>{cancelAnimationFrame(frame);clearTimeout(timeout);resolve()},timeout=setTimeout(finish,seconds*1000+3000);const tick=(now:number)=>{if(!map.getCanvas().isConnected){finish();return}if(document.hidden)hiddenFrames++;samples.push(now-last);last=now;const elapsed=now-started;if(options?.pan!==false)map.jumpTo({center:[original.lng+Math.sin(elapsed/500)*.0003,original.lat]});if(elapsed<seconds*1000)frame=requestAnimationFrame(tick);else finish()};frame=requestAnimationFrame(tick)})
      const duration=performance.now()-started
      observer?.disconnect();if(!map.getCanvas().isConnected)return {cancelled:true};map.jumpTo({center:original,zoom})
      // Pause the one playback clock after the timed sample, then wait for its final
      // source update. Cluster IDs must be inspected against an immutable index.
      const frozenTime=freeze?.(),settleStarted=performance.now()
      const source=map.getSource('m4-fleet') as GeoJSONSource
      // A fixed delay can read old rendered tiles against a newly rebuilt cluster
      // index. First await the final clock snapshot + quiet source, then MapLibre
      // idle (including placement/fades). This is outside the FPS window.
      const snapshotSettled=await new Promise<boolean>(resolve=>{
        let frame=0
        const finish=(ok:boolean)=>{cancelAnimationFrame(frame);clearTimeout(timeout);resolve(ok)}
        const timeout=setTimeout(()=>finish(false),5000)
        const check=()=>{
          if(!map.getCanvas().isConnected){finish(false);return}
          const matching=typeof frozenTime!=='number'||Math.abs((snapshotRef.current?.simulationTimeSeconds??-1)-frozenTime)<=.001
          if(matching&&map.isSourceLoaded('m4-fleet')&&!submitted.current&&performance.now()-t.snapshotReceivedWall>=250){finish(true);return}
          frame=requestAnimationFrame(check)
        };check()
      })
      const renderSettled=snapshotSettled&&await new Promise<boolean>(resolve=>{
        const finish=(ok:boolean)=>{clearTimeout(timer);map.off('idle',idle);resolve(ok)}
        const idle=()=>finish(true),timer=setTimeout(()=>finish(false),5000)
        map.on('idle',idle);map.triggerRepaint()
      })
      const features=map.queryRenderedFeatures({layers:[ids[0],ids[2]]}),clusters=new Map<string,{count:number;car:number;bike:number}>(),vehicles=new Set<string>()
      for(const f of features)if(f.properties.cluster_id!==undefined)clusters.set(String(f.properties.cluster_id),{count:Number(f.properties.point_count),car:Number(f.properties.carCount),bike:Number(f.properties.bikeCount)});else vehicles.add(String(f.id??f.properties.id))
      const oracleFailures:string[]=[],leafIds=new Set<string>();let checked=0,representedLeafCount=0
      if(hiddenFrames)oracleFailures.push('Tab was hidden during sampled frames; foreground benchmark condition failed')
      if(!snapshotSettled||!renderSettled)oracleFailures.push('Final snapshot/source/render did not settle; capture cannot certify clusters')
      for(const [id,cluster] of clusters) {
        try {
          const leaves=await source.getClusterLeaves(Number(id),cluster.count,0);checked++;representedLeafCount+=leaves.length
          const car=leaves.filter(f=>f.properties?.vehicleType==='CAR').length,bike=leaves.filter(f=>f.properties?.vehicleType==='MOTORBIKE').length
          if(leaves.length!==cluster.count||car!==cluster.car||bike!==cluster.bike||car+bike!==leaves.length)oracleFailures.push(`cluster ${id}: count/type mismatch`)
          for(const leaf of leaves){const key=String(leaf.id??leaf.properties?.id);if(!key||key==='undefined'||leafIds.has(key)||vehicles.has(key))oracleFailures.push(`cluster ${id}: missing/duplicate leaf ${key}`);leafIds.add(key)}
        }catch(e){oracleFailures.push(`cluster ${id}: ${String(e)}`)}
      }
      const represented=[...clusters.values()].reduce((a,b)=>a+b.count,0)+vehicles.size
      const inView=snapshotRef.current?.vehicles.filter(v=>map.getBounds().contains(v.position)).length??0
      if(represented===0)oracleFailures.push(inView>0?'Vehicles are inside viewport but no fleet features were rendered':'No vehicles visible: choose a viewport containing vehicles before accepting this benchmark')
      const sourceData=await source.getData()
      const diagnostics={center:map.getCenter().toArray(),bounds:map.getBounds().toArray(),inputVehiclesInBounds:inView,sourceFeatures:sourceData.type==='FeatureCollection'?sourceData.features.length:null,loaded:map.isSourceLoaded('m4-fleet')}
      const clusterOracle={checked,failures:oracleFailures,representedLeafCount,uniqueLeafCount:leafIds.size,scope:represented===snapshotRef.current?.counts.total?'all fleet represented in current viewport':'visible viewport clusters only',passed:oracleFailures.length===0,diagnostics,snapshotSettled,renderSettled,postFreezeWaitMs:performance.now()-settleStarted,frozenTime}
      const gl=map.getCanvas().getContext('webgl2'),debug=gl?.getExtension('WEBGL_debug_renderer_info')
      const memory=(performance as Performance & {memory?:{usedJSHeapSize:number;totalJSHeapSize:number;jsHeapSizeLimit:number}}).memory
      const style=map.getStyle(),selection=snapshotRef.current?.vehicles[0]
      if(selection){const begin=performance.now();selectRef.current(selection.id);await new Promise<void>(r=>requestAnimationFrame(()=>{t.selectionMs.push(performance.now()-begin);r()}))}
      return {kind:'browser-webgl-render-only',visibility:{atStart:visibilityAtStart,atEnd:document.visibilityState,focusAtStart,focusAtEnd:document.hasFocus(),hiddenFrames,maxFrameGapMs:Math.max(0,...samples)},cadenceDiagnostic:samples.length/(duration/1000)<10?'LOW_RAF_CADENCE: compare plain RAF in Performance Lab; do not infer fleet/icon cause':'NORMAL_IN_CAPTURE',rawFrameGapsMs:samples,sampleCondition:'warm in-page; no page/process restart',pageAgeMs:performance.now(),sourceUpdatesBefore:updatesStart,fixture:snapshotRef.current?.runId.startsWith('fixture-'),fleetSize:snapshotRef.current?.counts.total,simulationTimeSeconds:snapshotRef.current?.simulationTimeSeconds,zoom,browser:navigator.userAgent,viewport:[map.getCanvas().clientWidth,map.getCanvas().clientHeight],devicePixelRatio,webglRenderer:gl?(debug?gl.getParameter(debug.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER)):'unavailable',durationMs:duration,frames:samples.length,fps:samples.length/(duration/1000),frameTimeP50Ms:quantile(samples,.5),frameTimeP95Ms:quantile(samples,.95),longTaskSupported:PerformanceObserver.supportedEntryTypes.includes('longtask'),longTasks:longTasks.length,longTaskTotalMs:longTasks.reduce((a,b)=>a+b,0),heap:memory?{usedJSHeapSize:memory.usedJSHeapSize,totalJSHeapSize:memory.totalJSHeapSize,jsHeapSizeLimit:memory.jsHeapSizeLimit}:null,domMarkerCount:map.getContainer().querySelectorAll('.maplibregl-marker').length,sourceCount:Object.keys(style.sources).length,layerCount:style.layers.length,setDataSubmissionP50Ms:quantile(t.setDataMs.slice(updatesStart),.5),setDataSubmissionP95Ms:quantile(t.setDataMs.slice(updatesStart),.95),sourceLoadedLagP95Ms:quantile(t.sourceLagMs.slice(lagStart),.95),dataUpdates:t.setDataMs.length-updatesStart,selectionToNextFrameMs:quantile(t.selectionMs.slice(selectionStart),.95),snapshotAgeMs:performance.now()-t.snapshotReceivedWall,visibleClusterCount:clusters.size,visibleVehicleCount:vehicles.size,visibleRepresentedVehicles:represented,clusterOracle,clusterScope:'viewport; duplicates removed; not full-source coverage assertion',pan:options?.pan===false?'OFF':'continuous small jumpTo pan during capture; zoom fixed',mapLifetime:map.getCanvas().dataset.mapLifetime}
    }
    if(!map.getCanvas().dataset.mapLifetime)map.getCanvas().dataset.mapLifetime=crypto.randomUUID()
    return ()=>{
      icons.abort();t.mapReady=false;t.focus=()=>{};t.focusTrip=()=>{};t.zoomTo=()=>{};t.measure=async()=>({error:'Map đã đóng'})
      map.off('click',clicked);map.off('sourcedata',settled)
      // Parent Map may already have removed its style before child passive cleanup.
      // MapLibre.hasImage dereferences style directly, unlike getSource/getLayer.
      if(map.getStyle()) {
        for(const id of [...ids].reverse())if(map.getLayer(id))map.removeLayer(id)
        for(const id of ['m4-fleet','m4-selected-route','m4-selection','s1-journey','s1-stops'])if(map.getSource(id))map.removeSource(id)
        for(const kind of iconKinds)if(map.hasImage(`gsm-${kind}`))map.removeImage(`gsm-${kind}`)
      }
    }
  },[map,isLoaded,telemetry])
  useEffect(()=>{
    if(!map||!isLoaded||!map.getSource('m4-fleet'))return
    const start=performance.now();(map.getSource('m4-fleet') as GeoJSONSource).setData(snapshot?vehicleFeatures(snapshot):empty)
    const t=telemetry.current;t.setDataMs.push(performance.now()-start);t.snapshotReceivedWall=performance.now();submitted.current=start
    // Bounded instrumentation; benchmark windows never retain unbounded playback history.
    if(t.setDataMs.length>10000)t.setDataMs.splice(0,5000);if(t.sourceLagMs.length>10000)t.sourceLagMs.splice(0,5000)
  },[snapshot,map,isLoaded,telemetry])
  useEffect(()=>{
    if(!map||!isLoaded||!map.getSource('m4-selection'))return
    const source=map.getSource('m4-selection') as GeoJSONSource,vehicle=snapshot?.vehicles.find(v=>v.id===selectedId)
    if(!vehicle||!snapshot){source.setData(empty);return}
    // Exactly the authoritative snapshot position. No chord interpolation across curved roads.
    source.setData({type:'Feature',id:vehicle.id,geometry:{type:'Point',coordinates:vehicle.position},properties:{id:vehicle.id,vehicleType:vehicle.vehicleType,state:vehicle.serviceState}})
  },[snapshot,selectedId,map,isLoaded])
  useEffect(()=>{
    if(map&&isLoaded&&map.getSource('m4-selected-route'))(map.getSource('m4-selected-route') as GeoJSONSource).setData(!journey&&route?{type:'Feature',geometry:{type:'LineString',coordinates:route.coordinates},properties:{}}:empty)
  },[map,isLoaded,route,journey])
  const state=snapshot?.vehicles.find(v=>v.id===selectedId)?.serviceState
  useEffect(()=>{
    if(!map||!isLoaded||!map.getSource('s1-journey'))return
    const lines:GeoJSON.FeatureCollection={type:'FeatureCollection',features:[]},stops:GeoJSON.FeatureCollection={type:'FeatureCollection',features:[]}
    if(journey) {
      for(const [phase,r] of [['pickup',journey.pickupRoute],['trip',journey.tripRoute]] as const)if(r)lines.features.push({type:'Feature',geometry:{type:'LineString',coordinates:r.coordinates},properties:{phase,active:state===(phase==='pickup'?'ASSIGNED':'ON_TRIP')}})
      const waiting=state==='ASSIGNED',d=journey.detail
      stops.features=[{type:'Feature',id:'pickup',geometry:{type:'Point',coordinates:d.pickup},properties:{kind:waiting?'passenger':'pickup',label:waiting?'Khách chờ đón':'Điểm đón · đã đón'}},{type:'Feature',id:'dropoff',geometry:{type:'Point',coordinates:d.dropoff},properties:{kind:'dropoff',label:'Điểm trả khách'}}]
    }
    ;(map.getSource('s1-journey') as GeoJSONSource).setData(lines)
    ;(map.getSource('s1-stops') as GeoJSONSource).setData(stops)
  },[map,isLoaded,journey,state])
  return iconStatus?<div className="simulation-icon-status" role="status">{iconStatus}</div>:null
}
