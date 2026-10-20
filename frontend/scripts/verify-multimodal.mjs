// Verify an actual browser JSON export using the product's M2 validator.
import { build } from 'vite'
import { readFile } from 'node:fs/promises'
import { resolve,dirname } from 'node:path'
import { fileURLToPath,pathToFileURL } from 'node:url'
import assert from 'node:assert/strict'
const frontend=resolve(dirname(fileURLToPath(import.meta.url)),'..')
const evidence=resolve(frontend,'../docs/nvmr/m2-evidence')
await build({configFile:false,logLevel:'warn',build:{lib:{entry:resolve(frontend,'src/lib/multimodal.ts'),formats:['es'],fileName:()=> 'multimodal.mjs'},outDir:resolve(frontend,'.replay-tools'),emptyOutDir:false}})
const {validateMixed}=await import(pathToFileURL(resolve(frontend,'.replay-tools/multimodal.mjs')).href)
const browser=JSON.parse(await readFile(resolve(process.argv[2] ?? resolve(evidence,'browser-mixed-plan.json')),'utf8'))
const pilot=JSON.parse(await readFile(resolve(evidence,'mixed-plan.json'),'utf8'))
validateMixed(browser,'nvmr-hanoi-core',pilot.config)
const semantic=value=>({...value,plan:Object.fromEntries(Object.entries(value.plan).filter(([k])=>!['createdAt','preparationMilliseconds'].includes(k)))})
assert.deepEqual(semantic(browser),semantic(pilot))
console.log(JSON.stringify({status:'PASS',browserExport:'typed contract, routes, lifecycle, graph identity',semanticMatch:'independent API rerun excluding wall-clock timing',portableReplay:'not supported; contract is gsm-multimodal-scenario/v1',planId:browser.plan.id}))
