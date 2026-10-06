import { useCallback, useEffect, useState } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { AdminDashboard } from './pages/AdminDashboard';
import { LoginPage } from './pages/LoginPage';
import { AppUser } from './types';
import * as api from './services/api';

function AdminRoute({ user, onLogout }: { user: AppUser; onLogout: () => void }) {
  return <AdminDashboard user={user} onLogout={onLogout} />;
}

function App() {
  const [user, setUser] = useState<AppUser | null>(null);
  const [checking, setChecking] = useState(true);

  const logout = useCallback(async () => {
    await api.logout();
    setUser(null);
  }, []);

  useEffect(() => {
    if (!api.getToken()) {
      setChecking(false);
      return;
    }
    api
      .me()
      .then(setUser)
      .catch(() => api.setToken(null))
      .finally(() => setChecking(false));
  }, []);

  if (checking) {
    return (
      <div className="min-h-screen bg-cream flex items-center justify-center">
        <p className="text-sm text-ink-mute">Loading Waste Watch…</p>
      </div>
    );
  }

  return (
    <Routes>
      <Route
        path="/login"
        element={user ? <Navigate to="/admin" replace /> : <LoginPage onLoggedIn={setUser} />}
      />
      <Route
        path="/admin"
        element={user ? <AdminRoute user={user} onLogout={logout} /> : <Navigate to="/login" replace />}
      />
      <Route
        path="/admin/*"
        element={user ? <AdminRoute user={user} onLogout={logout} /> : <Navigate to="/login" replace />}
      />
      <Route path="/" element={<Navigate to={user ? '/admin' : '/login'} replace />} />
      <Route path="*" element={<Navigate to={user ? '/admin' : '/login'} replace />} />
    </Routes>
  );
}

export default App;
