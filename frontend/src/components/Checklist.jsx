import { useState } from 'react'

const STAGES = [
  {
    title: '집 보러 갈 때',
    items: [
      '등기부등본(인터넷등기소, 700원)을 떼서 소유자 이름과 집주인 신분증이 같은지 확인',
      '등기부 "을구"의 근저당 채권최고액 확인 → 보증금과 합쳐 매매가의 70%를 넘지 않는지',
      '등기부 "갑구"에 압류·가압류·가처분·신탁 등기가 있는지 확인',
      '건축물대장(정부24)에서 용도가 주택인지, "위반건축물" 표시가 있는지 확인',
      '다가구 주택이면 다른 세입자들의 보증금(선순위 임차보증금) 총액 확인',
    ],
  },
  {
    title: '계약할 때',
    items: [
      '계약은 반드시 등기부상 집주인 본인과 (대리인이면 위임장·인감증명서 확인)',
      '집주인 국세·지방세 완납증명서 요구 (체납 세금은 보증금보다 먼저 가져갈 수 있어요)',
      '보증금은 등기부상 집주인 명의 계좌로만 송금',
      '특약: "잔금일 다음 날까지 근저당 등 권리 변동이 없을 것, 위반 시 계약 해제·보증금 반환"',
      '공인중개사 등록 여부와 중개사무소 정보 확인 (관할 시·군·구청)',
    ],
  },
  {
    title: '잔금·입주 날',
    items: [
      '잔금 직전에 등기부등본을 한 번 더 떼서 새로 생긴 권리가 없는지 확인',
      '입주 당일 전입신고 + 확정일자 받기 (주민센터 또는 정부24)',
      '전세보증금반환보증(HUG·HF·SGI) 가입',
    ],
  },
]

export default function Checklist() {
  const [done, setDone] = useState({})
  return (
    <div className="checklist">
      {STAGES.map((stage) => (
        <div key={stage.title} className="checklist__stage">
          <h3>{stage.title}</h3>
          <ul>
            {stage.items.map((item) => {
              const key = `${stage.title}:${item}`
              return (
                <li key={key}>
                  <label className={done[key] ? 'is-done' : ''}>
                    <input
                      type="checkbox"
                      checked={!!done[key]}
                      onChange={() => setDone((d) => ({ ...d, [key]: !d[key] }))}
                    />
                    <span>{item}</span>
                  </label>
                </li>
              )
            })}
          </ul>
        </div>
      ))}
    </div>
  )
}
