import React, { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { getScript, getOfferingStudents } from '../api.js'
import { useAuth } from '../context/AuthContext.jsx'

export default function StudentView() {
  const { offeringId } = useParams()
  const { user } = useAuth()
  
  const [script, setScript] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!offeringId || !user) return
    
    // We need to find the student's script for this offering
    getOfferingStudents(offeringId)
      .then(async (students) => {
        // Assume user.email or user.name matches student for this MVP
        const myRecord = students.find(s => s.full_name === user.name || (s.email && s.email === user.name))
        
        if (!myRecord) {
          setError("You are not enrolled in this offering.")
          return
        }
        
        if (!myRecord.script) {
          setError("No marksheet has been uploaded for you yet.")
          return
        }

        // We check if results are published via the analytics endpoint or dashboard
        const { getAnalytics } = await import('../api.js')
        const analytics = await getAnalytics(offeringId)
        
        if (!analytics.results_published) {
          setError("Results are not yet released for this class offering.")
          return
        }

        const scriptData = await getScript(myRecord.script.id)
        setScript(scriptData)
      })
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false))
  }, [offeringId, user])

  if (loading) return <div style={{ padding: '40px', color: '#94a3b8', textAlign: 'center' }}>Loading your results...</div>
  if (error) return <div className="flag" style={{ margin: '20px' }}>⚠️ {error}</div>
  if (!script) return null

  const pdfUrl = `/api/scripts/${script.id}/annotated.pdf?t=${Date.now()}#navpanes=0&view=FitH`

  return (
    <div style={{ padding: '20px', maxWidth: '1200px', margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <h2 style={{ color: '#f8fafc', margin: 0 }}>🎓 Your Results</h2>
        <Link to={`/`} className="button secondary">
          &larr; Back to Home
        </Link>
      </div>

      <div className="stats-grid" style={{ marginBottom: '24px' }}>
        <div className="stat-card" style={{ background: '#18181b', border: '1px solid rgba(255,255,255,0.1)' }}>
          <h4>Total Score</h4>
          <div className="stat-value" style={{ color: '#38bdf8' }}>{script.summary?.total_awarded || 0} / {script.summary?.total_max || 0}</div>
          <div className="stat-trend trend-up">Final Marks</div>
        </div>
        <div className="stat-card" style={{ background: '#18181b', border: '1px solid rgba(255,255,255,0.1)' }}>
          <h4>Status</h4>
          <div className="stat-value success" style={{ fontSize: '1.2rem', marginTop: '10px' }}>PUBLISHED</div>
        </div>
      </div>

      <div style={{ display: 'flex', gap: '24px', height: '600px' }}>
        <div style={{ flex: 1, background: '#18181b', borderRadius: '16px', border: '1px solid rgba(255,255,255,0.1)', overflow: 'hidden' }}>
          <iframe title="annotated script" src={pdfUrl} style={{ width: '100%', height: '100%', border: 'none' }} />
        </div>
        
        <div style={{ width: '350px', background: '#18181b', borderRadius: '16px', border: '1px solid rgba(255,255,255,0.1)', padding: '20px', overflowY: 'auto' }}>
          <h3 style={{ color: '#f8fafc', margin: '0 0 16px 0', fontSize: '1.1rem' }}>Marks Breakdown</h3>
          {script.evaluations.map(ev => (
            <div key={ev.id} style={{ marginBottom: '16px', borderBottom: '1px solid rgba(255,255,255,0.08)', paddingBottom: '12px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <strong style={{ color: '#e2e8f0' }}>Q{ev.question_number}</strong>
                <span style={{ color: '#38bdf8', fontWeight: 700 }}>{ev.marks_awarded} / {ev.max_marks} pts</span>
              </div>
              {(ev.pass1?.point_evaluations || []).filter(p => p.marks_awarded > 0).map((p, i) => (
                <div key={i} style={{ fontSize: '0.8rem', color: '#94a3b8', marginBottom: '4px' }}>
                  ✓ {p.rubric_point_id}
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
