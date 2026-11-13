import { Link } from 'react-router-dom'

export default function Header() {
  return (
    <header className="header">
      <div className="container header__inner">
        <Link to="/" className="logo" aria-label="전세체크 홈">
          <svg viewBox="0 0 32 32" width="28" height="28" aria-hidden="true">
            <rect width="32" height="32" rx="8" fill="var(--primary)" />
            <path d="M8 15.5 16 9l8 6.5V24a1 1 0 0 1-1 1H9a1 1 0 0 1-1-1z" fill="#fff" />
            <path d="m12.5 18.5 2.5 2.5 4.5-5" stroke="var(--primary)" strokeWidth="2.2" fill="none" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <span>전세체크</span>
        </Link>
        <nav className="header__nav">
          <Link to="/">새 진단</Link>
        </nav>
      </div>
    </header>
  )
}
