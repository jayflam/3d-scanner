import { useEffect, useRef, useState, useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { getWebSocketUrl } from "../lib/api-client";
import type { AssessmentStatus, ProgressUpdate } from "../lib/api-types";

interface JobProgressState {
  status: AssessmentStatus | null;
  progressPct: number;
  message: string;
  isConnected: boolean;
}

export default function useJobProgress(assessmentId: string | undefined): JobProgressState {
  const queryClient = useQueryClient();
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>();
  const [state, setState] = useState<JobProgressState>({
    status: null,
    progressPct: 0,
    message: "",
    isConnected: false,
  });

  const connect = useCallback(() => {
    if (!assessmentId) return;

    const wsUrl = getWebSocketUrl(assessmentId);
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setState((s) => ({ ...s, isConnected: true }));
    };

    ws.onmessage = (event) => {
      try {
        const update: ProgressUpdate = JSON.parse(event.data);
        setState({
          status: update.status,
          progressPct: update.progress_pct,
          message: update.message,
          isConnected: true,
        });

        // Invalidate queries when assessment reaches terminal state
        if (update.status === "complete" || update.status === "failed") {
          queryClient.invalidateQueries({ queryKey: ["assessment", assessmentId] });
          queryClient.invalidateQueries({ queryKey: ["damageReport", assessmentId] });
          ws.close();
        }
      } catch {
        // Ignore malformed messages
      }
    };

    ws.onclose = () => {
      setState((s) => ({ ...s, isConnected: false }));
      wsRef.current = null;

      // Auto-reconnect after 3s unless terminal
      setState((s) => {
        if (s.status !== "complete" && s.status !== "failed") {
          reconnectTimer.current = setTimeout(connect, 3000);
        }
        return s;
      });
    };

    ws.onerror = () => {
      ws.close();
    };
  }, [assessmentId, queryClient]);

  useEffect(() => {
    connect();

    return () => {
      clearTimeout(reconnectTimer.current);
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect]);

  return state;
}
