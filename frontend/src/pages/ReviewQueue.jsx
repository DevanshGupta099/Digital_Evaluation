import React, { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { getReviewQueue } from '../api.js'

export default function ReviewQueue() {
  const { offeringId } = useParams()
  const [flags, setFlags] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!offeringId) return
    setLoading(true)
    getReviewQueue(offeringId)
      .then(res => {
        setFlags(res.flags || [])
        setError('')
      })
      .catch(err => setError(String(err)))
      .finally(() => setLoading(false))
  }, [offeringId])

  if (!offeringId) return <main><div className="card" style={{ padding: 24, margin: 20 }}>Please select an offering first.</div></main>

  const getTierColor = (tier) => {
    if (tier === 1) return '#ef4444' // red
    if (tier === 2) return '#f59e0b' // orange
    return '#3b82f6' // blue
  }

  const getTierLabel = (tier) => {
    if (tier === 1) return 'Tier 1: High Priority'
    if (tier === 2) return 'Tier 2: Verification Needed'
    return 'Tier 3: Low Confidence'
  }

  return (
    <div className="review-queue-container" style={{ padding: '20px', maxWidth: '1200px', margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <h2 style={{ fontSize: '1.8rem', color: '#f8fafc', margin: 0 }}>📋 Reconciliation & Review Queue</h2>
        <div style={{ background: '#1e1e24', padding: '8px 16px', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.1)' }}>
          <span style={{ color: '#94a3b8', fontSize: '0.9rem', marginRight: '8px' }}>Open Flags:</span>
          <span style={{ color: '#f8fafc', fontSize: '1.2rem', fontWeight: 700 }}>{flags.length}</span>
        </div>
      </div>

      {error && <div className="card flag" style={{ padding: 16, marginBottom: 20 }}>⚠️ {error}</div>}

      {loading ? (
        <div className="loader-container" style={{ textAlign: 'center', padding: '80px 20px' }}>
          <div className="spinner"></div>
          <p style={{ marginTop: 16, color: '#94a3b8' }}>Loading priority queue...</p>
        </div>
      ) : flags.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: '80px 20px', background: 'rgba(16, 185, 129, 0.05)', border: '1px solid rgba(16, 185, 129, 0.2)' }}>
          <h3 style={{ color: '#10b981', fontSize: '1.5rem', marginBottom: '8px' }}>🎉 All Clear!</h3>
          <p style={{ color: '#94a3b8' }}>There are no open flags requiring human intervention for this class offering.</p>
        </div>
      ) : (
        <div className="flags-list" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {flags.map(flag => (
            <div key={flag.id} style={{ 
              background: '#27272a', 
              borderRadius: '16px', 
              border: '1px solid rgba(255,255,255,0.08)', 
              borderLeft: `4px solid ${getTierColor(flag.priority_tier)}`,
              padding: '20px',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              boxShadow: '0 4px 15px rgba(0,0,0,0.2)'
            }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
                  <span style={{ 
                    background: `${getTierColor(flag.priority_tier)}20`, 
                    color: getTierColor(flag.priority_tier),
                    padding: '4px 10px',
                    borderRadius: '6px',
                    fontSize: '0.75rem',
                    fontWeight: 700,
                    textTransform: 'uppercase'
                  }}>
                    {getTierLabel(flag.priority_tier)}
                  </span>
                  <span style={{ color: '#cbd5e1', fontSize: '0.9rem', fontWeight: 600 }}>{flag.flag_type.toUpperCase()}</span>
                </div>
                
                <p style={{ color: '#f8fafc', fontSize: '1.05rem', margin: '0 0 8px 0' }}>
                  {flag.notes || "System flagged for review"}
                </p>
                
                <div style={{ display: 'flex', gap: '16px', color: '#94a3b8', fontSize: '0.85rem' }}>
                  <span><strong style={{ color: '#cbd5e1' }}>Script ID:</strong> {flag.answer_script_id.substring(0,8)}</span>
                  {flag.question_number && <span><strong style={{ color: '#cbd5e1' }}>Question:</strong> {flag.question_number}</span>}
                  {flag.subpart_id && <span><strong style={{ color: '#cbd5e1' }}>Subpart:</strong> {flag.subpart_id}</span>}
                </div>
              </div>
              
              <Link 
                to={`/dashboard/review/${flag.answer_script_id}?question=${flag.question_number || ''}`}
                className="button primary"
                style={{ 
                  background: '#6366f1', 
                  textDecoration: 'none', 
                  padding: '10px 20px', 
                  fontWeight: 600,
                  whiteSpace: 'nowrap'
                }}
              >
                Review & Resolve &rarr;
              </Link>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
