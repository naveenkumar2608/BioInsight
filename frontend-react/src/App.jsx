import { useState, useEffect } from 'react';
import axios from 'axios';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Login from './components/Login';
import Signup from './components/Signup';
import Chat from './components/Chat';
import './index.css';

function App() {
  const [loading, setLoading] = useState(true);
  const [token, setToken] = useState(() => {
    const saved = localStorage.getItem('token');
    return (saved && saved !== 'undefined' && saved !== 'null') ? saved : null;
  });

  // Configure Axios Defaults
  useEffect(() => {
    // We use the Vite proxy for /api and /auth
    if (token) {
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
    } else {
      delete axios.defaults.headers.common['Authorization'];
    }
  }, [token]);

  // Initial Token Verification
  useEffect(() => {
    const verifyToken = async () => {
      const savedToken = localStorage.getItem('token');
      if (savedToken && savedToken !== 'undefined' && savedToken !== 'null') {
        try {
          // Verify token with backend
          await axios.get('/auth/me', {
            headers: { Authorization: `Bearer ${savedToken}` },
            timeout: 5000 // Fast timeout for initial check
          });
          // Verification success - token is already in state from initializer
        } catch (err) {
          console.warn('Initial session verification failed or timed out. Proceeding as logged out.');
          if (err.response?.status === 401 || err.code === 'ECONNABORTED') {
            handleLogout();
          }
        }
      }
      setLoading(false);
    };

    verifyToken();
  }, []);

  // Sync token across tabs
  useEffect(() => {
    const handleStorageChange = (e) => {
      if (e.key === 'token') {
        if (!e.newValue || e.newValue === 'null' || e.newValue === 'undefined') {
          setToken(null);
        } else {
          setToken(e.newValue);
        }
      }
    };
    window.addEventListener('storage', handleStorageChange);
    return () => window.removeEventListener('storage', handleStorageChange);
  }, []);

  const handleLogout = () => {
    setToken(null);
    localStorage.removeItem('token');
    delete axios.defaults.headers.common['Authorization'];
  };

  // Global Axios Interceptor for 401s
  useEffect(() => {
    const interceptor = axios.interceptors.response.use(
      (response) => response,
      (error) => {
        const isAuthRequest = error.config?.url?.includes('/auth/login') || error.config?.url?.includes('/auth/signup');

        // If the server explicitly says 401 and it's NOT a login/signup attempt, clear the session
        if (error.response?.status === 401 && !isAuthRequest) {
          console.warn('Session expired or unauthorized. Logging out...');
          handleLogout();
        }
        return Promise.reject(error);
      }
    );
    return () => axios.interceptors.response.eject(interceptor);
  }, []);

  if (loading) {
    return (
      <div className="loading-screen">
        <div className="spinner"></div>
        <p>Verifying session...</p>
      </div>
    );
  }

  return (
    <Router>
      <Routes>
        <Route
          path="/"
          element={!token ? <Login setToken={setToken} /> : <Navigate to="/chat" />}
        />
        <Route
          path="/login"
          element={!token ? <Login setToken={setToken} /> : <Navigate to="/chat" />}
        />
        <Route
          path="/signup"
          element={!token ? <Signup /> : <Navigate to="/chat" />}
        />
        <Route
          path="/chat"
          element={token ? <Chat token={token} onLogout={handleLogout} /> : <Navigate to="/" />}
        />
        <Route
          path="/c/:sessionId"
          element={token ? <Chat token={token} onLogout={handleLogout} /> : <Navigate to="/" />}
        />
      </Routes>
    </Router>
  );
}

export default App;
