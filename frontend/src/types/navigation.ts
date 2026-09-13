export interface NavItem {
  path: string;
  label: string;
}

// The 11 main pages from DATAQX.pdf S45.
export const NAV_ITEMS: NavItem[] = [
  { path: "/", label: "Dashboard" },
  { path: "/upload", label: "Upload Dataset" },
  { path: "/dataset-overview", label: "Dataset Overview" },
  { path: "/data-quality", label: "Data Quality" },
  { path: "/cleaning-actions", label: "Cleaning Actions" },
  { path: "/before-after", label: "Before vs After" },
  { path: "/lineage", label: "Data Lineage" },
  { path: "/drift", label: "Data Drift" },
  { path: "/powerbi-readiness", label: "Power BI Readiness" },
  { path: "/data-dictionary", label: "Data Dictionary" },
  { path: "/reports", label: "Reports & Downloads" },
];
