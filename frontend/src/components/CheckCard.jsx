import { useState } from 'react'
import { STATUS } from '../format.js'

export default function CheckCard({ check }) {
  const [open, setOpen] = useState(false)
  const s = STATUS[check.status] || STATUS.unknown
  return (
    <li className={`check ${s.className}`}>
      <button type="button" className="check__head" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
        <span className="check__badge" aria-hidden="true">{s.icon}</span>
        <span className="check__text">
          <span className="check__title">
            {check.title}
            <span className="check__status">{s.label}</span>
          </span>
          <span className="check__summary">{check.summary}</span>
        </span>
        <span className="check__value">{check.value}</span>
        <svg className="check__chev" viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
          <path d="m6 9 6 6 6-6" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </svg>
      </button>
      {open && (
        <div className="check__body">
          <p>{check.detail}</p>
          {check.basis && <p className="check__basis">근거: {check.basis}</p>}
        </div>
      )}
    </li>
  )
}
