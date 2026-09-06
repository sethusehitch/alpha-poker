import type { Metadata } from "next";
import { headers } from "next/headers";
import { Geist, Geist_Mono } from "next/font/google";
import { FeedbackWidget } from "./components/FeedbackWidget";
import { ToastHost } from "./components/Toast";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export async function generateMetadata(): Promise<Metadata> {
  const requestHeaders = await headers();
  const host =
    requestHeaders.get("x-forwarded-host") ??
    requestHeaders.get("host") ??
    "localhost:3001";
  const protocol =
    requestHeaders.get("x-forwarded-proto") ??
    (host.startsWith("localhost") || host.startsWith("127.0.0.1")
      ? "http"
      : "https");
  const metadataBase = new URL(`${protocol}://${host}`);

  return {
    metadataBase,
    title: "Alpha Poker: Build a poker bot. Prove it's the best.",
    description: "A private arena for testing autonomous poker agents.",
    icons: {
      icon: "/favicon.svg",
      shortcut: "/favicon.svg",
    },
    openGraph: {
      title: "Alpha Poker: Build a poker bot. Prove it's the best.",
      description: "A private arena for testing autonomous poker agents.",
      type: "website",
      siteName: "Alpha Poker",
      url: "/",
      images: [
        {
          url: "/alpha-poker-preview-v2.png",
          width: 1200,
          height: 630,
          alt: "Alpha Poker: Code. Compete. Climb.",
        },
      ],
    },
    twitter: {
      card: "summary_large_image",
      title: "Alpha Poker: Build a poker bot. Prove it's the best.",
      description: "A private arena for testing autonomous poker agents.",
      images: ["/alpha-poker-preview-v2.png"],
    },
  };
}

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
        {children}
        <FeedbackWidget />
        <ToastHost />
      </body>
    </html>
  );
}
