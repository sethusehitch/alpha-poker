"use client";

import { useEffect, useState } from "react";
import { on } from "./uiBus";

export type Session = { username: string; isOperator: boolean } | null;

export function useSession() {
  const [session, setSession] = useState<Session>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    function refresh() {
      fetch("/browser-api/auth/me")
        .then(async (response) => {
          if (cancelled) return;
          if (!response.ok) {
            setSession(null);
            return;
          }
          const result = await response.json();
          if (typeof result.username === "string") {
            setSession({ username: result.username, isOperator: Boolean(result.is_operator) });
          } else {
            setSession(null);
          }
        })
        .catch(() => {
          if (!cancelled) setSession(null);
        })
        .finally(() => {
          if (!cancelled) setLoaded(true);
        });
    }
    refresh();
    const offLogin = on("session-changed", ({ username, isOperator }) => {
      setSession(username ? { username, isOperator } : null);
      setLoaded(true);
    });
    return () => {
      cancelled = true;
      offLogin();
    };
  }, []);

  return { session, loaded };
}
