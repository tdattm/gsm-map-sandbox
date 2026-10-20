import { createContext, useContext, useState, type ReactNode } from 'react'
import { Menu, Navigation } from 'lucide-react'
import { Button } from './ui/button'
import { PrimaryNavigation } from './primary-navigation'
import type { AppMode } from '@/lib/navigation'

const ShellContext = createContext<{openMenu:()=>void}|null>(null)
export function useApplicationShell() { return useContext(ShellContext) }

export function ApplicationShell({mode,onMode,children}:{mode:AppMode;onMode:(mode:AppMode)=>void;children:ReactNode}) {
  const [open,setOpen]=useState(false)
  return <ShellContext.Provider value={{openMenu:()=>setOpen(true)}}><div className="application-root" data-testid="application-shell">
    {children}
    <PrimaryNavigation mode={mode} size="hidden" onSize={()=>{}} onMode={onMode} mobileOpen={open} onMobileOpen={setOpen} popupOnly/>
  </div></ShellContext.Provider>
}
export function ApplicationMenuButton() {
  const shell=useApplicationShell()
  return <Button variant="ghost" size="icon" aria-label="Mở menu chính" title="Menu chính" onClick={shell?.openMenu}><Menu size={18}/></Button>
}
export function ApplicationBrand({subtitle,compact=false}:{subtitle:string;compact?:boolean}) {
  return <div className={compact?'connected-brand':'brand'}>{!compact&&<span className="brand-icon"><Navigation size={24}/></span>}<div><h1>GSM Mobility Sandbox</h1><span className="brand-subtitle">{subtitle}</span></div></div>
}
