import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { getScript, submitReview, finalizeScript, bulkAcceptEvaluations, getPeerComparisons } from '../api.js'
import { useAuth } from '../context/AuthContext'

export default function ReviewPage() {
  const { scriptId } = useParams()
  const [script, setScript] = useState(null)
  const [error, setError] = useState('')
  const [activeTab, setActiveTab] = useState('breakdown') // 'breakdown' | 'comparison' | 'ocr'
  const [viewOriginal, setViewOriginal] = useState(false)
  const [finalizing, setFinalizing] = useState(false)
  const [bulkAccepting, setBulkAccepting] = useState(false)
  const [statusMsg, setStatusMsg] = useState('')
  const { user } = useAuth()

  const refresh = useCallback(
    () => getScript(scriptId).then(setScript).catch((e) => setError(String(e))),
    [scriptId],
  )

  useEffect(() => { refresh() }, [refresh])

  const handleFinalize = async () => {
    if (!confirm("Approve and finalize this script evaluation? This will transition status to FINAL and generate an immutable evaluation run version.")) return
    setFinalizing(true)
    try {
      await finalizeScript(scriptId)
      setStatusMsg("Script evaluation approved and status set to FINAL!")
      await refresh()
    } catch (err) {
      setError(String(err))
    } finally {
      setFinalizing(false)
      setTimeout(() => setStatusMsg(''), 5000)
    }
  }

  if (error) return <main><div className="card flag" style={{ padding: 24, margin: 20 }}>⚠️ {error}</div></main>
  if (!script) return (
    <main>
      <div className="loader-container" style={{ textAlign: 'center', padding: '80px 20px' }}>
        <div className="spinner"></div>
        <p style={{ marginTop: 16, color: '#94a3b8' }}>Loading high-resolution script evaluation canvas & AI audit...</p>
      </div>
    </main>
  )

  const isFinal = script.status === 'FINAL' || script.status === 'finalized'
  const pdfUrl = `/api/scripts/${script.id}/${viewOriginal ? 'original.pdf' : 'annotated.pdf'}?t=${Date.now()}#navpanes=0&view=FitH`

  return (
    <div className="review-container" style={{ padding: '20px', maxWidth: '1800px', margin: '0 auto' }}>
      {statusMsg && (
        <div className="status-banner" style={{ background: 'rgba(16, 185, 129, 0.2)', color: '#10b981', border: '1px solid #10b981', padding: '12px 20px', borderRadius: '12px', marginBottom: '20px', fontWeight: 700 }}>
          🎉 {statusMsg}
        </div>
      )}

      <div className="review-header" style={{ background: 'rgba(24, 24, 27, 0.85)', backdropFilter: 'blur(16px)', border: '1px solid rgba(255,255,255,0.1)', padding: '20px 28px', borderRadius: '16px', display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: '15px' }}>
        <Link to="/dashboard" className="back-link" style={{ color: '#8b5cf6', fontWeight: 600, textDecoration: 'none' }}>
          &larr; Back to Dashboard Queue
        </Link>

        <div style={{ marginLeft: '20px', display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span style={{ fontSize: '1.4rem', fontWeight: 700, color: '#f8fafc' }}>
            {script.student_name || 'Anonymous Student'}
          </span>
          <span className={`status-pill ${isFinal ? 'success' : 'warning'}`} style={{ textTransform: 'uppercase', fontSize: '0.8rem', padding: '6px 12px' }}>
            {script.status}
          </span>
        </div>

        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '16px' }}>
          {script.summary && (
            <div style={{ background: '#1e1e24', border: '1px solid rgba(255,255,255,0.15)', padding: '8px 16px', borderRadius: '12px', textAlign: 'right' }}>
              <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: '#94a3b8', fontWeight: 600 }}>Total Score</div>
              <div style={{ fontSize: '1.35rem', fontWeight: 700, color: '#38bdf8' }}>
                {script.summary.total_awarded} <span style={{ fontSize: '0.9rem', color: '#64748b' }}>/ {script.summary.total_max} pts</span>
              </div>
            </div>
          )}

          {!isFinal ? (
            <div style={{ display: 'flex', gap: '8px' }}>
              <button
                onClick={async () => {
                  if(!confirm("Bulk accept all sub-parts where both models agree and confidence > 90%?")) return;
                  setBulkAccepting(true);
                  try {
                    const res = await bulkAcceptEvaluations(scriptId, user?.name || 'Faculty', 0.90);
                    setStatusMsg(`Bulk accepted ${res.accepted_count} evaluation(s)!`);
                    await refresh();
                  } catch(err) {
                    setError(String(err));
                  } finally {
                    setBulkAccepting(false);
                    setTimeout(() => setStatusMsg(''), 5000);
                  }
                }}
                disabled={bulkAccepting}
                className="button secondary"
                style={{ background: '#3b82f6', color: '#fff', border: 'none', padding: '12px 16px', fontWeight: 700, fontSize: '0.95rem' }}
              >
                {bulkAccepting ? 'Accepting...' : '✨ Auto-Accept High Confidence'}
              </button>
              <button
                onClick={handleFinalize}
                disabled={finalizing}
                className="button primary"
                style={{ background: '#10b981', padding: '12px 24px', fontWeight: 700, fontSize: '0.95rem', boxShadow: '0 4px 14px rgba(16, 185, 129, 0.4)' }}
              >
                {finalizing ? 'Finalizing...' : '✅ Approve & Finalize Script'}
              </button>
            </div>
          ) : (
            <span style={{ background: 'rgba(16, 185, 129, 0.15)', color: '#10b981', padding: '10px 18px', borderRadius: '10px', fontWeight: 700, border: '1px solid #10b981' }}>
              🔒 Finalized Version Approved
            </span>
          )}
        </div>
      </div>

      <div style={{ marginTop: 24 }}>
        <div className="review-layout" style={{ display: 'grid', gridTemplateColumns: '1.1fr 0.9fr', gap: '24px', height: 'calc(100vh - 180px)' }}>
          
          {/* Left Pane: Interactive High-Res PDF Canvas */}
          <div className="pdf-pane" style={{ background: '#18181b', borderRadius: '16px', border: '1px solid rgba(255,255,255,0.1)', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
            <div style={{ padding: '14px 20px', background: '#27272a', borderBottom: '1px solid rgba(255,255,255,0.08)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontWeight: 700, color: '#f8fafc', fontSize: '0.95rem' }}>
                🖼️ {viewOriginal ? 'Original 300 DPI Script Scan' : 'Annotated Canvas (RapidFuzz Deterministic Ticks)'}
              </span>
              <div style={{ display: 'flex', gap: '8px', background: '#18181b', padding: '4px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.1)' }}>
                <button
                  onClick={() => setViewOriginal(false)}
                  style={{ background: !viewOriginal ? '#6366f1' : 'transparent', color: !viewOriginal ? '#fff' : '#94a3b8', border: 'none', padding: '6px 12px', borderRadius: '6px', cursor: 'pointer', fontWeight: 600, fontSize: '0.82rem' }}
                >
                  ✓ AI Annotations
                </button>
                <button
                  onClick={() => setViewOriginal(true)}
                  style={{ background: viewOriginal ? '#6366f1' : 'transparent', color: viewOriginal ? '#fff' : '#94a3b8', border: 'none', padding: '6px 12px', borderRadius: '6px', cursor: 'pointer', fontWeight: 600, fontSize: '0.82rem' }}
                >
                  📄 Raw Original
                </button>
              </div>
            </div>
            <div style={{ flex: 1, position: 'relative' }}>
              <iframe title="annotated script" src={pdfUrl} style={{ width: '100%', height: '100%', border: 'none' }} />
            </div>
          </div>
          
          {/* Right Pane: Multi-Tab AI Evaluation Breakdown & Audit */}
          <div className="eval-pane" style={{ background: '#18181b', borderRadius: '16px', border: '1px solid rgba(255,255,255,0.1)', padding: '24px', overflowY: 'auto' }}>
            {/* Tab Navigation */}
            <div style={{ display: 'flex', gap: '10px', borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '16px', marginBottom: '24px' }}>
              <button
                onClick={() => setActiveTab('breakdown')}
                style={{ padding: '10px 18px', borderRadius: '10px', border: 'none', cursor: 'pointer', fontWeight: 700, fontSize: '0.9rem', background: activeTab === 'breakdown' ? '#6366f1' : '#27272a', color: activeTab === 'breakdown' ? '#fff' : '#94a3b8', transition: 'all 0.2s' }}
              >
                📊 Rubric Evaluation ({script.evaluations.length})
              </button>
              <button
                onClick={() => setActiveTab('comparison')}
                style={{ padding: '10px 18px', borderRadius: '10px', border: 'none', cursor: 'pointer', fontWeight: 700, fontSize: '0.9rem', background: activeTab === 'comparison' ? '#6366f1' : '#27272a', color: activeTab === 'comparison' ? '#fff' : '#94a3b8', transition: 'all 0.2s' }}
              >
                ⚖️ Pass 1 vs Pass 2 Comparison
              </button>
              <button
                onClick={() => setActiveTab('ocr')}
                style={{ padding: '10px 18px', borderRadius: '10px', border: 'none', cursor: 'pointer', fontWeight: 700, fontSize: '0.9rem', background: activeTab === 'ocr' ? '#6366f1' : '#27272a', color: activeTab === 'ocr' ? '#fff' : '#94a3b8', transition: 'all 0.2s' }}
              >
                🔍 Raw OCR & Bounding Boxes
              </button>
            </div>
            
            {script.evaluations.length === 0 && (
              <div className="card" style={{ textAlign: 'center', padding: '60px 20px', background: '#27272a', border: '1px solid rgba(255,255,255,0.08)' }}>
                <div className="spinner" style={{ margin: '0 auto' }}></div>
                <h3 style={{ marginTop: 24, color: '#f8fafc' }}>AI Evaluation in Progress...</h3>
                <p style={{ color: '#94a3b8', maxWidth: '400px', margin: '12px auto 0' }}>
                  Our dual-model pipeline is recognizing text, aligning evidence via RapidFuzz, and enforcing strict score Enums.
                </p>
              </div>
            )}
            
            {/* TAB 1: BREAKDOWN */}
            {activeTab === 'breakdown' && (
              <div>
                {script.evaluations.map((ev) => (
                  <QuestionCard key={ev.id} ev={ev} onReviewed={refresh} offeringId={script.class_offering_id} excludeScriptId={script.id} />
                ))}
              </div>
            )}

            {/* TAB 2: PASS 1 VS PASS 2 COMPARISON */}
            {activeTab === 'comparison' && (
              <div>
                <h3 style={{ color: '#f8fafc', marginBottom: '8px', fontSize: '1.2rem' }}>🤝 Dual-Model Cross-Check Audit</h3>
                <p style={{ color: '#94a3b8', fontSize: '0.88rem', marginBottom: '24px' }}>
                  Per Rule 3, two independent LLMs (Primary vs. Cross-Check) grade each question. If scores differ by $&gt; 1.0$ mark, a HIGH_VARIANCE flag is triggered for mandatory faculty alignment.
                </p>

                {script.evaluations.map(ev => {
                  const p1Score = ev.marks_awarded
                  const p2Score = ev.pass2 ? ev.pass2.point_evaluations.reduce((a, p) => a + p.marks_awarded, 0) : null
                  const hasVariance = p2Score !== null && Math.abs(p1Score - p2Score) > 1.0

                  return (
                    <div key={ev.id} style={{ background: '#27272a', borderRadius: '14px', border: '1px solid rgba(255,255,255,0.1)', padding: '20px', marginBottom: '20px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                        <h4 style={{ margin: 0, color: '#f8fafc', fontSize: '1.15rem' }}>Question {ev.question_number} (Max: {ev.max_marks} pts)</h4>
                        {hasVariance ? (
                          <span style={{ background: 'rgba(239, 68, 68, 0.2)', color: '#ef4444', border: '1px solid #ef4444', padding: '4px 12px', borderRadius: '8px', fontWeight: 700, fontSize: '0.78rem' }}>
                            ⚠️ HIGH_VARIANCE DETECTED (Δ &gt; 1.0)
                          </span>
                        ) : (
                          <span style={{ color: '#10b981', fontWeight: 600, fontSize: '0.85rem' }}>✓ Models Aligned</span>
                        )}
                      </div>

                      {hasVariance && (
                        <div style={{ background: 'rgba(239, 68, 68, 0.15)', borderLeft: '4px solid #ef4444', padding: '12px 16px', borderRadius: '6px', color: '#fca5a5', fontSize: '0.88rem', marginBottom: '16px' }}>
                          <strong>Discrepancy Alert:</strong> Primary model awarded <strong>{p1Score} pts</strong> while cross-check model awarded <strong>{p2Score} pts</strong>. Please review evidence quotes below and apply faculty override if necessary.
                        </div>
                      )}

                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                        {/* Pass 1 */}
                        <div style={{ background: '#18181b', padding: '16px', borderRadius: '10px', border: '1px solid rgba(255,255,255,0.08)' }}>
                          <div style={{ fontSize: '0.8rem', textTransform: 'uppercase', color: '#6366f1', fontWeight: 700, marginBottom: '6px' }}>Pass 1 • Primary Evaluator</div>
                          <div style={{ fontSize: '1.3rem', fontWeight: 700, color: '#38bdf8', marginBottom: '12px' }}>{p1Score} <span style={{ fontSize: '0.8rem', color: '#64748b' }}>/ {ev.max_marks}</span></div>
                          {(ev.pass1?.point_evaluations || []).map((pt, i) => (
                            <div key={i} style={{ fontSize: '0.85rem', color: '#cbd5e1', marginBottom: '8px', borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: '6px' }}>
                              <strong>{pt.rubric_point_id} ({pt.marks_awarded} pt):</strong> {pt.reasoning || 'Matched criteria'}
                            </div>
                          ))}
                        </div>

                        {/* Pass 2 */}
                        <div style={{ background: '#18181b', padding: '16px', borderRadius: '10px', border: '1px solid rgba(255,255,255,0.08)' }}>
                          <div style={{ fontSize: '0.8rem', textTransform: 'uppercase', color: '#a855f7', fontWeight: 700, marginBottom: '6px' }}>Pass 2 • Cross-Check Evaluator</div>
                          <div style={{ fontSize: '1.3rem', fontWeight: 700, color: '#c084fc', marginBottom: '12px' }}>{p2Score !== null ? p2Score : 'N/A'} <span style={{ fontSize: '0.8rem', color: '#64748b' }}>/ {ev.max_marks}</span></div>
                          {(ev.pass2?.point_evaluations || []).map((pt, i) => (
                            <div key={i} style={{ fontSize: '0.85rem', color: '#cbd5e1', marginBottom: '8px', borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: '6px' }}>
                              <strong>{pt.rubric_point_id} ({pt.marks_awarded} pt):</strong> {pt.reasoning || 'Matched criteria'}
                            </div>
                          ))}
                          {!ev.pass2 && <div style={{ color: '#64748b', fontStyle: 'italic', fontSize: '0.85rem' }}>Single-pass evaluation run or secondary model disabled.</div>}
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}

            {/* TAB 3: RAW OCR */}
            {activeTab === 'ocr' && (
              <div>
                <h3 style={{ color: '#f8fafc', marginBottom: '8px', fontSize: '1.2rem' }}>📜 Raw OCR Tokens & Scale Factor Metas</h3>
                <p style={{ color: '#94a3b8', fontSize: '0.88rem', marginBottom: '20px' }}>
                  Server-side OCRPageData and line confidence values used by the deterministic RapidFuzz matching engine.
                </p>
                <div style={{ background: '#09090b', padding: '20px', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.1)', fontFamily: 'monospace', color: '#10b981', fontSize: '0.85rem', whiteSpace: 'pre-wrap', maxHeight: '550px', overflowY: 'auto' }}>
                  {JSON.stringify({
                    script_id: script.id,
                    student_name: script.student_name,
                    pipeline_status: script.status,
                    evaluations_count: script.evaluations.length,
                    raw_evaluations_audit: script.evaluations.map(e => ({
                      question: e.question_number,
                      confidence: e.confidence,
                      flags: e.flags,
                      cited_quotes: e.pass1?.point_evaluations?.map(p => p.evidence_quote)
                    }))
                  }, null, 2)}
                </div>
              </div>
            )}
            
          </div>
          
        </div>
      </div>
    </div>
  )
}

function QuestionCard({ ev, onReviewed, offeringId, excludeScriptId }) {
  const [overrideMarks, setOverrideMarks] = useState(ev.marks_awarded)
  const [reviewer, setReviewer] = useState('')
  const [comment, setComment] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [peers, setPeers] = useState(null)
  const [loadingPeers, setLoadingPeers] = useState(false)

  const loadPeers = async () => {
    setLoadingPeers(true)
    try {
      const data = await getPeerComparisons(offeringId, ev.question_number, ev.subpart_id, excludeScriptId)
      setPeers(data.peers)
    } catch(err) {
      console.error(err)
    } finally {
      setLoadingPeers(false)
    }
  }

  async function decide(action) {
    setBusy(true)
    setError('')
    
    if (action === 'overridden') {
      const markValue = Number(overrideMarks)
      if (ev.allowed_increments && ev.allowed_increments.length > 0) {
        if (!ev.allowed_increments.includes(markValue)) {
          setError(`Invalid mark. Must be one of: ${ev.allowed_increments.join(', ')}`)
          setBusy(false)
          return
        }
      }
    }
    
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
    <div className="audit-card" style={{ background: '#27272a', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '14px', padding: '20px', marginBottom: '20px', boxShadow: '0 4px 20px rgba(0,0,0,0.25)' }}>
      <div className="audit-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', borderBottom: '1px solid rgba(255,255,255,0.08)', paddingBottom: '12px' }}>
        <div className="audit-title">
          <h3 style={{ margin: 0, color: '#f8fafc', fontSize: '1.25rem' }}>Question {ev.question_number}</h3>
          <div className="audit-confidence" style={{ color: '#10b981', fontSize: '0.82rem', fontWeight: 600, marginTop: '2px' }}>
            ⚡ Recognition Confidence: {(ev.confidence * 100).toFixed(0)}%
          </div>
        </div>
        <div className="audit-score-box" style={{ background: '#18181b', padding: '8px 16px', borderRadius: '10px', border: '1px solid rgba(255,255,255,0.1)' }}>
          <span className="audit-score-awarded" style={{ fontSize: '1.4rem', fontWeight: 700, color: '#38bdf8' }}>{ev.marks_awarded}</span>
          <span className="audit-score-max" style={{ color: '#64748b', fontSize: '0.9rem' }}> / {ev.max_marks} pts</span>
        </div>
      </div>
      
      {ev.flags.length > 0 && (
        <div className="audit-flags" style={{ background: 'rgba(239, 68, 68, 0.15)', border: '1px solid rgba(239, 68, 68, 0.4)', borderRadius: '10px', padding: '12px', marginBottom: '16px' }}>
          {ev.flags.map((f, i) => (
            <div key={i} className="audit-flag-item" style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#f87171', fontSize: '0.88rem', fontWeight: 600 }}>
              <span>⚠️ {f.reason}</span>
            </div>
          ))}
        </div>
      )}
      
      <div className="audit-points-list" style={{ marginBottom: '20px' }}>
        {(ev.pass1?.point_evaluations || []).map((p) => (
          <div key={p.rubric_point_id} className="audit-point" style={{ background: '#18181b', border: '1px solid rgba(255,255,255,0.06)', borderRadius: '10px', padding: '14px', marginBottom: '10px' }}>
            <div className="audit-point-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <div className="audit-point-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span className={`status-pill ${p.marks_awarded > 0 ? 'success' : 'warning'}`} style={{ fontSize: '0.7rem' }}>
                  {p.marks_awarded > 0 ? 'MATCHED' : 'UNMATCHED / MISSING'}
                </span>
                <strong style={{ color: '#f8fafc', fontSize: '0.95rem' }}>{p.rubric_point_id}</strong>
              </div>
              <strong style={{ color: p.marks_awarded > 0 ? '#10b981' : '#f87171', fontSize: '1.05rem', fontWeight: 700 }}>
                {p.marks_awarded > 0 ? '+' : ''}{p.marks_awarded} pt
              </strong>
            </div>
            
            {p.evidence_quote && (
              <div className="audit-quote" style={{ background: '#27272a', padding: '8px 12px', borderRadius: '6px', fontStyle: 'italic', color: '#e2e8f0', fontSize: '0.85rem', borderLeft: '3px solid #6366f1', marginBottom: '8px' }}>
                "{p.evidence_quote}"
              </div>
            )}
            {p.reasoning && <div className="audit-reasoning" style={{ color: '#94a3b8', fontSize: '0.85rem' }}>💡 {p.reasoning}</div>}
          </div>
        ))}
      </div>
      
      <div className="audit-controls" style={{ borderTop: '1px solid rgba(255,255,255,0.08)', paddingTop: '16px' }}>
        {ev.review ? (
          <div className="audit-reviewed" style={{ background: 'rgba(16, 185, 129, 0.1)', border: '1px solid rgba(16, 185, 129, 0.3)', borderRadius: '10px', padding: '12px 16px', color: '#10b981' }}>
            <div style={{ fontWeight: 700, marginBottom: '4px' }}>
              {ev.review.action === 'accepted' ? '✓ Accepted by Instructor' : '⚡ Overridden by Faculty'} (Reviewer: {ev.review.reviewer || 'Faculty'})
            </div>
            <div style={{ color: '#f8fafc' }}>
              <strong>Final Awarded Score: {ev.review.final_marks} / {ev.max_marks} pts</strong>
              {ev.review.comment && <div style={{ color: '#94a3b8', fontStyle: 'italic', marginTop: '4px' }}>Remarks: "{ev.review.comment}"</div>}
            </div>
          </div>
        ) : (
          <div className="audit-action-panel">
            <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 2fr', gap: '10px', marginBottom: '12px' }}>
              <input type="text" placeholder="Reviewer (e.g. Prof. Devansh)" value={reviewer} onChange={(e) => setReviewer(e.target.value)} style={{ padding: '10px', borderRadius: '8px', background: '#18181b', color: '#fff', border: '1px solid #444', outline: 'none', fontSize: '0.85rem' }} />
              <input type="text" placeholder="Faculty review remarks / feedback..." value={comment} onChange={(e) => setComment(e.target.value)} style={{ padding: '10px', borderRadius: '8px', background: '#18181b', color: '#fff', border: '1px solid #444', outline: 'none', fontSize: '0.85rem' }} />
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '12px' }}>
              <button className="button primary" style={{ background: '#10b981', flex: 1 }} disabled={busy} onClick={() => decide('accepted')}>
                ✓ Accept AI ({ev.marks_awarded} pts)
              </button>
              
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flex: 1.2 }}>
                <input
                  type="number"
                  step="0.5"
                  min="0"
                  max={ev.max_marks}
                  value={overrideMarks}
                  onChange={(e) => setOverrideMarks(e.target.value)}
                  style={{ width: '80px', padding: '10px', borderRadius: '8px', background: '#18181b', color: '#fff', border: '1px solid #6366f1', textAlign: 'center', fontWeight: 700, outline: 'none' }}
                />
                <button className="button secondary" style={{ background: '#ef4444', color: '#fff', flex: 1 }} disabled={busy} onClick={() => decide('overridden')}>
                  ⚡ Apply Override
                </button>
              </div>
            </div>
            {error && <p style={{ color: '#ef4444', fontSize: '0.85rem', margin: '8px 0 0 0' }}>{error}</p>}
          </div>
        )}

        <div style={{ marginTop: '16px', paddingTop: '16px', borderTop: '1px solid rgba(255,255,255,0.05)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.85rem', color: '#94a3b8' }}>Unsure? Check how other faculty evaluated this sub-part.</span>
            <button 
              onClick={loadPeers} 
              disabled={loadingPeers}
              style={{ background: 'transparent', border: '1px solid #3b82f6', color: '#3b82f6', padding: '6px 12px', borderRadius: '6px', fontSize: '0.8rem', cursor: 'pointer' }}
            >
              {loadingPeers ? 'Loading peers...' : '👥 View Peer Comparison'}
            </button>
          </div>
          
          {peers && (
            <div style={{ marginTop: '12px', display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
              {peers.length === 0 ? (
                <div style={{ fontSize: '0.85rem', color: '#64748b', fontStyle: 'italic' }}>No peer evaluations found for this question yet.</div>
              ) : (
                peers.map((peer, i) => (
                  <div key={i} style={{ flex: 1, minWidth: '200px', background: '#18181b', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', padding: '12px' }}>
                    <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: '6px' }}>Student Script {peer.script_id.substring(0,6)}...</div>
                    <div style={{ fontSize: '1.2rem', color: '#38bdf8', fontWeight: 700, marginBottom: '6px' }}>{peer.marks_awarded} pts</div>
                    {peer.evidence_quote && <div style={{ fontSize: '0.8rem', color: '#cbd5e1', fontStyle: 'italic', background: 'rgba(255,255,255,0.05)', padding: '6px', borderRadius: '4px' }}>"{peer.evidence_quote}"</div>}
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
