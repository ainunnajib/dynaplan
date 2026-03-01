"use client";

// Re-exports the auth hook from AuthContext so consumers can import from a
// single, conventional location: import { useAuth } from "@/hooks/useAuth"
export { useAuthContext as useAuth } from "@/contexts/AuthContext";
export type { AuthUser } from "@/contexts/AuthContext";
