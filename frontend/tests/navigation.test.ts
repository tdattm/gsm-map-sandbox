import { describe, expect, it } from 'vitest'
import { modeFromUrl, modeUrl } from '../src/lib/navigation'

describe('GSM navigation and backward compatible deep links', () => {
  it('restores simulation, Saved v1, legacy modes and safe unknown mode', () => {
    expect(modeFromUrl('')).toBe('simulation')
    expect(modeFromUrl('?mode=single')).toBe('single')
    expect(modeFromUrl('?runtime=simulation')).toBe('simulation')
    expect(modeFromUrl('?runtime=saved&mode=booking')).toBe('voucher')
    expect(modeFromUrl('?mode=booking')).toBe('booking')
    expect(modeFromUrl('?mode=unknown')).toBe('single')
  })
  it('roundtrips mode transitions without carrying fixture flags to legacy', () => {
    const href='http://127.0.0.1:5183/?runtime=simulation&fixture=1&fleet=5000&zoom=11&audit=1'
    const next=modeUrl(href,'booking')
    expect(next).toBe('/?audit=1&mode=booking')
    expect(modeFromUrl(new URL(next,'http://localhost').search)).toBe('booking')
    expect(modeUrl(href,'voucher','saved')).toBe('/?audit=1&runtime=saved')
    expect(modeUrl(href,'single')).toBe('/?audit=1&mode=single')
    expect(modeUrl(href,'simulation')).toBe('/?audit=1&runtime=simulation')
  })
})
