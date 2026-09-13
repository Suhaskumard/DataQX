import { Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import { RunProvider } from "./context/RunContext";
import Dashboard from "./pages/Dashboard";
import PlaceholderPage from "./pages/PlaceholderPage";
import Upload from "./pages/Upload";
import { NAV_ITEMS } from "./types/navigation";

export default function App() {
  const placeholderItems = NAV_ITEMS.filter((item) => item.path !== "/" && item.path !== "/upload");

  return (
    <RunProvider>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/upload" element={<Upload />} />
          {placeholderItems.map((item) => (
            <Route
              key={item.path}
              path={item.path}
              element={<PlaceholderPage title={item.label} />}
            />
          ))}
        </Route>
      </Routes>
    </RunProvider>
  );
}
