import React, { useState, useEffect } from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { Link, useSearchParams } from 'react-router-dom'
import { 
  getDepartments, getCourses, getSections, getTerms, getSubjects, 
  getDashboardAnalytics, exportClassMarks 
} from '../api.js'

export default function AnalyticsDashboard() {
  const [departments, setDepartments] = useState([])
  const [courses, setCourses] = useState([])
  const [sections, setSections] = useState([])
  const [terms, setTerms] = useState([])
  const [subjects, setSubjects] = useState([])
  
  const [filters, setFilters] = useState({ dept: '', course: '', section: '', term: '', subject: '' })
  
  const [searchParams] = useSearchParams()
  const [offeringId, setOfferingId] = useState(searchParams.get('offeringId') || null)
  const [analytics, setAnalytics] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  // Init: load departments
  useEffect(() => {
    getDepartments().then(setDepartments).catch(e => setError(String(e)))
  }, [])

  // Cascade handlers
  const handleDeptChange = (e) => {
    const val = e.target.value
    setFilters({ dept: val, course: '', section: '', term: '', subject: '' })
    setCourses([]); setSections([]); setTerms([]); setSubjects([])
    setOfferingId(null)
    if (val) getCourses(val).then(setCourses).catch(e => setError(String(e)))
  }

  const handleCourseChange = (e) => {
    const val = e.target.value
    setFilters(f => ({ ...f, course: val, section: '', term: '', subject: '' }))
    setSections([]); setTerms([]); setSubjects([])
    setOfferingId(null)
    if (val) getSections(val).then(setSections).catch(e => setError(String(e)))
  }

  const handleSectionChange = (e) => {
    const val = e.target.value
    setFilters(f => ({ ...f, section: val, term: '', subject: '' }))
    setTerms([]); setSubjects([])
    setOfferingId(null)
    if (val) getTerms(val).then(setTerms).catch(e => setError(String(e)))
  }

  const handleTermChange = (e) => {
    const val = e.target.value
    setFilters(f => ({ ...f, term: val, subject: '' }))
    setSubjects([])
    setOfferingId(null)
    if (val && filters.section) {
      getSubjects(filters.section, val).then(setSubjects).catch(e => setError(String(e)))
    }
  }

  const handleSubjectChange = (e) => {
    const val = e.target.value
    setFilters(f => ({ ...f, subject: val }))
    const subj = subjects.find(s => s.id === val)
    if (subj) {
      setOfferingId(subj.class_offering_id)
    } else {
      setOfferingId(null)
    }
  }

  // Load analytics when offering resolved
  useEffect(() => {
    if (!offeringId) {
      setAnalytics(null)
      return
    }
    setLoading(true)
    getDashboardAnalytics(offeringId)
      .then(res => {
        setAnalytics(res)
        setError('')
      })
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false))
  }, [offeringId])

  const handleExport = async () => {
    if (!offeringId) return
    try {
      const blob = await exportClassMarks(offeringId)
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `class_marks_${offeringId}.csv`
      document.body.appendChild(a)
      a.click()
      a.remove()
    } catch (e) {
      setError(String(e))
    }
  }

  return (
    <div className="analytics-dashboard" style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <h2 style={{ fontSize: '1.8rem', color: '#f8fafc', margin: 0 }}>📊 Analytics & Reports</h2>
        {offeringId && (
          <button onClick={handleExport} className="button primary" style={{ background: '#10b981' }}>
            📥 Export CSV
          </button>
        )}
      </div>

      {error && <div className="card flag" style={{ padding: 16, marginBottom: 20 }}>⚠️ {error}</div>}

      {/* Cascading Filter Bar */}
      <div className="card" style={{ padding: '20px', marginBottom: '24px', background: 'rgba(24,24,27,0.85)', border: '1px solid rgba(255,255,255,0.1)' }}>
        <h3 style={{ marginTop: 0, marginBottom: '16px', fontSize: '1.1rem', color: '#cbd5e1' }}>Filter Class Offering</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '16px' }}>
          <select value={filters.dept} onChange={handleDeptChange} style={selectStyle}>
            <option value="">1. Select Department...</option>
            {departments.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>

          <select value={filters.course} onChange={handleCourseChange} disabled={!filters.dept} style={selectStyle}>
            <option value="">2. Select Course...</option>
            {courses.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>

          <select value={filters.section} onChange={handleSectionChange} disabled={!filters.course} style={selectStyle}>
            <option value="">3. Select Section...</option>
            {sections.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>

          <select value={filters.term} onChange={handleTermChange} disabled={!filters.section} style={selectStyle}>
            <option value="">4. Select Term...</option>
            {terms.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>

          <select value={filters.subject} onChange={handleSubjectChange} disabled={!filters.term} style={selectStyle}>
            <option value="">5. Select Subject...</option>
            {subjects.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        </div>
      </div>

      {/* Analytics Content */}
      {loading ? (
        <div className="loader-container" style={{ textAlign: 'center', padding: '60px' }}>
          <div className="spinner"></div>
          <p style={{ marginTop: 16, color: '#94a3b8' }}>Crunching numbers...</p>
        </div>
      ) : analytics ? (
        <div className="analytics-content">
          {/* Overview Cards */}
          <div className="stats-grid" style={{ marginBottom: '24px' }}>
            <div className="stat-card" style={{ background: 'rgba(24, 24, 27, 0.8)', border: '1px solid rgba(255,255,255,0.08)' }}>
              <h4>Class Average</h4>
              <div className="stat-value" style={{ color: '#38bdf8' }}>{analytics.summary.class_average}</div>
            </div>
            <div className="stat-card" style={{ background: 'rgba(24, 24, 27, 0.8)', border: '1px solid rgba(255,255,255,0.08)' }}>
              <h4>Pass Rate</h4>
              <div className="stat-value success">{analytics.summary.pass_rate}%</div>
            </div>
            <div className="stat-card" style={{ background: 'rgba(24, 24, 27, 0.8)', border: '1px solid rgba(255,255,255,0.08)' }}>
              <h4>High / Low</h4>
              <div className="stat-value" style={{ color: '#f8fafc' }}>{analytics.summary.highest_score} / {analytics.summary.lowest_score}</div>
            </div>
            <div className="stat-card" style={{ background: 'rgba(24, 24, 27, 0.8)', border: '1px solid rgba(255,255,255,0.08)' }}>
              <h4>Human Trust Metric</h4>
              <div className="stat-value warning">{100 - analytics.summary.override_rate}%</div>
              <div className="stat-trend trend-neutral">{analytics.summary.override_rate}% Override Rate</div>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '24px', marginBottom: '24px' }}>
            {/* Chart */}
            <div className="card" style={{ padding: '24px', background: 'rgba(24,24,27,0.85)', border: '1px solid rgba(255,255,255,0.1)' }}>
              <h3 style={{ marginTop: 0, marginBottom: '20px', fontSize: '1.2rem' }}>Per-Question Average</h3>
              <div style={{ height: '300px', width: '100%' }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={analytics.question_averages} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
                    <XAxis dataKey="question" stroke="#94a3b8" fontSize={12} tickMargin={10} />
                    <YAxis stroke="#94a3b8" fontSize={12} />
                    <Tooltip 
                      cursor={{fill: 'rgba(255,255,255,0.05)'}}
                      contentStyle={{ background: '#1e1e24', border: '1px solid #334155', borderRadius: '8px' }}
                    />
                    <Bar dataKey="average" fill="#6366f1" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Status Breakdown & Flags */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
              <div className="card" style={{ padding: '20px', background: 'rgba(24,24,27,0.85)', border: '1px solid rgba(255,255,255,0.1)' }}>
                <h3 style={{ marginTop: 0, marginBottom: '16px', fontSize: '1.1rem' }}>Processing Status</h3>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', color: '#94a3b8' }}>
                  <span>Finalized:</span> <strong style={{ color: '#10b981' }}>{analytics.status_counts.final || 0}</strong>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', color: '#94a3b8' }}>
                  <span>Provisional:</span> <strong style={{ color: '#f59e0b' }}>{analytics.status_counts.provisional || 0}</strong>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', color: '#94a3b8' }}>
                  <span>Pending / Graded:</span> <strong style={{ color: '#cbd5e1' }}>{(analytics.status_counts.pending || 0) + (analytics.status_counts.graded || 0)}</strong>
                </div>
              </div>

              <div className="card" style={{ padding: '20px', background: 'rgba(24,24,27,0.85)', border: '1px solid rgba(255,255,255,0.1)' }}>
                <h3 style={{ marginTop: 0, marginBottom: '16px', fontSize: '1.1rem' }}>Open Review Flags</h3>
                {Object.keys(analytics.open_flags_by_type).length === 0 ? (
                  <div style={{ color: '#10b981', fontSize: '0.9rem' }}>✓ All clear. No open flags.</div>
                ) : (
                  <>
                    {Object.entries(analytics.open_flags_by_type).map(([type, count]) => (
                      <div key={type} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', fontSize: '0.9rem' }}>
                        <span style={{ color: '#f87171' }}>{type}</span>
                        <strong>{count}</strong>
                      </div>
                    ))}
                    <div style={{ marginTop: '16px' }}>
                      <Link to={`/dashboard/queue/${offeringId}`} className="button secondary" style={{ width: '100%', textAlign: 'center' }}>
                        Go to Priority Queue &rarr;
                      </Link>
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="card" style={{ padding: '60px 20px', textAlign: 'center', background: 'rgba(24,24,27,0.5)', border: '1px dashed rgba(255,255,255,0.1)' }}>
          <p style={{ color: '#64748b', margin: 0, fontSize: '1.1rem' }}>Use the filters above to select a specific class offering.</p>
        </div>
      )}
    </div>
  )
}

const selectStyle = {
  padding: '10px 14px',
  borderRadius: '8px',
  background: '#18181b',
  border: '1px solid #334155',
  color: '#f8fafc',
  fontSize: '0.95rem',
  outline: 'none',
  width: '100%',
  cursor: 'pointer'
}
