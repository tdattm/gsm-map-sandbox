// Production browser QA. Only loopback servers; evidence is separate from historical docs/evidence.
import { createRequire } from 'node:module'
import fs from 'node:fs/promises'
import http from 'node:http'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import assert from 'node:assert/strict'
import { build } from 'vite'
const require = createRequire(import.meta.url)
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright')
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..'),dest=path.join(root,'docs/localization/qa'),dist=path.join(root,'frontend/dist')
await fs.mkdir(dest,{recursive:true})
await build({configFile:false,logLevel:'warn',build:{lib:{entry:path.join(root,'frontend/src/lib/batch.ts'),formats:['es'],fileName:()=> 'batch.mjs'},outDir:path.join(root,'frontend/.replay-tools'),emptyOutDir:false}})
const sample=JSON.parse(await fs.readFile(path.join(dist,'replay/demo-experiment.json'),'utf8'))
const artifact=await import(pathToFileURL(path.join(root,'frontend/.replay-tools/artifact.mjs')))
const voucher=await import(pathToFileURL(path.join(root,'frontend/.replay-tools/voucher.mjs')))
const report={checks:[],layouts:[],console:[],requests:[],downloads:[],errors:[]}
const check=(name,details={})=>{report.checks.push({name,status:'PASS',...details});console.log(name,'PASS')}
const mime={'.html':'text/html','.js':'text/javascript','.mjs':'text/javascript','.css':'text/css','.json':'application/json','.geojson':'application/json','.woff2':'font/woff2','.svg':'image/svg+xml'}
const server=http.createServer(async(req,res)=>{try{const url=new URL(req.url,'http://127.0.0.1');if(url.pathname.startsWith('/api/')||req.method!=='GET'){res.writeHead(503);res.end('STATIC_REPLAY_HAS_NO_BACKEND');return}const file=path.resolve(dist,'.'+decodeURIComponent(url.pathname==='/'?'/index.html':url.pathname));if(!file.startsWith(dist+path.sep)){res.writeHead(403);res.end();return}const bytes=await fs.readFile(file);res.writeHead(200,{'Content-Type':mime[path.extname(file)]||'application/octet-stream'});res.end(bytes)}catch{res.writeHead(404);res.end()}})
await new Promise(resolve=>server.listen(4183,'127.0.0.1',resolve))
const browser=await chromium.launch({headless:true}),context=await browser.newContext({viewport:{width:1440,height:900},acceptDownloads:true}),page=await context.newPage()
page.on('console',m=>{if(['error','warning'].includes(m.type()))report.console.push({type:m.type(),message:m.text(),url:page.url()})});page.on('pageerror',e=>report.errors.push(e.message));page.on('request',r=>report.requests.push({url:r.url(),method:r.method(),runtime:page.url()}))
const button=name=>page.getByRole('button',{name,exact:true})
page.on('response',r=>{if(r.status()>=400)report.requests.push({failedUrl:r.url(),status:r.status()})})
const waitUsable=()=>button('Phát').waitFor({state:'visible'}).then(()=>page.waitForFunction(()=>!document.querySelector('.dock-buttons button')?.disabled,{},{timeout:120000}))
async function snapshot(name){
 await page.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth,{},{timeout:5000}).catch(()=>{})
 await page.screenshot({path:path.join(dest,name+'.png')})
 const layout=await page.evaluate(()=>({width:innerWidth,height:innerHeight,scrollWidth:document.documentElement.scrollWidth,canvasCount:document.querySelectorAll('.maplibregl-canvas').length,overflowElements:[...document.querySelectorAll('*')].filter(e=>e.getBoundingClientRect().right>innerWidth+2).slice(0,20).map(e=>({tag:e.tagName,cls:e.className,right:e.getBoundingClientRect().right})),visiblePanels:[...document.querySelectorAll('.map-workspace,.analytics-panel,.playback-dock')].filter(e=>e.getBoundingClientRect().width>0).map(e=>e.className),clippedButtons:[...document.querySelectorAll('button')].filter(e=>e.getBoundingClientRect().width>0 && e.scrollWidth>e.clientWidth+2).map(e=>e.textContent),bodyText:document.body.innerText}));report.layouts.push({name,...layout});assert(layout.scrollWidth<=layout.width,name+' horizontal overflow');assert.equal(layout.canvasCount,1);check('layout '+name,{clippedButtons:layout.clippedButtons})
}
async function download(name,label){const waiting=page.waitForEvent('download');await button(label).click();const d=await waiting,file=path.join(dest,name);await d.saveAs(file);report.downloads.push({name,suggestedFilename:d.suggestedFilename()});return fs.readFile(file,'utf8')}
async function modeLayouts(mode) {
 for(const [width,height]of [[1366,768],[390,844]]){await page.setViewportSize({width,height});await snapshot(mode+'-'+width+'-inspector');if(width<900){await button('Đóng bảng chi tiết').click();await snapshot(mode+'-'+width+'-map');await button('Mở hoặc ẩn bảng chi tiết').click()}}
 await page.setViewportSize({width:1440,height:900})
}
async function chartQa(title,expected) {
 const viewport=page.locator(`[data-chart-viewport="${title}"]`),chart=viewport.locator('.experiment-chart')
 // Offscreen chart placeholders mount their content only after intersection.
 await viewport.scrollIntoViewIfNeeded()
 await chart.locator('svg.recharts-surface').waitFor()
 const legend=await chart.locator('.recharts-legend-wrapper').count()
 assert(legend>0,'chart legend '+title)
 const shape=chart.locator('.recharts-bar-rectangle').first()
 if(await shape.count()){await shape.hover({force:true});await page.waitForTimeout(100);const tooltip=await chart.locator('.recharts-tooltip-wrapper').innerText();assert(expected.some(word=>tooltip.includes(word)),'tooltip terminology '+title)}
 await page.screenshot({path:path.join(dest,'chart-'+(title.includes('ngân sách')?'budget':'funnel')+'.png')})
 check('chart '+title,{legend,expected})
}
try{
 await page.goto('http://127.0.0.1:4183/?runtime=saved&audit=1');await button('Tải kịch bản mẫu').click();await waitUsable();await page.waitForTimeout(800);check('saved actual artifact')
 for(const [width,height] of [[1440,900],[1366,768],[390,844]]){
  await page.setViewportSize({width,height});if(width<900){await button('Đóng bảng chi tiết').click();await button('Phân tích').click()}
  await snapshot('saved-'+width+'-analytics');if(width<900){await button('Bản đồ').click();await snapshot('saved-'+width+'-map');await button('Mở menu chính').click();await page.getByRole('navigation',{name:'Menu chính trên di động'}).waitFor();await page.keyboard.press('Escape');await button('Mở hoặc ẩn bảng chi tiết').click()}
 }
 await page.setViewportSize({width:1440,height:900});await button('Thu gọn menu').click();await button('Mở rộng menu').click();await button('Ẩn menu').click();await button('Mở menu chính').click();check('navigation collapse expand hide restore')
 await button('Kết quả cuối kịch bản').click()
 const metrics=JSON.parse(await page.locator('[data-experiment-metrics]').getAttribute('data-experiment-metrics'));for(const arm of ['baseline','treatment'])assert(artifact.sameData(metrics[arm],sample.payload.final[arm]));check('saved final KPI equals artifact')
 await chartQa('Các bước chuyển đổi đặt xe',['Baseline','Treatment'])
 const portable=await download('portable.json','Xuất thí nghiệm Portable v1'),validated=await artifact.importArtifact(portable);assert.equal(artifact.canonicalJson(validated),artifact.canonicalJson(sample));check('portable roundtrip digest',{digest:validated.integrity.digest})
 const legacy=await download('legacy.json','Xuất JSON · toàn bộ kế hoạch');assert.equal(artifact.canonicalJson(JSON.parse(legacy)),artifact.canonicalJson(sample.payload))
 await page.locator('.experiment-actions summary').click()
 for(const [key,label] of Object.entries({summary:'Tổng hợp',decisions:'Quyết định đặt xe',bookings:'Yêu cầu đặt xe',ledger:'Sổ ngân sách',series:'Chuỗi thời gian'})){const text=await download(key+'.csv','CSV · '+label);assert.equal(text,voucher.experimentCsv(sample.payload)[key])}check('legacy JSON and five byte-exact CSV exports')
 await page.getByLabel('Nhập thí nghiệm đã lưu',{exact:true}).setInputFiles(path.join(dest,'portable.json'));await waitUsable();check('browser reimport portable')
 for(const [text,expected] of [['{invalid','không hợp lệ'],[JSON.stringify({...sample,schemaVersion:'unsupported/v9'}),'Phiên bản schema'],[JSON.stringify({...sample,integrity:{...sample.integrity,digest:'0'.repeat(64)}}),'SHA-256']]){await page.getByLabel('Nhập thí nghiệm đã lưu',{exact:true}).setInputFiles({name:'invalid.json',mimeType:'application/json',buffer:Buffer.from(text)});await page.getByRole('alert').waitFor();assert((await page.getByRole('alert').innerText()).includes(expected));assert.equal(await page.locator('[data-experiment-id]').getAttribute('data-experiment-id'),sample.payload.id)}check('invalid JSON schema hash preserve verified replay')
 await button('Phân tích kinh doanh nâng cao').click();await button('Phân tích nhiều lượt chạy').click();await button('Chạy nhiều lượt').waitFor();assert(await button('Chạy nhiều lượt').isDisabled());check('batch saved guard')
 await chartQa('Phân bổ ngân sách voucher',['Ngân sách','Chi phí'])
 const slider=page.getByRole('slider',{name:'Dòng thời gian mô phỏng'});await slider.focus();await page.keyboard.press('ArrowRight');assert(await slider.getAttribute('aria-valuenow'));check('keyboard timeline')
 assert(!report.requests.some(r=>r.runtime.includes(':4183') && (new URL(r.url).origin!=='http://127.0.0.1:4183'||new URL(r.url).pathname.startsWith('/api/'))));check('static no API OSRM external requests')
 // Capture the final desktop after the GeoJSON worker has painted, beyond initial loading.
 await page.getByLabel('Nhập thí nghiệm đã lưu',{exact:true}).setInputFiles(path.join(dest,'portable.json'));await waitUsable();await button('Đóng phân tích kinh doanh').click();await button('Tại thời điểm hiện tại').click();await page.locator('.analytics-panel').evaluate(e=>{e.scrollTop=0});await snapshot('saved-1440-analytics')
 if(!process.argv.includes('--saved-only')){
  await page.goto('http://127.0.0.1:4174/?audit=1');await page.waitForFunction(()=>document.querySelector('.header-status')?.textContent.includes('OSRM kết nối'),{},{timeout:30000})
  const canvas=page.locator('.maplibregl-canvas');let routeOk=false
  for(const points of [[[.45,.45],[.55,.55]],[[.4,.5],[.6,.5]],[[.45,.6],[.5,.4]]]){const box=await canvas.boundingBox();for(const [x,y]of points)await page.mouse.click(box.x+box.width*x,box.y+box.height*y);try{await page.waitForFunction(()=>!document.querySelector('.dock-buttons button')?.disabled,{},{timeout:15000});routeOk=true;break}catch{await button('Xóa điểm A/B và chọn lại').click()}}
  assert(routeOk,'A1 route calculation');await snapshot('live-a1-desktop');check('A1 actual route')
  await modeLayouts('live-a1')
  await button('Mô phỏng đội xe').click();await button('Tạo kịch bản').click();await waitUsable();assert.equal(await page.locator('[data-vehicle-row]').count(),5);await snapshot('live-a2-desktop');check('A2 actual fleet routes')
  await modeLayouts('live-a2')
  await button('Phát').click();await button('Tạm dừng').click();await button('Về đầu').click()
  await button('Đặt xe và điều phối').click();await button('Tạo kịch bản đặt xe').click();await waitUsable();await snapshot('live-a3-desktop');check('A3 actual dispatch')
  await modeLayouts('live-a3')
  await button('Phòng thí nghiệm voucher').click();await button('Chuẩn bị thí nghiệm').click();await waitUsable();check('A4 actual paired preparation')
  for(const speed of [1,2,4,8,16,32,64]){await page.getByLabel('Tốc độ tùy chỉnh',{exact:true}).fill(String(speed));await button('Áp dụng').click();assert.equal(await page.locator('.playback-dock').getAttribute('data-dock-speed'),String(speed))}check('speeds 1x to 64x')
  await button('Phát').click();await page.waitForFunction(()=>Number(document.querySelector('.playback-dock').dataset.dockTime)>0);await button('Tạm dừng').click();const time=await page.locator('.playback-dock').getAttribute('data-dock-time');await button('Baseline').click();await button('Treatment').click();assert.equal(await page.locator('.playback-dock').getAttribute('data-dock-time'),time);await page.getByLabel('Thời điểm mô phỏng (giây)',{exact:true}).fill('100');await button('Đến thời điểm').click();await button('Về đầu').click();assert.equal(await page.locator('.playback-dock').getAttribute('data-dock-time'),'0');check('A4 play pause seek reset arm preserve time')
  await button('Kết quả cuối kịch bản').click();await snapshot('live-a4-desktop');await button('Phân tích kinh doanh nâng cao').click();await button('Phân tích nhiều lượt chạy').click();await page.getByLabel('Seed gốc cho nhiều lượt chạy').fill('a5-real-2026');await button('Chạy nhiều lượt').click();await page.waitForFunction(()=>document.querySelector('[data-batch-status]')?.dataset.batchStatus.startsWith('Complete'),{},{timeout:180000});check('batch real completion',{summary:JSON.parse(await page.locator('[data-batch-summary]').getAttribute('data-batch-summary'))})
  await snapshot('live-batch-desktop');await download('batch.json','Xuất JSON nhiều lượt chạy');await download('batch.csv','Xuất CSV từng lượt chạy');await download('batch-summary.csv','Xuất CSV tổng hợp')
  const exportedBatch=JSON.parse(await fs.readFile(path.join(dest,'batch.json'),'utf8'));assert.equal(await fs.readFile(path.join(dest,'batch.csv'),'utf8'),(await import(pathToFileURL(path.join(root,'frontend/.replay-tools/batch.mjs')))).batchCsv(exportedBatch.results));check('batch CSV retains exact field/value semantics')
  await page.getByLabel('Yếu tố phân tích độ nhạy').selectOption('beta');await button('Chạy nhiều lượt').click();await page.waitForFunction(()=>document.querySelector('[data-batch-status]')?.dataset.batchStatus.startsWith('Complete'),{},{timeout:240000});await download('sensitivity.json','Xuất JSON nhiều lượt chạy');check('actual beta OFAT')
  for(const[name,prior]of [['batch','none'],['sensitivity','beta']]){const current=JSON.parse(await fs.readFile(path.join(dest,name+'.json'),'utf8')),original=JSON.parse(await fs.readFile(path.join(root,'docs/evidence/a5/real-batch-'+prior+'.json'),'utf8'));assert(artifact.sameData(current.summary,original.summary));for(let i=0;i<current.results.length;i++){const a=current.results[i],b=original.results[i];for(const key of ['baseline','treatment','increment','cpic','status'])assert(artifact.sameData(a[key],b[key]),name+' '+i+' '+key)}check(name+' matches historical A5 numerical results',{successful:current.summary.successful,failed:current.summary.errors})}
  await page.getByLabel('Seed gốc cho nhiều lượt chạy').fill('cancel-localization');await button('Chạy nhiều lượt').click();await button('Hủy các lượt chạy').click();await page.waitForFunction(()=>document.querySelector('[data-batch-status]')?.dataset.batchStatus.startsWith('Cancelled'));check('batch cancellation')
  for(const [width,height]of [[1366,768],[390,844]]){await page.setViewportSize({width,height});if(width<900){await button('Đóng bảng chi tiết').click();await button('Phân tích').click()}await snapshot('live-a4-'+width);if(width<900){await button('Bản đồ').click();await snapshot('live-a4-mobile-map')}}
 }
 check('browser no uncaught exceptions',{count:report.errors.length});assert.equal(report.errors.length,0)
}catch(error){report.errors.push(error.stack);process.exitCode=1;console.error(error.message);await page.screenshot({path:path.join(dest,'failure.png')})}
finally{await fs.writeFile(path.join(dest,process.argv.includes('--saved-only')?'saved-browser-report.json':'browser-report.json'),JSON.stringify(report,null,2)+'\n');await browser.close();await new Promise(resolve=>server.close(resolve))}
