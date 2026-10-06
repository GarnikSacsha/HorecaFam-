import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { ApiError, apiClient, type ApiClient } from "../api/client";
import type { SessionResponse } from "../api/contracts";

type SessionStatus = "bootstrapping" | "anonymous" | "authenticated" | "error";

interface SessionContextValue {
  client: ApiClient;
  session: SessionResponse | null;
  status: SessionStatus;
  sessionNotice: string | null;
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
  const [sessionNotice, setSessionNotice] = useState<string | null>(null);
  const sessionRef = useRef<SessionResponse | null>(null);

  const scopedClient = useMemo<ApiClient>(
    () => ({
      getSession: () => client.getSession(),
      request: async (path, ...options) => {
        const requestSession = sessionRef.current;
        try {
          return await client.request(path, ...options);
        } catch (error) {
          // Відповідь старої сесії не повинна завершувати новий вхід користувача.
          if (
            error instanceof ApiError &&
            error.status === 401 &&
            !path.startsWith("/auth/") &&
            requestSession &&
            sessionRef.current === requestSession
          ) {
            sessionRef.current = null;
            updateSession(null);
            setStatus("anonymous");
            setSessionNotice(
              "Сесію завершено або відкликано. Увійдіть знову; якщо доступ вимкнено, зверніться до адміністратора.",
            );
          }
          throw error;
        }
      },
    }),
    [client],
  );

  const refreshSession = useCallback(async () => {
    setStatus("bootstrapping");
    try {
      const nextSession = await client.getSession();
      sessionRef.current = nextSession;
      updateSession(nextSession);
      setStatus("authenticated");
    } catch (error) {
      sessionRef.current = null;
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
        sessionRef.current = nextSession;
        updateSession(nextSession);
        setStatus("authenticated");
      })
      .catch((error: unknown) => {
        if (!active) return;
        sessionRef.current = null;
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
      sessionRef.current = null;
    };
  }, [client]);

  const value = useMemo<SessionContextValue>(
    () => ({
      client: scopedClient,
      session,
      status,
      sessionNotice,
      clearSession: () => {
        sessionRef.current = null;
        setSessionNotice(null);
        updateSession(null);
        setStatus("anonymous");
      },
      refreshSession,
      setSession: (nextSession) => {
        sessionRef.current = nextSession;
        setSessionNotice(null);
        updateSession(nextSession);
        setStatus("authenticated");
      },
    }),
    [scopedClient, refreshSession, session, status, sessionNotice],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionContextValue {
  const context = useContext(SessionContext);
  if (!context) throw new Error("useSession must be used inside SessionProvider");
  return context;
}
