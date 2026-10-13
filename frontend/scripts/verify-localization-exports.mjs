import fs from 'node:fs/promises'
import path from 'node:path'
import assert from 'node:assert/strict'
import { fileURLToPath, pathToFileURL } from 'node:url'
const frontend=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),root=path.resolve(frontend,'..'),qa=path.join(root,'docs/localization/qa')
const batch=await import(pathToFileURL(path.join(frontend,'.replay-tools/batch.mjs'))),artifact=await import(pathToFileURL(path.join(frontend,'.replay-tools/artifact.mjs')))
const data=JSON.parse(await fs.readFile(path.join(qa,'batch.json'),'utf8'))
assert.equal(data.schemaVersion,'gsm-paired-batch/v1')
assert.equal(artifact.canonicalJson(data.definitions),artifact.canonicalJson(batch.statisticalDefinitions))
assert.equal(await fs.readFile(path.join(qa,'batch.csv'),'utf8'),batch.batchCsv(data.results))
assert.equal(await fs.readFile(path.join(qa,'batch-summary.csv'),'utf8'),batch.batchSummaryCsv(data.spec,data.results,data.status))
const audit={schema:'PASS',originalDefinitions:'PASS',runsCsv:'PASS: byte-exact',summaryCsv:'PASS: byte-exact',requested:data.requestedRuns,successful:data.summary.successful,failed:data.summary.errors,rawExportStatus:data.status}
await fs.writeFile(path.join(qa,'batch-export-verification.json'),JSON.stringify(audit,null,2)+'\n');console.log(JSON.stringify(audit,null,2))
