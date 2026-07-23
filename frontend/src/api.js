async function json(res) {
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`)
  return res.json()
}

export const listScripts = () => fetch('/api/scripts').then(json)
export const getScript = (id) => fetch(`/api/scripts/${id}`).then(json)

export function uploadScript(file, studentName, examId = 'default') {
  const form = new FormData()
  form.append('file', file)
  const params = new URLSearchParams({ student_name: studentName, exam_id: examId })
  return fetch(`/api/scripts?${params}`, { method: 'POST', body: form }).then(json)
}

export function submitReview(evaluationId, decision) {
  return fetch(`/api/evaluations/${evaluationId}/review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(decision),
  }).then(json)
}
