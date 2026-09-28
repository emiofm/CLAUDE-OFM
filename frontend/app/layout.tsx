import type { Metadata } from "next";
import "./globals.css";
import Sidebar from "@/components/Sidebar";
import Toaster from "@/components/Toaster";

export const metadata: Metadata = {
  title: "Threads Purge",
  description: "Threads Purge — Profile Search Engine and Models/Accs manager.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        {/* ambient background glow */}
        <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
          <div className="absolute -left-40 -top-40 h-[480px] w-[480px] animate-float rounded-full bg-brand-600/15 blur-[120px]" />
          <div className="absolute -bottom-40 right-0 h-[420px] w-[420px] animate-float rounded-full bg-accent-500/10 blur-[120px] [animation-delay:-7s]" />
        </div>
        <div className="flex min-h-screen flex-col md:flex-row">
          <Sidebar />
          <main className="min-w-0 flex-1 px-4 py-6 sm:px-8 md:py-10">
            <div className="mx-auto max-w-7xl">{children}</div>
          </main>
        </div>
        <Toaster />
      </body>
    </html>
  );
}
