import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { PlaybackDock } from '../src/components/playback-dock'
import { FleetClock } from '../src/lib/fleet-clock'
import { useFleetClock } from '../src/lib/use-fleet'

afterEach(()=>{vi.restoreAllMocks();vi.unstubAllGlobals()})

function CompactClock({clock}:{clock:FleetClock}) {
  const state=useFleetClock(clock)
  return <PlaybackDock compact time={state.simulationTimeSeconds} duration={100}
    speed={state.speedMultiplier} status={state.playbackStatus} enabled label="Test"
    play={clock.play} pause={clock.pause} reset={clock.reset} seek={clock.seek} setSpeed={clock.setSpeed}/>
}

it.each([32,64])('compact %s× drives the real clock by authoritative time and stops at duration',speed=>{
  let now=0,frame:FrameRequestCallback=()=>{}
  vi.spyOn(performance,'now').mockImplementation(()=>now)
  vi.stubGlobal('requestAnimationFrame',vi.fn((callback:FrameRequestCallback)=>{frame=callback;return 1}))
  vi.stubGlobal('cancelAnimationFrame',vi.fn())
  const clock=new FleetClock();clock.configure(100)
  const view=render(<CompactClock clock={clock}/>)
  const selector=screen.getByRole('combobox',{name:'Tốc độ phát lại'})
  expect([...selector.querySelectorAll('option')].map(option=>option.value)).toEqual(['1','2','4','8','16','32','64'])
  fireEvent.change(selector,{target:{value:String(speed)}})
  expect(clock.getSnapshot().speedMultiplier).toBe(speed)
  expect(selector).toHaveValue(String(speed))
  fireEvent.click(screen.getByRole('button',{name:'Phát'}))
  act(()=>{now=1000;frame(now)})
  expect(clock.getSnapshot().simulationTimeSeconds).toBe(speed)
  expect(document.querySelector('.compact-playback')).toHaveAttribute('data-dock-time',String(speed))
  act(()=>{now=10000;frame(now)})
  expect(clock.getSnapshot()).toEqual({simulationTimeSeconds:100,speedMultiplier:speed,playbackStatus:'completed'})
  expect(document.querySelector('.compact-playback')).toHaveAttribute('data-dock-time','100')
  view.unmount();clock.dispose()
})
