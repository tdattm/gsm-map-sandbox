import type { ArmMetrics } from '@/lib/voucher'
import { moneyText as vnd } from '@/lib/vi'

export function FinancialComparison({ baseline, treatment }: { baseline: ArmMetrics; treatment: ArmMetrics }) {
  const rows = [
    ["Tổng giá trị cước trước ưu đãi (GFV)", baseline.grossFareVnd, treatment.grossFareVnd, true],
    ["Tổng tiền hành khách thanh toán", baseline.riderPaymentsVnd, treatment.riderPaymentsVnd, true],
    ["Chi phí voucher đã sử dụng", baseline.voucherSpendVnd, treatment.voucherSpendVnd, true],
    ["Số chuyến hoàn tất", baseline.completed, treatment.completed, false],
  ] as const
  return <details className="financial-comparison" open><summary>So sánh tài chính và vận hành</summary><div className="comparison-scroll"><table><thead><tr>{["Chỉ số mô phỏng",'Baseline','Treatment',"Chênh lệch"].map(label => <th key={label} scope="col">{label}</th>)}</tr></thead><tbody>{rows.map(([label,b,t,money]) => <tr key={label}><th scope="row">{label}</th><td>{money ? vnd(b) : b}</td><td>{money ? vnd(t) : t}</td><td>{t > b ? '+' : t < b ? '−' : ''}{money ? vnd(Math.abs(t-b)) : Math.abs(t-b)}</td></tr>)}</tbody></table></div><p className="small-note">Chênh lệch = Treatment − Baseline · GFV = tiền hành khách thanh toán + chi phí voucher đã sử dụng · chỉ số mô phỏng</p></details>
}
