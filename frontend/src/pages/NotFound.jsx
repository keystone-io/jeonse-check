import { Link } from 'react-router-dom'

export default function NotFound() {
  return (
    <div className="container narrow">
      <div className="card empty">
        <h1>페이지를 찾을 수 없어요</h1>
        <Link to="/" className="btn btn--primary">처음으로</Link>
      </div>
    </div>
  )
}
