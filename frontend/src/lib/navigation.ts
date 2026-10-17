export type AppMode = 'single' | 'fleet' | 'booking' | 'voucher' | 'simulation'

export function modeFromUrl(search: string): AppMode {
  const query = new URLSearchParams(search)
  if (query.get('runtime') === 'simulation') return 'simulation'
  if (query.get('runtime') === 'saved') return 'voucher'
  const mode = query.get('mode')
  return mode === 'fleet' || mode === 'booking' || mode === 'voucher' ? mode : 'single'
}

export function modeUrl(href: string, mode: AppMode, runtime: 'live' | 'saved' = 'live') {
  const url = new URL(href)
  // Preserve unrelated URL options; fixture controls belong only to Simulation.
  for (const name of ['runtime', 'mode', 'fixture', 'fleet', 'zoom']) url.searchParams.delete(name)
  if (mode === 'simulation') url.searchParams.set('runtime', 'simulation')
  else if (mode === 'voucher' && runtime === 'saved') url.searchParams.set('runtime', 'saved')
  else if (mode !== 'single') url.searchParams.set('mode', mode)
  return url.pathname + url.search + url.hash
}
