// 만원 단위 숫자 → "3억 2,500만원"
export function money(manwon) {
  if (manwon == null || Number.isNaN(manwon)) return '-'
  const v = Math.round(manwon)
  const eok = Math.floor(v / 10000)
  const man = v % 10000
  if (eok && man) return `${eok}억 ${man.toLocaleString()}만원`
  if (eok) return `${eok}억원`
  return `${man.toLocaleString()}만원`
}

// 그래프 축용 짧은 표기: 32500 → "3.3억"
export function shortMoney(manwon) {
  if (manwon >= 10000) return `${(manwon / 10000).toFixed(1).replace(/\.0$/, '')}억`
  return `${Math.round(manwon).toLocaleString()}만`
}

export const HOUSE_TYPES = [
  { code: 'apt', label: '아파트' },
  { code: 'rh', label: '빌라', sub: '연립·다세대' },
  { code: 'offi', label: '오피스텔' },
]

export const STATUS = {
  good: { label: '양호', icon: '●', className: 'is-good' },
  caution: { label: '주의', icon: '▲', className: 'is-caution' },
  danger: { label: '위험', icon: '■', className: 'is-danger' },
  unknown: { label: '확인 필요', icon: '?', className: 'is-unknown' },
}

// 진단 조건 <-> URL 쿼리 (리포트 링크를 그대로 공유할 수 있게)
const FIELDS = {
  b_code: 'b', main_no: 'm', sub_no: 's', mountain: 'mt', sido: 'sd', dong: 'dg',
  building_name: 'bn', jibun_address: 'ja', road_address: 'ra', x: 'x', y: 'y',
  house_type: 't', deposit: 'dp', area: 'ar', senior_debt: 'sr', official_price: 'op',
}

export function toQuery(state) {
  const p = new URLSearchParams()
  for (const [k, short] of Object.entries(FIELDS)) {
    const v = state[k]
    if (v === undefined || v === null || v === '' || v === false) continue
    p.set(short, v === true ? '1' : String(v))
  }
  return p.toString()
}

export function fromQuery(search) {
  const p = new URLSearchParams(search)
  const out = {}
  for (const [k, short] of Object.entries(FIELDS)) {
    if (p.has(short)) out[k] = p.get(short)
  }
  out.mountain = out.mountain === '1'
  for (const k of ['deposit', 'area', 'senior_debt', 'official_price', 'x', 'y']) {
    if (out[k] !== undefined) out[k] = Number(out[k])
  }
  return out
}
