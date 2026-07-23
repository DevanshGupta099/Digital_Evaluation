import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import ScriptsPage from './pages/ScriptsPage.jsx'
import ReviewPage from './pages/ReviewPage.jsx'
import './styles.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<ScriptsPage />} />
        <Route path="/scripts/:scriptId" element={<ReviewPage />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
)
