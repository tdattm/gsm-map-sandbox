import type { Map as LibreMap } from 'maplibre-gl'
import { mobilityIconUrl, type MobilityIconKind } from '@/components/mobility-icon'

export const iconKinds:MobilityIconKind[]=['car','motorbike','passenger','pickup','dropoff']
export async function registerMobilityIcons(map:LibreMap,signal:AbortSignal) {
  await Promise.all(iconKinds.map(kind=>new Promise<void>((resolve,reject)=>{
    const img=new Image()
    const cleanup=()=>{img.onload=null;img.onerror=null;signal.removeEventListener('abort',aborted)}
    const aborted=()=>{cleanup();img.src='';resolve()}
    signal.addEventListener('abort',aborted,{once:true})
    img.onerror=()=>{cleanup();reject(new Error(`Không tải được icon ${kind}`))}
    img.onload=()=>{
      cleanup();if(signal.aborted||!map.getStyle()){resolve();return}
      try {
        const canvas=document.createElement('canvas');canvas.width=64;canvas.height=64
        const ctx=canvas.getContext('2d');if(!ctx)throw new Error('Canvas icon unavailable')
        ctx.drawImage(img,0,0,64,64)
        if(!map.hasImage(`gsm-${kind}`))map.addImage(`gsm-${kind}`,ctx.getImageData(0,0,64,64),{pixelRatio:2})
        resolve()
      }catch(e){reject(e)}
    }
    img.src=mobilityIconUrl(kind)
  })))
}
