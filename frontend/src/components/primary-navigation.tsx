import { Car, FlaskConical, Route, Users, PanelLeftClose, EyeOff, X, Layers } from 'lucide-react'
import { modeLabels } from '@/lib/vi'
import { Dialog } from '@base-ui/react/dialog'
import { Button } from './ui/button'

import type { AppMode as Mode } from '@/lib/navigation'
type NavigationSize = 'expanded' | 'collapsed' | 'hidden'
const modes = [
  { id: 'single', label: modeLabels.single, icon: Route },
  { id: 'fleet', label: modeLabels.fleet, icon: Car },
  { id: 'booking', label: modeLabels.booking, icon: Users },
  { id: 'voucher', label: modeLabels.voucher, icon: FlaskConical },
  { id: 'simulation', label: 'Mô phỏng quy mô lớn', icon: Layers },
] as const

export function PrimaryNavigation({ mode, size, onMode, onSize, mobileOpen, onMobileOpen }: {
  mode: Mode; size: NavigationSize; onMode: (mode: Mode) => void; onSize: (size: NavigationSize) => void
  mobileOpen: boolean; onMobileOpen: (open: boolean) => void
}) {
  const menu = (mobile: boolean) => <nav aria-label={mobile ? "Menu chính trên di động" : "Menu chính"}>{modes.map(item => <button key={item.id} title={item.label} aria-label={item.label} aria-current={mode === item.id ? 'page' : undefined} onClick={() => { onMode(item.id); onMobileOpen(false) }}><item.icon size={19} /><span>{item.label}</span></button>)}</nav>
  return <>
    <aside className={`primary-navigation ${size}`} aria-label="Menu chính" hidden={size === 'hidden'}>
      <p className="nav-caption">CHẾ ĐỘ MÔ PHỎNG</p>{menu(false)}
      <div className="nav-actions"><Button variant="ghost" aria-label={size === 'expanded' ? "Thu gọn menu" : "Mở rộng menu"} onClick={() => onSize(size === 'expanded' ? 'collapsed' : 'expanded')}><PanelLeftClose size={18} /></Button><Button variant="ghost" aria-label="Ẩn menu" onClick={() => onSize('hidden')}><EyeOff size={18}/></Button></div>
      <small>Mô phỏng cục bộ<br/>OSM · OSRM</small>
    </aside>
    <Dialog.Root open={mobileOpen} onOpenChange={onMobileOpen}>
      <Dialog.Portal><Dialog.Backdrop className="sheet-backdrop"/><Dialog.Popup className="navigation-sheet"><Dialog.Title>Menu chính</Dialog.Title><Dialog.Description>Chọn chế độ mô phỏng</Dialog.Description><Dialog.Close aria-label="Đóng menu" className="sheet-close"><X size={20}/></Dialog.Close>{menu(true)}</Dialog.Popup></Dialog.Portal>
    </Dialog.Root>
  </>
}
