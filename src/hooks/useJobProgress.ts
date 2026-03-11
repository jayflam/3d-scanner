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
    // Don't open a second connection if one is already live
    if (wsRef.current) return;

    const wsUrl = getWebSocketUrl(assessmentId);
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setState((s) => ({ ...s, isConnected: true }));
    };

    ws.onmessage = (event) => {
      try {
        const update: ProgressUpdate = JSON.parse(event.data);

        // Derive assessment status from stage + progress since backend publishes
        // progress messages without a top-level status field.
        let derivedStatus: AssessmentStatus | null = null;
        const { stage, progress_pct: pct } = update;
        if (stage === "frame_extraction") derivedStatus = "extracting_frames";
        else if (stage === "splatting") derivedStatus = "splatting";
        else if (stage === "analysis") derivedStatus = "analyzing";
        else if (stage === "report_generation") {
          derivedStatus = pct >= 100 ? "complete" : "analyzing";
        }

        setState({
          status: derivedStatus,
          progressPct: pct,
          message: update.message,
          isConnected: true,
        });

        // Invalidate queries when assessment reaches terminal state
        if (derivedStatus === "complete" || derivedStatus === "failed") {
          queryClient.invalidateQueries({ queryKey: ["assessment", assessmentId] });
          queryClient.invalidateQueries({ queryKey: ["damageReport", assessmentId] });
          ws.close();
        }
      } catch {
        // Ignore malformed messages
      }
    };

    ws.onclose = () => {
      // Guard: ignore stale onclose fired after a newer WS was already created
      // (happens in React Strict Mode dev double-mount / rapid reconnect cycles)
      if (wsRef.current !== ws) return;

      wsRef.current = null;
      setState((s) => ({ ...s, isConnected: false }));

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
    // Delay the initial connect by one tick. In React Strict Mode (dev), the
    // effect fires, immediately unmounts, and remounts. Without this delay the
    // WS is created and then closed within milliseconds, generating browser
    // console errors. The timeout is cancelled by the cleanup so the WS is
    // never opened during the "fake" unmount cycle.
    const initTimer = setTimeout(connect, 0);

    return () => {
      clearTimeout(initTimer);
      clearTimeout(reconnectTimer.current);
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect]);

  return state;
}
