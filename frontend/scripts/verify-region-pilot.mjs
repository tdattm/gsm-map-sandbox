// Validate actual live JSON/CSV exports with the existing domain validators.
// This deliberately does not wrap Hanoi in a Portable v1 envelope.
import { build } from 'vite'
import { readFile } from 'node:fs/promises'
import { resolve, dirname } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
const frontend=resolve(dirname(fileURLToPath(import.meta.url)),'..')
const root=resolve(frontend,'..'), qa=resolve(process.argv[2] ?? resolve(root,'docs/nvmr/m1b-qa'))
await build({configFile:false,logLevel:'warn',build:{lib:{entry:resolve(frontend,'src/lib/voucher.ts'),formats:['es'],fileName:()=> 'voucher.mjs'},outDir:resolve(frontend,'.replay-tools'),emptyOutDir:false}})
const { validateExperiment, experimentCsv }=await import(pathToFileURL(resolve(frontend,'.replay-tools/voucher.mjs')).href)
const e=validateExperiment(JSON.parse(await readFile(resolve(qa,'hanoi-browser-plan.json'),'utf8')))
if(e.provenance.region_id!=='nvmr-hanoi-core')throw new Error('WRONG_REGION')
for(const [name,text] of Object.entries(experimentCsv(e))){
  if(await readFile(resolve(qa,`hanoi-browser-${name}.csv`),'utf8')!==text)throw new Error('CSV_MISMATCH: '+name)
}
console.log(JSON.stringify({liveJson:'PASS: frontend route/lifecycle/pairing/ledger/KPI validator',csv:'PASS: 5 exact browser exports',region:e.provenance.region_id,portableV1:'UNSUPPORTED by design',experimentId:e.id}))
