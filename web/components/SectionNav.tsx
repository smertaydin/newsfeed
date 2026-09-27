"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { SECTIONS } from "@/lib/types";
import ThemeToggle from "./ThemeToggle";

export default function SectionNav({ children }: { children?: ReactNode }) {
  const path = usePathname();
  const links = [{ href: "/", name: "Tümü", key: "" }, ...SECTIONS.map((s) => ({ href: `/${s.key}`, name: s.name, key: s.key }))];
  return (
    <nav className="nav" aria-label="Bölümler">
      <div className="wrap nav-inner">
        <div className="nav-links">
          {links.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              aria-current={path === l.href ? "page" : undefined}
              style={l.key ? ({ "--accent": `var(--s-${l.key})` } as React.CSSProperties) : undefined}
            >
              {l.name}
            </Link>
          ))}
        </div>
        {children}
        <ThemeToggle />
      </div>
    </nav>
  );
}
