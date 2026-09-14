import type { LucideIcon } from "lucide-react";
import {
  LayoutDashboard,
  UploadCloud,
  Table2,
  ShieldCheck,
  Wrench,
  CheckSquare,
  GitCompare,
  ClipboardList,
  Workflow,
  Activity,
  BarChart3,
  BookOpen,
  FolderDown,
} from "lucide-react";

export interface NavItem {
  path: string;
  label: string;
  icon: LucideIcon;
  group: string;
}

// Grouped to communicate the real DataQX workflow (Profile -> Detect -> Clean ->
// Validate -> Govern -> Analytics Ready -> Export) instead of one flat list.
export const NAV_ITEMS: NavItem[] = [
  { path: "/", label: "Dashboard", icon: LayoutDashboard, group: "Workspace" },
  { path: "/upload", label: "Upload Dataset", icon: UploadCloud, group: "Workspace" },
  { path: "/dataset-overview", label: "Dataset Overview", icon: Table2, group: "Workspace" },
  { path: "/data-quality", label: "Data Quality", icon: ShieldCheck, group: "Quality" },
  { path: "/cleaning-actions", label: "Cleaning Actions", icon: Wrench, group: "Quality" },
  { path: "/validation", label: "Validation", icon: CheckSquare, group: "Quality" },
  { path: "/before-after", label: "Before vs After", icon: GitCompare, group: "Trust" },
  { path: "/audit", label: "Audit", icon: ClipboardList, group: "Trust" },
  { path: "/lineage", label: "Data Lineage", icon: Workflow, group: "Trust" },
  { path: "/drift", label: "Data Drift", icon: Activity, group: "Trust" },
  { path: "/analytics-readiness", label: "Analytics Readiness", icon: BarChart3, group: "Analytics" },
  { path: "/data-dictionary", label: "Data Dictionary", icon: BookOpen, group: "Analytics" },
  { path: "/reports", label: "Reports & Downloads", icon: FolderDown, group: "Output" },
];

export const NAV_GROUPS = ["Workspace", "Quality", "Trust", "Analytics", "Output"] as const;
