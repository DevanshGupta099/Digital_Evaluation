import { useEffect, useState } from 'react'
import { Link, Outlet, useLocation } from 'react-router-dom'
import { Logo } from './Logo.jsx'
import { API_URL } from '../api.js'

export default function Layout() {
  const location = useLocation()
  const [metrics, setMetrics] = useState({ percentage: 0, calls_made: 0, limit: 1500, status: 'online' })
  
  useEffect(() => {
    fetch(`${API_URL}/system/metrics`)
      .then(res => res.json())
      .then(data => setMetrics(data))
      .catch(err => console.error("Could not fetch metrics:", err))
  }, [location.pathname]) // Refresh metrics on navigation

  const navItems = [
    { name: 'Home', path: '/', icon: <path strokeLinecap="round" strokeLinejoin="round" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" /> },
    { name: 'Dashboard', path: '/dashboard', icon: <path strokeLinecap="round" strokeLinejoin="round" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" /> },
    { name: 'New Evaluation', path: '/dashboard/new', icon: <path strokeLinecap="round" strokeLinejoin="round" d="M9 13h6m-3-3v6m5 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /> }
  ]

  return (
    <div className="app-layout">
      {/* Floating Sidebar */}
      <aside className="sidebar floating-sidebar">
        <div className="sidebar-brand">
          <Link to="/">
            <Logo />
            <span>DigitalEval</span>
          </Link>
        </div>
        
        <div className="sidebar-section-title">MAIN MENU</div>
        <nav className="sidebar-nav">
          {navItems.map(item => (
            <Link 
              key={item.path} 
              to={item.path} 
              className={`nav-link ${location.pathname === item.path ? 'active' : ''}`}
            >
              <svg className="nav-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                {item.icon}
              </svg>
              {item.name}
            </Link>
          ))}
        </nav>
        
        <div className="sidebar-footer">
          <div className="system-status-block">
            <div className="status-header">
              <span className={`pulse-dot ${metrics.status === 'online' ? 'green' : 'red'}`}></span>
              <span className="status-text">{metrics.status === 'online' ? 'API Online' : 'Rate Limited'}</span>
            </div>
            <div className="quota-bar-container">
              <div className="quota-label">
                <span>API Quota</span>
                <span>{metrics.percentage}%</span>
              </div>
              <div className="quota-bar">
                <div className="quota-fill" style={{width: `${metrics.percentage}%`}}></div>
              </div>
              <div className="quota-subtext">
                {metrics.calls_made} / {metrics.limit} requests today
              </div>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  )
}
