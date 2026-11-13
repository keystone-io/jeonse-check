import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { diagnose } from '../api.js'
import CheckCard from '../components/CheckCard.jsx'
import Checklist from '../components/Checklist.jsx'
import Gauge from '../components/Gauge.jsx'
import KakaoMap from '../components/KakaoMap.jsx'
import MoneyInput from '../components/MoneyInput.jsx'
import TrendChart from '../components/TrendChart.jsx'
import { fromQuery, money, toQuery } from '../format.js'

export default function Report() {
  const { search } = useLocation()
  const navigate = useNavigate()
  const q = fromQuery(search)
  const [state, setState] = useState({ loading: true, error: '', data: null })
  const [debt, setDebt] = useState(q.senior_debt ? String(q.senior_debt) : '')
  const [official, setOfficial] = useState(q.official_price ? String(q.official_price) : '')
  const [retry, setRetry] = useState(0)

  useEffect(() => {
    const p = fromQuery(search)
    if (!p.b_code || !p.house_type || !p.deposit) {
      setState({ loading: false, error: 'missing', data: null })
      return
    }
    const ac = new AbortController()
    setState((s) => ({ ...s, loading: true, error: '' }))
    diagnose(
      {
        b_code: p.b_code,
        main_no: p.main_no,
        sub_no: p.sub_no || '',
        mountain: p.mountain,
        sido: p.sido || '',
        dong: p.dong || '',
        building_name: p.building_name || '',
        house_type: p.house_type,
        deposit: p.deposit,
        area: p.area || null,
        senior_debt: p.senior_debt || 0,
        official_price: p.official_price || null,
      },
      ac.signal,
    )
      .then((data) => {
        if (!ac.signal.aborted) setState({ loading: false, error: '', data })
      })
      .catch((e) => {
        if (!ac.signal.aborted && e.name !== 'AbortError') setState({ loading: false, error: e.message, data: null })
      })
    return () => {
      ac.abort()
    }
  }, [search, retry])

  function update(patch) {
    navigate(`/report?${toQuery({ ...q, ...patch })}`, { replace: true })
  }

  if (state.error === 'missing') {
    return (
      <div className="container narrow">
        <div className="card empty">
          <h1>진단 정보가 없어요</h1>
          <p className="muted">주소와 보증금을 먼저 입력해 주세요.</p>
          <Link to="/" className="btn btn--primary">진단하러 가기</Link>
        </div>
      </div>
    )
  }

  const title = state.data?.complex_name || q.building_name || q.road_address || q.jibun_address

  return (
    <div className="container report">
      <section className="card summary">
        <div className="summary__addr">
          <p className="summary__type">{state.data?.house_type?.label}</p>
          <h1>{title}</h1>
          <p className="muted small">{q.road_address ? `${q.road_address} · ` : ''}지번 {q.jibun_address}</p>
          <dl className="summary__facts">
            <div><dt>보증금</dt><dd>{money(q.deposit)}</dd></div>
            {state.data?.area?.selected ? (
              <div><dt>전용면적</dt><dd>{state.data.area.selected}㎡{state.data.area.source === 'auto' ? ' (자동)' : ''}</dd></div>
            ) : null}
          </dl>
        </div>

        {state.loading ? (
          <div className="loading">
            <span className="spinner spinner--lg" />
            <p><strong>실거래가 2년치를 모으는 중이에요</strong></p>
            <p className="muted small">처음 조회하는 지역은 10~30초 정도 걸릴 수 있어요.</p>
          </div>
        ) : state.error ? (
          <div className="error-box">
            <p><strong>진단하지 못했어요</strong></p>
            <p>{state.error}</p>
            <button type="button" className="btn btn--ghost" onClick={() => setRetry((n) => n + 1)}>다시 시도</button>
          </div>
        ) : (
          <div className="summary__verdict">
            <Gauge status={state.data.overall.status} score={state.data.overall.score} />
            <h2>{state.data.overall.headline}</h2>
            <p>{state.data.overall.message}</p>
          </div>
        )}

        <div className="summary__actions no-print">
          <Link to={`/?${toQuery(q)}`} className="btn btn--ghost btn--sm">조건 바꾸기</Link>
          {state.data && (
            <button type="button" className="btn btn--ghost btn--sm" onClick={() => window.print()}>PDF로 저장</button>
          )}
        </div>
      </section>

      {state.data && (
        <>
          {state.data.area.groups.length > 1 && (
            <section className="card no-print">
              <h2 className="sec-title">전용면적 선택</h2>
              <p className="muted small">이 건물에서 거래된 면적이에요. 계약할 집의 면적을 고르면 더 정확해져요.</p>
              <div className="chips">
                {state.data.area.groups.map((g) => (
                  <button
                    type="button"
                    key={g.area}
                    className={`chip ${Math.abs(g.area - state.data.area.selected) < 0.5 ? 'is-on' : ''}`}
                    onClick={() => update({ area: g.area })}
                  >
                    {g.area}㎡ <small>{g.count}건</small>
                  </button>
                ))}
              </div>
            </section>
          )}

          <section className="card">
            <h2 className="sec-title">항목별 진단</h2>
            <ul className="checks">
              {state.data.checks.map((c) => (
                <CheckCard key={c.id} check={c} />
              ))}
            </ul>
            <form
              className="refine no-print"
              onSubmit={(e) => {
                e.preventDefault()
                update({ senior_debt: Number(debt) || '', official_price: Number(official) || '' })
              }}
            >
              <p className="refine__title">등기부·공시가격을 알면 입력해서 다시 계산하세요</p>
              <div className="refine__grid">
                <MoneyInput id="r-debt" label="선순위 근저당 (채권최고액)" value={debt} onChange={setDebt} placeholder="없으면 비워두기" hint="등기부 을구" />
                <MoneyInput id="r-official" label="공시가격" value={official} onChange={setOfficial} placeholder="예) 18000" hint="부동산공시가격알리미" />
              </div>
              <div className="refine__actions">
                <a className="link small" href="https://www.realtyprice.kr" target="_blank" rel="noreferrer">공시가격 확인하러 가기 ↗</a>
                <button type="submit" className="btn btn--primary btn--sm">다시 계산</button>
              </div>
            </form>
          </section>

          <section className="card">
            <h2 className="sec-title">추정 시세</h2>
            <div className="stats">
              <Stat label="추정 매매가" est={state.data.estimates.sale} />
              <Stat label="주변 전세 시세" est={state.data.estimates.jeonse} />
              <div className="stat">
                <span className="stat__label">공시가격</span>
                <span className="stat__value">{money(state.data.estimates.official_price)}</span>
                <span className="stat__sub">{state.data.estimates.official_price ? '' : '입력하면 보증보험 계산'}</span>
              </div>
            </div>
          </section>

          <section className="card">
            <h2 className="sec-title">최근 {state.data.months / 12}년 실거래가 추이</h2>
            <TrendChart series={state.data.series} deposit={q.deposit} months={state.data.months} />
          </section>

          {state.data.building && (
            <section className="card">
              <h2 className="sec-title">건축물대장 요약</h2>
              <dl className="table">
                <div><dt>건물명</dt><dd>{state.data.building.name || '-'}</dd></div>
                <div><dt>주용도</dt><dd>{state.data.building.purposes.join(', ') || '-'}</dd></div>
                {state.data.building.etc_purposes.length > 0 && (
                  <div><dt>기타용도</dt><dd>{state.data.building.etc_purposes.join(', ')}</dd></div>
                )}
                <div><dt>사용승인일</dt><dd>{fmtDate(state.data.building.approval_date)}</dd></div>
                <div><dt>구조</dt><dd>{state.data.building.structure || '-'}</dd></div>
                <div><dt>지상층수</dt><dd>{state.data.building.floors ? `${state.data.building.floors}층` : '-'}</dd></div>
                <div><dt>세대(호)수</dt><dd>{state.data.building.households || '-'}</dd></div>
              </dl>
            </section>
          )}

          {q.x && q.y ? (
            <section className="card no-print">
              <h2 className="sec-title">위치</h2>
              <KakaoMap x={q.x} y={q.y} label={title} />
            </section>
          ) : null}

          <section className="card">
            <h2 className="sec-title">계약 전 꼭 확인할 것</h2>
            <Checklist />
          </section>

          {state.data.warnings.length > 0 && (
            <section className="card warn">
              <h2 className="sec-title">데이터 안내</h2>
              <ul>
                {state.data.warnings.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}
    </div>
  )
}

function Stat({ label, est }) {
  return (
    <div className="stat">
      <span className="stat__label">{label}</span>
      <span className="stat__value">{est ? money(est.value) : '-'}</span>
      <span className="stat__sub">
        {est ? `${est.scope === 'same' ? '같은 건물' : '주변 시세'} · 신뢰도 ${est.confidence}` : '거래 없음'}
      </span>
    </div>
  )
}

function fmtDate(s) {
  if (!s || s.length !== 8) return s || '-'
  return `${s.slice(0, 4)}.${s.slice(4, 6)}.${s.slice(6)}`
}
