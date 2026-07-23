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

  if (error) return <main><p className="flag">{error}</p></main>
  if (!script) return <main>Loading…</main>

  return (
    <>
      <header>
        <Link to="/">Answer Script Grader</Link>
        <span>
          {script.student_name || 'Unnamed student'} — <span className={`status ${script.status}`}>{script.status}</span>
        </span>
        {script.summary && (
          <span className="marks">
            {script.summary.total_awarded} / {script.summary.total_max}
          </span>
        )}
      </header>
      <main>
        <div className="review-layout">
          <div className="pdf-pane">
            <iframe title="annotated script" src={`/api/scripts/${script.id}/annotated.pdf`} />
          </div>
          <div className="eval-pane">
            {script.evaluations.map((ev) => (
              <QuestionCard key={ev.id} ev={ev} onReviewed={refresh} />
            ))}
            {script.evaluations.length === 0 && (
              <div className="card">No evaluations yet — grading may still be running.</div>
            )}
          </div>
        </div>
      </main>
    </>
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
        reviewer,
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
      <h3>
        Question {ev.question_number}{' '}
        <span className="marks">{ev.marks_awarded} / {ev.max_marks}</span>{' '}
        <small>confidence {(ev.confidence * 100).toFixed(0)}%</small>
      </h3>
      {ev.flags.map((f, i) => (
        <div key={i} className="flag">⚑ {f.reason}</div>
      ))}
      {ev.pass1?.examiner_note && <p><em>{ev.pass1.examiner_note}</em></p>}
      {(ev.pass1?.point_evaluations || []).map((p) => (
        <div key={p.rubric_point_id} className="point">
          <span className={p.status}>{p.status.toUpperCase()}</span>{' '}
          <strong>{p.rubric_point_id}</strong> — {p.marks_awarded} marks
          {p.evidence_quote && <div className="quote">“{p.evidence_quote}”</div>}
          {p.reasoning && <div>{p.reasoning}</div>}
        </div>
      ))}
      {ev.pass2 && (
        <p><small>Second pass total: {ev.pass2.point_evaluations.reduce((a, p) => a + p.marks_awarded, 0)} marks</small></p>
      )}
      {ev.review ? (
        <p className="reviewed">
          {ev.review.action === 'accepted' ? 'Accepted' : 'Overridden'} — final {ev.review.final_marks} marks
          {ev.review.reviewer && ` by ${ev.review.reviewer}`}
          {ev.review.comment && ` — ${ev.review.comment}`}
        </p>
      ) : (
        <>
          <div className="actions">
            <button className="accept" disabled={busy} onClick={() => decide('accepted')}>
              Accept {ev.marks_awarded} marks
            </button>
            <input
              type="number"
              step="0.5"
              min="0"
              max={ev.max_marks}
              value={overrideMarks}
              onChange={(e) => setOverrideMarks(e.target.value)}
            />
            <button className="override" disabled={busy} onClick={() => decide('overridden')}>
              Override
            </button>
          </div>
          <div className="actions">
            <input type="text" placeholder="Reviewer" value={reviewer} onChange={(e) => setReviewer(e.target.value)} />
            <input type="text" placeholder="Comment" value={comment} onChange={(e) => setComment(e.target.value)} />
          </div>
          {error && <p className="flag">{error}</p>}
        </>
      )}
    </div>
  )
}
