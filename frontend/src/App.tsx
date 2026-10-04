import { Routes, Route, Outlet, useLocation } from 'react-router-dom';
import { useEffect } from 'react';
import { PublicNav } from './components/PublicNav';
import { LandingPage } from './pages/LandingPage';
import { ReportPage } from './pages/ReportPage';
import { ServicesPage } from './pages/ServicesPage';
import { MarketPage } from './pages/MarketPage';
import { CollectorPage } from './pages/CollectorPage';
import { AdminDashboard } from './pages/AdminDashboard';

function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);
  return null;
}

function PublicLayout() {
  return (
    <div className="min-h-screen bg-cream">
      <PublicNav />
      <main>
        <Outlet />
      </main>
      <footer className="border-t border-earth-100 bg-white">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-2 px-4 py-6 text-xs text-ink-mute sm:flex-row">
          <p>Waste Watch · Bamenda Municipality — a cleaner city, a fairer waste economy.</p>
          <p>
            Report waste · Vendors buy · Collectors earn
          </p>
        </div>
      </footer>
    </div>
  );
}

function App() {
  return (
    <>
      <ScrollToTop />
      <Routes>
        <Route element={<PublicLayout />}>
          <Route path="/" element={<LandingPage />} />
          <Route path="/report" element={<ReportPage />} />
          <Route path="/services" element={<ServicesPage />} />
          <Route path="/market" element={<MarketPage />} />
          <Route path="/collector" element={<CollectorPage />} />
        </Route>
        <Route path="/admin" element={<AdminDashboard />} />
        <Route path="/admin/*" element={<AdminDashboard />} />
        <Route path="*" element={<LandingPage />} />
      </Routes>
    </>
  );
}

export default App;
