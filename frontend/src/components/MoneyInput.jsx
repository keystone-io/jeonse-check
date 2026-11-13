import { money } from '../format.js'

// 만원 단위 숫자 입력 + "= 2억원" 보조 표기
export default function MoneyInput({ id, label, value, onChange, placeholder, hint, required }) {
  const num = Number(value)
  return (
    <div className="field">
      <label className="field-label" htmlFor={id}>{label}</label>
      <div className="money">
        <input
          id={id}
          inputMode="numeric"
          placeholder={placeholder}
          value={value}
          required={required}
          onChange={(e) => onChange(e.target.value.replace(/[^\d]/g, ''))}
        />
        <span className="money__unit">만원</span>
      </div>
      <p className="field-hint">{num > 0 ? `= ${money(num)}` : hint}</p>
    </div>
  )
}
