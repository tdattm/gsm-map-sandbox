import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, renderHook, screen } from '@testing-library/react'
import { moneyText, numberText, percentText, dateText, stateText, presetText, errorText, batchStatusText, modeLabels } from '../src/lib/vi'
import { Slider } from '../src/components/ui/slider'
import BatchAnalysis from '../src/components/batch-analysis'
import { VoucherPanel } from '../src/components/voucher-panel'
import { useVoucher } from '../src/lib/use-voucher'
import type { Experiment } from '../src/lib/voucher'
import recorded from '../../docs/evidence/a4/default.json'

describe('Vietnamese presentation preserves protocol values', () => {
  it('formats money, decimals and percentages without substituting zero for null', () => {
    expect(moneyText(200000).replace(/\s/g,' ')).toBe('200.000 ₫')
    expect(numberText(1234)).toBe('1.234'); expect(numberText(3.14,2)).toBe('3,14')
    expect(percentText(.125)).toBe('12,5%'); expect(numberText(179.5,1)).toBe('179,5')
    for(const value of [moneyText(null),numberText(null),percentText(null)]) expect(value).toBe('Không áp dụng')
  })
  it('formats preparation wall time in Vietnam and leaves metadata unchanged', () => {
    const original='2026-10-13T03:04:05Z'; expect(dateText(original)).toContain('10:04:05'); expect(original).toBe('2026-10-13T03:04:05Z')
    expect(dateText('original metadata')).toBe('original metadata')
  })
  it.each([['idle','Đang rảnh'],['assigned','Đã phân công xe'],['picked_up','Đã đón khách'],['on_trip','Đang chở khách'],['completed','Hoàn tất'],['RESERVED','Đang giữ trước'],['SETTLED','Đã sử dụng']])('localizes %s as %s', (raw,label) => {
    expect(stateText(raw)).toBe(label); expect(stateText('future-contract-status')).toBe('future-contract-status')
  })
  it('explains known errors while retaining codes and unknown diagnostics', () => {
    expect(errorText('INVALID_SAVED_ARTIFACT: Unsupported schema version.')).toContain('Phiên bản schema')
    expect(errorText('INVALID_SAVED_ARTIFACT: Checksum không khớp')).toContain('SHA-256')
    expect(errorText('Error: ROUTER_TIMEOUT: OSRM local timeout.')).toBe('OSRM cục bộ phản hồi quá thời gian cho phép. (ROUTER_TIMEOUT)')
    expect(errorText('future diagnostic')).toBe('future diagnostic')
  })
  it('keeps original batch export status distinct from its displayed label', () => {
    const status='Cancelled — partial results'; expect(batchStatusText(status)).toBe('Đã hủy · kết quả chưa đầy đủ'); expect(status).toBe('Cancelled — partial results')
  })
  it('names actual focusable timeline inputs for assistive technology', () => {
    render(<Slider aria-label="Dòng thời gian mô phỏng" value={[10]} min={0} max={100} />)
    // jsdom has zero layout dimensions, so Base UI hides its thumb. Real focus is checked in Chromium.
    const input = screen.getByRole('slider',{hidden:true})
    expect(input).toHaveAttribute('aria-label','Dòng thời gian mô phỏng')
    expect(input).toHaveAttribute('aria-valuenow','10')
  })
  it('names batch controls in Vietnamese while keeping factor values and saved guard', () => {
    const e=recorded as unknown as Experiment, before=JSON.stringify(e)
    render(<BatchAnalysis experiment={e} live={false}/>)
    expect(screen.getByRole('button',{name:'Chạy nhiều lượt'})).toBeDisabled()
    expect(screen.getByRole('combobox',{name:'Yếu tố phân tích độ nhạy'})).toHaveValue('none')
    expect(screen.getByRole('option',{name:'Ngân sách voucher'})).toHaveValue('budget')
    expect(JSON.stringify(e)).toBe(before)
  })
  it('opens the original JSON input through a Vietnamese file picker button', () => {
    const {result}=renderHook(()=>useVoucher(true,false,'saved'))
    render(<VoucherPanel ready session={result.current} onFocus={vi.fn()}/>)
    const input=screen.getByLabelText('Nhập thí nghiệm đã lưu')
    const click=vi.spyOn(input,'click')
    expect(input).toHaveAttribute('accept','.json,application/json')
    expect(screen.getByText('Chưa chọn file')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button',{name:'Chọn file JSON'})); expect(click).toHaveBeenCalledOnce()
  })
  it('localizes preset labels, accounting and accessible controls without rewriting experiment data', () => {
    const e=recorded as unknown as Experiment,before=JSON.stringify(e)
    const {result}=renderHook(()=>useVoucher(true,true))
    render(<VoucherPanel ready session={{...result.current,experiment:e}} onFocus={vi.fn()}/>)
    expect(screen.getByRole('option',{name:'Thấp'})).toHaveValue('Low'); expect(presetText('High')).toBe('Cao')
    expect(screen.getByRole('button',{name:'Chuẩn bị thí nghiệm'})).toBeEnabled()
    expect(screen.getByText(/Ngân sách đang giữ trước/)).toHaveTextContent('Chi phí voucher đã sử dụng')
    expect(screen.getByRole('group',{name:'Kịch bản thí nghiệm'})).toBeInTheDocument()
    expect(JSON.stringify(e)).toBe(before); expect(modeLabels.voucher).toBe('Phòng thí nghiệm voucher')
  })
})
