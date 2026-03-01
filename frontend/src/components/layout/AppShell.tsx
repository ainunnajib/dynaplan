"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import AuthNav from "./AuthNav";

interface AppShellProps {
  children: React.ReactNode;
}

export default function AppShell({ children }: AppShellProps) {
  const pathname = usePathname();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  useEffect(() => {
    setIsMobileMenuOpen(false);
  }, [pathname]);

  return (
    <div className="flex min-h-svh flex-col">
      <header className="sticky top-0 z-40 border-b border-gray-800 bg-gray-900">
        <div className="mx-auto flex h-14 w-full max-w-[1600px] items-center gap-2 px-3 sm:px-4">
          <button
            type="button"
            onClick={() => setIsMobileMenuOpen((v) => !v)}
            className="rounded p-1.5 text-gray-300 transition-colors hover:bg-gray-700 hover:text-white md:hidden"
            aria-label="Toggle navigation"
            aria-expanded={isMobileMenuOpen}
          >
            <MenuIcon />
          </button>

          <Link
            href="/"
            className="flex items-center gap-2 text-sm font-bold tracking-tight text-white"
          >
            <span className="flex h-6 w-6 items-center justify-center rounded bg-blue-600 text-xs font-bold text-white">
              D
            </span>
            Dynaplan
          </Link>

          <nav className="ml-4 hidden items-center gap-1 text-xs text-gray-300 md:flex">
            <NavLink href="/workspaces">Workspaces</NavLink>
            <NavLink href="/models">Models</NavLink>
          </nav>

          <span className="flex-1" />
          <AuthNav />
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        <aside className="hidden w-56 shrink-0 flex-col gap-1 overflow-y-auto border-r border-gray-800 bg-gray-900 px-2 py-4 md:flex">
          <p className="mb-1 px-2 text-[10px] font-semibold uppercase tracking-widest text-gray-500">
            Navigate
          </p>
          <SidebarLink href="/workspaces">Workspaces</SidebarLink>
          <SidebarLink href="/models">Models</SidebarLink>
          <div className="my-2 border-t border-gray-800" />
          <p className="mb-1 px-2 text-[10px] font-semibold uppercase tracking-widest text-gray-500">
            Recent
          </p>
          <p className="px-2 text-xs text-gray-600">No recent items</p>
        </aside>

        <main className="min-h-0 flex-1 overflow-y-auto bg-gray-50">
          {children}
        </main>
      </div>

      {isMobileMenuOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          <button
            type="button"
            className="absolute inset-0 bg-black/50"
            onClick={() => setIsMobileMenuOpen(false)}
            aria-label="Close navigation"
          />
          <aside className="relative z-10 flex h-full w-72 max-w-[85vw] flex-col gap-1 overflow-y-auto bg-gray-900 px-3 py-4 shadow-2xl">
            <div className="mb-2 flex items-center justify-between">
              <p className="text-[10px] font-semibold uppercase tracking-widest text-gray-500">
                Navigate
              </p>
              <button
                type="button"
                onClick={() => setIsMobileMenuOpen(false)}
                className="rounded p-1 text-gray-400 hover:bg-gray-700 hover:text-white"
                aria-label="Close menu"
              >
                <CloseIcon />
              </button>
            </div>

            <SidebarLink href="/workspaces">Workspaces</SidebarLink>
            <SidebarLink href="/models">Models</SidebarLink>
          </aside>
        </div>
      )}
    </div>
  );
}

function NavLink({
  href,
  children,
}: {
  href: string;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      className="rounded px-2 py-1 transition-colors hover:bg-gray-700 hover:text-white"
    >
      {children}
    </Link>
  );
}

function SidebarLink({
  href,
  children,
}: {
  href: string;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      className="rounded px-2 py-1.5 text-sm text-gray-300 transition-colors hover:bg-gray-700 hover:text-white"
    >
      {children}
    </Link>
  );
}

function MenuIcon() {
  return (
    <svg
      className="h-5 w-5"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5"
      />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg
      className="h-5 w-5"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
    </svg>
  );
}
