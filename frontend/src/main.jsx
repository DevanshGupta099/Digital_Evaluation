import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import LandingPage from './pages/LandingPage.jsx'
import Layout from './components/Layout.jsx'
import Dashboard from './pages/Dashboard.jsx'
import NewEvaluation from './pages/NewEvaluation.jsx'
import ReviewPage from './pages/ReviewPage.jsx'
import './styles.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/dashboard" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="new" element={<NewEvaluation />} />
          <Route path="review/:scriptId" element={<ReviewPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
)
