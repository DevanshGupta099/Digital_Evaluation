import React, { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { getHierarchy, createHierarchyEntity, updateHierarchyEntity, deleteHierarchyEntity } from '../api.js'

export default function HierarchyBar({ selectedOfferingId, onOfferingChange }) {
  const [hierarchy, setHierarchy] = useState({
    departments: [], courses: [], sections: [], terms: [], subjects: [], offerings: []
  })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  // Selected state
  const [deptId, setDeptId] = useState('')
  const [courseId, setCourseId] = useState('')
  const [sectionId, setSectionId] = useState('')
  const [termId, setTermId] = useState('')
  const [subjectId, setSubjectId] = useState('')

  // Inline creation state
  const [creating, setCreating] = useState(null)
  const [editing, setEditing] = useState(null) // { key, id }
  const [editMode, setEditMode] = useState(false)
  
  const [newName, setNewName] = useState('')
  const [newSemester, setNewSemester] = useState('1')
  const [newYear, setNewYear] = useState(new Date().getFullYear())

  const loadData = async (preserveSelections = false) => {
    try {
      const data = await getHierarchy()
      setHierarchy(data)
      setLoading(false)
      
      if (!preserveSelections && selectedOfferingId && data.offerings) {
        const off = data.offerings.find(o => o.id === selectedOfferingId)
        if (off) {
          setDeptId(off.department_id || '')
          setCourseId(off.course_id || '')
          setSectionId(off.section_id || '')
          setTermId(off.academic_term_id || '')
          setSubjectId(off.subject_id || '')
        }
      }
    } catch (err) {
      console.error("Failed to load hierarchy:", err)
      setError(String(err))
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  // Sync state if selectedOfferingId changes from parent
  useEffect(() => {
    if (hierarchy.offerings && hierarchy.offerings.length > 0 && selectedOfferingId) {
      const off = hierarchy.offerings.find(o => o.id === selectedOfferingId)
      if (off) {
        setDeptId(off.department_id || '')
        setCourseId(off.course_id || '')
        setSectionId(off.section_id || '')
        setTermId(off.academic_term_id || '')
        setSubjectId(off.subject_id || '')
      }
    }
  }, [selectedOfferingId, hierarchy.offerings])

  // Resolve ClassOffering when all 5 pieces are selected
  useEffect(() => {
    if (deptId && courseId && sectionId && termId && subjectId && hierarchy.offerings) {
      const off = hierarchy.offerings.find(o => 
        o.department_id === deptId &&
        o.course_id === courseId &&
        o.section_id === sectionId &&
        o.academic_term_id === termId &&
        o.subject_id === subjectId
      )
      if (off && off.id !== selectedOfferingId) {
        onOfferingChange(off.id, off)
      } else if (!off && selectedOfferingId) {
        // Selected context but no offering exists yet
        onOfferingChange('', null)
      }
    } else {
      if (selectedOfferingId) onOfferingChange('', null)
    }
  }, [deptId, courseId, sectionId, termId, subjectId, hierarchy.offerings])

  const courseOptions = hierarchy.courses ? hierarchy.courses.filter(c => c.department_id === deptId) : []
  const sectionOptions = hierarchy.sections ? hierarchy.sections.filter(s => s.course_id === courseId) : []
  
  // Check if a class offering exists for current selection
  const currentOffering = hierarchy.offerings ? hierarchy.offerings.find(o => 
    o.department_id === deptId &&
    o.course_id === courseId &&
    o.section_id === sectionId &&
    o.academic_term_id === termId &&
    o.subject_id === subjectId
  ) : null

  const handleCreate = async (e) => {
    e.preventDefault()
    if (!creating) return
    setError('')
    try {
      let payload = {}
      if (creating === 'departments') payload = { name: newName }
      else if (creating === 'courses') payload = { name: newName, department_id: deptId }
      else if (creating === 'sections') payload = { name: newName, course_id: courseId }
      else if (creating === 'academic-terms') payload = { number: newSemester, calendar_year: newYear }
      else if (creating === 'subjects') payload = { name: newName }
      else if (creating === 'offerings') {
        payload = { department_id: deptId, course_id: courseId, section_id: sectionId, semester_id: termId, subject_id: subjectId }
      }
      
      const res = await createHierarchyEntity(creating, payload)
      
      if (creating === 'departments') setDeptId(res.id)
      else if (creating === 'courses') setCourseId(res.id)
      else if (creating === 'sections') setSectionId(res.id)
      else if (creating === 'academic-terms') setTermId(res.id)
      else if (creating === 'subjects') setSubjectId(res.id)
      
      setCreating(null)
      setNewName('')
      await loadData(true)
    } catch(err) {
      setError(String(err))
    }
  }

  const handleEditSubmit = async (e) => {
    e.preventDefault()
    if (!editing) return
    setError('')
    try {
      let payload = {}
      if (editing.key === 'academic-terms') payload = { number: newSemester, calendar_year: newYear }
      else payload = { name: newName }
      
      await updateHierarchyEntity(editing.key, editing.id, payload)
      setEditing(null)
      await loadData(true)
    } catch(err) {
      setError(String(err))
    }
  }

  const handleDelete = async (key, id) => {
    if (!window.confirm(`Are you sure you want to delete this item?`)) return
    setError('')
    try {
      await deleteHierarchyEntity(key, id)
      // Reset local selection if we deleted it
      if (key === 'departments' && deptId === id) setDeptId('')
      if (key === 'courses' && courseId === id) setCourseId('')
      if (key === 'sections' && sectionId === id) setSectionId('')
      if (key === 'academic-terms' && termId === id) setTermId('')
      if (key === 'subjects' && subjectId === id) setSubjectId('')
      await loadData(true)
    } catch (err) {
      setError(String(err))
    }
  }

  const renderSelect = (label, value, setter, options, createKey, disabled = false) => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', flex: 1, minWidth: '150px' }}>
      <label className="font-sans" style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)' }}>{label}</label>
      <div style={{ display: 'flex', gap: '4px' }}>
        <select
          value={value}
          onChange={(e) => {
            if (e.target.value === '__NEW__') {
              setNewName('')
              setNewSemester('1')
              setNewYear(new Date().getFullYear())
              setCreating(createKey)
            } else {
              setter(e.target.value)
              if (createKey === 'departments') { setCourseId(''); setSectionId('') }
              if (createKey === 'courses') setSectionId('')
            }
          }}
          disabled={disabled}
          style={{
            padding: '8px 12px',
            borderRadius: '4px',
            background: 'var(--surface-container-high)',
            color: 'var(--on-surface)',
            border: '1px solid var(--outline-variant)',
            outline: 'none',
            flex: 1,
            opacity: disabled ? 0.5 : 1
          }}
          className="font-sans"
        >
          <option value="">-- Select --</option>
          {options.map(opt => <option key={opt.id} value={opt.id}>{opt.name}</option>)}
          <option value="__NEW__" style={{ fontWeight: 'bold', color: 'var(--primary)' }}>+ New...</option>
        </select>
        
        {editMode && value && (
          <div style={{ display: 'flex', gap: '2px', alignItems: 'center' }}>
            <button 
              onClick={() => {
                const opt = options.find(o => o.id === value)
                if (opt) {
                  if (createKey === 'academic-terms') {
                    setNewSemester(opt.semester || '1')
                    setNewYear(opt.year || new Date().getFullYear())
                  } else {
                    setNewName(opt.name || '')
                  }
                  setEditing({ key: createKey, id: value })
                }
              }}
              style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '4px' }} title="Edit"
            >
              ✏️
            </button>
            <button 
              onClick={() => handleDelete(createKey, value)}
              style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '4px' }} title="Delete"
            >
              🗑️
            </button>
          </div>
        )}
      </div>
    </div>
  )

  return (
    <div className="hierarchy-container card" style={{
      padding: '20px',
      marginBottom: '28px'
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
        <div className="font-sans" style={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '1.2px', color: 'var(--primary)' }}>
          Active Institutional Context
        </div>
        <button 
          onClick={() => setEditMode(!editMode)}
          style={{ 
            background: editMode ? 'rgba(99, 102, 241, 0.2)' : 'none', 
            border: editMode ? '1px solid #6366f1' : '1px solid transparent', 
            color: '#94a3b8', fontSize: '0.75rem', padding: '4px 8px', borderRadius: '6px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px'
          }}
        >
          ⚙️ {editMode ? 'Done Editing' : 'Settings Mode'}
        </button>
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px', alignItems: 'flex-end' }}>
        {renderSelect('Department', deptId, setDeptId, hierarchy.departments || [], 'departments')}
        {renderSelect('Programme', courseId, setCourseId, courseOptions, 'courses', !deptId)}
        {renderSelect('Section', sectionId, setSectionId, sectionOptions, 'sections', !courseId)}
        {renderSelect('Semester & Year', termId, setTermId, hierarchy.terms || [], 'academic-terms')}
        {renderSelect('Subject', subjectId, setSubjectId, hierarchy.subjects || [], 'subjects')}
      </div>

      {deptId && courseId && sectionId && termId && subjectId && !currentOffering && (
        <div style={{ marginTop: '16px', padding: '16px', background: 'rgba(99, 102, 241, 0.1)', borderRadius: '12px', border: '1px dashed #6366f1', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h4 style={{ margin: 0, color: '#f8fafc' }}>Unlinked Context</h4>
            <p style={{ margin: '4px 0 0', fontSize: '0.85rem', color: '#94a3b8' }}>This combination is valid but doesn't exist as a Class Offering yet.</p>
          </div>
          <button 
            onClick={() => { setCreating('offerings'); handleCreate({ preventDefault: () => {} }) }}
            className="button primary"
          >
            + Create Class Offering
          </button>
        </div>
      )}

      {/* Inline Creation / Edit Modal */}
      {(creating || editing) && (creating !== 'offerings') && createPortal(
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(10px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000
        }}>
          <div style={{
            background: '#18181b', border: '1px solid rgba(255,255,255,0.15)', borderRadius: '16px',
            padding: '32px', width: '100%', maxWidth: '400px', boxShadow: '0 25px 50px -12px rgba(0,0,0,0.7)'
          }}>
            <h3 style={{ margin: '0 0 20px 0', color: '#f8fafc' }}>
              {editing ? 'Edit' : 'Create New'} {(creating || editing.key).replace('-', ' ').replace(/\b\w/g, l => l.toUpperCase())}
            </h3>
            
            {error && <div className="flag error" style={{ marginBottom: 16 }}>{error}</div>}

            <form onSubmit={editing ? handleEditSubmit : handleCreate}>
              {(creating === 'academic-terms' || (editing && editing.key === 'academic-terms')) ? (
                <>
                  <div style={{ marginBottom: '16px' }}>
                    <label style={{ display: 'block', marginBottom: '8px', color: '#94a3b8', fontSize: '0.85rem' }}>Semester Number</label>
                    <input type="text" value={newSemester} onChange={e => setNewSemester(e.target.value)} required className="input" />
                  </div>
                  <div style={{ marginBottom: '24px' }}>
                    <label style={{ display: 'block', marginBottom: '8px', color: '#94a3b8', fontSize: '0.85rem' }}>Start Year</label>
                    <input type="number" value={newYear} onChange={e => setNewYear(e.target.value)} required className="input" />
                  </div>
                </>
              ) : (
                <div style={{ marginBottom: '24px' }}>
                  <label style={{ display: 'block', marginBottom: '8px', color: '#94a3b8', fontSize: '0.85rem' }}>Name</label>
                  <input type="text" value={newName} onChange={e => setNewName(e.target.value)} required className="input" autoFocus />
                </div>
              )}
              
              <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end' }}>
                <button type="button" onClick={() => { setCreating(null); setEditing(null) }} className="button secondary">Cancel</button>
                <button type="submit" className="button primary">{editing ? 'Save' : 'Create'}</button>
              </div>
            </form>
          </div>
        </div>,
        document.body
      )}
    </div>
  )
}
