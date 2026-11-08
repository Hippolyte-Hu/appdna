"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { getConnections } from "@/lib/task-api";
import type { Connections } from "@/lib/task-types";

const ConnectionContext = createContext<{
  connections: Connections | null;
  connectionError: string;
  refreshConnections: () => Promise<Connections>;
} | null>(null);

export function Providers({ children }: { children: ReactNode }) {
  const [connections, setConnections] = useState<Connections | null>(null);
  const [connectionError, setConnectionError] = useState("");
  const refreshConnections = useCallback(async () => {
    try {
      const next = await getConnections();
      setConnections(next);
      setConnectionError("");
      return next;
    } catch (err) {
      setConnectionError(
        err instanceof Error ? err.message : "Connections could not be loaded.",
      );
      throw err;
    }
  }, []);
  useEffect(() => {
    void refreshConnections().catch(() => {});
  }, [refreshConnections]);
  return (
    <TooltipProvider>
      <ConnectionContext.Provider
        value={{ connections, connectionError, refreshConnections }}
      >
        {children}
      </ConnectionContext.Provider>
      <Toaster position="bottom-right" richColors theme="light" />
    </TooltipProvider>
  );
}

export function useConnections() {
  const value = useContext(ConnectionContext);
  if (!value) throw new Error("Connection context is unavailable");
  return value;
}
