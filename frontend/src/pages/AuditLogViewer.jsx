import React, { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { getAuditLogs } from '../api.js'

export default function AuditLogViewer() {
  const { offeringId } = useParams()
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!offeringId) return
    getAuditLogs(offeringId)
      .then(setLogs)
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false))
  }, [offeringId])

  if (loading) return <div style={{ padding: '40px', color: '#94a3b8', textAlign: 'center' }}>Loading audit logs...</div>
  if (error) return <div className="flag" style={{ margin: '20px' }}>⚠️ {error}</div>

  return (
    <div style={{ padding: '20px', maxWidth: '1200px', margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <h2 style={{ color: '#f8fafc', margin: 0 }}>📜 Audit Trail Logs</h2>
        <Link to={`/dashboard?offeringId=${offeringId}`} className="button secondary">
          &larr; Back to Dashboard
        </Link>
      </div>

      <div className="card" style={{ background: '#18181b', border: '1px solid rgba(255,255,255,0.1)' }}>
        <table className="premium-table">
          <thead>
            <tr>
              <th>Timestamp (UTC)</th>
              <th>Action</th>
              <th>User</th>
              <th>Details</th>
            </tr>
          </thead>
          <tbody>
            {logs.length === 0 ? (
              <tr><td colSpan="4" style={{ textAlign: 'center', padding: '40px', color: '#64748b' }}>No audit logs found for this offering.</td></tr>
            ) : (
              logs.map(log => (
                <tr key={log.id}>
                  <td style={{ color: '#94a3b8', fontSize: '0.85rem' }}>{new Date(log.timestamp).toLocaleString()}</td>
                  <td>
                    <span style={{ background: '#3f3f46', padding: '4px 8px', borderRadius: '6px', fontSize: '0.8rem', color: '#e2e8f0', fontWeight: 600 }}>
                      {log.action_type}
                    </span>
                  </td>
                  <td style={{ fontWeight: 600, color: '#38bdf8' }}>{log.user_name}</td>
                  <td>
                    <pre style={{ margin: 0, fontSize: '0.75rem', color: '#a1a1aa', background: '#09090b', padding: '8px', borderRadius: '6px', overflowX: 'auto' }}>
                      {JSON.stringify(log.details, null, 2)}
                    </pre>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
