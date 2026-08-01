export const API_URL = '/api'

const _fetch = async (url, options = {}) => {
  const userStr = localStorage.getItem('digital_eval_user');
  const headers = new Headers(options.headers || {});
  if (userStr) {
    const user = JSON.parse(userStr);
    headers.set('Authorization', `Bearer ${user.id}`);
  }
  return fetch(url, { ...options, headers });
};

async function json(res) {
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`)
  return res.json()
}

export const listScripts = () => _fetch(`${API_URL}/scripts`).then(json)
export const getScript = (id) => _fetch(`/api/review/scripts/${id}`).then(json)

export function uploadScript(file, studentName, examId = 'default') {
  const form = new FormData()
  form.append('file', file)
  const params = new URLSearchParams({ student_name: studentName, exam_id: examId })
  return _fetch(`/api/scripts?${params}`, { method: 'POST', body: form }).then(json)
}

export const submitReview = async (evalId, payload) => {
  const res = await fetch(`${API_URL}/review/evaluations/${evalId}/review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  })
  if (!res.ok) throw new Error("Failed to submit review")
  return await res.json()
}

export const bulkAcceptEvaluations = async (scriptId, reviewer, confidenceThreshold) => {
  const res = await fetch(`${API_URL}/review/scripts/${scriptId}/bulk-accept`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reviewer, confidence_threshold: confidenceThreshold })
  })
  if (!res.ok) throw new Error("Failed to bulk accept")
  return await res.json()
}

export const getPeerComparisons = async (offeringId, questionNumber, subpartId, excludeScriptId) => {
  const params = new URLSearchParams({ question_number: questionNumber })
  if (subpartId) params.append('subpart_id', subpartId)
  if (excludeScriptId) params.append('exclude_script_id', excludeScriptId)
  
  const res = await fetch(`${API_URL}/review/peer-comparison/${offeringId}?${params.toString()}`)
  if (!res.ok) throw new Error("Failed to fetch peer comparisons")
  return await res.json()
}

export const getReviewQueue = (offeringId) => _fetch(`/api/review/queue/${offeringId}`).then(json)

export function analyzeMaterials(questionPaperFile, answerKeyFile) {
  const form = new FormData()
  form.append('question_paper', questionPaperFile)
  form.append('answer_key', answerKeyFile)
  return _fetch('/api/analyze/materials', { method: 'POST', body: form }).then(json)
}

export const getRubrics = () => _fetch('/api/rubrics').then(json)

// --- Hierarchy & Student Management ---

export const getHierarchy = () => _fetch('/api/hierarchy').then(json)

// --- Filtered Hierarchy Analytics (Phase 7) ---
export const getDepartments = () => _fetch('/api/hierarchy/filters/departments').then(json)
export const getCourses = (deptId) => _fetch(`/api/hierarchy/filters/departments/${deptId}/courses`).then(json)
export const getSections = (courseId) => _fetch(`/api/hierarchy/filters/courses/${courseId}/sections`).then(json)
export const getTerms = (sectionId) => _fetch(`/api/hierarchy/filters/sections/${sectionId}/terms`).then(json)
export const getSubjects = (sectionId, termId) => _fetch(`/api/hierarchy/filters/sections/${sectionId}/terms/${termId}/subjects`).then(json)

