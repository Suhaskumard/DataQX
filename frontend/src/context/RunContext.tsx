import { createContext, useContext, useState, type ReactNode } from "react";

interface RunResults {
  runId: string;
  uploadResult: any;
  analyzeResult: any;
  cleanResult: any;
  validateResult: any;
  issues: any;
  quality: any;
  powerbi: any;
  drift: any;
  lineage: any;
  beforeAfter: any;
  dictionary: any;
}

interface RunContextValue {
  run: RunResults | null;
  setRun: (run: RunResults | null) => void;
}

// Backend is stateless (no server-side session) -- this context is the frontend's
// only notion of "the active run", intentionally not persisted across a reload.
const RunContext = createContext<RunContextValue | undefined>(undefined);

export function RunProvider({ children }: { children: ReactNode }) {
  const [run, setRun] = useState<RunResults | null>(null);
  return <RunContext.Provider value={{ run, setRun }}>{children}</RunContext.Provider>;
}

export function useRun(): RunContextValue {
  const context = useContext(RunContext);
  if (!context) {
    throw new Error("useRun must be used within a RunProvider");
  }
  return context;
}

export type { RunResults };
