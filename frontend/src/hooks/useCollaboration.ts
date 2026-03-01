"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "@/hooks/useAuth";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const WS_BASE = API_BASE.replace(/^http/, "ws");

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type CollabMessageType =
  | "connected"
  | "heartbeat_ack"
  | "cell_change"
  | "cursor_move"
  | "presence_join"
  | "presence_leave"
  | "error";

export interface CollabMessage {
  type: CollabMessageType;
  session_id?: string;
  user_id?: string;
  user_full_name?: string;
  payload?: Record<string, unknown>;
}

export interface RemoteCursorState {
  userId: string;
  userFullName: string | null;
  cellRef: string | null;
  sessionId: string;
}

export interface RemotePresence {
  userId: string;
  userFullName: string | null;
  sessionId: string;
}

export type CellChangeHandler = (
  payload: Record<string, unknown>,
  senderId: string
) => void;

export interface UseCollaborationOptions {
  modelId: string;
  /** Called when a remote cell_change event is received. */
  onCellChange?: CellChangeHandler;
  /** Reconnect delay in ms. Defaults to 3000. */
  reconnectDelayMs?: number;
  /** Heartbeat interval in ms. Defaults to 30000. */
  heartbeatIntervalMs?: number;
}

export interface UseCollaborationReturn {
  /** Whether the WebSocket connection is currently open. */
  isConnected: boolean;
  /** Our own session ID assigned by the server. */
  sessionId: string | null;
  /** Remote users currently in the model. */
  remotePresence: RemotePresence[];
  /** Remote cursor positions. */
  remoteCursors: RemoteCursorState[];
  /** Send a cell change event to all collaborators. */
  sendCellChange: (payload: Record<string, unknown>) => void;
  /** Send a cursor move event. */
  sendCursorMove: (cellRef: string | null) => void;
  /** Manually disconnect. */
  disconnect: () => void;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useCollaboration({
  modelId,
  onCellChange,
  reconnectDelayMs = 3000,
  heartbeatIntervalMs = 30000,
}: UseCollaborationOptions): UseCollaborationReturn {
  const { token } = useAuth();

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const heartbeatTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const shouldReconnectRef = useRef(true);
  const isMountedRef = useRef(true);

  const [isConnected, setIsConnected] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [remotePresence, setRemotePresence] = useState<RemotePresence[]>([]);
  const [remoteCursors, setRemoteCursors] = useState<RemoteCursorState[]>([]);

  // ---------------------------------------------------------------------------
  // Connection lifecycle
  // ---------------------------------------------------------------------------

  const connect = useCallback(() => {
    if (!token || !modelId) return;
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) return;

    const url = `${WS_BASE}/ws/models/${modelId}?token=${encodeURIComponent(token)}`;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      if (!isMountedRef.current) return;
      setIsConnected(true);

      // Start heartbeat
      if (heartbeatTimerRef.current) clearInterval(heartbeatTimerRef.current);
      heartbeatTimerRef.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: "heartbeat" }));
        }
      }, heartbeatIntervalMs);
    };

    ws.onmessage = (event: MessageEvent) => {
      if (!isMountedRef.current) return;
      let msg: CollabMessage;
      try {
        msg = JSON.parse(event.data as string) as CollabMessage;
      } catch {
        return;
      }

      if (msg.type === "connected") {
        if (msg.session_id) setSessionId(msg.session_id);

      } else if (msg.type === "presence_join") {
        if (msg.user_id && msg.session_id) {
          setRemotePresence((prev) => {
            const filtered = prev.filter((p) => p.sessionId !== msg.session_id);
            return [
              ...filtered,
              {
                userId: msg.user_id!,
                userFullName: msg.user_full_name ?? null,
                sessionId: msg.session_id!,
              },
            ];
          });
        }

      } else if (msg.type === "presence_leave") {
        if (msg.session_id) {
          setRemotePresence((prev) =>
            prev.filter((p) => p.sessionId !== msg.session_id)
          );
          setRemoteCursors((prev) =>
            prev.filter((c) => c.sessionId !== msg.session_id)
          );
        }

      } else if (msg.type === "cursor_move") {
        if (msg.user_id && msg.session_id) {
          const cellRef =
            (msg.payload?.cell_ref as string | null | undefined) ?? null;
          setRemoteCursors((prev) => {
            const filtered = prev.filter((c) => c.sessionId !== msg.session_id);
            return [
              ...filtered,
              {
                userId: msg.user_id!,
                userFullName: msg.user_full_name ?? null,
                cellRef,
                sessionId: msg.session_id!,
              },
            ];
          });
        }

      } else if (msg.type === "cell_change") {
        if (onCellChange && msg.user_id && msg.payload) {
          onCellChange(msg.payload, msg.user_id);
        }
      }
    };

    ws.onerror = () => {
      // Will be followed by onclose
    };

    ws.onclose = () => {
      if (!isMountedRef.current) return;
      setIsConnected(false);
      if (heartbeatTimerRef.current) {
        clearInterval(heartbeatTimerRef.current);
        heartbeatTimerRef.current = null;
      }
      if (shouldReconnectRef.current) {
        reconnectTimerRef.current = setTimeout(() => {
          connect();
        }, reconnectDelayMs);
      }
    };
  }, [token, modelId, onCellChange, reconnectDelayMs, heartbeatIntervalMs]);

  // ---------------------------------------------------------------------------
  // Mount / unmount
  // ---------------------------------------------------------------------------

  useEffect(() => {
    isMountedRef.current = true;
    shouldReconnectRef.current = true;
    connect();

    return () => {
      isMountedRef.current = false;
      shouldReconnectRef.current = false;
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      if (heartbeatTimerRef.current) clearInterval(heartbeatTimerRef.current);
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [modelId, token]);

  // ---------------------------------------------------------------------------
  // Public API
  // ---------------------------------------------------------------------------

  const sendCellChange = useCallback(
    (payload: Record<string, unknown>) => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: "cell_change", payload }));
      }
    },
    []
  );

  const sendCursorMove = useCallback((cellRef: string | null) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({ type: "cursor_move", payload: { cell_ref: cellRef } })
      );
    }
  }, []);

  const disconnect = useCallback(() => {
    shouldReconnectRef.current = false;
    if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
    if (heartbeatTimerRef.current) clearInterval(heartbeatTimerRef.current);
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setIsConnected(false);
  }, []);

  return {
    isConnected,
    sessionId,
    remotePresence,
    remoteCursors,
    sendCellChange,
    sendCursorMove,
    disconnect,
  };
}
