import { createHash } from 'node:crypto'
import { existsSync, readFileSync, readdirSync, writeFileSync } from 'node:fs'
import { resolve, relative } from 'node:path'
import { fileURLToPath } from 'node:url'
const root=fileURLToPath(new URL('..',import.meta.url))
const files=[]
function visit(dir){for(const entry of readdirSync(resolve(root,dir),{withFileTypes:true})){const name=`${dir}/${entry.name}`;if(entry.isDirectory())visit(name);else files.push(name)}}
visit('src');visit('public/icons');visit('scripts')
files.push('index.html','performance.html','package.json','package-lock.json','vite.config.ts','tsconfig.app.json')
const hash=createHash('sha256')
for(const file of files.sort()){hash.update(file.replaceAll('\\','/'));hash.update(readFileSync(resolve(root,file)))}
const sha256=hash.digest('hex'),path=resolve(root,'dist/.gsm-build.json')
if(process.argv.includes('--check')){
  if(!existsSync(path)||JSON.parse(readFileSync(path,'utf8')).sourceSha256!==sha256){console.error('Production build missing/stale. Run npm.cmd run build in frontend when enough RAM is available.');process.exit(1)}
  console.log(`Fresh production build: ${sha256}`)
}else{
  writeFileSync(path,JSON.stringify({sourceSha256:sha256,builtAt:new Date().toISOString(),scope:relative(root,path)},null,2))
}
