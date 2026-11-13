import { shortMoney, money } from '../format.js'

const W = 640
const H = 280
const PAD = { top: 16, right: 16, bottom: 32, left: 52 }

function toTime(s) {
  return new Date(s.length === 7 ? `${s}-15` : s).getTime()
}

export default function TrendChart({ series, deposit, months = 24 }) {
  const trade = series?.trade?.points || []
  const jeonse = series?.jeonse?.points || []
  if (!trade.length && !jeonse.length) {
    return <p className="muted">그래프로 보여줄 거래가 없어요.</p>
  }

  const now = Date.now()
  const start = new Date()
  start.setMonth(start.getMonth() - months)
  const x0 = start.getTime()
  const values = [...trade, ...jeonse].map((p) => p.value).concat(deposit ? [deposit] : [])
  let y0 = Math.min(...values) * 0.9
  let y1 = Math.max(...values) * 1.08
  if (y1 - y0 < 1000) {
    y0 -= 500
    y1 += 500
  }
  y0 = Math.max(0, y0)

  const sx = (t) => PAD.left + ((t - x0) / (now - x0)) * (W - PAD.left - PAD.right)
  const sy = (v) => PAD.top + (1 - (v - y0) / (y1 - y0)) * (H - PAD.top - PAD.bottom)
  const ticks = Array.from({ length: 5 }, (_, i) => y0 + ((y1 - y0) * i) / 4)

  const xTicks = []
  const d = new Date(start)
  d.setDate(1)
  d.setMonth(d.getMonth() + 1)
  while (d.getTime() <= now) {
    if (d.getMonth() % 6 === 0) xTicks.push(new Date(d))
    d.setMonth(d.getMonth() + 1)
  }

  const line = (monthly) =>
    monthly.map((m, i) => `${i ? 'L' : 'M'} ${sx(toTime(m.month)).toFixed(1)} ${sy(m.value).toFixed(1)}`).join(' ')

  const scopeNote = (s) => (s === 'nearby' ? '주변 비슷한 면적 (면적 환산)' : '같은 건물')

  return (
    <div className="chart">
      <div className="chart__legend">
        <span className="lg lg--trade">매매 <small>({scopeNote(series.trade.scope)} {trade.length}건)</small></span>
        <span className="lg lg--jeonse">전세 <small>({scopeNote(series.jeonse.scope)} {jeonse.length}건)</small></span>
        {deposit ? <span className="lg lg--mine">내 보증금 {money(deposit)}</span> : null}
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="최근 매매·전세 실거래가 추이">
        {ticks.map((v) => (
          <g key={v}>
            <line x1={PAD.left} x2={W - PAD.right} y1={sy(v)} y2={sy(v)} className="chart__grid" />
            <text x={PAD.left - 8} y={sy(v) + 4} textAnchor="end" className="chart__axis">{shortMoney(v)}</text>
          </g>
        ))}
        {xTicks.map((t) => (
          <text key={t.getTime()} x={sx(t.getTime())} y={H - 10} textAnchor="middle" className="chart__axis">
            {`${String(t.getFullYear()).slice(2)}.${String(t.getMonth() + 1).padStart(2, '0')}`}
          </text>
        ))}
        {deposit ? (
          <line x1={PAD.left} x2={W - PAD.right} y1={sy(deposit)} y2={sy(deposit)} className="chart__mine" />
        ) : null}
        {trade.map((p, i) => (
          <circle key={`t${i}`} cx={sx(toTime(p.date))} cy={sy(p.value)} r="3.5" className="chart__dot chart__dot--trade">
            <title>{`매매 ${p.date} ${money(p.value)}`}</title>
          </circle>
        ))}
        {jeonse.map((p, i) => (
          <circle key={`j${i}`} cx={sx(toTime(p.date))} cy={sy(p.value)} r="3.5" className="chart__dot chart__dot--jeonse">
            <title>{`전세 ${p.date} ${money(p.value)}`}</title>
          </circle>
        ))}
        {series.trade.monthly.length > 1 && <path d={line(series.trade.monthly)} className="chart__line chart__line--trade" />}
        {series.jeonse.monthly.length > 1 && <path d={line(series.jeonse.monthly)} className="chart__line chart__line--jeonse" />}
      </svg>
      <p className="muted small">점은 개별 거래, 선은 월별 중앙값이에요. 매매선과 전세선이 가까울수록 위험해요.</p>
    </div>
  )
}
