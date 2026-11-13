export default function Footer() {
  return (
    <footer className="footer">
      <div className="container">
        <p>
          전세체크의 진단 결과는 국토교통부 실거래가·건축물대장 등 공공데이터로 계산한 <strong>참고용 정보</strong>이며,
          법률·중개·감정 자문이 아닙니다. 계약 전 등기부등본, 건축물대장, 집주인 세금 체납 여부를 반드시 직접 확인하세요.
        </p>
        <p className="footer__src">데이터: 국토교통부(공공데이터포털), 카카오 로컬 · 지도</p>
      </div>
    </footer>
  )
}
