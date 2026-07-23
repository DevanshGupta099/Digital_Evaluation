import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { listScripts } from '../api.js'

export default function Dashboard() {
  const [scripts, setScripts] = useState([])
  const [error, setError] = useState('')

  const refreshScripts = () => listScripts().then(setScripts).catch((e) => setError(String(e)))

  useEffect(() => {
    refreshScripts()
    const t = setInterval(refreshScripts, 4000)
    return () => clearInterval(t)
  }, [])

  const completed = scripts.filter(s => s.status === 'finalized' || s.status === 'annotated').length
  const pending = scripts.filter(s => s.status === 'in_review').length
  const processing = scripts.length - completed - pending

  const currentTime = new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'short', day: 'numeric' })

  return (
    <>
      <div className="dashboard-welcome">
        <h2>Welcome back, Admin</h2>
        <p>{currentTime} &mdash; Here's what's happening with your evaluations today.</p>
      </div>

      <div className="stats-grid">
        <div className="stat-card">
          <h4>Total Uploaded</h4>
          <div className="stat-value">{scripts.length}</div>
          <div className="stat-trend trend-up">↑ 12% from last week</div>
        </div>
        <div className="stat-card">
          <h4>Needs Review</h4>
          <div className="stat-value warning">{pending}</div>
          <div className="stat-trend trend-neutral">→ 0% change</div>
        </div>
        <div className="stat-card">
          <h4>Completed</h4>
          <div className="stat-value success">{completed}</div>
          <div className="stat-trend trend-up">↑ 8% from last week</div>
        </div>
      </div>

      <div className="card premium-table-card">
        <div className="card-header">
          <h2>Evaluation Queue</h2>
          <Link to="/dashboard/new" className="button primary">New Evaluation</Link>
        </div>
        {error && <div className="flag" style={{marginBottom: 16}}>{error}</div>}
        
        <table className="premium-table">
          <thead>
            <tr><th>Student</th><th>File</th><th>Status</th><th>Action</th></tr>
          </thead>
          <tbody>
            {scripts.length === 0 ? (
              <tr>
                <td colSpan="4" className="empty-state">
                  <div className="empty-icon">📂</div>
                  <h3>No scripts uploaded yet</h3>
                  <p>Start a new evaluation to populate your queue.</p>
                </td>
              </tr>
            ) : (
              scripts.map((s) => (
                <tr key={s.id}>
                  <td>
                    <div className="student-cell">
                      <div className="student-avatar">{s.student_name ? s.student_name.charAt(0).toUpperCase() : 'A'}</div>
                      <span className="student-name">{s.student_name || 'Anonymous'}</span>
                    </div>
                  </td>
                  <td className="file-cell">{s.filename}</td>
                  <td>
                    <span className={`status-pill ${s.status}`}>{s.status.replace('_', ' ')}</span>
                    {s.error && <div className="error-subtext">{s.error}</div>}
                  </td>
                  <td>
                    {(s.status === 'in_review' || s.status === 'annotated' || s.status === 'finalized') ? (
                      <Link to={`/dashboard/review/${s.id}`} className="button secondary small">Open Review &rarr;</Link>
                    ) : (
                      <span className="processing-text">
                        <span className="dot-pulse"></span> Processing...
                      </span>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </>
  )
}
