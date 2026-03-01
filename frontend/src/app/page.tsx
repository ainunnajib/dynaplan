import Link from "next/link";

export default function Home() {
  return (
    <div className="flex min-h-full flex-col bg-gray-50">
      {/* Hero */}
      <main className="flex flex-1 flex-col items-center justify-center px-4 py-14 sm:px-6 sm:py-20">
        <div className="w-full max-w-2xl">
          <div className="mb-6 inline-flex items-center rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700">
            Open-source Anaplan replacement
          </div>

          <h1 className="mb-4 text-3xl font-bold tracking-tight text-gray-900 sm:text-4xl">
            Connected planning,{" "}
            <span className="text-blue-600">without the lock-in.</span>
          </h1>

          <p className="mb-8 text-base leading-relaxed text-gray-500 sm:text-lg">
            Dynaplan is a multidimensional planning platform with a formula
            engine, spreadsheet grid, scenario analysis, and real-time
            collaboration — built on open standards.
          </p>

          {/* Get Started */}
          <div className="mb-10 rounded-xl border border-gray-200 bg-white p-4 shadow-sm sm:p-6">
            <h2 className="mb-4 text-base font-semibold text-gray-800">
              Get Started
            </h2>
            <div className="flex flex-col gap-3 sm:flex-row">
              <Link
                href="/login"
                className="flex items-center justify-center rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-medium text-white shadow-sm transition-colors hover:bg-blue-700"
              >
                Login
              </Link>
              <Link
                href="/register"
                className="flex items-center justify-center rounded-lg border border-blue-200 bg-blue-50 px-5 py-2.5 text-sm font-medium text-blue-700 shadow-sm transition-colors hover:bg-blue-100"
              >
                Sign up
              </Link>
            </div>
            <div className="mt-3 flex flex-col gap-3 sm:flex-row">
              <Link
                href="/workspaces"
                className="flex items-center justify-center rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-medium text-white shadow-sm transition-colors hover:bg-blue-700"
              >
                View Workspaces
              </Link>
              <Link
                href="/models"
                className="flex items-center justify-center rounded-lg border border-gray-200 bg-white px-5 py-2.5 text-sm font-medium text-gray-700 shadow-sm transition-colors hover:bg-gray-50"
              >
                Browse Models
              </Link>
            </div>
          </div>

          {/* Feature cards */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            {[
              {
                title: "Multidimensional",
                desc: "Model any business structure with named dimensions, hierarchies, and sparse data storage.",
              },
              {
                title: "Formula Engine",
                desc: "Anaplan-compatible formula syntax with dependency graph and automatic recalculation.",
              },
              {
                title: "Grid View",
                desc: "High-performance virtualized spreadsheet UI with in-line editing and cell formatting.",
              },
            ].map((card) => (
              <div
                key={card.title}
                className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm"
              >
                <h3 className="mb-1 text-sm font-semibold text-gray-800">
                  {card.title}
                </h3>
                <p className="text-xs leading-relaxed text-gray-500">
                  {card.desc}
                </p>
              </div>
            ))}
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-200 py-4 text-center text-xs text-gray-400">
        Dynaplan — open-source enterprise planning platform
      </footer>
    </div>
  );
}
