import React, { useEffect, useState, useRef } from 'react'
import { createPortal } from 'react-dom'
import { Link, useSearchParams, Navigate } from 'react-router-dom'
import {
  getOfferingStudents,
  getOfferingRubric,
  uploadQuestionPaper,
  uploadAnswerKey,
  generateRubric,
  uploadStudentScript,
  addStudentToOffering,
  deleteStudent,
  getAnalytics,
  triggerAnalysis,
  getUsageMetrics,
  publishResults
} from '../api.js'
import HierarchyBar from '../components/HierarchyBar.jsx'
import BulkRosterModal from '../components/BulkRosterModal.jsx'
import BulkScriptModal from '../components/BulkScriptModal.jsx'
import { useAuth } from '../context/AuthContext.jsx'

export default function Dashboard() {
  const { user } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()
  const selectedOfferingId = searchParams.get('offeringId') || ''
  
  const [offering, setOffering] = useState(null)
  const [students, setStudents] = useState([])
  const [rubric, setRubric] = useState({ status: 'NONE', rubric_data: [] })
  const [analytics, setAnalytics] = useState({ summary: { class_average_percent: 0, pass_rate_percent: 0, total_flagged_scripts: 0, human_override_rate_percent: 0 } })
  const [usage, setUsage] = useState({ estimated_cost_usd: 0 })
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [sortConfig, setSortConfig] = useState({ key: 'enrollment', direction: 'asc' })
  const [error, setError] = useState('')
  const [statusMessage, setStatusMessage] = useState('')
  const [selectedScripts, setSelectedScripts] = useState([])

  // Student creation state
  const [showAddStudentModal, setShowAddStudentModal] = useState(false)
  const [showBulkRosterModal, setShowBulkRosterModal] = useState(false)
  const [showBulkScriptModal, setShowBulkScriptModal] = useState(false)
  const [newStudent, setNewStudent] = useState({ enrollment_number: '', full_name: '', email: '' })

  // Rubric upload state
  const qpInputRef = useRef(null)
  const akInputRef = useRef(null)

  const loadOfferingData = async (offId) => {
    if (!offId) return
    setLoading(true)
    try {
      const [stuData, rubData, anaData, usageData] = await Promise.all([
        getOfferingStudents(offId),
        getOfferingRubric(offId),
        getAnalytics(offId),
        getUsageMetrics(offId)
      ])
      setStudents(stuData || [])
      setRubric(rubData || { status: 'NONE', rubric_data: [] })
      setAnalytics(anaData || { summary: {} })
      setUsage(usageData || { estimated_cost_usd: 0 })
      setError('')
    } catch (err) {
      console.error("Error loading dashboard details:", err)
      setError("Failed to fetch offering details. Ensure your local server is running.")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (selectedOfferingId) {
      loadOfferingData(selectedOfferingId)
      
      const es = new EventSource(`/api/stream/events?offering_id=${selectedOfferingId}`);
      
      es.addEventListener('status_update', (e) => {
        const data = JSON.parse(e.data);
        if (data.script_id && data.status) {
          setStudents(prev => prev.map(s => {
            if (s.script && s.script.id === data.script_id) {
              return { ...s, script: { ...s.script, status: data.status } };
            }
            return s;
          }));
        }
      });

      return () => {
        es.close();
      }
    }
  }, [selectedOfferingId])

  const handleOfferingChange = (offId, offObj) => {
    setSearchParams(offId ? { offeringId: offId } : {})
    if (offId) {
      localStorage.setItem('lastOfferingId', offId)
    } else {
      localStorage.removeItem('lastOfferingId')
    }
    setOffering(offObj)
  }

  const handleUploadQP = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    try {
      setStatusMessage("Uploading Question Paper...")
      await uploadQuestionPaper(selectedOfferingId, file)
      setStatusMessage("Question Paper uploaded!")
      await loadOfferingData(selectedOfferingId)
    } catch(err) {
      setError(String(err))
    }
  }

  const handleUploadAK = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    try {
      setStatusMessage("Uploading Answer Key...")
      await uploadAnswerKey(selectedOfferingId, file)
      setStatusMessage("Answer Key uploaded!")
      await loadOfferingData(selectedOfferingId)
    } catch(err) {
      setError(String(err))
    }
  }

  const handleGenerateRubric = async () => {
    try {
      setStatusMessage("Generating draft rubric via Multimodal AI...")
      await generateRubric(selectedOfferingId)
      setStatusMessage("Draft rubric generated successfully!")
      await loadOfferingData(selectedOfferingId)
    } catch(err) {
      setError(String(err))
    }
  }

  const handleStudentScriptUpload = async (studentId, file) => {
    if (!file) return
    try {
      setStatusMessage(`Uploading scan for student...`)
      await uploadStudentScript(selectedOfferingId, studentId, file)
      setStatusMessage("Script uploaded! Select it in the roster to trigger analysis.")
      await loadOfferingData(selectedOfferingId)
    } catch (err) {
      setError(String(err))
    } finally {
      setTimeout(() => setStatusMessage(''), 4000)
    }
  }

  const handleTriggerAnalysis = async (scriptIds) => {
    if (scriptIds.length === 0) return
    try {
      setStatusMessage(`Triggering evaluation pipeline for ${scriptIds.length} script(s)...`)
      await triggerAnalysis(selectedOfferingId, scriptIds)
      setStatusMessage(`Evaluation pipeline queued for ${scriptIds.length} script(s)!`)
      setSelectedScripts([])
      await loadOfferingData(selectedOfferingId)
    } catch(err) {
      setError(String(err))
    } finally {
      setTimeout(() => setStatusMessage(''), 4000)
    }
  }

  const handleAddStudent = async (e) => {
    e.preventDefault()
    if (!newStudent.enrollment_number || !newStudent.full_name) return
    try {
      await addStudentToOffering(selectedOfferingId, newStudent)
      setShowAddStudentModal(false)
      setNewStudent({ enrollment_number: '', full_name: '', email: '' })
      await loadOfferingData(selectedOfferingId)
    } catch (err) {
      setError(String(err))
    }
  }

  const handleDeleteStudent = async (studentId, name) => {
    if (!confirm(`Delete student ${name}? Use this option to clean wrong entries.`)) return
    try {
      await deleteStudent(studentId)
      await loadOfferingData(selectedOfferingId)
    } catch (err) {
      setError(String(err))
    }
  }

  const handlePublishResults = async () => {
    if (!confirm("Are you sure you want to publish results? This will make them visible to students.")) return
    try {
      setStatusMessage("Publishing results...")
      await publishResults(selectedOfferingId, user.name, user.role)
      setStatusMessage("Results published successfully!")
      await loadOfferingData(selectedOfferingId)
    } catch (err) {
      setError(String(err))
    } finally {
      setTimeout(() => setStatusMessage(''), 4000)
    }
  }

  const handleSort = (key) => {
    let direction = 'asc';
    if (sortConfig.key === key && sortConfig.direction === 'asc') {
      direction = 'desc';
    }
    setSortConfig({ key, direction });
  }

  const getSortedStudents = (studentsList) => {
    return [...studentsList].sort((a, b) => {
      const aScript = a.script || {};
      const bScript = b.script || {};

      let valA, valB;
      
      switch (sortConfig.key) {
        case 'enrollment':
          valA = a.enrollment_number || '';
          valB = b.enrollment_number || '';
          break;
        case 'name':
          valA = a.full_name || '';
          valB = b.full_name || '';
          break;
        case 'status':
          valA = aScript.status || '';
          valB = bScript.status || '';
          break;
        case 'score':
          valA = aScript.marks_awarded || 0;
          valB = bScript.marks_awarded || 0;
          break;
        case 'flags':
          valA = aScript.flags_count || 0;
          valB = bScript.flags_count || 0;
          break;
        default:
          valA = a.full_name || '';
          valB = b.full_name || '';
      }

      if (typeof valA === 'string' && typeof valB === 'string') {
        const cmp = valA.localeCompare(valB, undefined, { numeric: true, sensitivity: 'base' });
        return sortConfig.direction === 'asc' ? cmp : -cmp;
      }

      if (valA < valB) {
        return sortConfig.direction === 'asc' ? -1 : 1;
      }
      if (valA > valB) {
        return sortConfig.direction === 'asc' ? 1 : -1;
      }
      return 0;
    });
  }

  const filteredStudents = getSortedStudents(students.filter(s => {
    const name = s.full_name || ''
    const enroll = s.enrollment_number || ''
    const query = searchQuery ? searchQuery.toLowerCase() : ''
    return name.toLowerCase().includes(query) || enroll.toLowerCase().includes(query)
  }))

  const uploadedScripts = filteredStudents
    .map(s => s.script)
    .filter(sc => sc && ['uploaded', 'queued', 'processing'].includes(sc.status))

  const handleToggleSelectAll = () => {
    if (selectedScripts.length === uploadedScripts.length) {
      setSelectedScripts([])
    } else {
      setSelectedScripts(uploadedScripts.map(sc => sc.id))
    }
  }

  const handleToggleSelect = (scriptId) => {
    setSelectedScripts(prev => 
      prev.includes(scriptId) ? prev.filter(id => id !== scriptId) : [...prev, scriptId]
    )
  }

  if (user?.role === 'student') {
    if (selectedOfferingId) {
      return <Navigate to={`/dashboard/student-view/${selectedOfferingId}`} replace />
    }
    return (
      <>
        <HierarchyBar selectedOfferingId={selectedOfferingId} onOfferingChange={handleOfferingChange} />
        <div className="card" style={{ padding: '40px', textAlign: 'center', margin: '40px auto', maxWidth: '600px' }}>
          <h3>Welcome, {user.name}</h3>
          <p style={{ color: '#94a3b8' }}>Please select a class offering from the hierarchy bar above to view your results.</p>
        </div>
      </>
    )
  }

  return (
    <>
      <HierarchyBar selectedOfferingId={selectedOfferingId} onOfferingChange={handleOfferingChange} />

      {error && <div className="flag" style={{ marginBottom: 20 }}>⚠️ {error}</div>}
      {statusMessage && (
        <div className="status-banner" style={{ background: 'rgba(16, 185, 129, 0.2)', color: '#10b981', border: '1px solid #10b981', padding: '12px 20px', borderRadius: '12px', marginBottom: '20px', fontWeight: 600 }}>
          🚀 {statusMessage}
        </div>
      )}

      {/* Analytics Overview Tiles */}
      {selectedOfferingId ? (
        <>
          <div className="stats-grid" style={{ marginBottom: '28px' }}>
        {loading ? (
          <>
            <div className="skeleton-card" style={{ height: '120px', borderRadius: '12px' }}></div>
            <div className="skeleton-card" style={{ height: '120px', borderRadius: '12px' }}></div>
            <div className="skeleton-card" style={{ height: '120px', borderRadius: '12px' }}></div>
            <div className="skeleton-card" style={{ height: '120px', borderRadius: '12px' }}></div>
            <div className="skeleton-card" style={{ height: '120px', borderRadius: '12px' }}></div>
            <div className="skeleton-card" style={{ height: '120px', borderRadius: '12px' }}></div>
          </>
        ) : (
          <>
            <div className="stat-card">
              <h4>Enrolled Students</h4>
              <div className="stat-value data-mono">{students.length}</div>
              <div className="stat-trend trend-up">Active Roster</div>
            </div>
            <div className="stat-card">
              <h4>Class Average</h4>
              <div className="stat-value data-mono" style={{ color: 'var(--primary)' }}>{analytics?.summary?.class_average_percent || 0}%</div>
              <div className="stat-trend trend-up">Rubric Weighted</div>
            </div>
            <div className="stat-card">
              <h4>Pass Rate</h4>
              <div className="stat-value success data-mono">{analytics?.summary?.pass_rate_percent || 0}%</div>
              <div className="stat-trend trend-up">Threshold: ≥ 40%</div>
            </div>
            <Link to={selectedOfferingId ? `/dashboard/queue/${selectedOfferingId}` : '#'} style={{ textDecoration: 'none', color: 'inherit' }}>
              <div className="stat-card" style={{ cursor: 'pointer', transition: 'all 0.2s', height: '100%' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <h4>Flagged Queue / Variance</h4>
                  <span style={{ fontSize: '0.8rem', color: '#6366f1', fontWeight: 600 }}>Review &rarr;</span>
                </div>
                <div className="stat-value warning data-mono">{analytics?.summary?.total_flagged_scripts || 0}</div>
                <div className="stat-trend trend-neutral">Needs Faculty Check</div>
              </div>
            </Link>
            <div className="stat-card">
              <h4>API Compute Cost</h4>
              <div className="stat-value data-mono" style={{ color: 'var(--success)' }}>${(usage?.estimated_cost_usd || 0).toFixed(4)}</div>
              <div className="stat-trend trend-up">Prompt Caching Enabled</div>
            </div>
            <Link to={selectedOfferingId ? `/dashboard/audit/${selectedOfferingId}` : '#'} style={{ textDecoration: 'none', color: 'inherit' }}>
              <div className="stat-card" style={{ cursor: 'pointer', transition: 'all 0.2s', height: '100%' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <h4>Audit Trail</h4>
                  <span style={{ fontSize: '0.8rem', color: '#6366f1', fontWeight: 600 }}>View &rarr;</span>
                </div>
                <div className="stat-value" style={{ color: '#a1a1aa' }}>Logs</div>
                <div className="stat-trend trend-neutral">Immutable Records</div>
              </div>
            </Link>
          </>
        )}
      </div>

      {/* Shared Rubric & Question Paper Card */}
      <div className="card" style={{ marginBottom: '32px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '15px' }}>
          <div style={{ flex: 1, minWidth: '300px' }}>
            <span style={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', color: '#8b5cf6', letterSpacing: '1px' }}>
              Subject Master Rubric & Question Paper
            </span>
            <h3 className="heading-serif" style={{ fontSize: '1.35rem', margin: '4px 0 0 0', display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span>📑 Evaluation Schema: {offering ? offering?.subject?.name || 'Shared Subject' : 'Shared Subject'}</span>
              <span className={`status-pill ${rubric?.is_locked ? 'success' : rubric?.status?.includes('Draft') ? 'warning' : ''}`}>
                {rubric?.status || 'Missing Materials'}
              </span>
            </h3>
            <p style={{ color: '#94a3b8', margin: '8px 0 0 0', fontSize: '0.9rem', lineHeight: 1.5 }}>
              {rubric.status === 'Missing Materials' && "Upload the Question Paper and Answer Key to generate evaluation criteria."}
              {rubric.status === 'Ready to Generate' && "Materials uploaded! Click Generate Rubric to extract the criteria using AI."}
              {rubric.status?.includes('Draft') && "Draft rubric generated! Click Review & Approve to lock in the scoring scheme."}
              {rubric.is_locked && "🔒 Rubric is LOCKED. Strict scoring increments are active as the absolute single source of truth."}
            </p>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', minWidth: '200px' }}>
            {(!rubric.has_qp || !rubric.has_ak) && (
              <div style={{ display: 'flex', gap: '8px', flexDirection: 'column' }}>
                {!rubric.has_qp && (
                  <label className="button primary" style={{ cursor: user?.role === 'read_only' || user?.role === 'evaluator' ? 'not-allowed' : 'pointer', textAlign: 'center', opacity: user?.role === 'read_only' || user?.role === 'evaluator' ? 0.5 : 1 }}>
                    📤 Upload Question Paper
                    <input type="file" ref={qpInputRef} disabled={user?.role === 'read_only' || user?.role === 'evaluator'} style={{ display: 'none' }} accept="application/pdf" onChange={handleUploadQP} />
                  </label>
                )}
                {!rubric.has_ak && (
                  <label className="button secondary" style={{ cursor: user?.role === 'read_only' || user?.role === 'evaluator' ? 'not-allowed' : 'pointer', textAlign: 'center', background: '#3f3f46', opacity: user?.role === 'read_only' || user?.role === 'evaluator' ? 0.5 : 1 }}>
                    🔑 Upload Answer Key
                    <input type="file" ref={akInputRef} disabled={user?.role === 'read_only' || user?.role === 'evaluator'} style={{ display: 'none' }} accept="application/pdf" onChange={handleUploadAK} />
                  </label>
                )}
              </div>
            )}

            {rubric.status === 'Ready to Generate' && (
              <button onClick={handleGenerateRubric} disabled={user?.role === 'read_only' || user?.role === 'evaluator'} className="button primary" style={{ background: '#6366f1', opacity: user?.role === 'read_only' || user?.role === 'evaluator' ? 0.5 : 1, cursor: user?.role === 'read_only' || user?.role === 'evaluator' ? 'not-allowed' : 'pointer' }}>
                ✨ Generate Rubric
              </button>
            )}

            {(rubric.status?.includes('Draft') || rubric.is_locked) && (
              <Link to={`/dashboard/rubrics?offeringId=${selectedOfferingId}`} className="button primary" style={{ textAlign: 'center', background: rubric.is_locked ? '#10b981' : '#f59e0b', color: '#18181b', fontWeight: 700 }}>
                {rubric.is_locked ? 'View Locked Rubric & Addendums \u2192' : 'Review & Approve Draft \u2192'}
              </Link>
            )}
          </div>
        </div>
      </div>

      {/* Student Evaluation Roster Table */}
      <div className="card premium-table-card" style={{ padding: 0, overflow: 'hidden' }}>
        <div className="card-header" style={{ padding: '24px', borderBottom: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '15px' }}>
          <div>
            <h2 className="heading-serif" style={{ fontSize: '1.5rem' }}>🎓 Enrolled Student Roster & Script Uploads</h2>
            <p style={{ margin: '4px 0 0 0', fontSize: '0.88rem', color: '#94a3b8' }}>
              Upload individual marksheet scans next to each student to start automated AI grading against the shared rubric.
            </p>
          </div>
          
          <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
            {/* Publish Results Button */}
            {(user?.role === 'admin' || user?.role === 'exam_coordinator') && (
              <button
                onClick={handlePublishResults}
                disabled={!students.length || students.some(s => !s.script || s.script.status !== 'final' && s.script.status !== 'FINAL') || analytics.results_published}
                className="button"
                style={{
                  background: analytics.results_published ? '#10b981' : '#f59e0b',
                  color: '#fff',
                  opacity: (!students.length || students.some(s => !s.script || s.script.status !== 'final' && s.script.status !== 'FINAL') && !analytics.results_published) ? 0.5 : 1,
                  cursor: (!students.length || students.some(s => !s.script || s.script.status !== 'final' && s.script.status !== 'FINAL') && !analytics.results_published) ? 'not-allowed' : 'pointer'
                }}
                title={analytics.results_published ? "Results already published" : "All scripts must be FINAL to publish"}
              >
                {analytics.results_published ? '✅ Results Published' : '📢 Publish Results'}
              </button>
            )}
            
            <input
              type="text"
              placeholder="🔍 Filter by name or roll number..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              style={{ padding: '8px 16px', borderRadius: '10px', background: '#18181b', border: '1px solid rgba(255,255,255,0.15)', color: '#fff', outline: 'none', width: '250px' }}
            />
            <button onClick={() => setShowBulkRosterModal(true)} className="button secondary" style={{ whiteSpace: 'nowrap' }}>
              Import Roster (CSV)
            </button>
            <button onClick={() => setShowAddStudentModal(true)} className="button primary" style={{ background: '#3b82f6', whiteSpace: 'nowrap' }}>
              + Add Student
            </button>
          </div>
        </div>

        <div style={{ padding: '16px 24px', background: 'rgba(255,255,255,0.02)', borderBottom: '1px solid rgba(255,255,255,0.08)', display: 'flex', gap: '12px', alignItems: 'center', flexWrap: 'wrap' }}>
          <button
            onClick={() => handleTriggerAnalysis(selectedScripts)}
            disabled={!rubric.is_locked || selectedScripts.length === 0 || user?.role === 'read_only' || user?.role === 'evaluator'}
            className="button primary"
            style={{ opacity: (!rubric.is_locked || selectedScripts.length === 0 || user?.role === 'read_only' || user?.role === 'evaluator') ? 0.5 : 1, cursor: (!rubric.is_locked || selectedScripts.length === 0 || user?.role === 'read_only' || user?.role === 'evaluator') ? 'not-allowed' : 'pointer' }}
            title={!rubric.is_locked ? 'Lock the rubric before analyzing' : user?.role === 'read_only' || user?.role === 'evaluator' ? 'Permission denied' : ''}
          >
            ⚡ Analyze Selected ({selectedScripts.length})
          </button>
          <button
            onClick={() => handleTriggerAnalysis(uploadedScripts.map(sc => sc.id))}
            disabled={!rubric.is_locked || uploadedScripts.length === 0 || user?.role === 'read_only' || user?.role === 'evaluator'}
            className="button secondary"
            style={{ opacity: (!rubric.is_locked || uploadedScripts.length === 0 || user?.role === 'read_only' || user?.role === 'evaluator') ? 0.5 : 1, cursor: (!rubric.is_locked || uploadedScripts.length === 0 || user?.role === 'read_only' || user?.role === 'evaluator') ? 'not-allowed' : 'pointer' }}
            title={!rubric.is_locked ? 'Lock the rubric before analyzing' : user?.role === 'read_only' || user?.role === 'evaluator' ? 'Permission denied' : ''}
          >
            🚀 Analyze All Uploaded ({uploadedScripts.length})
          </button>
          <button
            onClick={() => setShowBulkScriptModal(true)}
            disabled={user?.role === 'read_only' || user?.role === 'evaluator'}
            className="button secondary"
            style={{ background: '#8b5cf6', color: 'white', border: 'none', opacity: (user?.role === 'read_only' || user?.role === 'evaluator') ? 0.5 : 1, cursor: (user?.role === 'read_only' || user?.role === 'evaluator') ? 'not-allowed' : 'pointer' }}
          >
            📥 Bulk Upload Scripts
          </button>
          
          <div style={{ flex: 1 }}></div>

          <a href={`/api/analytics/export/pdf/${selectedOfferingId}`} target="_blank" rel="noopener noreferrer" className="button secondary" style={{ background: 'transparent', borderColor: '#3b82f6', color: '#3b82f6' }}>
            📄 PDF Gradesheet
          </a>
          <a href={`/api/analytics/export/csv/${selectedOfferingId}`} target="_blank" rel="noopener noreferrer" className="button secondary" style={{ background: 'transparent', borderColor: '#10b981', color: '#10b981' }}>
            📊 LMS Export (CSV)
          </a>

          {!rubric.is_locked && (
            <span style={{ fontSize: '0.85rem', color: '#f59e0b', fontWeight: 600, width: '100%' }}>⚠️ Rubric must be LOCKED before analysis.</span>
          )}
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table className="premium-table">
            <thead>
              <tr>
                <th style={{ width: '40px' }}>
                  <input
                    type="checkbox"
                    checked={uploadedScripts.length > 0 && selectedScripts.length === uploadedScripts.length}
                    onChange={handleToggleSelectAll}
                    disabled={!rubric.is_locked || uploadedScripts.length === 0}
                  />
                </th>
                <th onClick={() => handleSort('enrollment')} style={{ cursor: 'pointer' }}>
                  Enrollment ID {sortConfig.key === 'enrollment' ? (sortConfig.direction === 'asc' ? '↑' : '↓') : ''}
                </th>
                <th onClick={() => handleSort('name')} style={{ cursor: 'pointer' }}>
                  Student Name {sortConfig.key === 'name' ? (sortConfig.direction === 'asc' ? '↑' : '↓') : ''}
                </th>
                <th>Marksheet / Script File</th>
                <th onClick={() => handleSort('status')} style={{ cursor: 'pointer' }}>
                  Evaluation Status {sortConfig.key === 'status' ? (sortConfig.direction === 'asc' ? '↑' : '↓') : ''}
                </th>
                <th onClick={() => handleSort('score')} style={{ cursor: 'pointer' }}>
                  Score Awrd. {sortConfig.key === 'score' ? (sortConfig.direction === 'asc' ? '↑' : '↓') : ''}
                </th>
                <th onClick={() => handleSort('flags')} style={{ cursor: 'pointer' }}>
                  Flags & Variance {sortConfig.key === 'flags' ? (sortConfig.direction === 'asc' ? '↑' : '↓') : ''}
                </th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                Array(5).fill(0).map((_, i) => (
                  <tr key={`skel-${i}`}>
                    <td><div className="skeleton-card" style={{ width: '20px', height: '20px' }}></div></td>
                    <td><div className="skeleton-card" style={{ width: '80px', height: '20px' }}></div></td>
                    <td><div className="skeleton-card" style={{ width: '150px', height: '20px' }}></div></td>
                    <td><div className="skeleton-card" style={{ width: '120px', height: '20px' }}></div></td>
                    <td><div className="skeleton-card" style={{ width: '100px', height: '20px' }}></div></td>
                    <td><div className="skeleton-card" style={{ width: '50px', height: '20px' }}></div></td>
                    <td><div className="skeleton-card" style={{ width: '80px', height: '20px' }}></div></td>
                    <td><div className="skeleton-card" style={{ width: '60px', height: '20px' }}></div></td>
                  </tr>
                ))
              ) : filteredStudents.length === 0 ? (
                <tr><td colSpan="8" className="empty-state"><p>No students yet — import a roster or add one.</p></td></tr>
              ) : (
                filteredStudents.map((s) => {
                  const sc = s.script
                  const hasScript = Boolean(sc)
                  const isSelectable = hasScript && rubric.is_locked && ['uploaded', 'queued', 'processing'].includes(sc.status)
                  return (
                    <tr key={s.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)', background: selectedScripts.includes(sc?.id) ? 'rgba(56, 189, 248, 0.05)' : 'transparent' }}>
                      <td>
                        <input
                          type="checkbox"
                          disabled={!isSelectable}
                          checked={hasScript && selectedScripts.includes(sc.id)}
                          onChange={() => handleToggleSelect(sc.id)}
                        />
                      </td>
                      <td><code className="data-mono" style={{ background: '#27272a', padding: '4px 8px', borderRadius: '6px', color: '#38bdf8', fontWeight: 600 }}>{s.enrollment_number}</code></td>
                      <td>
                        <div className="student-cell" style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                          <div className="student-avatar" style={{ background: 'linear-gradient(135deg, #6366f1, #a855f7)', width: '36px', height: '36px', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, color: '#fff' }}>
                            {(s.full_name || '?').charAt(0).toUpperCase()}
                          </div>
                          <div>
                            <div className="heading-serif" style={{ fontWeight: 700, color: '#f8fafc' }}>{s.full_name}</div>
                            {s.email && <div style={{ fontSize: '0.78rem', color: '#64748b' }}>{s.email}</div>}
                          </div>
                        </div>
                      </td>
                      <td style={{ color: '#cbd5e1' }}>
                        {hasScript ? (
                          <span style={{ fontSize: '0.88rem' }}>📄 {sc.filename}</span>
                        ) : (
                          <label className="button secondary small" style={{ background: 'transparent', border: '1px dashed #3b82f6', color: '#3b82f6', cursor: user?.role === 'read_only' || user?.role === 'evaluator' ? 'not-allowed' : 'pointer', display: 'inline-flex', alignItems: 'center', gap: '4px', padding: '4px 8px', opacity: user?.role === 'read_only' || user?.role === 'evaluator' ? 0.5 : 1 }}>
                            <span>📤 Upload Marksheet</span>
                            <input
                              type="file"
                              accept=".pdf,.png,.jpg,.jpeg"
                              style={{ display: 'none' }}
                              disabled={user?.role === 'read_only' || user?.role === 'evaluator'}
                              onChange={(e) => handleStudentScriptUpload(s.id, e.target.files[0])}
                            />
                          </label>
                        )}
                      </td>
                      <td>
                        {hasScript ? (
                          <span className={`status-pill ${sc.status === 'FINAL' || sc.status === 'finalized' || sc.status === 'annotated' ? 'success' : sc.status === 'PROVISIONAL' || sc.status === 'in_review' ? 'warning' : 'processing'}`} style={{ textTransform: 'uppercase', fontSize: '0.72rem' }}>
                            {sc.status === 'in_review' ? 'NEEDS REVIEW' : sc.status}
                          </span>
                        ) : (
                          <span className="status-pill" style={{ background: 'rgba(100, 116, 139, 0.2)', color: '#94a3b8' }}>PENDING UPLOAD</span>
                        )}
                      </td>
                      <td>
                        {hasScript && sc.max_marks > 0 ? (
                          <span className="data-mono" style={{ fontWeight: 700, color: '#38bdf8', fontSize: '0.95rem' }}>
                            {sc.marks_awarded} <span style={{ fontSize: '0.78rem', color: '#64748b' }}>/ {sc.max_marks}</span>
                          </span>
                        ) : (
                          <span style={{ color: '#64748b' }}>&mdash;</span>
                        )}
                      </td>
                      <td>
                        {hasScript && sc.flags_count > 0 ? (
                          <span style={{ background: 'rgba(239, 68, 68, 0.2)', color: '#f87171', padding: '4px 8px', borderRadius: '6px', fontSize: '0.78rem', fontWeight: 600 }}>
                            ⚠️ {sc.flags_count} Flag{sc.flags_count > 1 ? 's' : ''} (Review)
                          </span>
                        ) : hasScript ? (
                          <span style={{ color: '#10b981', fontSize: '0.85rem', fontWeight: 600 }}>✅ Verified</span>
                        ) : (
                          <span style={{ color: '#64748b' }}>&mdash;</span>
                        )}
                      </td>
                      <td>
                        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                          {hasScript && (
                            <Link to={`/dashboard/review/${sc.id}`} className="button primary small" style={{ background: '#6366f1', whiteSpace: 'nowrap' }}>
                              Review & Annotations &rarr;
                            </Link>
                          )}
                          
                          <button
                            onClick={() => handleDeleteStudent(s.id, s.full_name)}
                            title="Remove student / clean wrong entry"
                            style={{ background: 'transparent', border: '1px solid rgba(239, 68, 68, 0.3)', color: '#ef4444', borderRadius: '8px', padding: '6px 10px', cursor: 'pointer', fontSize: '0.8rem', transition: 'all 0.2s' }}
                            onMouseOver={e => e.currentTarget.style.background = 'rgba(239,68,68,0.2)'}
                            onMouseOut={e => e.currentTarget.style.background = 'transparent'}
                          >
                            🗑️
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
      </>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '400px', borderRadius: '16px', border: '1px dashed rgba(255,255,255,0.1)' }}>
          <div style={{ fontSize: '3rem', marginBottom: '16px' }}>🏫</div>
          <h3 className="heading-serif" style={{ color: '#f8fafc', margin: '0 0 8px 0' }}>No Class Offering Selected</h3>
          <p style={{ color: '#94a3b8', margin: 0, textAlign: 'center', maxWidth: '400px' }}>
            Please select a Department, Course, Section, Semester, and Subject from the context bar above to view the dashboard.
          </p>
        </div>
      )}

      {/* Modal: Add Student */}
      {showAddStudentModal && createPortal(
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.8)', backdropFilter: 'blur(8px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ background: '#18181b', border: '1px solid rgba(255,255,255,0.15)', borderRadius: '20px', padding: '32px', width: '100%', maxWidth: '450px', boxShadow: '0 25px 50px -12px rgba(0,0,0,0.7)' }}>
            <h3 style={{ margin: '0 0 20px 0', fontSize: '1.4rem', color: '#f8fafc' }}>➕ Add Student to Offering</h3>
            <form onSubmit={handleAddStudent}>
              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.85rem', color: '#cbd5e1' }}>Enrollment / Roll Number *</label>
                <input required type="text" placeholder="e.g. BBA2026-061" value={newStudent.enrollment_number} onChange={e => setNewStudent({ ...newStudent, enrollment_number: e.target.value })} style={{ width: '100%', padding: '10px', borderRadius: '8px', background: '#27272a', border: '1px solid #444', color: '#fff', outline: 'none' }} />
              </div>
              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.85rem', color: '#cbd5e1' }}>Full Name *</label>
                <input required type="text" placeholder="e.g. Rahul Sharma" value={newStudent.full_name} onChange={e => setNewStudent({ ...newStudent, full_name: e.target.value })} style={{ width: '100%', padding: '10px', borderRadius: '8px', background: '#27272a', border: '1px solid #444', color: '#fff', outline: 'none' }} />
              </div>
              <div style={{ marginBottom: '24px' }}>
                <label style={{ display: 'block', marginBottom: '6px', fontSize: '0.85rem', color: '#cbd5e1' }}>Email Address (Optional)</label>
                <input type="email" placeholder="e.g. rahul@university.edu" value={newStudent.email} onChange={e => setNewStudent({ ...newStudent, email: e.target.value })} style={{ width: '100%', padding: '10px', borderRadius: '8px', background: '#27272a', border: '1px solid #444', color: '#fff', outline: 'none' }} />
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
                <button type="button" onClick={() => setShowAddStudentModal(false)} className="button secondary">Cancel</button>
                <button type="submit" className="button primary" style={{ background: '#3b82f6' }}>Add to Roster</button>
              </div>
            </form>
          </div>
        </div>
      , document.body)}

      {/* Modals for Add Student (Rubric upload modal removed) */}
      
      {showBulkRosterModal && (
        <BulkRosterModal
          offeringId={selectedOfferingId}
          onClose={() => setShowBulkRosterModal(false)}
          onRefresh={() => loadOfferingData(selectedOfferingId)}
        />
      )}

      {showBulkScriptModal && (
        <BulkScriptModal
          offeringId={selectedOfferingId}
          onClose={() => setShowBulkScriptModal(false)}
          onRefresh={() => loadOfferingData(selectedOfferingId)}
        />
      )}
    </>
  )
}
