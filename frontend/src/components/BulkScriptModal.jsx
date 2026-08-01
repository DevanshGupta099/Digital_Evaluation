import React, { useState, useEffect } from 'react';
import { bulkValidateScripts, bulkCommitScripts, getOfferingStudents } from '../api';

const BulkScriptModal = ({ offeringId, onClose, onRefresh }) => {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState(1); // 1: Upload, 2: Mapping
  const [error, setError] = useState(null);
  
  const [batchId, setBatchId] = useState(null);
  const [mappings, setMappings] = useState([]);
  const [roster, setRoster] = useState([]);
  
  useEffect(() => {
    // Load roster for manual mapping dropdowns
    getOfferingStudents(offeringId).then(data => {
      setRoster(data || []);
    }).catch(err => console.error(err));
  }, [offeringId]);

  const handleFileChange = (e) => {
    setFiles(Array.from(e.target.files));
  };

  const handleUpload = async () => {
    if (files.length === 0) return;
    setLoading(true);
    setError(null);
    try {
      const res = await bulkValidateScripts(offeringId, files);
      setBatchId(res.batch_id);
      
      // Initialize mappings with default actions
      const initMappings = (res.files || []).map(f => ({
        ...f,
        action: f.conflict ? 'skip' : (f.matched_student_id ? 'commit' : 'skip'),
        selected_student_id: f.matched_student_id || ''
      }));
      setMappings(initMappings);
      setStep(2);
    } catch (err) {
      setError(err.message || 'Validation failed');
    } finally {
      setLoading(false);
    }
  };

  const updateMapping = (index, key, value) => {
    const updated = [...mappings];
    updated[index][key] = value;
    
    // Auto-update action based on selection if not conflict
    if (key === 'selected_student_id' && !updated[index].conflict) {
      updated[index].action = value ? 'commit' : 'skip';
    }
    
    setMappings(updated);
  };

  const handleCommit = async () => {
    const payload = mappings.map(m => ({
      temp_file_id: m.temp_file_id,
      filename: m.filename,
      student_id: m.selected_student_id,
      action: m.action
    }));
    
    setLoading(true);
    try {
      await bulkCommitScripts(batchId, offeringId, payload);
      onRefresh();
      onClose();
    } catch (err) {
      setError(err.message || 'Commit failed');
      setLoading(false);
    }
  };

  return (
    <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
      <div style={{ background: '#1e293b', width: '900px', borderRadius: '12px', padding: '24px', color: 'white', maxHeight: '90vh', display: 'flex', flexDirection: 'column' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '16px' }}>
          <h2 style={{ margin: 0, fontSize: '1.25rem' }}>Bulk Upload Scripts</h2>
          <button onClick={onClose} style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer', fontSize: '1.25rem' }}>&times;</button>
        </div>

        {error && <div style={{ background: 'rgba(239, 68, 68, 0.2)', color: '#f87171', padding: '12px', borderRadius: '8px', marginBottom: '16px' }}>{error}</div>}

        {step === 1 ? (
          <div>
            <p style={{ color: '#94a3b8', marginBottom: '16px' }}>Upload multiple PDF or Image files. The system will attempt to automatically match them to students via OCR on the header.</p>
            
            <div style={{ border: '2px dashed #475569', padding: '40px', borderRadius: '8px', textAlign: 'center', marginBottom: '24px' }}>
              <input type="file" multiple accept=".pdf,.jpg,.jpeg,.png" onChange={handleFileChange} id="script_upload" style={{ display: 'none' }} />
              <label htmlFor="script_upload" style={{ cursor: 'pointer', color: '#a855f7', fontWeight: 500 }}>
                {files.length > 0 ? `${files.length} files selected` : "Click to select files"}
              </label>
            </div>
            
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
              <button onClick={onClose} style={{ padding: '10px 16px', background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer' }}>Cancel</button>
              <button onClick={handleUpload} disabled={files.length === 0 || loading} style={{ padding: '10px 16px', background: '#4f46e5', color: 'white', border: 'none', borderRadius: '6px', cursor: (files.length > 0 && !loading) ? 'pointer' : 'not-allowed', opacity: (files.length > 0 && !loading) ? 1 : 0.6 }}>
                {loading ? 'Processing OCR...' : 'Validate Scripts'}
              </button>
            </div>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
            <p style={{ color: '#94a3b8', marginBottom: '16px' }}>Review OCR matches. Resolve any conflicts or unmatched scripts.</p>
            
            <div style={{ flex: 1, overflowY: 'auto', border: '1px solid #334155', borderRadius: '8px', marginBottom: '24px' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
                <thead style={{ background: '#0f172a', position: 'sticky', top: 0 }}>
                  <tr>
                    <th style={{ padding: '12px', textAlign: 'left', borderBottom: '1px solid #334155' }}>Filename</th>
                    <th style={{ padding: '12px', textAlign: 'left', borderBottom: '1px solid #334155' }}>Extracted Roll</th>
                    <th style={{ padding: '12px', textAlign: 'left', borderBottom: '1px solid #334155' }}>Matched Student</th>
                    <th style={{ padding: '12px', textAlign: 'left', borderBottom: '1px solid #334155' }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {mappings.map((m, i) => (
                    <tr key={i} style={{ borderBottom: '1px solid #1e293b' }}>
                      <td style={{ padding: '12px', maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={m.filename}>
                        {m.filename}
                        {m.conflict && <div style={{ color: '#fbbf24', fontSize: '0.75rem', marginTop: '4px' }}>⚠️ Student already has script</div>}
                      </td>
                      <td style={{ padding: '12px' }}>{m.extracted_roll || '-'}</td>
                      <td style={{ padding: '12px' }}>
                        <select 
                          value={m.selected_student_id}
                          onChange={(e) => updateMapping(i, 'selected_student_id', e.target.value)}
                          style={{ padding: '6px', background: '#0f172a', color: 'white', border: '1px solid #475569', borderRadius: '4px', width: '100%' }}
                        >
                          <option value="">-- Select Student --</option>
                          {roster.map(s => (
                            <option key={s.id} value={s.id}>{s.enrollment_number} - {s.full_name}</option>
                          ))}
                        </select>
                      </td>
                      <td style={{ padding: '12px' }}>
                        <select
                          value={m.action}
                          onChange={(e) => updateMapping(i, 'action', e.target.value)}
                          style={{ padding: '6px', background: m.action === 'skip' ? 'rgba(239, 68, 68, 0.2)' : 'rgba(16, 185, 129, 0.2)', color: m.action === 'skip' ? '#f87171' : '#34d399', border: '1px solid #475569', borderRadius: '4px' }}
                        >
                          <option value="commit">Commit</option>
                          {m.conflict && <option value="replace">Replace Existing</option>}
                          <option value="skip">Skip</option>
                        </select>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <button onClick={() => setStep(1)} style={{ padding: '10px 16px', background: 'transparent', border: '1px solid #475569', color: '#94a3b8', borderRadius: '6px', cursor: 'pointer' }}>Back</button>
              <button onClick={handleCommit} disabled={loading} style={{ padding: '10px 16px', background: '#10b981', color: 'white', border: 'none', borderRadius: '6px', cursor: !loading ? 'pointer' : 'not-allowed', opacity: !loading ? 1 : 0.6 }}>
                {loading ? 'Committing...' : 'Confirm Uploads'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default BulkScriptModal;
