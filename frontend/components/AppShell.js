import Link from "next/link";

const navItems = [
  { href: "/", label: "Guide" },
  { href: "/jobs", label: "Jobs" },
  { href: "/annotations", label: "Annotations" },
];

export default function AppShell({ children }) {
  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-white/10 bg-slate-950/95">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-6 py-5 sm:flex-row sm:items-center sm:justify-between">
          <Link href="/" className="group">
            <p className="text-sm font-semibold uppercase tracking-[0.35em] text-cyan-300">
              Gene Autoannotator
            </p>
            <p className="mt-1 text-sm text-slate-400">
              Web queue for long-running annotation jobs
            </p>
          </Link>

          <nav className="flex flex-wrap gap-2">
            {navItems.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="rounded-full border border-white/10 px-4 py-2 text-sm font-medium text-slate-200 transition hover:border-cyan-300/70 hover:text-cyan-100"
              >
                {item.label}
              </Link>
            ))}
          </nav>
        </div>
      </header>

      <div className="mx-auto max-w-7xl px-6 py-10">{children}</div>
    </main>
  );
}
