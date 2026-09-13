import { Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import PlaceholderPage from "./pages/PlaceholderPage";
import { NAV_ITEMS } from "./types/navigation";

export default function App() {
  const placeholderItems = NAV_ITEMS.filter((item) => item.path !== "/");

  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        {placeholderItems.map((item) => (
          <Route
            key={item.path}
            path={item.path}
            element={<PlaceholderPage title={item.label} />}
          />
        ))}
      </Route>
    </Routes>
  );
}
