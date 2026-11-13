// 프론트는 항상 같은 주소의 /api/* 만 호출한다 (개발: Vite 프록시, 운영: Nginx).

async function request(path, options = {}) {
  let res
  try {
    res = await fetch(path, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    })
  } catch (e) {
    // 화면 이동·재요청으로 취소된 요청은 오류가 아니므로 그대로 넘긴다
    if (e?.name === 'AbortError' || options.signal?.aborted) throw e
    throw new Error('서버에 연결하지 못했어요. 잠시 후 다시 시도해 주세요.')
  }
  let data = null
  try {
    data = await res.json()
  } catch {
    data = null
  }
  if (!res.ok) {
    const detail = data?.detail
    const message = typeof detail === 'string' ? detail : '요청을 처리하지 못했어요.'
    throw new Error(message)
  }
  return data
}

export function searchAddress(q, signal) {
  return request(`/api/address?q=${encodeURIComponent(q)}`, { signal })
}

export function diagnose(body, signal) {
  return request('/api/diagnose', { method: 'POST', body: JSON.stringify(body), signal })
}
