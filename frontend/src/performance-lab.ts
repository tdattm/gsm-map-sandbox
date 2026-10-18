import type { Map as MLMap, GeoJSONSource } from 'maplibre-gl'
const el=<T extends HTMLElement>(id:string)=>document.getElementById(id) as T
const state=el('state'),output=el('result'),rows:Record<string,unknown>[]=[]
let map:MLMap|null=null,update:number|undefined,videoTimer:number|undefined,stream:MediaStream|null=null
let stage='plain',sourceUpdates=0,sourceBytes=0,renderEvents=0,sourceEvents=0,preparedAt=performance.now(),errors:string[]=[]
type SelfProfile={sampleInterval:number;stop:()=>Promise<unknown>}
type ProfilerWindow=Window&{Profiler?:new(options:{sampleInterval:number;maxBufferSize:number})=>SelfProfile}
const q=(v:number[],p:number)=>v.length?[...v].sort((a,b)=>a-b)[Math.min(v.length-1,Math.floor(v.length*p))]:null
async function prepare(){
  clearInterval(update);map?.remove();map=null;errors=[];sourceUpdates=0;sourceBytes=0;renderEvents=0;sourceEvents=0
  stage=el<HTMLSelectElement>('stage').value;state.textContent=`Đang chuẩn bị ${stage}…`
  if(stage!=='plain'){
    const [ml,styles,fixtures,icons]=await Promise.all([import('maplibre-gl'),import('./lib/map-style'),import('./lib/simulation'),import('./lib/simulation-map-icons')])
    await import('maplibre-gl/dist/maplibre-gl.css')
    ml.setWorkerUrl('/maplibre-gl-worker.mjs')
    map=new ml.Map({container:'map',style:stage==='blank'?styles.emptyStyle:styles.regionMapStyle('nvmr-hanoi-core'),center:[105.84,21.028],zoom:13,attributionControl:false})
    map.on('error',e=>errors.push(String(e.error)))
    await new Promise<void>((resolve,reject)=>{const timer=setTimeout(()=>reject(new Error('Map load timeout (15s)')),15000);map!.once('load',()=>{clearTimeout(timer);resolve()})})
    map.on('render',()=>renderEvents++);map.on('sourcedata',()=>sourceEvents++)
    const size=Number(stage.split('-')[0])
    if(size){
      await icons.registerMobilityIcons(map,new AbortController().signal)
      map.addSource('fleet',{type:'geojson',data:fixtures.vehicleFeatures(fixtures.fixtureSnapshot(size)),cluster:true,clusterMaxZoom:13,clusterRadius:45})
      map.addLayer({id:'clusters',type:'circle',source:'fleet',filter:['has','point_count'],paint:{'circle-radius':18,'circle-color':'#2779a7'}})
      map.addLayer({id:'vehicles',type:'symbol',source:'fleet',filter:['!',['has','point_count']],layout:{'icon-image':['match',['get','vehicleType'],'CAR','gsm-car','gsm-motorbike'],'icon-allow-overlap':true,'icon-ignore-placement':true}})
      const begun=performance.now();const publish=()=>{if(!map)return;const data=fixtures.vehicleFeatures(fixtures.fixtureSnapshot(size,(performance.now()-begun)/1000));(map.getSource('fleet') as GeoJSONSource).setData(data);sourceUpdates++;if(!sourceBytes)sourceBytes=new TextEncoder().encode(JSON.stringify(data)).length}
      publish();if(stage.endsWith('play'))update=window.setInterval(publish,100)
    }
  }
  preparedAt=performance.now();state.textContent=`Sẵn sàng ${stage}; nền Hà Nội ${stage!=='plain'&&stage!=='blank'?'ON':'OFF (isolation only)'}`
}
el('prepare').onclick=()=>void prepare().catch(e=>{state.textContent=String(e);errors.push(String(e))})
el<HTMLInputElement>('video').onchange=()=>{
  clearInterval(videoTimer);stream?.getTracks().forEach(t=>t.stop());stream=null;el('media').replaceChildren()
  if(!el<HTMLInputElement>('video').checked)return
  const canvas=document.createElement('canvas');canvas.width=640;canvas.height=360;const ctx=canvas.getContext('2d')!
  let i=0;videoTimer=window.setInterval(()=>{ctx.fillStyle=`hsl(${i++%360} 30% 30%)`;ctx.fillRect(0,0,640,360);ctx.fillStyle='white';ctx.fillRect(i%600,80,40,40)},1000/30)
  stream=canvas.captureStream(30);const video=document.createElement('video');video.muted=true;video.autoplay=true;video.srcObject=stream;el('media').append(video);void video.play()
}
async function measure(){
  const button=el<HTMLButtonElement>('measure');button.disabled=true;state.textContent='Đang đo…'
  const seconds=Math.min(60,Math.max(3,Number(el<HTMLInputElement>('seconds').value)||5)),pan=el<HTMLInputElement>('pan').checked
  const start=performance.now(),times:number[]=[],timers:number[]=[],tasks:{start:number;duration:number}[]=[],vis:{at:number;state:string;focus:boolean}[]=[]
  const before={sourceUpdates,renderEvents,sourceEvents},netStart=performance.getEntriesByType('resource').length
  let profiler:SelfProfile|null=null,profileError:string|null=null
  if(el<HTMLInputElement>('profile').checked){
    try{const Constructor=(window as ProfilerWindow).Profiler;if(Constructor)profiler=new Constructor({sampleInterval:10,maxBufferSize:20000});else profileError='JS Self-Profiling API unsupported in this browser'}catch(e){profileError=String(e)}
  }
  const visibility=()=>vis.push({at:performance.now()-start,state:document.visibilityState,focus:document.hasFocus()});visibility();document.addEventListener('visibilitychange',visibility)
  let observer:PerformanceObserver|null=null
  try{observer=new PerformanceObserver(list=>list.getEntries().forEach(e=>tasks.push({start:e.startTime,duration:e.duration})));observer.observe({type:'longtask'})}catch{/* unsupported */}
  let prev=start;const interval=window.setInterval(()=>{const now=performance.now();timers.push(now-prev);prev=now},20)
  const center=map?.getCenter(),panTimes:number[]=[]
  let timedOut=false
  await new Promise<void>(resolve=>{let raf=0;const finish=()=>{cancelAnimationFrame(raf);clearTimeout(timeout);resolve()},timeout=setTimeout(()=>{timedOut=true;finish()},seconds*1000+3000);const frame=(now:number)=>{times.push(now);if(pan&&map&&center){const t=performance.now();map.jumpTo({center:[center.lng+Math.sin((now-start)/500)*.0003,center.lat]});panTimes.push(performance.now()-t)}if(now-start<seconds*1000)raf=requestAnimationFrame(frame);else finish()};raf=requestAnimationFrame(frame)})
  clearInterval(interval);observer?.disconnect();document.removeEventListener('visibilitychange',visibility);visibility()
  let jsProfile:unknown=null
  if(profiler)try{jsProfile=await profiler.stop()}catch(e){profileError=String(e)}
  const duration=performance.now()-start,gaps=times.slice(1).map((t,i)=>t-times[i]),style=map?.getStyle(),gl=map?.getCanvas().getContext('webgl2'),debug=gl?.getExtension('WEBGL_debug_renderer_info')
  const mem=(performance as Performance&{memory?:{usedJSHeapSize:number;totalJSHeapSize:number;jsHeapSizeLimit:number}}).memory
  const row={schemaVersion:'gsm-browser-isolation/v1',at:new Date().toISOString(),build:import.meta.env.DEV?'development':'production',stage,seconds,pan,syntheticVideo:!!stream,meeting:'NOT TESTED: synthetic video only',browser:navigator.userAgent,renderer:gl?(debug?gl.getParameter(debug.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER)):null,viewport:[innerWidth,innerHeight],canvas:map?[map.getCanvas().clientWidth,map.getCanvas().clientHeight]:null,dpr:devicePixelRatio,documentAgeMs:performance.now(),warmupMs:start-preparedAt,visibility:vis,frames:times.length,durationMs:duration,fps:times.length/(duration/1000),p95GapMs:q(gaps,.95),maxGapMs:Math.max(0,...gaps),rawRafTimesMs:times.map(t=>t-start),timerP95Ms:q(timers,.95),rawTimerGapsMs:timers,longTasks:tasks,panP95Ms:q(panTimes,.95),sourceUpdates:sourceUpdates-before.sourceUpdates,renderEvents:renderEvents-before.renderEvents,sourceEvents:sourceEvents-before.sourceEvents,sourceCount:style?Object.keys(style.sources).length:0,layerCount:style?.layers.length??0,geojsonUtf8Bytes:sourceBytes,heap:mem?{usedJSHeapSize:mem.usedJSHeapSize,totalJSHeapSize:mem.totalJSHeapSize,jsHeapSizeLimit:mem.jsHeapSizeLimit}:null,network:performance.getEntriesByType('resource').slice(netStart).map(e=>({name:new URL(e.name).pathname,duration:e.duration})),errors:[...errors]}
  const traceEvents=[{name:'thread_name',ph:'M',pid:1,tid:1,args:{name:'GSM page application instrumentation'}} as Record<string,unknown>,
    ...gaps.map((gap,i)=>({name:'RAF interval',cat:'gsm.raf',ph:'X',pid:1,tid:1,ts:(times[i]-start)*1000,dur:gap*1000,args:{visible:vis[0]?.state}})),
    ...tasks.map(task=>({name:'Main thread long task',cat:'gsm.longtask',ph:'X',pid:1,tid:2,ts:(task.start-start)*1000,dur:task.duration*1000})),
    ...vis.map(v=>({name:'Visibility/focus',ph:'i',s:'t',pid:1,tid:3,ts:v.at*1000,args:{state:v.state,focus:v.focus}}))]
  let elapsed=0
  for(const gap of timers){traceEvents.push({name:'20ms timer interval',cat:'gsm.timer',ph:'X',pid:1,tid:3,ts:elapsed*1000,dur:gap*1000});elapsed+=gap}
  Object.assign(row,{timedOut,jsProfile,profileError,profileSampleIntervalMs:profiler?.sampleInterval??null,
    applicationTrace:{traceEvents,displayTimeUnit:'ms',scope:'Own-page RAF/timer/long-task instrumentation; not Chrome compositor/GPU trace'},
    syntheticVideoFrames:el('media').querySelector('video')?.getVideoPlaybackQuality().totalVideoFrames??0})
  rows.push(row);output.textContent=JSON.stringify(row,null,2);el('all-results').textContent=JSON.stringify(rows);state.textContent=`${stage}: ${row.fps.toFixed(2)} FPS, p95=${row.p95GapMs?.toFixed(1)}ms${row.fps<10?' · RAF cadence thấp; kiểm tra host/scheduler trước khi quy cho fleet':''}`;button.disabled=false
}
el('measure').onclick=()=>void measure()
el('matrix').onclick=async()=>{
  const button=el<HTMLButtonElement>('matrix');button.disabled=true
  try{for(const next of ['plain','blank','basemap','100-static','100-play','1000-play','5000-play']){el<HTMLSelectElement>('stage').value=next;await prepare();await new Promise(r=>setTimeout(r,1000));await measure()}}catch(e){state.textContent=String(e);errors.push(String(e))}finally{button.disabled=false}
}
el('download').onclick=()=>{const url=URL.createObjectURL(new Blob([JSON.stringify(rows,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='gsm-browser-isolation.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
