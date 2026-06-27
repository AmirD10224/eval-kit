import type { Metadata, Viewport } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import Image from "next/image";
import Link from "next/link";
import { Github } from "lucide-react";
import "./globals.css";

export const metadata: Metadata = {
  title: "EvalKit, production-grade evals for LLM apps",
  description:
    "Calibrated LLM-as-judge, synthetic adversarial data, regression detection, and a GitHub Action that auto-rejects regressing PRs.",
};

export const viewport: Viewport = {
  themeColor: "#0a0a0a",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${GeistSans.variable} ${GeistMono.variable}`}>
      <body>
        <div className="min-h-dvh flex flex-col">
          <header className="sticky top-0 z-30 border-b border-[var(--color-line)] bg-[var(--color-bg)]/85 backdrop-blur-md">
            <div className="max-w-[1200px] mx-auto px-6 h-14 flex items-center justify-between">
              <Link href="/" className="flex items-center gap-2.5 group">
                <Image src="/logo.svg" alt="eval-kit" width={28} height={28} priority className="h-7 w-7" />
                <span className="text-[15px] font-semibold tracking-tight text-[var(--color-fg)]">
                  EvalKit
                </span>
                <span className="hidden sm:inline-flex items-center gap-1.5 text-[11px] font-mono text-[var(--color-fg-sub)] ml-1">
                  v0.1.0
                </span>
              </Link>

              <nav className="flex items-center gap-1">
                <a
                  href="#features"
                  className="hidden sm:inline-flex items-center px-3 py-2 text-[13.5px] text-[var(--color-fg-mute)] hover:text-[var(--color-fg)] transition-colors"
                >
                  Features
                </a>
                <a
                  href="#pitch"
                  className="hidden sm:inline-flex items-center px-3 py-2 text-[13.5px] text-[var(--color-fg-mute)] hover:text-[var(--color-fg)] transition-colors"
                >
                  Pitch
                </a>
                <a
                  href="https://AmirD10224.github.io/eval-kit/"
                  target="_blank"
                  rel="noreferrer"
                  className="hidden sm:inline-flex items-center px-3 py-2 text-[13.5px] text-[var(--color-fg-mute)] hover:text-[var(--color-fg)] transition-colors"
                >
                  Docs
                </a>
                <a
                  href="https://github.com/AmirD10224/eval-kit"
                  target="_blank"
                  rel="noreferrer"
                  aria-label="GitHub"
                  className="inline-flex h-9 w-9 items-center justify-center rounded-lg text-[var(--color-fg-mute)] hover:text-[var(--color-fg)] hover:bg-[var(--color-bg-2)] transition-colors"
                >
                  <Github className="size-4" />
                </a>
                <a
                  href="#install"
                  className="ml-1 inline-flex items-center gap-1.5 rounded-lg px-3.5 py-2 text-[12.5px] font-medium bg-[var(--color-fg)] text-[var(--color-bg)] hover:bg-[var(--color-fg-dim)] transition-colors"
                >
                  Install
                </a>
              </nav>
            </div>
          </header>

          <main className="flex-1 max-w-[1200px] mx-auto w-full px-6">{children}</main>

          <footer className="border-t border-[var(--color-line)] mt-32">
            <div className="max-w-[1200px] mx-auto px-6 py-10 grid grid-cols-1 md:grid-cols-[1.4fr_1fr_1fr_1fr] gap-10">
              <div>
                <Link href="/" className="flex items-center gap-2.5">
                  <Image src="/logo.svg" alt="eval-kit" width={28} height={28} className="h-7 w-7" />
                  <span className="text-[15px] font-semibold tracking-tight">
                    EvalKit
                  </span>
                </Link>
                <p className="mt-4 max-w-xs text-[13.5px] leading-[1.55] text-[var(--color-fg-mute)]">
                  Production-grade evals for LLM apps. Calibrated judges,
                  synthetic data, regression gates.
                </p>
              </div>
              <FooterCol title="Library">
                <FooterLink href="#install">Install</FooterLink>
                <FooterLink href="https://AmirD10224.github.io/eval-kit/" external>Docs</FooterLink>
                <FooterLink href="https://pypi.org/project/evalkit-oss/" external>PyPI</FooterLink>
                <FooterLink href="https://github.com/AmirD10224/eval-kit" external>GitHub</FooterLink>
              </FooterCol>
              <FooterCol title="Concepts">
                <FooterLink href="#" external>Calibration</FooterLink>
                <FooterLink href="#" external>Synthetic data</FooterLink>
                <FooterLink href="#" external>Regression gates</FooterLink>
                <FooterLink href="#" external>Bias auditing</FooterLink>
              </FooterCol>
              <FooterCol title="Maintainer">
                <li className="text-[13.5px] text-[var(--color-fg-mute)]">Amir Dhibi</li>
              </FooterCol>
            </div>
            <div className="border-t border-[var(--color-line)]">
              <div className="max-w-[1200px] mx-auto px-6 h-12 flex items-center justify-between text-[12px] text-[var(--color-fg-sub)] font-mono">
                <span>v0.1.0 · MIT · 2026</span>
                <span className="hidden md:inline tabular">
                  161 tests · 87% coverage · mypy --strict
                </span>
                <span>Built by Amir Dhibi</span>
              </div>
            </div>
          </footer>
        </div>
      </body>
    </html>
  );
}

function FooterCol({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="text-[11px] font-mono uppercase tracking-[0.16em] text-[var(--color-fg-sub)] mb-3">
        {title}
      </p>
      <ul className="space-y-2">{children}</ul>
    </div>
  );
}

function FooterLink({
  href,
  children,
  external = false,
}: {
  href: string;
  children: React.ReactNode;
  external?: boolean;
}) {
  return (
    <li>
      <a
        href={href}
        {...(external ? { target: "_blank", rel: "noreferrer" } : {})}
        className="text-[13.5px] text-[var(--color-fg-mute)] hover:text-[var(--color-fg)] transition-colors"
      >
        {children}
      </a>
    </li>
  );
}
