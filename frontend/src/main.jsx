import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext.jsx'
import LandingPage from './pages/LandingPage.jsx'
import Layout from './components/Layout.jsx'
import Dashboard from './pages/Dashboard.jsx'
import NewEvaluation from './pages/NewEvaluation.jsx'
import ReviewPage from './pages/ReviewPage.jsx'
import ReviewQueue from './pages/ReviewQueue.jsx'
import RubricsPage from './pages/RubricsPage.jsx'
import AnalyticsDashboard from './pages/AnalyticsDashboard.jsx'
import AuditLogViewer from './pages/AuditLogViewer.jsx'
import StudentView from './pages/StudentView.jsx'
import './styles.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/dashboard" element={<Layout />}>
            <Route index element={<Dashboard />} />
            <Route path="new" element={<NewEvaluation />} />
            <Route path="rubrics" element={<RubricsPage />} />
            <Route path="analytics" element={<AnalyticsDashboard />} />
            <Route path="audit/:offeringId" element={<AuditLogViewer />} />
            <Route path="student-view/:offeringId" element={<StudentView />} />
            <Route path="queue/:offeringId" element={<ReviewQueue />} />
            <Route path="review/:scriptId" element={<ReviewPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  </React.StrictMode>,
)
