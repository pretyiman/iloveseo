import type { Metadata } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import { Geist, Geist_Mono } from "next/font/google";
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
  title: "SEO Repair Kit",
  description: "All-in-one SEO and site-health audit platform for web developers",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <ClerkProvider>
      <html
        lang="en"
        className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
      >
        {/* ClerkJS overwrites <body>'s className at runtime (observed: it
            replaces it with "cl-component v6"), which silently drops any
            Tailwind classes placed directly on <body> -- so the dark theme
            background lives on this inner wrapper div instead, which Clerk
            doesn't touch. */}
        <body className="h-full">
          <div className="flex min-h-screen flex-col bg-neutral-950 text-neutral-100">{children}</div>
        </body>
      </html>
    </ClerkProvider>
  );
}
