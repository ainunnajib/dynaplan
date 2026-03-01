import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import { AuthProvider } from "@/contexts/AuthContext";
import AuthNav from "@/components/layout/AuthNav";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Dynaplan",
  description: "Open-source connected planning platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <AuthProvider>
          <div className="flex h-screen flex-col">
            {/* Top nav bar */}
            <header className="flex h-12 shrink-0 items-center gap-4 border-b border-gray-800 bg-gray-900 px-4">
              <Link
                href="/"
                className="flex items-center gap-2 text-sm font-bold tracking-tight text-white"
              >
                <span className="flex h-6 w-6 items-center justify-center rounded bg-blue-600 text-xs font-bold text-white">
                  D
                </span>
                Dynaplan
              </Link>
              <span className="flex-1" />
              <nav className="flex items-center gap-1 text-xs text-gray-300">
                <Link
                  href="/workspaces"
                  className="rounded px-2 py-1 transition-colors hover:bg-gray-700 hover:text-white"
                >
                  Workspaces
                </Link>
                <Link
                  href="/models"
                  className="rounded px-2 py-1 transition-colors hover:bg-gray-700 hover:text-white"
                >
                  Models
                </Link>
              </nav>
              <AuthNav />
            </header>

            {/* Body: sidebar + content */}
            <div className="flex flex-1 overflow-hidden">
              {/* Dark sidebar */}
              <aside className="flex w-52 shrink-0 flex-col gap-1 overflow-y-auto border-r border-gray-800 bg-gray-900 px-2 py-4">
                <p className="mb-1 px-2 text-[10px] font-semibold uppercase tracking-widest text-gray-500">
                  Navigate
                </p>

                <SidebarLink href="/workspaces">Workspaces</SidebarLink>
                <SidebarLink href="/models">Models</SidebarLink>

                <div className="my-2 border-t border-gray-800" />

                <p className="mb-1 px-2 text-[10px] font-semibold uppercase tracking-widest text-gray-500">
                  Recent
                </p>
                <p className="px-2 text-xs text-gray-600">
                  No recent items
                </p>
              </aside>

              {/* Main content */}
              <main className="flex-1 overflow-y-auto bg-gray-50">
                {children}
              </main>
            </div>
          </div>
        </AuthProvider>
      </body>
    </html>
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
