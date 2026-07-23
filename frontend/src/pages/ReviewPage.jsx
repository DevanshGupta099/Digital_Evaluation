import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { getScript, submitReview } from '../api.js'

export default function ReviewPage() {
  const { scriptId } = useParams()
  const [script, setScript] = useState(null)
  const [error, setError] = useState('')

  const refresh = useCallback(
    () => getScript(scriptId).then(setScript).catch((e) => setError(String(e))),
    [scriptId],
  )

  useEffect(() => { refresh() }, [refresh])

  if (error) return <main><div className="card flag">{error}</div></main>
  if (!script) return (
    <main>
      <div className="loader-container">
        <div className="spinner"></div>
        <p style={{marginTop: 16}}>Loading evaluation data...</p>
      </div>
    </main>
  )

  return (
    <div className="review-container">
      <div className="review-header">
        <Link to="/dashboard" className="back-link">&larr; Back to Dashboard</Link>
        <span style={{marginLeft: 'auto', fontWeight: 600}}>
          {script.student_name || 'Anonymous Script'}
        </span>
        <span className={`status ${script.status}`}>{script.status.replace('_', ' ')}</span>
        {script.summary && (
          <span className="status finalized" style={{fontSize: '1rem'}}>
            Total: {script.summary.total_awarded} / {script.summary.total_max}
          </span>
        )}
      </div>
      <div style={{marginTop: 24}}>
        <div className="review-layout">
          
          {/* Left Pane: Annotated PDF */}
          <div className="pdf-pane">
            <iframe title="annotated script" src={`/api/scripts/${script.id}/annotated.pdf`} />
          </div>
          
          {/* Right Pane: AI Evaluation Breakdown */}
          <div className="eval-pane">
            <h2 style={{marginBottom: 24}}>AI Evaluation Audit</h2>
            
            {script.evaluations.length === 0 && (
              <div className="card" style={{textAlign: 'center', padding: 48}}>
                <div className="spinner"></div>
                <h3 style={{marginTop: 24}}>Evaluation in Progress</h3>
                <p style={{color: 'var(--text-muted)'}}>The AI is currently analyzing the handwritten answers, matching them to the rubric, and drawing annotations on the script.</p>
              </div>
            )}
            
            {script.evaluations.map((ev) => (
              <QuestionCard key={ev.id} ev={ev} onReviewed={refresh} />
            ))}
          </div>
          
        </div>
      </div>
    </div>
  )
}

function QuestionCard({ ev, onReviewed }) {
  const [overrideMarks, setOverrideMarks] = useState(ev.marks_awarded)
  const [reviewer, setReviewer] = useState('')
  const [comment, setComment] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function decide(action) {
    setBusy(true)
    setError('')
    try {
      await submitReview(ev.id, {
        action,
        final_marks: action === 'accepted' ? ev.marks_awarded : Number(overrideMarks),
        reviewer: reviewer || 'Instructor',
        comment,
      })
      onReviewed()
    } catch (err) {
      setError(String(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="card question-card">
      <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start'}}>
        <h3>Question {ev.question_number}</h3>
        <div style={{textAlign: 'right'}}>
          <span className="marks">{ev.marks_awarded} <span style={{fontSize: '1rem', color: 'var(--text-muted)'}}>/ {ev.max_marks}</span></span>
          <div style={{fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: 4}}>
            Confidence: {(ev.confidence * 100).toFixed(0)}%
          </div>
        </div>
      </div>
      
      {ev.flags.length > 0 && (
        <div style={{marginTop: 12}}>
          {ev.flags.map((f, i) => (
            <div key={i} className="flag">⚑ Warning: {f.reason}</div>
          ))}
        </div>
      )}
      
      {ev.pass1?.examiner_note && (
        <p style={{background: '#F1F5F9', padding: 12, borderRadius: 8, fontStyle: 'italic', fontSize: '0.95rem'}}>
          {ev.pass1.examiner_note}
        </p>
      )}
      
      <div style={{marginTop: 16}}>
        {(ev.pass1?.point_evaluations || []).map((p) => (
          <div key={p.rubric_point_id} className="point">
            <div style={{display: 'flex', justifyContent: 'space-between'}}>
              <div>
                <span className={p.status}>{p.status.toUpperCase()}</span>
                <strong style={{marginLeft: 8}}>{p.rubric_point_id}</strong>
              </div>
              <strong style={{color: p.marks_awarded > 0 ? 'var(--success)' : 'var(--danger)'}}>
                {p.marks_awarded > 0 ? '+' : ''}{p.marks_awarded}
              </strong>
            </div>
            
            {p.evidence_quote && <div className="quote">"{p.evidence_quote}"</div>}
            {p.reasoning && <div style={{marginTop: 4, color: 'var(--text-muted)'}}>{p.reasoning}</div>}
          </div>
        ))}
      </div>
      
      {ev.pass2 && (
        <div style={{marginTop: 16, paddingTop: 16, borderTop: '1px solid var(--border-color)', fontSize: '0.85rem', color: 'var(--text-muted)'}}>
          <strong>Cross-Check Pass 2 (Groq):</strong> Evaluated {ev.pass2.point_evaluations.reduce((a, p) => a + p.marks_awarded, 0)} marks total.
        </div>
      )}
      
      <div style={{marginTop: 24, paddingTop: 16, borderTop: '1px solid var(--border-color)'}}>
        {ev.review ? (
          <div className="reviewed">
            {ev.review.action === 'accepted' ? '✓ Accepted by human' : '⚠ Overridden by human'} 
            <span style={{marginLeft: 8, paddingLeft: 8, borderLeft: '1px solid #10B981'}}>
              Final: {ev.review.final_marks} marks
            </span>
            {ev.review.comment && (
              <span style={{marginLeft: 8, fontStyle: 'italic', opacity: 0.8}}>— "{ev.review.comment}"</span>
            )}
          </div>
        ) : (
          <div style={{display: 'flex', flexDirection: 'column', gap: 12}}>
            <div className="actions" style={{marginTop: 0}}>
              <input type="text" placeholder="Reviewer Initials" value={reviewer} onChange={(e) => setReviewer(e.target.value)} style={{width: 140}} />
              <input type="text" placeholder="Optional comment" value={comment} onChange={(e) => setComment(e.target.value)} style={{flex: 1}} />
            </div>
            <div className="actions" style={{marginTop: 0, justifyContent: 'space-between'}}>
              <button className="primary" disabled={busy} onClick={() => decide('accepted')} style={{flex: 1}}>
                Accept {ev.marks_awarded} marks
              </button>
              <div style={{display: 'flex', gap: 8, flex: 1, justifyContent: 'flex-end'}}>
                <input
                  type="number"
                  step="0.5"
                  min="0"
                  max={ev.max_marks}
                  value={overrideMarks}
                  onChange={(e) => setOverrideMarks(e.target.value)}
                />
                <button className="override" disabled={busy} onClick={() => decide('overridden')}>
                  Override Marks
                </button>
              </div>
            </div>
            {error && <p className="flag">{error}</p>}
          </div>
        )}
      </div>
    </div>
  )
}
