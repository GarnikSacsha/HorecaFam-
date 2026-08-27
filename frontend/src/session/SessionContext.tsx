import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { ApiError, apiClient, type ApiClient } from "../api/client";
import type { SessionResponse } from "../api/contracts";

type SessionStatus = "bootstrapping" | "anonymous" | "authenticated" | "error";

interface SessionContextValue {
  client: ApiClient;
  session: SessionResponse | null;
  status: SessionStatus;
  clearSession: () => void;
  refreshSession: () => Promise<void>;
  setSession: (session: SessionResponse) => void;
}

const SessionContext = createContext<SessionContextValue | null>(null);

export function SessionProvider({
  children,
  client = apiClient,
}: {
  children: React.ReactNode;
  client?: ApiClient;
}) {
  const [session, updateSession] = useState<SessionResponse | null>(null);
  const [status, setStatus] = useState<SessionStatus>("bootstrapping");

  const refreshSession = useCallback(async () => {
    setStatus("bootstrapping");
    try {
      const nextSession = await client.getSession();
      updateSession(nextSession);
      setStatus("authenticated");
    } catch (error) {
      updateSession(null);
      if (
        (error instanceof ApiError || (error && typeof error === "object")) &&
        "status" in error
      ) {
        if ((error as { status?: unknown }).status === 401) {
          setStatus("anonymous");
          return;
        }
      }
      setStatus("error");
    }
  }, [client]);

  useEffect(() => {
    let active = true;
    client
      .getSession()
      .then((nextSession) => {
        if (!active) return;
        updateSession(nextSession);
        setStatus("authenticated");
      })
      .catch((error: unknown) => {
        if (!active) return;
        updateSession(null);
        if (
          (error instanceof ApiError || (error && typeof error === "object")) &&
          "status" in error &&
          (error as { status?: unknown }).status === 401
        ) {
          setStatus("anonymous");
        } else {
          setStatus("error");
        }
      });
    return () => {
      active = false;
    };
  }, [client]);

  const value = useMemo<SessionContextValue>(
    () => ({
      client,
      session,
      status,
      clearSession: () => {
        updateSession(null);
        setStatus("anonymous");
      },
      refreshSession,
      setSession: (nextSession) => {
        updateSession(nextSession);
        setStatus("authenticated");
      },
    }),
    [client, refreshSession, session, status],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionContextValue {
  const context = useContext(SessionContext);
  if (!context) throw new Error("useSession must be used inside SessionProvider");
  return context;
}
