"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const navItems = [
  { href: "/", label: "Guide" },
  { href: "/jobs", label: "Jobs" },
  { href: "/annotations", label: "Annotations" },
];

export default function AppShell({ children }) {
  const pathname = usePathname();

  return (
    <main className="min-h-screen bg-[var(--background)] text-[var(--foreground)]">
      <header className="border-b border-white/10 bg-gradient-to-br from-[var(--nav)] to-[var(--nav-soft)] text-[#f5f0e6]">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-6 py-5 sm:flex-row sm:items-center sm:justify-between">
          <Link href="/" className="group">
            <p className="text-sm font-bold uppercase tracking-[0.08em] text-[#f5f0e6]">
              Gene Autoannotator
            </p>
            <p className="mt-1 text-sm text-[#aebcaf]">
              Web queue for long-running annotation jobs
            </p>
          </Link>

          <nav className="flex flex-wrap gap-2">
            {navItems.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={`rounded-full border px-4 py-2 text-sm font-semibold transition ${
                  pathname === item.href
                    ? "border-[#f3eee4] bg-[#f3eee4] text-[var(--foreground)]"
                    : "border-white/10 text-[#dce5de] hover:border-white/25 hover:text-white"
                }`}
              >
                {item.label}
              </Link>
            ))}
          </nav>
        </div>
      </header>

      <div className="mx-auto max-w-7xl px-6 py-8">{children}</div>
    </main>
  );
}
