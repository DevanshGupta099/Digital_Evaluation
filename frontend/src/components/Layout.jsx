import { useEffect, useState } from 'react'
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { Logo } from './Logo.jsx'
import { API_URL, getNotifications, markNotificationRead } from '../api.js'
import { useAuth } from '../context/AuthContext'
import RBACModal from './RBACModal'

export default function Layout() {
  const location = useLocation()
  const { user } = useAuth()
  const [metrics, setMetrics] = useState({ percentage: 0, calls_made: 0, limit: 1500, status: 'online' })
  const [showRBAC, setShowRBAC] = useState(!user)
  
  const [notifications, setNotifications] = useState([])
  const [showNotifications, setShowNotifications] = useState(false)
  const [toasts, setToasts] = useState([])

  const navigate = useNavigate()
  const urlOfferingId = new URLSearchParams(location.search).get('offeringId')
  const offeringId = urlOfferingId || localStorage.getItem('lastOfferingId')

  useEffect(() => {
    if (urlOfferingId) {
      localStorage.setItem('lastOfferingId', urlOfferingId)
    } else if (offeringId && location.pathname.startsWith('/dashboard')) {
      navigate(`${location.pathname}?offeringId=${offeringId}`, { replace: true })
    }
  }, [urlOfferingId, offeringId, location.pathname, navigate])

  useEffect(() => {
    if (!user) setShowRBAC(true)
  }, [user])

  useEffect(() => {
    if (offeringId) {
      getNotifications(offeringId).then(data => setNotifications(data || [])).catch(() => {})
      
      const es = new EventSource(`/api/stream/events?offering_id=${offeringId}`);
      es.addEventListener('notification', (e) => {
        const data = JSON.parse(e.data);
        const newNotif = { id: Date.now().toString(), type: data.type, message: data.message, is_read: false, created_at: new Date().toISOString() };
        setNotifications(prev => [newNotif, ...prev]);
        setToasts(prev => [...prev, newNotif]);
        
        // Auto remove toast
        setTimeout(() => {
          setToasts(prev => prev.filter(t => t.id !== newNotif.id));
        }, 5000);
      });
      return () => es.close();
    }
  }, [offeringId])

  const handleMarkRead = async (id) => {
    setNotifications(prev => prev.map(n => n.id === id ? { ...n, is_read: true } : n));
    try { await markNotificationRead(id); } catch (e) {}
  };

  useEffect(() => {
    fetch(`${API_URL}/system/metrics`)
      .then(res => {
        if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`)
        return res.json()
      })
      .then(data => setMetrics(data))
      .catch(err => console.error("Could not fetch metrics:", err))
  }, [location.pathname]) // Refresh metrics on navigation

  const navItems = [
    { name: 'Home', path: '/', icon: <path strokeLinecap="round" strokeLinejoin="round" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" /> },
    { name: 'Dashboard', path: '/dashboard', icon: <path strokeLinecap="round" strokeLinejoin="round" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" /> },
    { name: 'Developer Sandbox', path: '/dashboard/new', icon: <path strokeLinecap="round" strokeLinejoin="round" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" /> },
    { name: 'Grading Rubrics', path: '/dashboard/rubrics', icon: <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /> },
    { name: 'Analytics', path: '/dashboard/analytics', icon: <path strokeLinecap="round" strokeLinejoin="round" d="M11 3.055A9.001 9.001 0 1020.945 13H11V3.055z" /> }
  ]

  return (
    <div className="app-layout">
      {showRBAC && <RBACModal onClose={user ? () => setShowRBAC(false) : undefined} />}
      
      {/* Floating Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-brand">
          <Link to="/" style={{ textDecoration: 'none', color: 'var(--text-main)' }}>
            <span className="heading-serif" style={{ fontSize: '1.25rem', fontWeight: 600 }}>Digital Evaluation</span>
          </Link>
        </div>
        
        <div style={{ padding: '0 20px', marginBottom: '16px', position: 'relative' }}>
          <button 
            onClick={() => setShowNotifications(!showNotifications)}
            style={{ width: '100%', background: 'var(--surface-container)', border: '1px solid var(--border-color)', padding: '10px', borderRadius: '4px', color: 'var(--text-main)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer' }}
          >
            <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              🔔 Notifications
            </span>
            {notifications.filter(n => !n.is_read).length > 0 && (
              <span style={{ background: '#ef4444', color: 'white', borderRadius: '12px', padding: '2px 8px', fontSize: '0.75rem', fontWeight: 600 }}>
                {notifications.filter(n => !n.is_read).length}
              </span>
            )}
          </button>
          
          {showNotifications && (
            <div style={{ position: 'absolute', top: '100%', left: '20px', right: '20px', background: '#1e293b', border: '1px solid #334155', borderRadius: '8px', marginTop: '8px', zIndex: 50, maxHeight: '300px', overflowY: 'auto', boxShadow: '0 10px 25px rgba(0,0,0,0.5)' }}>
              {notifications.length === 0 ? (
                <div style={{ padding: '16px', color: '#64748b', textAlign: 'center', fontSize: '0.85rem' }}>No notifications</div>
              ) : (
                notifications.map(n => (
                  <div key={n.id} onClick={() => !n.is_read && handleMarkRead(n.id)} style={{ padding: '12px', borderBottom: '1px solid #334155', cursor: n.is_read ? 'default' : 'pointer', background: n.is_read ? 'transparent' : 'rgba(59, 130, 246, 0.1)' }}>
                    <div style={{ fontSize: '0.85rem', color: n.is_read ? '#cbd5e1' : '#fff', fontWeight: n.is_read ? 400 : 600 }}>{n.message}</div>
                    <div style={{ fontSize: '0.7rem', color: '#64748b', marginTop: '4px' }}>{new Date(n.created_at).toLocaleTimeString()}</div>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
        
        <div className="sidebar-section-title">MAIN MENU</div>
        <nav className="sidebar-nav">
          {navItems.map(item => {
            const destPath = (item.path !== '/' && offeringId) ? `${item.path}?offeringId=${offeringId}` : item.path;
            return (
              <Link 
                key={item.path} 
                to={destPath} 
                className={`nav-link ${location.pathname === item.path ? 'active' : ''}`}
              >
                <svg className="nav-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  {item.icon}
                </svg>
                {item.name}
              </Link>
            )
          })}
        </nav>
        
        <div className="sidebar-footer">
          <div style={{ marginBottom: '16px' }}>
            <button 
              onClick={() => setShowRBAC(true)} 
              style={{
                width: '100%',
                padding: '10px',
                background: 'var(--surface-container-low)',
                border: '1px solid var(--outline-variant)',
                borderRadius: '8px',
                color: 'var(--primary)',
                fontWeight: '600',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px',
                transition: 'all 0.2s'
              }}
              onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--surface-container-highest)'; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = 'var(--surface-container-low)'; }}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                <circle cx="12" cy="7" r="4"></circle>
              </svg>
              Switch Role
            </button>
            {user && (
              <div style={{ textAlign: 'center', marginTop: '8px', fontSize: '0.75rem', color: '#94a3b8' }}>
                Current: <span style={{ color: '#f8fafc', fontWeight: 600 }}>{user.name}</span>
              </div>
            )}
          </div>
          <div style={{ background: 'var(--surface-container-high)', border: '1px solid var(--outline-variant)', borderRadius: '8px', padding: '16px', marginTop: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px', borderBottom: '1px solid var(--border-color)', paddingBottom: '8px' }}>
              <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#10b981', boxShadow: '0 0 8px rgba(16, 185, 129, 0.4)' }}></span>
              <span className="heading-serif" style={{ fontSize: '0.85rem', color: 'var(--text-main)' }}>Active AI Models</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <span className="font-sans" style={{ fontSize: '0.85rem', color: 'var(--text-main)', fontWeight: 600 }}>Claude 3.5 Sonnet</span>
                <span style={{ fontSize: '0.65rem', background: 'var(--primary)', color: 'var(--on-primary)', padding: '2px 6px', borderRadius: '4px', width: 'fit-content' }}>Primary</span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <span className="font-sans" style={{ fontSize: '0.85rem', color: 'var(--text-main)', fontWeight: 600 }}>Gemini 1.5 Pro</span>
                <span style={{ fontSize: '0.65rem', background: 'var(--secondary-container)', color: 'var(--on-secondary-container)', padding: '2px 6px', borderRadius: '4px', width: 'fit-content' }}>Cross-Check</span>
              </div>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="main-wrapper">
        <header style={{ 
          height: '70px', 
          flexShrink: 0,
          borderBottom: '1px solid var(--border-color)', 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'space-between',
          padding: '0 40px',
          background: 'var(--surface-container)',
          position: 'sticky',
          top: 0,
          zIndex: 10
        }}>
          <div style={{ flex: 1, display: 'flex', alignItems: 'center' }}>
            <div style={{ position: 'relative', width: '400px' }}>
              <svg 
                style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} 
                width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
              >
                <circle cx="11" cy="11" r="8"></circle>
                <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
              </svg>
              <input 
                type="text" 
                placeholder="Global search across departments, courses, students..." 
                className="font-sans"
                style={{
                  width: '100%',
                  background: 'var(--surface-container)',
                  border: '1px solid var(--outline-variant)',
                  borderRadius: '6px',
                  padding: '8px 16px 8px 36px',
                  color: 'var(--text-main)',
                  outline: 'none',
                  fontSize: '0.85rem',
                  transition: 'all 0.2s ease'
                }}
                onFocus={e => {
                  e.target.style.background = 'var(--surface-container-high)';
                  e.target.style.borderColor = 'var(--primary)';
                  e.target.style.boxShadow = '0 0 0 2px rgba(192, 193, 255, 0.1)';
                }}
                onBlur={e => {
                  e.target.style.background = 'var(--surface-container)';
                  e.target.style.borderColor = 'var(--outline-variant)';
                  e.target.style.boxShadow = 'none';
                }}
              />
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
            <div className="status-pill success" style={{ textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: 'currentColor', display: 'inline-block', marginRight: '6px' }}></span>
              System Online
            </div>
            {user && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{ width: '32px', height: '32px', borderRadius: '50%', background: 'var(--primary)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 600, color: 'var(--on-primary)', fontSize: '0.8rem' }}>
                  {user.name.charAt(0)}
                </div>
              </div>
            )}
          </div>
        </header>

        <main className="dashboard-content">
          <Outlet />
        </main>
      </div>

      {/* Global Toasts */}
      <div style={{ position: 'fixed', bottom: '24px', right: '24px', zIndex: 9999, display: 'flex', flexDirection: 'column', gap: '12px' }}>
        {toasts.map(t => (
          <div key={t.id} style={{ background: '#1e293b', borderLeft: '4px solid #3b82f6', color: '#f8fafc', padding: '16px 20px', borderRadius: '8px', boxShadow: '0 10px 25px rgba(0,0,0,0.4)', minWidth: '300px', display: 'flex', alignItems: 'center', gap: '12px', animation: 'slideIn 0.3s ease-out forwards' }}>
            <span style={{ fontSize: '1.25rem' }}>🔔</span>
            <div>
              <div style={{ fontSize: '0.9rem', fontWeight: 600 }}>{t.type === 'batch_complete' ? 'Evaluation Complete' : 'New Alert'}</div>
              <div style={{ fontSize: '0.85rem', color: '#cbd5e1' }}>{t.message}</div>
            </div>
          </div>
        ))}
      </div>
      <style>{`
        @keyframes slideIn {
          from { transform: translateX(100%); opacity: 0; }
          to { transform: translateX(0); opacity: 1; }
        }
      `}</style>
    </div>
  )
}
