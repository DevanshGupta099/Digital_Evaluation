import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { listScripts, uploadScript } from '../api.js'

export default function ScriptsPage() {
  const [scripts, setScripts] = useState([])
  const [studentName, setStudentName] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const fileRef = useRef()

  const refresh = () => listScripts().then(setScripts).catch((e) => setError(String(e)))

  useEffect(() => {
    refresh()
    const t = setInterval(refresh, 4000)
    return () => clearInterval(t)
  }, [])

  async function onUpload(e) {
    e.preventDefault()
    const file = fileRef.current.files[0]
    if (!file) return
    setBusy(true)
    setError('')
    try {
      await uploadScript(file, studentName)
      fileRef.current.value = ''
      setStudentName('')
      refresh()
    } catch (err) {
      setError(String(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <header>
        <Link to="/">Answer Script Grader</Link>
      </header>
      <main>
        <div className="card">
          <h2>Upload answer script</h2>
          <form onSubmit={onUpload} className="actions">
            <input type="file" ref={fileRef} accept=".pdf,.png,.jpg,.jpeg" required />
            <input
              type="text"
              placeholder="Student name"
              value={studentName}
              onChange={(e) => setStudentName(e.target.value)}
            />
            <button className="accept" disabled={busy}>
              {busy ? 'Uploading…' : 'Upload & grade'}
            </button>
          </form>
          {error && <p className="flag">{error}</p>}
        </div>

        <div className="card">
          <h2>Scripts</h2>
          <table>
            <thead>
              <tr><th>Student</th><th>File</th><th>Status</th><th></th></tr>
            </thead>
            <tbody>
              {scripts.map((s) => (
                <tr key={s.id}>
                  <td>{s.student_name || '—'}</td>
                  <td>{s.filename}</td>
                  <td><span className={`status ${s.status}`}>{s.status}</span>{s.error && ` — ${s.error}`}</td>
                  <td><Link to={`/scripts/${s.id}`}>Open review</Link></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </main>
    </>
  )
}
