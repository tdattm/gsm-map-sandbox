export type MobilityIconKind='car'|'motorbike'|'passenger'|'pickup'|'dropoff'
/** Shared local silhouettes for native MapLibre sprites and small legacy markers. */
export const mobilityIconUrl=(kind:MobilityIconKind)=>`${import.meta.env.BASE_URL}icons/gsm/${kind}.svg`
export function MobilityIcon({kind,size=26}:{kind:MobilityIconKind;size?:number}) {
  return <img src={mobilityIconUrl(kind)} width={size} height={size} alt="" aria-hidden="true" draggable={false}/>
}
