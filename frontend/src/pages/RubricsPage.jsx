import React, { useState, useEffect } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { getOfferingRubric, lockOfferingRubric, updateRubricItem, addRubricAddendum } from '../api'
import { useAuth } from '../context/AuthContext'

export default function RubricsPage() {
  const { user } = useAuth()
  const [searchParams] = useSearchParams()
  const offeringId = searchParams.get('offeringId')

  const [rubric, setRubric] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [statusMsg, setStatusMsg] = useState('')

  const [editingItem, setEditingItem] = useState(null)
  const [editForm, setEditForm] = useState({})
  
  const [addendumText, setAddendumText] = useState({})
  const [previousRubrics, setPreviousRubrics] = useState([])
  const [selectedPreviousId, setSelectedPreviousId] = useState('')
  const [cloning, setCloning] = useState(false)

  const fetchRubric = async () => {
    if (!offeringId) {
      setError("No Class Offering selected. Please go back to the Dashboard and select a context.")
      setLoading(false)
      return
    }
    setLoading(true)
    setError('')
    try {
      const data = await getOfferingRubric(offeringId)
      setRubric(data)
      if (data.subject_id && (data.status === 'Missing Materials' || data.status === 'Ready to Generate')) {
        const { getSubjectRubrics } = await import('../api')
        const prev = await getSubjectRubrics(data.subject_id)
        // Filter out current offering's rubrics if they exist, though here it's locked rubrics
        setPreviousRubrics(prev.filter(r => r.class_offering_id !== offeringId))
      }
    } catch (err) {
      setError(String(err))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchRubric()
  }, [offeringId])

  const handleLock = async () => {
    if (!confirm("Are you sure you want to approve and lock this rubric? Once locked, max marks and increments become strictly immutable.")) return
    try {
      await lockOfferingRubric(rubric.version_id, "Faculty User")
      setStatusMsg("Rubric successfully LOCKED as immutable single source of truth!")
      await fetchRubric()
      setTimeout(() => setStatusMsg(''), 4000)
    } catch (err) {
      setError(String(err))
    }
  }

  const handleEditClick = (item) => {
    setEditingItem(item.id)
    setEditForm({
      expected_concepts: item.expected_concepts.join(', '),
      accepted_alternates: item.accepted_alternates.join(', '),
      max_marks: item.max_marks,
      allowed_increments: item.allowed_increments.join(', ')
    })
  }

  const handleSaveEdit = async (itemId) => {
    try {
      const updates = {
        expected_concepts: editForm.expected_concepts.split(',').map(s => s.trim()).filter(Boolean),
        accepted_alternates: editForm.accepted_alternates.split(',').map(s => s.trim()).filter(Boolean),
        max_marks: parseFloat(editForm.max_marks),
        allowed_increments: editForm.allowed_increments.split(',').map(s => parseFloat(s.trim())).filter(n => !isNaN(n))
      }
      await updateRubricItem(itemId, updates)
      setEditingItem(null)
      await fetchRubric()
      setStatusMsg("Item updated successfully!")
      setTimeout(() => setStatusMsg(''), 3000)
    } catch (err) {
      setError(String(err))
    }
  }

  const handleAddAddendum = async (itemId) => {
    const text = addendumText[itemId]
    if (!text) return
    try {
      await addRubricAddendum(itemId, text, "Faculty User")
      setAddendumText({ ...addendumText, [itemId]: '' })
      await fetchRubric()
      setStatusMsg("Addendum added successfully!")
      setTimeout(() => setStatusMsg(''), 3000)
    } catch (err) {
      setError(String(err))
    }
  }

  if (loading) return <div style={{ padding: 40, color: '#a1a1aa' }}>Loading context rubric...</div>
  if (error) return <div style={{ padding: 40, color: '#ef4444' }}>⚠️ {error}</div>

  const handleClonePrevious = async () => {
    if (!selectedPreviousId) return
    setCloning(true)
    try {
      const { cloneRubricToOffering } = await import('../api')
      await cloneRubricToOffering(offeringId, selectedPreviousId)
      setStatusMsg("Successfully cloned rubric from previous offering!")
      await fetchRubric()
      setTimeout(() => setStatusMsg(''), 4000)
    } catch (err) {
      setError(String(err))
    } finally {
      setCloning(false)
    }
  }

  if (!rubric || rubric.status === 'Missing Materials' || rubric.status === 'Ready to Generate') {
    return (
      <div style={{ padding: 40, color: '#a1a1aa' }}>
        <h3>Rubric not ready</h3>
        <p>Please upload materials and generate the rubric from the Dashboard first.</p>
        
        {previousRubrics.length > 0 && (
          <div style={{ marginTop: '24px', padding: '20px', background: '#18181b', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.1)' }}>
            <h4 style={{ margin: '0 0 12px 0', color: '#f8fafc' }}>Or start from a previous rubric</h4>
            <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
              <select 
                value={selectedPreviousId} 
                onChange={e => setSelectedPreviousId(e.target.value)}
                style={{ padding: '8px', borderRadius: '8px', background: '#27272a', color: '#fff', border: '1px solid #3f3f46', flex: 1, outline: 'none' }}
              >
                <option value="">-- Select a previous locked rubric --</option>
                {previousRubrics.map(pr => (
                  <option key={pr.rubric_version_id} value={pr.rubric_version_id}>
                    Rubric v{pr.version_number} (Locked on {new Date(pr.created_at).toLocaleDateString()}) - Offering {pr.class_offering_id}
                  </option>
                ))}
              </select>
              <button 
                onClick={handleClonePrevious} 
                disabled={!selectedPreviousId || cloning || user?.role === 'read_only' || user?.role === 'evaluator'} 
                className="button secondary"
                style={{ opacity: (!selectedPreviousId || cloning || user?.role === 'read_only' || user?.role === 'evaluator') ? 0.5 : 1, cursor: (!selectedPreviousId || cloning || user?.role === 'read_only' || user?.role === 'evaluator') ? 'not-allowed' : 'pointer' }}
              >
                {cloning ? 'Cloning...' : 'Clone to this Offering'}
              </button>
            </div>
          </div>
        )}

        <div style={{ marginTop: '24px' }}>
          <Link to={`/dashboard?offeringId=${offeringId}`} className="button primary">Go to Dashboard</Link>
        </div>
      </div>
    )
  }

  return (
    <div className="dashboard-content fade-in" style={{ padding: '24px' }}>
      <div style={{ marginBottom: 24 }}>
        <Link to={`/dashboard?offeringId=${offeringId}`} style={{ color: '#6366f1', textDecoration: 'none', fontWeight: 600 }}>&larr; Back to Dashboard</Link>
      </div>
      
      {statusMsg && (
        <div style={{ background: 'rgba(16, 185, 129, 0.2)', color: '#10b981', border: '1px solid #10b981', padding: '12px 20px', borderRadius: '12px', marginBottom: '20px', fontWeight: 600 }}>
          {statusMsg}
        </div>
      )}

      <div className="header-container" style={{ background: 'rgba(24, 24, 27, 0.8)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '16px', padding: '24px', marginBottom: '32px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ margin: 0, color: '#f8fafc', fontSize: '1.8rem' }}>📐 Rubric Review</h1>
          <p className="subtitle" style={{ margin: '8px 0 0 0', color: '#94a3b8', fontSize: '0.95rem' }}>
            Status: <strong style={{ color: rubric.is_locked ? '#10b981' : '#f59e0b' }}>{rubric.status}</strong>
          </p>
        </div>
        {!rubric.is_locked && (
          <button 
            onClick={handleLock} 
            disabled={user?.role === 'read_only' || user?.role === 'evaluator'}
            className="button primary" 
            style={{ background: '#10b981', opacity: user?.role === 'read_only' || user?.role === 'evaluator' ? 0.5 : 1, cursor: user?.role === 'read_only' || user?.role === 'evaluator' ? 'not-allowed' : 'pointer' }}
            title={user?.role === 'read_only' || user?.role === 'evaluator' ? 'Permission denied' : ''}
          >
            🔒 Approve & Lock Rubric
          </button>
        )}
      </div>

      <div className="rubrics-list" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
        {rubric.rubric_data?.map(item => (
          <div key={item.id} style={{ background: '#27272a', borderRadius: '16px', border: '1px solid rgba(255,255,255,0.1)', padding: '20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
              <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                <div style={{ background: '#6366f1', color: '#fff', fontWeight: 700, padding: '8px 16px', borderRadius: '10px' }}>
                  Q{item.question_number}{item.subpart_id ? `(${item.subpart_id})` : ''}
                </div>
                <div style={{ fontSize: '1.1rem', color: '#f8fafc', fontWeight: 600 }}>
                  Max Marks: {item.max_marks}
                </div>
              </div>
              {!rubric.is_locked && editingItem !== item.id && (
                <button 
                  onClick={() => handleEditClick(item)} 
                  disabled={user?.role === 'read_only' || user?.role === 'evaluator'}
                  className="button secondary"
                  style={{ opacity: user?.role === 'read_only' || user?.role === 'evaluator' ? 0.5 : 1, cursor: user?.role === 'read_only' || user?.role === 'evaluator' ? 'not-allowed' : 'pointer' }}
                  title={user?.role === 'read_only' || user?.role === 'evaluator' ? 'Permission denied' : ''}
                >
                  Edit Draft
                </button>
              )}
            </div>

            {editingItem === item.id ? (
              <div style={{ background: '#18181b', padding: '16px', borderRadius: '12px', border: '1px solid #3f3f46', display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <div>
                  <label style={{ display: 'block', color: '#a1a1aa', fontSize: '0.85rem', marginBottom: '6px' }}>Max Marks</label>
                  <input type="number" className="input" value={editForm.max_marks} onChange={e => setEditForm({...editForm, max_marks: e.target.value})} />
                </div>
                <div>
                  <label style={{ display: 'block', color: '#a1a1aa', fontSize: '0.85rem', marginBottom: '6px' }}>Allowed Increments (comma separated)</label>
                  <input type="text" className="input" value={editForm.allowed_increments} onChange={e => setEditForm({...editForm, allowed_increments: e.target.value})} />
                </div>
                <div>
                  <label style={{ display: 'block', color: '#a1a1aa', fontSize: '0.85rem', marginBottom: '6px' }}>Expected Concepts (comma separated)</label>
                  <textarea className="input" value={editForm.expected_concepts} onChange={e => setEditForm({...editForm, expected_concepts: e.target.value})} />
                </div>
                <div>
                  <label style={{ display: 'block', color: '#a1a1aa', fontSize: '0.85rem', marginBottom: '6px' }}>Accepted Alternates (comma separated)</label>
                  <textarea className="input" value={editForm.accepted_alternates} onChange={e => setEditForm({...editForm, accepted_alternates: e.target.value})} />
                </div>
                <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end' }}>
                  <button onClick={() => setEditingItem(null)} className="button secondary">Cancel</button>
                  <button onClick={() => handleSaveEdit(item.id)} className="button primary">Save Changes</button>
                </div>
              </div>
            ) : (
              <div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 20 }}>
                  <div>
                    <strong style={{ color: '#cbd5e1' }}>Expected Concepts:</strong>
                    <ul style={{ color: '#94a3b8', margin: '8px 0', paddingLeft: 20 }}>
                      {item.expected_concepts.map((c, i) => <li key={i}>{c}</li>)}
                    </ul>
                  </div>
                  <div>
                    <strong style={{ color: '#cbd5e1' }}>Accepted Alternates:</strong>
                    <ul style={{ color: '#94a3b8', margin: '8px 0', paddingLeft: 20 }}>
                      {item.accepted_alternates.map((c, i) => <li key={i}>{c}</li>)}
                    </ul>
                  </div>
                </div>
                <div style={{ color: '#94a3b8', fontSize: '0.9rem' }}>
                  <strong>Allowed increments:</strong> {item.allowed_increments.join(', ')}
                </div>

                {/* Addendums display */}
                {item.addendums && item.addendums.length > 0 && (
                  <div style={{ marginTop: 16, padding: 12, background: 'rgba(245, 158, 11, 0.1)', border: '1px dashed #f59e0b', borderRadius: 8 }}>
                    <strong style={{ color: '#f59e0b', fontSize: '0.9rem' }}>Version Addendums:</strong>
                    <ul style={{ color: '#fbbf24', margin: '8px 0 0 0', paddingLeft: 20, fontSize: '0.9rem' }}>
                      {item.addendums.map(add => (
                        <li key={add.id}>{add.added_text} <span style={{ color: '#a1a1aa', fontSize: '0.8rem' }}>— by {add.added_by}</span></li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Add Addendum Input (Only if locked) */}
                {rubric.is_locked && (
                  <div style={{ marginTop: 20, display: 'flex', gap: 12 }}>
                    <input 
                      type="text" 
                      className="input" 
                      placeholder="Add an alternate acceptable answer (Addendum)..." 
                      value={addendumText[item.id] || ''}
                      onChange={e => setAddendumText({...addendumText, [item.id]: e.target.value})}
                      disabled={user?.role === 'read_only' || user?.role === 'evaluator'}
                      style={{ flex: 1 }}
                    />
                    <button 
                      onClick={() => handleAddAddendum(item.id)} 
                      disabled={user?.role === 'read_only' || user?.role === 'evaluator'}
                      className="button secondary" 
                      style={{ whiteSpace: 'nowrap', opacity: user?.role === 'read_only' || user?.role === 'evaluator' ? 0.5 : 1, cursor: user?.role === 'read_only' || user?.role === 'evaluator' ? 'not-allowed' : 'pointer' }}
                      title={user?.role === 'read_only' || user?.role === 'evaluator' ? 'Permission denied' : ''}
                    >
                      Add Addendum
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
