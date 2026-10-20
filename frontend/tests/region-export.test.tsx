import { fireEvent, render, renderHook, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import recorded from '../../docs/evidence/a4/default.json'
import VoucherDashboard from '../src/components/voucher-dashboard'
import { useVoucher } from '../src/lib/use-voucher'
import { experimentCsv, validateExperiment, type Experiment } from '../src/lib/voucher'

vi.mock('../src/components/voucher-charts', () => ({ DefaultCharts: () => null }))
vi.mock('../src/components/financial-comparison', () => ({ FinancialComparison: () => null }))

describe('Hanoi export scope', () => {
  it('keeps raw JSON and CSV available while explicitly disabling HCM Portable v1', () => {
    // Contract fixture; actual Hanoi payload validation also runs in live pilot QA.
    const experiment = structuredClone(recorded) as unknown as Experiment
    experiment.provenance.region_id = 'nvmr-hanoi-core'
    const { result } = renderHook(() => useVoucher(true, true, 'live', 'nvmr-hanoi-core'))
    render(<VoucherDashboard session={{ ...result.current, experiment }} />)
    expect(screen.getByRole('button', { name: 'Xuất thí nghiệm Portable v1' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Xuất JSON · toàn bộ kế hoạch' })).toBeEnabled()
    expect(screen.getByText(/replay Hà Nội cần contract mới ở M5/)).toBeInTheDocument()
    fireEvent.click(screen.getByText('Xuất CSV · kết quả cuối và toàn bộ lịch sử'))
    expect(screen.getAllByRole('button', { name: /^CSV ·/ }).length).toBeGreaterThan(0)
    expect(Object.keys(experimentCsv(validateExperiment(experiment)))).toHaveLength(5)
  })
})
