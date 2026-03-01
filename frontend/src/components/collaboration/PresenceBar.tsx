"use client";

import { useEffect, useState, useCallback } from "react";
import { useAuth } from "@/hooks/useAuth";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// Deterministic color palette for user avatars
const AVATAR_COLORS = [
  "bg-blue-500",
  "bg-green-500",
  "bg-purple-500",
  "bg-orange-500",
  "bg-pink-500",
  "bg-teal-500",
  "bg-red-500",
  "bg-indigo-500",
];

function getColorForUser(userId: string): string {
  let hash = 0;
  for (let i = 0; i < userId.length; i++) {
    hash = (hash * 31 + userId.charCodeAt(i)) >>> 0;
  }
  return AVATAR_COLORS[hash % AVATAR_COLORS.length];
}

function getInitials(fullName: string): string {
  const parts = fullName.trim().split(/\s+/);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].charAt(0).toUpperCase();
  return (
    parts[0].charAt(0).toUpperCase() +
    parts[parts.length - 1].charAt(0).toUpperCase()
  );
}

export interface PresenceUser {
  id: string;
  user_id: string;
  user_full_name: string | null;
  user_email: string | null;
  cursor_cell: string | null;
  last_heartbeat: string;
}

interface PresenceBarProps {
  modelId: string;
  moduleId?: string;
  /** Poll interval in milliseconds. Defaults to 10000 (10s). */
  pollIntervalMs?: number;
}

/**
 * PresenceBar displays colored avatar circles for each active user in a model.
 * Polls the /models/{modelId}/presence REST endpoint every 10 seconds.
 */
export function PresenceBar({
  modelId,
  moduleId,
  pollIntervalMs = 10000,
}: PresenceBarProps) {
  const { token } = useAuth();
  const [users, setUsers] = useState<PresenceUser[]>([]);
  const [tooltip, setTooltip] = useState<string | null>(null);
  const [tooltipUserId, setTooltipUserId] = useState<string | null>(null);

  const fetchPresence = useCallback(async () => {
    if (!token) return;
    try {
      const params = new URLSearchParams();
      if (moduleId) params.set("module_id", moduleId);
      const url =
        `${API_BASE}/models/${modelId}/presence` +
        (params.toString() ? `?${params.toString()}` : "");
      const res = await fetch(url, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) return;
      const data = (await res.json()) as PresenceUser[];
      setUsers(data);
    } catch {
      // Silently ignore network errors for presence polling
    }
  }, [token, modelId, moduleId]);

  useEffect(() => {
    void fetchPresence();
    const interval = setInterval(() => {
      void fetchPresence();
    }, pollIntervalMs);
    return () => clearInterval(interval);
  }, [fetchPresence, pollIntervalMs]);

  if (users.length === 0) return null;

  return (
    <div
      className="flex items-center gap-1 px-2 py-1"
      aria-label="Active collaborators"
    >
      {users.map((user) => {
        const color = getColorForUser(user.user_id);
        const displayName = user.user_full_name ?? user.user_email ?? "User";
        const initials = getInitials(displayName);
        const isTooltipVisible = tooltipUserId === user.user_id;

        return (
          <div key={user.id} className="relative">
            <button
              type="button"
              className={`
                w-8 h-8 rounded-full flex items-center justify-center
                text-white text-xs font-semibold cursor-default select-none
                ring-2 ring-white focus:outline-none
                ${color}
              `}
              aria-label={displayName}
              onMouseEnter={() => {
                setTooltip(displayName);
                setTooltipUserId(user.user_id);
              }}
              onMouseLeave={() => {
                setTooltip(null);
                setTooltipUserId(null);
              }}
              onFocus={() => {
                setTooltip(displayName);
                setTooltipUserId(user.user_id);
              }}
              onBlur={() => {
                setTooltip(null);
                setTooltipUserId(null);
              }}
            >
              {initials}
            </button>

            {isTooltipVisible && tooltip && (
              <div
                className="
                  absolute bottom-full left-1/2 -translate-x-1/2 mb-2
                  bg-gray-900 text-white text-xs rounded px-2 py-1
                  whitespace-nowrap pointer-events-none z-50
                "
                role="tooltip"
              >
                {tooltip}
                {user.cursor_cell && (
                  <span className="ml-1 text-gray-400">
                    @ {user.cursor_cell}
                  </span>
                )}
                {/* Tooltip arrow */}
                <div className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-gray-900" />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
