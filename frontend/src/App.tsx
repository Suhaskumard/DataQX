import { Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import { RunProvider } from "./context/RunContext";
import BeforeAfter from "./pages/BeforeAfter";
import CleaningActions from "./pages/CleaningActions";
import Dashboard from "./pages/Dashboard";
import DataDictionaryPage from "./pages/DataDictionaryPage";
import DataDriftPage from "./pages/DataDriftPage";
import DataLineagePage from "./pages/DataLineagePage";
import DataQuality from "./pages/DataQuality";
import DatasetOverview from "./pages/DatasetOverview";
import PowerBIReadinessPage from "./pages/PowerBIReadinessPage";
import ReportsDownloads from "./pages/ReportsDownloads";
import Upload from "./pages/Upload";

export default function App() {
  return (
    <RunProvider>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/upload" element={<Upload />} />
          <Route path="/dataset-overview" element={<DatasetOverview />} />
          <Route path="/data-quality" element={<DataQuality />} />
          <Route path="/cleaning-actions" element={<CleaningActions />} />
          <Route path="/before-after" element={<BeforeAfter />} />
          <Route path="/lineage" element={<DataLineagePage />} />
          <Route path="/drift" element={<DataDriftPage />} />
          <Route path="/powerbi-readiness" element={<PowerBIReadinessPage />} />
          <Route path="/data-dictionary" element={<DataDictionaryPage />} />
          <Route path="/reports" element={<ReportsDownloads />} />
        </Route>
      </Routes>
    </RunProvider>
  );
}
