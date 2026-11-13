import { STATUS } from '../format.js'

// 반원 게이지: 왼쪽(0)=위험, 오른쪽(100)=양호
const CX = 110
const CY = 110
const R = 88

function point(score, r = R) {
  const angle = Math.PI * (1 - score / 100)
  return [CX + r * Math.cos(angle), CY - r * Math.sin(angle)]
}

function arc(from, to) {
  const [x1, y1] = point(from)
  const [x2, y2] = point(to)
  return `M ${x1} ${y1} A ${R} ${R} 0 0 1 ${x2} ${y2}`
}

export default function Gauge({ status, score }) {
  const s = STATUS[status] || STATUS.unknown
  const known = status !== 'unknown' && score != null
  const [nx, ny] = known ? point(score, R - 22) : [CX, CY]
  return (
    <div className={`gauge ${s.className}`}>
      <svg viewBox="0 0 220 128" role="img" aria-label={`종합 판정: ${s.label}`}>
        <path d={arc(0, 100)} className="gauge__track" />
        {known && (
          <>
            <path d={arc(1, 39)} className="gauge__seg gauge__seg--danger" />
            <path d={arc(41, 69)} className="gauge__seg gauge__seg--caution" />
            <path d={arc(71, 99)} className="gauge__seg gauge__seg--good" />
            <line x1={CX} y1={CY} x2={nx} y2={ny} className="gauge__needle" />
            <circle cx={CX} cy={CY} r="7" className="gauge__hub" />
          </>
        )}
      </svg>
      <div className="gauge__label">{s.label}</div>
    </div>
  )
}
