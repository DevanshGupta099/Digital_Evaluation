import React, { useState } from 'react';
import { bulkValidateStudents, bulkCommitStudents } from '../api';

const BulkRosterModal = ({ offeringId, onClose, onRefresh }) => {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [previewRows, setPreviewRows] = useState([]);
  const [step, setStep] = useState(1); // 1: Upload, 2: Preview
  const [error, setError] = useState(null);

  const handleFileChange = (e) => {
    if (e.target.files.length > 0) {
      setFile(e.target.files[0]);
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      const res = await bulkValidateStudents(offeringId, file);
      setPreviewRows(res.rows || []);
      setStep(2);
    } catch (err) {
      setError(err.message || 'Validation failed');
    } finally {
      setLoading(false);
    }
  };

  const handleCommit = async () => {
    const validRows = previewRows.filter(r => r.status === 'valid');
    if (validRows.length === 0) {
      alert("No valid rows to import.");
      return;
    }
    
    setLoading(true);
    try {
      await bulkCommitStudents(offeringId, validRows);
      onRefresh();
      onClose();
    } catch (err) {
      setError(err.message || 'Import failed');
      setLoading(false);
    }
  };

  const downloadTemplate = () => {
    const csvContent = "data:text/csv;charset=utf-8,roll_number,full_name\\nST001,John Doe\\nST002,Jane Smith";
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", "roster_template.csv");
    document.body.appendChild(link);
    link.click();
    link.remove();
  };

  const validCount = previewRows.filter(r => r.status === 'valid').length;

  return (
    <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
      <div style={{ background: '#1e293b', width: '700px', borderRadius: '12px', padding: '24px', color: 'white', maxHeight: '90vh', display: 'flex', flexDirection: 'column' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '16px' }}>
          <h2 style={{ margin: 0, fontSize: '1.25rem' }}>Bulk Import Roster</h2>
          <button onClick={onClose} style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer', fontSize: '1.25rem' }}>&times;</button>
        </div>

        {error && <div style={{ background: 'rgba(239, 68, 68, 0.2)', color: '#f87171', padding: '12px', borderRadius: '8px', marginBottom: '16px' }}>{error}</div>}

        {step === 1 ? (
          <div>
            <p style={{ color: '#94a3b8', marginBottom: '16px' }}>Upload a CSV file containing student roster details. The file must contain <code>roll_number</code> and <code>full_name</code> headers.</p>
            <div style={{ display: 'flex', gap: '12px', marginBottom: '24px' }}>
              <button onClick={downloadTemplate} style={{ padding: '8px 16px', background: 'transparent', border: '1px solid #4f46e5', color: '#4f46e5', borderRadius: '6px', cursor: 'pointer' }}>Download Template</button>
            </div>
            
            <div style={{ border: '2px dashed #475569', padding: '40px', borderRadius: '8px', textAlign: 'center', marginBottom: '24px' }}>
              <input type="file" accept=".csv" onChange={handleFileChange} id="csv_upload" style={{ display: 'none' }} />
              <label htmlFor="csv_upload" style={{ cursor: 'pointer', color: '#a855f7', fontWeight: 500 }}>
                {file ? file.name : "Click to select CSV file"}
              </label>
            </div>
            
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
              <button onClick={onClose} style={{ padding: '10px 16px', background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer' }}>Cancel</button>
              <button onClick={handleUpload} disabled={!file || loading} style={{ padding: '10px 16px', background: '#4f46e5', color: 'white', border: 'none', borderRadius: '6px', cursor: (file && !loading) ? 'pointer' : 'not-allowed', opacity: (file && !loading) ? 1 : 0.6 }}>
                {loading ? 'Validating...' : 'Validate CSV'}
              </button>
            </div>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
            <p style={{ color: '#94a3b8', marginBottom: '16px' }}>Previewing {previewRows.length} rows. ({validCount} valid ready to import)</p>
            
            <div style={{ flex: 1, overflowY: 'auto', border: '1px solid #334155', borderRadius: '8px', marginBottom: '24px' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
                <thead style={{ background: '#0f172a', position: 'sticky', top: 0 }}>
                  <tr>
                    <th style={{ padding: '12px', textAlign: 'left', borderBottom: '1px solid #334155' }}>Roll Number</th>
                    <th style={{ padding: '12px', textAlign: 'left', borderBottom: '1px solid #334155' }}>Name</th>
                    <th style={{ padding: '12px', textAlign: 'left', borderBottom: '1px solid #334155' }}>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {previewRows.map((r, i) => (
                    <tr key={i} style={{ borderBottom: '1px solid #1e293b' }}>
                      <td style={{ padding: '12px' }}>{r.roll_number}</td>
                      <td style={{ padding: '12px' }}>{r.full_name}</td>
                      <td style={{ padding: '12px' }}>
                        {r.status === 'valid' ? (
                          <span style={{ color: '#34d399', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '6px' }}>✓ Valid</span>
                        ) : (
                          <span style={{ color: r.status === 'duplicate' ? '#fbbf24' : '#f87171', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '6px' }}>
                            ⚠️ {r.reason}
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <button onClick={() => setStep(1)} style={{ padding: '10px 16px', background: 'transparent', border: '1px solid #475569', color: '#94a3b8', borderRadius: '6px', cursor: 'pointer' }}>Back</button>
              <button onClick={handleCommit} disabled={validCount === 0 || loading} style={{ padding: '10px 16px', background: '#10b981', color: 'white', border: 'none', borderRadius: '6px', cursor: (validCount > 0 && !loading) ? 'pointer' : 'not-allowed', opacity: (validCount > 0 && !loading) ? 1 : 0.6 }}>
                {loading ? 'Importing...' : `Import ${validCount} Valid Students`}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default BulkRosterModal;
