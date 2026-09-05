import { useState, useEffect } from 'react';
import { AppShell } from './components/layout/AppShell';
import { LandingPage } from './pages/LandingPage';
import { OverviewPage } from './pages/OverviewPage';
import { RecoveryPage } from './pages/RecoveryPage';
import { CaseDetailPage } from './pages/CaseDetailPage';
import { SegmentsPage } from './pages/SegmentsPage';
import { StrategiesPage } from './pages/StrategiesPage';
import { SimulatorPage } from './pages/SimulatorPage';
import { EvidencePage } from './pages/EvidencePage';

export function App() {
  const normalizePath = (rawHash: string): string => {
    if (rawHash && !rawHash.startsWith('#/')) {
      // Same-page section anchors (e.g. #how-it-works, #evidence, #why-nivaran) remain on the landing page ('/')
      return '/';
    }
    let p = rawHash.replace(/^#/, '').split('?')[0];
    if (!p.startsWith('/')) {
      p = '/' + p;
    }
    return p || '/';
  };

  const [currentPath, setCurrentPath] = useState<string>(() => {
    return normalizePath(window.location.hash);
  });

  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    const handleHashChange = () => {
      setCurrentPath(normalizePath(window.location.hash));
    };

    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  const navigate = (path: string) => {
    window.location.hash = path;
    setCurrentPath(normalizePath(path));
  };

  const handleRefreshData = () => {
    setRefreshKey((prev) => prev + 1);
  };

  // Layer 1: Public Landing Page
  if (currentPath === '/' || currentPath === '') {
    return <LandingPage onNavigate={navigate} />;
  }

  // Layer 2: Product Dashboard Experience
  const renderDashboardPage = () => {
    if (currentPath.startsWith('/recovery/')) {
      const caseId = currentPath.replace('/recovery/', '');
      return <CaseDetailPage caseId={caseId} onNavigate={navigate} key={`${caseId}-${refreshKey}`} />;
    }
    if (currentPath === '/recovery') {
      return <RecoveryPage key={`recovery-${refreshKey}`} />;
    }
    if (currentPath === '/segments') {
      return <SegmentsPage key={`segments-${refreshKey}`} />;
    }
    if (currentPath === '/strategies') {
      return <StrategiesPage key={`strategies-${refreshKey}`} />;
    }
    if (currentPath === '/simulator') {
      return <SimulatorPage key={`simulator-${refreshKey}`} />;
    }
    if (currentPath === '/evidence') {
      return <EvidencePage key={`evidence-${refreshKey}`} />;
    }
    // Default dashboard route: /home or /overview
    return <OverviewPage key={`overview-${refreshKey}`} />;
  };

  return (
    <AppShell currentPath={currentPath} onNavigate={navigate} onRefreshData={handleRefreshData}>
      {renderDashboardPage()}
    </AppShell>
  );
}

export default App;
