import { useEffect, useRef, useState } from 'react'

const KEY = import.meta.env.VITE_KAKAO_JS_KEY
let loader = null

function loadKakao() {
  if (window.kakao?.maps?.LatLng) return Promise.resolve(window.kakao)
  if (!loader) {
    loader = new Promise((resolve, reject) => {
      const script = document.createElement('script')
      script.src = `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${KEY}&autoload=false`
      script.async = true
      script.onload = () => {
        window.kakao.maps.load(() => resolve(window.kakao))
      }
      script.onerror = () => {
        loader = null
        reject(new Error('카카오 지도를 불러오지 못했어요.'))
      }
      document.head.appendChild(script)
    })
  }
  return loader
}

export default function KakaoMap({ x, y, label }) {
  const ref = useRef(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!KEY || !x || !y) {
      return
    }
    let cancelled = false
    loadKakao()
      .then((kakao) => {
        if (cancelled || !ref.current) return
        const pos = new kakao.maps.LatLng(y, x)
        const map = new kakao.maps.Map(ref.current, { center: pos, level: 3 })
        new kakao.maps.Marker({ map, position: pos, title: label })
      })
      .catch((e) => {
        if (!cancelled) setError(e.message)
      })
    return () => {
      cancelled = true
    }
  }, [x, y, label])

  if (!KEY) return <p className="muted small">지도를 보려면 frontend/.env 에 VITE_KAKAO_JS_KEY 를 입력하세요.</p>
  if (!x || !y) return null
  return (
    <>
      <div ref={ref} className="map" role="img" aria-label={`${label} 위치 지도`} />
      {error && <p className="form-error">{error} (카카오 앱에 이 사이트 도메인이 등록됐는지 확인하세요)</p>}
    </>
  )
}
