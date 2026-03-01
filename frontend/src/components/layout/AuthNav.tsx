"use client";

import Link from "next/link";
import { useAuth } from "@/hooks/useAuth";

export default function AuthNav() {
  const { isAuthenticated, isLoading, user, logout } = useAuth();

  if (isLoading) {
    return <span className="text-xs text-gray-400">Loading session...</span>;
  }

  if (!isAuthenticated || !user) {
    return (
      <div className="flex items-center gap-2">
        <Link
          href="/login"
          className="rounded px-2.5 py-1.5 text-xs text-gray-300 transition-colors hover:bg-gray-700 hover:text-white"
        >
          Login
        </Link>
        <Link
          href="/register"
          className="rounded bg-blue-600 px-2.5 py-1.5 text-xs font-medium text-white transition-colors hover:bg-blue-700"
        >
          Sign up
        </Link>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <span className="hidden text-xs text-gray-300 sm:inline">
        {user.full_name || user.email}
      </span>
      <button
        type="button"
        onClick={logout}
        className="rounded px-2.5 py-1.5 text-xs text-gray-300 transition-colors hover:bg-gray-700 hover:text-white"
      >
        Logout
      </button>
    </div>
  );
}
