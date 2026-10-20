export type AppMode = 'single' | 'fleet' | 'booking' | 'voucher' | 'simulation'

export function modeFromUrl(search: string): AppMode {
  const query = new URLSearchParams(search)
  if (query.get('runtime') === 'simulation') return 'simulation'
  if (query.get('runtime') === 'saved') return 'voucher'
  const mode = query.get('mode')
  if (!query.has('mode') && !query.has('runtime')) return 'simulation'
  return mode === 'fleet' || mode === 'booking' || mode === 'voucher' ? mode : 'single'
}

export function modeUrl(href: string, mode: AppMode, runtime: 'live' | 'saved' = 'live') {
  const url = new URL(href)
  // Preserve unrelated URL options; fixture controls belong only to Simulation.
  for (const name of ['runtime', 'mode', 'fixture', 'fleet', 'zoom', 'scenario', 'dev']) url.searchParams.delete(name)
  if (mode === 'simulation') { url.searchParams.set('runtime', 'simulation'); url.searchParams.set('scenario', 'connected') }
  else if (mode === 'voucher' && runtime === 'saved') url.searchParams.set('runtime', 'saved')
  else url.searchParams.set('mode', mode)
  return url.pathname + url.search + url.hash
}

/** Root presentation and explicit v5 links share the same stable workspace. */
export function connectedPresentation(search: string) {
  const query = new URLSearchParams(search)
  return (!query.has('runtime') && !query.has('mode')) ||
    (query.get('runtime') === 'simulation' && query.get('scenario') === 'connected')
}
