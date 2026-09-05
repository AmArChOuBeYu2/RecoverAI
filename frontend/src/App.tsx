import { useState, useEffect } from 'react';
import { AppShell } from './components/layout/AppShell';
import { OverviewPage } from './pages/OverviewPage';
import { RecoveryPage } from './pages/RecoveryPage';
import { SegmentsPage } from './pages/SegmentsPage';
import { StrategiesPage } from './pages/StrategiesPage';
import { SimulatorPage } from './pages/SimulatorPage';
import { EvidencePage } from './pages/EvidencePage';

export function App() {
  const [currentPath, setCurrentPath] = useState<string>(() => {
    const hash = window.location.hash.replace('#', '');
    return hash || '/overview';
  });

  useEffect(() => {
    const handleHashChange = () => {
      const hash = window.location.hash.replace('#', '');
      setCurrentPath(hash || '/overview');
    };

    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  const navigate = (path: string) => {
    window.location.hash = path;
    setCurrentPath(path);
  };

  const renderPage = () => {
    if (currentPath === '/recovery') {
      return <RecoveryPage />;
    }
    if (currentPath === '/segments') {
      return <SegmentsPage />;
    }
    if (currentPath === '/strategies') {
      return <StrategiesPage />;
    }
    if (currentPath === '/simulator') {
      return <SimulatorPage />;
    }
    if (currentPath === '/evidence') {
      return <EvidencePage />;
    }
    return <OverviewPage />;
  };

  return (
    <AppShell currentPath={currentPath} onNavigate={navigate}>
      {renderPage()}
    </AppShell>
  );
}

export default App;
