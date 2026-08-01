import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { API_URL } from '../api';

export default function RBACModal({ onClose }) {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const { login, user } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    fetch(`${API_URL}/auth/users`)
      .then(res => res.json())
      .then(data => {
        setUsers(data);
        setLoading(false);
      })
      .catch(err => {
        console.error("Failed to load mock users", err);
        setLoading(false);
      });
  }, []);

  const handleLogin = async (username) => {
    try {
      await login(username);
      if (onClose) onClose();
      if (window.location.pathname === '/') {
        navigate('/dashboard');
      }
    } catch (err) {
      alert(err.message);
    }
  };

  const getRoleIcon = (role) => {
    switch (role) {
      case 'admin': return '🛡️';
      case 'exam_coordinator': return '📋';
      case 'evaluator': return '✍️';
      case 'read_only': return '👁️';
      case 'student': return '🎓';
      default: return '👤';
    }
  };

  const getRoleDescription = (role) => {
    switch (role) {
      case 'admin': return 'Full system access & settings';
      case 'exam_coordinator': return 'Manage rubrics & class offerings';
      case 'evaluator': return 'Review & override AI grading';
      case 'read_only': return 'View dashboard & analytics';
      case 'student': return 'View own results';
      default: return 'Basic access';
    }
  };

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'rgba(0, 0, 0, 0.75)',
      backdropFilter: 'blur(8px)',
      color: '#f8fafc',
      fontFamily: 'Inter, system-ui, sans-serif',
      zIndex: 9999
    }}>
      <div style={{
        padding: '48px',
        width: '100%',
        maxWidth: '500px',
        background: 'rgba(24, 24, 27, 0.85)',
        border: '1px solid rgba(255,255,255,0.1)',
        borderRadius: '24px',
        boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.7)',
        position: 'relative'
      }}>
        {user && onClose && (
          <button
            onClick={onClose}
            style={{
              position: 'absolute',
              top: '24px',
              right: '24px',
              background: 'transparent',
              border: 'none',
              color: '#94a3b8',
              cursor: 'pointer',
              fontSize: '1.5rem',
              padding: '4px'
            }}
          >
            &times;
          </button>
        )}

        <div style={{ textAlign: 'center', marginBottom: '40px' }}>
          <div style={{
            width: '64px',
            height: '64px',
            background: 'linear-gradient(135deg, #6366f1, #a855f7)',
            borderRadius: '16px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            margin: '0 auto 20px',
            boxShadow: '0 10px 25px rgba(99, 102, 241, 0.5)'
          }}>
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2L2 7l10 5 10-5-10-5z"></path>
              <path d="M2 17l10 5 10-5"></path>
              <path d="M2 12l10 5 10-5"></path>
            </svg>
          </div>
          <h2 style={{ margin: '0 0 12px 0', fontSize: '1.75rem', fontWeight: '800', background: 'linear-gradient(to right, #fff, #94a3b8)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
            Welcome Back
          </h2>
          <p style={{ margin: 0, color: '#94a3b8', fontSize: '0.95rem' }}>Select your mock persona to continue into the system.</p>
        </div>

        {loading ? (
          <div style={{ textAlign: 'center', padding: '40px 0' }}>
            <div className="spinner" style={{ margin: '0 auto' }}></div>
            <p style={{ color: '#94a3b8', marginTop: '16px' }}>Loading mock environment...</p>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {users.map(u => (
              <button
                key={u.id}
                onClick={() => handleLogin(u.username)}
                className="role-select-btn"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  padding: '16px 20px',
                  background: user?.username === u.username ? 'rgba(99, 102, 241, 0.15)' : 'rgba(255, 255, 255, 0.03)',
                  border: '1px solid',
                  borderColor: user?.username === u.username ? 'rgba(99, 102, 241, 0.4)' : 'rgba(255, 255, 255, 0.08)',
                  borderRadius: '16px',
                  cursor: 'pointer',
                  textAlign: 'left',
                  transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
                  gap: '16px'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = user?.username === u.username ? 'rgba(99, 102, 241, 0.25)' : 'rgba(255, 255, 255, 0.08)';
                  e.currentTarget.style.borderColor = user?.username === u.username ? 'rgba(99, 102, 241, 0.6)' : 'rgba(255, 255, 255, 0.2)';
                  e.currentTarget.style.transform = 'translateY(-2px)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = user?.username === u.username ? 'rgba(99, 102, 241, 0.15)' : 'rgba(255, 255, 255, 0.03)';
                  e.currentTarget.style.borderColor = user?.username === u.username ? 'rgba(99, 102, 241, 0.4)' : 'rgba(255, 255, 255, 0.08)';
                  e.currentTarget.style.transform = 'translateY(0)';
                }}
              >
                <div style={{ fontSize: '1.8rem', background: 'rgba(255,255,255,0.05)', padding: '12px', borderRadius: '12px' }}>
                  {getRoleIcon(u.role)}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px', gap: '8px' }}>
                    <span style={{ fontWeight: 700, fontSize: '1.05rem', color: '#f8fafc', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{u.name}</span>
                    <span style={{
                      background: 'rgba(99, 102, 241, 0.15)',
                      color: '#818cf8',
                      padding: '4px 10px',
                      borderRadius: '20px',
                      fontSize: '0.65rem',
                      fontWeight: 700,
                      textTransform: 'uppercase',
                      letterSpacing: '0.05em',
                      whiteSpace: 'nowrap',
                      flexShrink: 0
                    }}>
                      {u.role === 'exam_coordinator' ? 'coordinator' : u.role.replace('_', ' ')}
                    </span>
                  </div>
                  <div style={{ fontSize: '0.85rem', color: '#94a3b8', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {getRoleDescription(u.role)}
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
