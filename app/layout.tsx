import type { Metadata } from "next";
import "./globals.css";
import { SessionProvider } from "next-auth/react";

export const metadata: Metadata = {
  title: "GradPath - BITS Placement Readiness",
  description: "Company-role readiness planning for BITS Pilani BE and MTech students.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-midnight-950 text-midnight-100 antialiased">
        <SessionProvider>{children}</SessionProvider>
      </body>
    </html>
  );
}