export const getDashboardAnalytics = (offeringId) => _fetch(`/api/analytics/dashboard/${offeringId}`).then(json)
export const getUsageMetrics = (offeringId) => _fetch(`/api/metrics/usage/${offeringId}`).then(json)
export async function exportClassMarks(offeringId) {
  const res = await _fetch(`/api/analytics/export/${offeringId}`)
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`)
  return res.blob()
}

export const createHierarchyEntity = (endpoint, data) => _fetch(`/api/${endpoint}`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(data),
}).then(json)

export const updateHierarchyEntity = (endpoint, id, data) => _fetch(`/api/${endpoint}/${id}`, {
  method: 'PUT',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(data),
}).then(json)

export const deleteHierarchyEntity = (endpoint, id) => _fetch(`/api/${endpoint}/${id}`, {
  method: 'DELETE',
}).then(json)

export const getOfferingStudents = (offeringId) => _fetch(`/api/offerings/${offeringId}/students`).then(json)

export const addStudentToOffering = (offeringId, studentData) => _fetch(`/api/offerings/${offeringId}/students`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(studentData),
}).then(json)

export const deleteStudent = (studentId) => _fetch(`/api/students/${studentId}`, {
  method: 'DELETE',
}).then(json)

// --- Offering Rubric & Student Script Upload ---

export const getOfferingRubric = (offeringId) => _fetch(`/api/offerings/${offeringId}/rubric`).then(json)

export function uploadQuestionPaper(offeringId, qpFile) {
  const data = new FormData()
  data.append('file', qpFile)
  return _fetch(`/api/offerings/${offeringId}/question-paper`, { method: 'POST', body: data }).then(json)
}

export function uploadAnswerKey(offeringId, akFile) {
  const data = new FormData()
  data.append('file', akFile)
  return _fetch(`/api/offerings/${offeringId}/answer-key`, { method: 'POST', body: data }).then(json)
}

export const generateRubric = (offeringId) => _fetch(`/api/rubric/generate`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ class_offering_id: offeringId })
}).then(json)

export const lockOfferingRubric = (versionId, approver) => _fetch(`/api/rubric/versions/${versionId}/approve`, { 
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ approver })
}).then(json)

export const updateRubricItem = (itemId, updates) => _fetch(`/api/rubric/items/${itemId}`, {
  method: 'PUT',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(updates)
}).then(json)

export const addRubricAddendum = (itemId, text, author) => _fetch(`/api/rubric/items/${itemId}/addendum`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ added_text: text, added_by: author })
}).then(json)

export function uploadStudentScript(offeringId, studentId, file) {
  const data = new FormData()
  data.append('file', file)
  data.append('student_id', studentId)
  data.append('class_offering_id', offeringId)
  return _fetch(`/api/ingestion/upload`, { method: 'POST', body: data }).then(json)
}

export const triggerAnalysis = (offeringId, scriptIds) => _fetch(`/api/offerings/${offeringId}/analyze`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ answer_script_ids: scriptIds }),
}).then(json)

export const getAnalytics = (offeringId = '') => _fetch(`/api/analytics${offeringId ? `?offering_id=${offeringId}` : ''}`).then(json)

export const finalizeScript = (scriptId) => _fetch(`/api/review/scripts/${scriptId}/finalize`, { method: 'POST' }).then(json)

export const overrideScriptEvaluation = (scriptId, req) => _fetch(`/api/scripts/${scriptId}/override`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(req),
}).then(json)

// --- Bulk Operations ---

export function bulkValidateStudents(offeringId, csvFile) {
  const data = new FormData();
  data.append('file', csvFile);
  return _fetch(`/api/offerings/${offeringId}/students/bulk-validate`, { method: 'POST', body: data }).then(json);
}

export function bulkCommitStudents(offeringId, studentsList) {
  return _fetch(`/api/offerings/${offeringId}/students/bulk-commit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ students: studentsList })
  }).then(json);
}

export function bulkValidateScripts(offeringId, files) {
  const data = new FormData();
  data.append('offering_id', offeringId);
  files.forEach(f => data.append('files', f));
  return _fetch(`/api/ingestion/bulk-scripts/validate`, { method: 'POST', body: data }).then(json);
}

export function bulkCommitScripts(batchId, offeringId, mappings) {
  return _fetch(`/api/ingestion/bulk-scripts/commit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ batch_id: batchId, offering_id: offeringId, mappings })
  }).then(json);
}

// --- Notifications ---

export const getNotifications = (offeringId) => _fetch(`/api/offerings/${offeringId}/notifications`).then(json);
export const markNotificationRead = (notifId) => _fetch(`/api/notifications/${notifId}/read`, { method: 'PUT' }).then(json);

// --- Phase 8 Features ---

export const publishResults = (offeringId, userName, userRole) => _fetch(`/api/offerings/${offeringId}/publish`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ user_name: userName, user_role: userRole })
}).then(json);

export const getAuditLogs = (offeringId) => _fetch(`/api/analytics/audit/${offeringId}`).then(json);

export const getSubjectRubrics = (subjectId) => _fetch(`/api/rubric/subject/${subjectId}`).then(json);

export const cloneRubricToOffering = (offeringId, prevVersionId) => _fetch(`/api/rubric/offerings/${offeringId}/clone/${prevVersionId}`, {
  method: 'POST'
}).then(json);
