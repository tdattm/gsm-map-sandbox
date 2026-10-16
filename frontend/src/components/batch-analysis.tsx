import { moneyText as vnd, numberText, percentText, stateText, errorText, factorLabels, presetText, batchStatusText, statisticalDefinitionsVi } from '@/lib/vi'
import { memo, useEffect, useRef, useState } from 'react'
import { Bar, BarChart, CartesianGrid, XAxis, YAxis, ReferenceLine, ScatterChart, Scatter } from 'recharts'
import { Button } from './ui/button'
import { ChartContainer, ChartTooltip, ChartTooltipContent } from './ui/chart'
import { ChartViewport } from './chart-viewport'
import { api, regionApi, assertRegionProvenance } from '@/lib/api'
import { canonicalJson } from '@/lib/artifact'
import { batchJobs, batchCsv, batchSummaryCsv, runBatch, summarizeRuns, statisticalDefinitions, factorValues, type BatchSpec, type Factor, type RunResult } from '@/lib/batch'
import { download, type Experiment } from '@/lib/voucher'

const chartNumber = (value: number) => numberText(value, Number.isInteger(value) ? 0 : 2)

function BatchAnalysis({ experiment,live,regionId }: {experiment:Experiment;live:boolean;regionId?:string}) {
  const [baseSeed,setBaseSeed]=useState(experiment.seed),[count,setCount]=useState<10|30>(10),[factor,setFactor]=useState<Factor>('none')
  const [results,setResults]=useState<RunResult[]>([]),[spec,setSpec]=useState<BatchSpec|null>(null),[running,setRunning]=useState(false),[status,setStatus]=useState('Chưa chạy'),[error,setError]=useState('')
  const controller=useRef<AbortController|null>(null),cache=useRef(new Map<string,RunResult>())
  useEffect(()=>()=>controller.current?.abort(),[])
  const start=async()=>{
    if(!live || running)return
    const next:BatchSpec={baseSeed,seedCount:count,factor,config:experiment.config,datasetFingerprint:experiment.datasetFingerprint,routingFingerprint:canonicalJson(experiment.provenance)}
    try {batchJobs(next)}catch(e){setError(String(e));return}
    controller.current?.abort();const request=new AbortController();controller.current=request
    setSpec(next);setResults([]);setError('');setRunning(true);setStatus('Đang chạy sequential · local OSRM')
    try {await runBatch(next,async(config,signal)=>{const result=await api<Experiment>(regionApi(regionId, '/voucher-experiment/prepare'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(config),signal});assertRegionProvenance(regionId,result.provenance);return result},request.signal,result=>{if(controller.current===request)setResults(previous=>[...previous,result])},cache.current)
      if(controller.current===request)setStatus(request.signal.aborted?'Cancelled — partial results':'Complete — tất cả jobs đã có kết quả')
    }catch(e){if(controller.current===request){setError(String(e));setStatus('Failed — partial results')}}
    finally {if(controller.current===request)setRunning(false)}
  }
  const summary=summarizeRuns(results),groups=[...new Set(results.map(r=>r.job.variation))].map(value=>({value,...summarizeRuns(results.filter(r=>r.job.variation===value))}))
  const total=spec?batchJobs(spec).length:count*factorValues[factor].length
  const exportData={schemaVersion:'gsm-paired-batch/v1',status,complete:!running&&results.length===total&&!results.some(r=>r.status==='cancelled'),requestedRuns:total,spec,definitions:statisticalDefinitions,results,summary,groups,modelVersions:experiment.assumptions.versions}
  return <section className="batch-analysis" aria-label="Phân tích nhiều lượt chạy" data-batch-status={status} data-batch-summary={JSON.stringify(summary)}>
    <h3>Phân tích nhiều lượt chạy</h3><p>Mô phỏng ghép cặp · phân tích từng yếu tố (OFAT) · tối đa 90 lượt · chỉ bắt đầu khi bấm Chạy. Mọi giá trị của yếu tố dùng cùng danh sách Seed.</p>
    <div className="booking-inputs">
      <label>Seed gốc<input aria-label="Seed gốc cho nhiều lượt chạy" value={baseSeed} maxLength={128} disabled={running} onChange={e=>setBaseSeed(e.target.value)}/></label>
      <label>Số Seed<select aria-label="Số Seed cho nhiều lượt chạy" value={count} disabled={running} onChange={e=>setCount(Number(e.target.value) as 10|30)}><option value={10}>10</option><option value={30}>30</option></select></label>
      <label>Yếu tố phân tích độ nhạy<select aria-label="Yếu tố phân tích độ nhạy" value={factor} disabled={running} onChange={e=>setFactor(e.target.value as Factor)}>{Object.keys(factorValues).map(v=><option key={v} value={v}>{factorLabels[v as Factor]}</option>)}</select></label>
    </div>
    <p>{factorLabels[factor]}: {factorValues[factor].map(v => typeof v === "number" ? numberText(v) : presetText(v)).join(' / ')} · {count*factorValues[factor].length} lượt trong cấu hình kế tiếp. Yếu tố mức giảm dùng số tiền cố định (VND); các yếu tố khác giữ chính sách voucher đang cấu hình.</p>
    {!live&&<p>Phát lại đã lưu: xem và xuất thí nghiệm; chạy nhiều lượt mới cần backend Live và OSRM cục bộ.</p>}
    <Button disabled={!live||running} onClick={()=>void start()}>Chạy nhiều lượt</Button> <Button variant="outline" disabled={!running} onClick={()=>controller.current?.abort()}>Hủy các lượt chạy</Button>
    <p role="status">{batchStatusText(status)} · {results.length}/{total} bản ghi · {summary.successful} thành công · {summary.errors} thất bại · {summary.cancelled} bị hủy</p>
    {error&&<p role="alert">{errorText(error)}</p>}
    {results.length>0&&<>
      {spec?.factor!=='none'&&<p>Tổng hợp chung gộp các nhóm tham số. Dùng Phân tích độ nhạy và trường groups trong JSON để so sánh từng nhóm; Seed lặp giữa các nhóm không phải mẫu độc lập.</p>}
      <p>Mức tăng trung bình {numberText(summary.mean, 2)} · trung vị {numberText(summary.median, 2)} · độ lệch chuẩn mẫu {numberText(summary.sampleSd, 2)} · nhỏ nhất/lớn nhất {numberText(summary.min)}/{numberText(summary.max)}<br/>Tỷ lệ lượt có cải thiện {percentText(summary.improvementRate)} (n={summary.successful}) · chi phí voucher trung bình {vnd(summary.meanSpend)} · CPIC gộp {vnd(summary.pooledCpic)}</p>
      <p>Mức sử dụng ngân sách {numberText(summary.budgetUtilization.mean, 3)} (n={summary.budgetUtilization.validCount}) · chênh lệch thời gian chờ {numberText(summary.waitingDifference.mean, 2)} giây (n={summary.waitingDifference.validCount}) · chênh lệch mức sử dụng đội xe {numberText(summary.utilizationDifference.mean, 3)} (n={summary.utilizationDifference.validCount})</p>
      <ChartViewport title="Phân bố mức tăng theo cặp"><div className="experiment-chart"><h4>Phân bố mức tăng theo cặp</h4><ChartContainer config={{increment:{label:"Chuyến hoàn tất tăng thêm",color:'var(--chart-1)'}}} style={{height:240,aspectRatio:'auto'}}><BarChart data={results.filter(r=>r.status==='success').map(r=>({seed:r.job.seed+' / '+r.job.variation,increment:r.increment,spend:r.treatment!.voucherSpendVnd}))}><CartesianGrid vertical={false}/><XAxis dataKey="seed" hide/><YAxis tickFormatter={chartNumber} domain={['auto','auto']} allowDecimals={false}/><ReferenceLine y={0}/><ChartTooltip content={<ChartTooltipContent/>}/><Bar dataKey="increment" fill="var(--chart-1)" isAnimationActive={false}/></BarChart></ChartContainer></div></ChartViewport>
      <ChartViewport title="Chi phí voucher và chuyến hoàn tất tăng thêm"><div className="experiment-chart"><h4>Chi phí voucher và chuyến hoàn tất tăng thêm</h4><ChartContainer config={{spend:{label:"Chi phí đã sử dụng (VND)",color:'var(--chart-2)'}}} style={{height:240,aspectRatio:'auto'}}><ScatterChart><CartesianGrid/><XAxis tickFormatter={chartNumber} type="number" dataKey="increment" name="Chuyến hoàn tất tăng thêm" domain={['auto','auto']}/><YAxis tickFormatter={chartNumber} type="number" dataKey="spend" name="Chi phí voucher (VND)"/><ChartTooltip content={<ChartTooltipContent labelFormatter={(label,payload)=>payload?.[0]?.payload?.seed??label}/>}/><Scatter data={results.filter(r=>r.status==='success').map(r=>({seed:r.job.seed,increment:r.increment,spend:r.treatment!.voucherSpendVnd}))} fill="var(--chart-2)" isAnimationActive={false}/></ScatterChart></ChartContainer></div></ChartViewport>
      {factor!=='none'&&<ChartViewport title="Phân tích độ nhạy"><div className="experiment-chart"><h4>Phân tích độ nhạy · mức tăng chuyến hoàn tất trung bình</h4><ChartContainer config={{mean:{label:"Mức tăng trung bình",color:'var(--chart-1)'}}} style={{height:240,aspectRatio:'auto'}}><BarChart data={groups}><CartesianGrid vertical={false}/><XAxis dataKey="value" tickFormatter={presetText}/><YAxis tickFormatter={chartNumber} domain={['auto','auto']}/><ReferenceLine y={0}/><ChartTooltip content={<ChartTooltipContent/>}/><Bar dataKey="mean" fill="var(--chart-1)" isAnimationActive={false}/></BarChart></ChartContainer></div></ChartViewport>}
      <Button variant="outline" onClick={()=>download('gsm-batch-v1.json',JSON.stringify({...exportData,createdAt:new Date().toISOString()},null,2),'application/json')}>Xuất JSON nhiều lượt chạy</Button> <Button variant="outline" onClick={()=>download('gsm-batch-runs.csv',batchCsv(results),'text/csv;charset=utf-8')}>Xuất CSV từng lượt chạy</Button>
      <Button variant="outline" onClick={()=>download('gsm-batch-summary.csv',batchSummaryCsv(spec!,results,status),'text/csv;charset=utf-8')}>Xuất CSV tổng hợp</Button>
      <details><summary>Danh sách lượt chạy và định nghĩa thống kê</summary><p>{statisticalDefinitionsVi.join(' ')}</p><table><thead><tr><th>Seed / yếu tố</th><th>Trạng thái</th><th>Δ</th><th>Lý do</th></tr></thead><tbody>{results.map(r=><tr key={r.job.id}><td>{r.job.seed} / {presetText(r.job.variation)}</td><td>{stateText(r.status)}</td><td>{numberText(r.increment)}</td><td>{r.error ? errorText(r.error) : '—'}</td></tr>)}</tbody></table></details>
    </>}
  </section>
}
export default memo(BatchAnalysis)
