export type PresentationProfile='standard'|'meeting'|'benchmark'
export const presentationPolicy={
  standard:{snapshotMs:100,clockHz:30,healthMs:15000},
  meeting:{snapshotMs:250,clockHz:10,healthMs:30000},
  benchmark:{snapshotMs:100,clockHz:30,healthMs:15000},
} as const
export function initialPresentationProfile():PresentationProfile {
  const value=new URLSearchParams(window.location.search).get('profile')
  return value==='meeting'||value==='benchmark'?value:'standard'
}
