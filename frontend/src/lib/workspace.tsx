import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, Organization } from "./api";
import { useAuth } from "./auth";
import { load, save } from "./storage";

const KEY = "dv.currentOrg";

type WorkspaceState = {
  orgs: Organization[];
  current: Organization | null;
  loading: boolean;
  select: (id: string) => void;
  reload: () => Promise<Organization[]>;
};

const WorkspaceContext = createContext<WorkspaceState | null>(null);

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const [orgs, setOrgs] = useState<Organization[]>([]);
  const [currentId, setCurrentId] = useState<string | null>(() => load(KEY));
  // Which user the current list belongs to. Until it matches the signed-in
  // user we are "loading" - this avoids a one-render gap right after login
  // where orgs=[] would wrongly send the user to onboarding.
  const [loadedFor, setLoadedFor] = useState<string | null>(null);
  const [fetching, setFetching] = useState(false);
  const userId = user?.id ?? null;

  const reload = useCallback(async () => {
    if (!userId) { setOrgs([]); setLoadedFor(null); return []; }
    setFetching(true);
    try {
      const list = await api<Organization[]>("/organizations/");
      setOrgs(list);
      return list;
    } catch {
      setOrgs([]);
      return [];
    } finally {
      setLoadedFor(userId);
      setFetching(false);
    }
  }, [userId]);

  const loading = userId !== null && (loadedFor !== userId || (fetching && orgs.length === 0));

  useEffect(() => { void reload(); }, [reload]);

  const current = useMemo(
    () => orgs.find((o) => o.id === currentId) ?? orgs[0] ?? null,
    [orgs, currentId],
  );

  const select = (id: string) => { setCurrentId(id); save(KEY, id); };

  return (
    <WorkspaceContext.Provider value={{ orgs, current, loading, select, reload }}>
      {children}
    </WorkspaceContext.Provider>
  );
}

export function useWorkspace(): WorkspaceState {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) throw new Error("useWorkspace must be used inside WorkspaceProvider");
  return ctx;
}
