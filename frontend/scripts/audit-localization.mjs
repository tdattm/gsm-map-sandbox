// Read-only source inventory plus byte-level preservation checks. No Git mutation.
import fs from 'node:fs/promises'
import { createHash } from 'node:crypto'
import path from 'node:path'
import ts from 'typescript'
import { fileURLToPath } from 'node:url'
const frontend=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),root=path.resolve(frontend,'..'),dest=path.join(root,'docs/localization')
const walk=async(dir)=>{const result=[];for(const e of await fs.readdir(dir,{withFileTypes:true})){const p=path.join(dir,e.name);if(e.isDirectory())result.push(...await walk(p));else result.push(p)}return result}
const candidates=[]
for(const file of (await walk(path.join(frontend,'src'))).filter(f=>f.endsWith('.tsx')||f.endsWith('vi.ts'))){
 const source=await fs.readFile(file,'utf8'),tree=ts.createSourceFile(file,source,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX)
 const visit=node=>{
  if(ts.isStringLiteral(node)||ts.isJsxText(node)||ts.isNoSubstitutionTemplateLiteral(node)){
   const value=ts.isJsxText(node)?node.getText(tree).trim():node.text
   if(value){const attribute=ts.isJsxAttribute(node.parent)?node.parent.name.getText(tree):null
    const category=ts.isJsxText(node)||['title','aria-label','aria-description','placeholder','label'].includes(attribute)?'presentation':attribute?'technical-attribute':'contextual-review'
    candidates.push({file:path.relative(root,file).replaceAll('\\','/'),line:tree.getLineAndCharacterOfPosition(node.getStart(tree)).line+1,value,category})}
  }
  ts.forEachChild(node,visit)
 };visit(tree)
}
await fs.writeFile(path.join(dest,'final-string-inventory.json'),JSON.stringify(candidates,null,2)+'\n')
const hashes=JSON.parse(await fs.readFile(path.join(dest,'protected-hashes.json'),'utf8')),changed=[]
for(const[file,expected]of Object.entries(hashes)){try{const actual=createHash('sha256').update(await fs.readFile(path.join(root,file))).digest('hex');if(actual!==expected)changed.push({file,expected,actual})}catch(error){changed.push({file,error:error.message})}}
const actualSource=(await walk(path.join(root,'backend/app'))).filter(f=>f.endsWith('.py'))
const summary={protectedFiles:Object.keys(hashes).length,changed,sourceCandidates:candidates.length,backendSourceFiles:actualSource.length,status:changed.length?'FAIL':'PASS'}
await fs.writeFile(path.join(dest,'integrity-report.json'),JSON.stringify(summary,null,2)+'\n');console.log(JSON.stringify(summary,null,2));if(changed.length)process.exitCode=1
