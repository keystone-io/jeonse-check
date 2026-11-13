import { useEffect, useRef, useState } from 'react'
import { searchAddress } from '../api.js'

export default function AddressSearch({ onSelect }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [searched, setSearched] = useState(false)
  const timer = useRef(null)
  const controller = useRef(null)

  function run(q) {
    if (controller.current) controller.current.abort()
    if (q.trim().length < 2) {
      setResults([])
      setSearched(false)
      return
    }
    const ac = new AbortController()
    controller.current = ac
    setLoading(true)
    setError('')
    searchAddress(q.trim(), ac.signal)
      .then((data) => {
        if (ac.signal.aborted) return
        setResults(data.results)
        setSearched(true)
      })
      .catch((e) => {
        if (!ac.signal.aborted && e.name !== 'AbortError') setError(e.message)
      })
      .finally(() => {
        if (controller.current === ac) setLoading(false)
      })
  }

  useEffect(() => {
    clearTimeout(timer.current)
    timer.current = setTimeout(() => {
      run(query)
    }, 350)
    return () => {
      clearTimeout(timer.current)
    }
  }, [query])

  return (
    <div className="addr">
      <label className="field-label" htmlFor="addr-input">주소 또는 건물명</label>
      <div className="addr__box">
        <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" className="addr__icon">
          <circle cx="11" cy="11" r="7" fill="none" stroke="currentColor" strokeWidth="2" />
          <path d="m20 20-3.5-3.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </svg>
        <input
          id="addr-input"
          type="search"
          autoComplete="off"
          placeholder="예) 역삼동 123-4, 테헤란로 152, ○○빌라"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              clearTimeout(timer.current)
              run(query)
            }
          }}
        />
        {loading && <span className="spinner" aria-label="검색 중" />}
      </div>
      {error && <p className="form-error">{error}</p>}
      {results.length > 0 && (
        <ul className="addr__list" role="listbox">
          {results.map((r) => (
            <li key={r.id}>
              <button type="button" onClick={() => onSelect(r)}>
                <strong>{r.building_name || r.road_address || r.jibun_address}</strong>
                <span>{r.road_address && r.building_name ? r.road_address : ''}</span>
                <span className="muted">지번 {r.jibun_address}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {searched && !loading && !error && results.length === 0 && (
        <p className="muted small">검색 결과가 없어요. 동 이름과 번지를 함께 입력해 보세요. (예: 역삼동 123-4)</p>
      )}
    </div>
  )
}
