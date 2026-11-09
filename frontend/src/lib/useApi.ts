import { useCallback, useEffect, useRef, useState } from "react";
import { api, errorText } from "./api";

/** GET a resource; re-fetches when `path` changes. Pass null to skip. */
export function useApi<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(!!path);
  const seq = useRef(0);
  const reload = useCallback(async () => {
    if (!path) return;
    const n = ++seq.current;
    setLoading(true);
    try {
      const d = await api<T>(path);
      if (n === seq.current) { setData(d); setError(""); }
    } catch (e) {
      if (n === seq.current) setError(errorText(e));
    } finally {
      if (n === seq.current) setLoading(false);
    }
  }, [path]);
  useEffect(() => { setData(null); void reload(); }, [reload]);
  return { data, error, loading, reload, setData };
}
