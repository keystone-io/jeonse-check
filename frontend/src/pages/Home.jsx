import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import AddressSearch from '../components/AddressSearch.jsx'
import MoneyInput from '../components/MoneyInput.jsx'
import { HOUSE_TYPES, fromQuery, toQuery } from '../format.js'

function guessType(name = '') {
  if (name.includes('오피스텔')) return 'offi'
  if (name.includes('아파트') || /자이|래미안|힐스테이트|푸르지오|e편한|아이파크|더샵|롯데캐슬/.test(name)) return 'apt'
  return ''
}

const FEATURES = [
  ['전세가율', '최근 매매 실거래가와 보증금을 비교해요'],
  ['주변 전세 시세', '너무 싸거나 비싼 보증금을 찾아내요'],
  ['보증보험 가능성', '공시가격 기준 한도를 계산해요'],
  ['건물 용도', '근생빌라(근린생활시설) 여부를 확인해요'],
  ['가격 추이', '집값이 떨어지는 중인지 보여줘요'],
]

export default function Home() {
  const navigate = useNavigate()
  const { search } = useLocation()
  const prev = fromQuery(search)
  const hasPrev = !!prev.b_code

  const [place, setPlace] = useState(
    hasPrev
      ? {
          b_code: prev.b_code, main_no: prev.main_no, sub_no: prev.sub_no || '', mountain: prev.mountain,
          sido: prev.sido || '', dong: prev.dong || '', building_name: prev.building_name || '',
          jibun_address: prev.jibun_address || '', road_address: prev.road_address || '', x: prev.x, y: prev.y,
        }
      : null,
  )
  const [houseType, setHouseType] = useState(prev.house_type || '')
  const [deposit, setDeposit] = useState(prev.deposit ? String(prev.deposit) : '')
  const [area, setArea] = useState(prev.area ? String(prev.area) : '')
  const [debt, setDebt] = useState(prev.senior_debt ? String(prev.senior_debt) : '')
  const [official, setOfficial] = useState(prev.official_price ? String(prev.official_price) : '')
  const [error, setError] = useState('')

  function select(r) {
    setPlace(r)
    const g = guessType(r.building_name)
    if (g) setHouseType(g)
  }

  function submit(e) {
    e.preventDefault()
    if (!place) return setError('주소를 먼저 선택해 주세요.')
    if (!houseType) return setError('주택 유형을 선택해 주세요.')
    if (!(Number(deposit) > 0)) return setError('보증금을 입력해 주세요.')
    setError('')
    const q = toQuery({
      ...place,
      house_type: houseType,
      deposit: Number(deposit),
      area: Number(area) || '',
      senior_debt: Number(debt) || '',
      official_price: Number(official) || '',
    })
    navigate(`/report?${q}`)
  }

  return (
    <div className="container home">
      <section className="hero">
        <p className="hero__eyebrow">공공데이터 기반 전세 안전 진단</p>
        <h1>
          이 전세, <span className="accent">안전할까?</span>
        </h1>
        <p className="hero__sub">주소와 보증금만 입력하면 실거래가·건축물대장을 모아 위험 신호를 알려드려요.</p>
      </section>

      <form className="card form" onSubmit={submit} noValidate>
        <div className="step">
          <span className="step__num">1</span>
          <div className="step__body">
            {place ? (
              <div className="picked">
                <div>
                  <strong>{place.building_name || place.road_address || place.jibun_address}</strong>
                  <p className="muted small">{place.road_address || ''} {place.road_address ? '·' : ''} 지번 {place.jibun_address}</p>
                </div>
                <button type="button" className="btn btn--ghost btn--sm" onClick={() => setPlace(null)}>변경</button>
              </div>
            ) : (
              <AddressSearch onSelect={select} />
            )}
          </div>
        </div>

        <div className="step">
          <span className="step__num">2</span>
          <div className="step__body">
            <span className="field-label">주택 유형</span>
            <div className="seg" role="radiogroup" aria-label="주택 유형">
              {HOUSE_TYPES.map((t) => (
                <button
                  type="button"
                  key={t.code}
                  role="radio"
                  aria-checked={houseType === t.code}
                  className={houseType === t.code ? 'is-on' : ''}
                  onClick={() => setHouseType(t.code)}
                >
                  {t.label}
                  {t.sub && <small>{t.sub}</small>}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="step">
          <span className="step__num">3</span>
          <div className="step__body">
            <MoneyInput id="deposit" label="전세 보증금" value={deposit} onChange={setDeposit} placeholder="예) 25000" hint="만원 단위로 입력하세요" required />
          </div>
        </div>

        <details className="more" open={!!(area || debt || official)}>
          <summary>더 정확하게 진단하기 (선택)</summary>
          <div className="more__grid">
            <div className="field">
              <label className="field-label" htmlFor="area">전용면적</label>
              <div className="money">
                <input id="area" inputMode="decimal" placeholder="예) 59.9" value={area} onChange={(e) => setArea(e.target.value.replace(/[^\d.]/g, ''))} />
                <span className="money__unit">㎡</span>
              </div>
              <p className="field-hint">비워 두면 거래가 가장 많은 면적으로 계산해요</p>
            </div>
            <MoneyInput id="debt" label="선순위 근저당 (채권최고액)" value={debt} onChange={setDebt} placeholder="예) 12000" hint="등기부 을구에서 확인" />
            <MoneyInput id="official" label="공시가격" value={official} onChange={setOfficial} placeholder="예) 18000" hint="부동산공시가격알리미에서 확인" />
          </div>
        </details>

        {error && <p className="form-error">{error}</p>}
        <button type="submit" className="btn btn--primary btn--lg">진단하기</button>
      </form>

      <section className="features">
        <h2>무엇을 확인하나요?</h2>
        <ul>
          {FEATURES.map(([t, d]) => (
            <li key={t}>
              <strong>{t}</strong>
              <span>{d}</span>
            </li>
          ))}
        </ul>
        <p className="notice">
          ⚠ 등기부등본(근저당·압류)과 집주인 세금 체납은 공공데이터로 확인할 수 없어요. 계약 전 반드시 직접 확인하세요.
        </p>
      </section>
    </div>
  )
}
