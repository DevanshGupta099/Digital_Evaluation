import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { uploadScript, analyzeMaterials } from '../api.js'

export default function NewEvaluation() {
  const [step, setStep] = useState(1)
  const [questionPaper, setQuestionPaper] = useState(null)
  const [answerKey, setAnswerKey] = useState(null)
  const [examId, setExamId] = useState('')
  const [rubrics, setRubrics] = useState([])
  const [studentName, setStudentName] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  
  const qpRef = useRef()
  const akRef = useRef()
  const scriptRef = useRef()
  const navigate = useNavigate()

  async function handleAnalyze() {
    if (!questionPaper || !answerKey) {
      setError("Please provide both Question Paper and Answer Key")
      return
    }
    setBusy(true)
    setError('')
    try {
      const res = await analyzeMaterials(questionPaper, answerKey)
      setExamId(res.exam_id)
      setRubrics(res.rubrics)
      setStep(3)
    } catch (err) {
      setError(String(err))
    } finally {
      setBusy(false)
    }
  }

  async function onUploadScript(e) {
    e.preventDefault()
    const file = scriptRef.current?.files[0]
    if (!file) return
    setBusy(true)
    setError('')
    try {
      await uploadScript(file, studentName, examId || 'default')
      navigate('/dashboard')
    } catch (err) {
      setError(String(err))
    } finally {
      setBusy(false)
    }
  }

  const triggerInput = (ref) => ref.current?.click()

  return (
    <div className="new-eval-container">
      <div className="wizard-progress">
        <div className={`wizard-step ${step === 1 ? 'active' : step > 1 ? 'completed' : ''}`}>1. Question Paper</div>
        <div className={`wizard-step ${step === 2 ? 'active' : step > 2 ? 'completed' : ''}`}>2. Answer Key</div>
        <div className={`wizard-step ${step === 3 ? 'active' : ''}`}>3. Student Scripts</div>
      </div>

      {error && <div className="flag" style={{marginBottom: 24}}>{error}</div>}

      {step === 1 && (
        <div className="card">
          <h2>Upload Question Paper</h2>
          <p style={{color: 'var(--text-muted)'}}>Upload the question paper (PDF or Image) to begin the evaluation setup.</p>
          <div className="dropzone" onClick={() => triggerInput(qpRef)}>
            <input type="file" ref={qpRef} accept=".pdf,.png,.jpg,.jpeg,.doc,.docx" onChange={(e) => {
              if (e.target.files[0]) {
                setQuestionPaper(e.target.files[0])
                setStep(2)
              }
            }} />
            <h3>{questionPaper ? questionPaper.name : 'Click to select Question Paper'}</h3>
            <p>Supports PDF, PNG, JPG</p>
          </div>
          {questionPaper && (
            <div className="actions" style={{justifyContent: 'flex-end'}}>
              <button className="primary" onClick={() => setStep(2)}>Continue to Answer Key &rarr;</button>
            </div>
          )}
        </div>
      )}

      {step === 2 && (
        <div className="card">
          <h2>Upload Answer Key</h2>
          <p style={{color: 'var(--text-muted)'}}>Provide the model answer key. The AI will cross-reference this with the question paper to build a structured rubric.</p>
          <div className="dropzone" onClick={() => triggerInput(akRef)}>
            <input type="file" ref={akRef} accept=".pdf,.png,.jpg,.jpeg,.doc,.docx" onChange={(e) => setAnswerKey(e.target.files[0])} />
            <h3>{answerKey ? answerKey.name : 'Click to select Answer Key'}</h3>
            <p>Supports PDF, PNG, JPG</p>
          </div>
          
          <div className="actions" style={{justifyContent: 'space-between'}}>
            <button className="secondary" onClick={() => setStep(1)}>&larr; Back</button>
            {answerKey && (
              <button className="primary" onClick={handleAnalyze} disabled={busy}>
                {busy ? 'Analyzing with AI...' : 'Generate Rubric &rarr;'}
              </button>
            )}
          </div>
          
          {busy && (
            <div className="loader-container" style={{marginTop: 24}}>
              <div className="spinner"></div>
              <p style={{marginTop: 16}}>AI is structuring the grading rubric. This takes a few seconds...</p>
            </div>
          )}
        </div>
      )}

      {step === 3 && (
        <>
          <div className="card" style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
            <div>
              <h2>Setup Complete</h2>
              <p><strong>Exam ID:</strong> {examId || 'default'}</p>
              <p style={{color: 'var(--success)', fontWeight: 600}}>✓ AI extracted {rubrics.length} questions into a structured rubric.</p>
            </div>
            <button className="secondary" onClick={() => { setStep(1); setQuestionPaper(null); setAnswerKey(null); setExamId(''); }}>Start Over</button>
          </div>

          <div className="card">
            <h2>Upload Student Script</h2>
            <form onSubmit={onUploadScript} className="actions">
              <input type="file" ref={scriptRef} accept=".pdf,.png,.jpg,.jpeg" required style={{flex: 1}} />
              <input type="text" placeholder="Student name (optional)" value={studentName} onChange={(e) => setStudentName(e.target.value)} />
              <button className="primary" disabled={busy}>
                {busy ? 'Uploading...' : 'Upload & Grade'}
              </button>
            </form>
          </div>
        </>
      )}
    </div>
  )
}
