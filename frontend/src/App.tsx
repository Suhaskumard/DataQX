import { Routes, Route } from "react-router-dom";
import ErrorBoundary from "./components/ErrorBoundary";
import Layout from "./components/Layout";
import { RunProvider } from "./context/RunContext";
import { ThemeProvider } from "./context/ThemeContext";
import AnalyticsReadinessPage from "./pages/AnalyticsReadinessPage";
import AuditPage from "./pages/AuditPage";
import BeforeAfter from "./pages/BeforeAfter";
import CleaningActions from "./pages/CleaningActions";
import Dashboard from "./pages/Dashboard";
import DataDictionaryPage from "./pages/DataDictionaryPage";
import DataDriftPage from "./pages/DataDriftPage";
import DataLineagePage from "./pages/DataLineagePage";
import DataQuality from "./pages/DataQuality";
import DatasetOverview from "./pages/DatasetOverview";
import NotFound from "./pages/NotFound";
import ReportsDownloads from "./pages/ReportsDownloads";
import Upload from "./pages/Upload";
import ValidationPage from "./pages/ValidationPage";

export default function App() {
  return (
    <ThemeProvider>
      <RunProvider>
        <ErrorBoundary>
          <Routes>
            <Route element={<Layout />}>
              <Route path="/" element={<Dashboard />} />
              <Route path="/upload" element={<Upload />} />
              <Route path="/dataset-overview" element={<DatasetOverview />} />
              <Route path="/data-quality" element={<DataQuality />} />
              <Route path="/cleaning-actions" element={<CleaningActions />} />
              <Route path="/validation" element={<ValidationPage />} />
              <Route path="/before-after" element={<BeforeAfter />} />
              <Route path="/audit" element={<AuditPage />} />
              <Route path="/lineage" element={<DataLineagePage />} />
              <Route path="/drift" element={<DataDriftPage />} />
              <Route path="/analytics-readiness" element={<AnalyticsReadinessPage />} />
              <Route path="/data-dictionary" element={<DataDictionaryPage />} />
              <Route path="/reports" element={<ReportsDownloads />} />
              <Route path="*" element={<NotFound />} />
            </Route>
          </Routes>
        </ErrorBoundary>
      </RunProvider>
    </ThemeProvider>
  );
}
