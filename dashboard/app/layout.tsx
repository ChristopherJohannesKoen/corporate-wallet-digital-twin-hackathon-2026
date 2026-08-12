import type { Metadata } from "next";
import { headers } from "next/headers";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export async function generateMetadata(): Promise<Metadata> {
  const requestHeaders = await headers();
  const host = requestHeaders.get("x-forwarded-host") ?? requestHeaders.get("host") ?? "corporate-wallet-digital-twin.local";
  const protocol = requestHeaders.get("x-forwarded-proto") ?? (host.includes("localhost") ? "http" : "https");
  const base = new URL(`${protocol}://${host}`);
  return {
    metadataBase: base,
    title: "Corporate Wallet Digital Twin V3.1 · Decision Twin",
    description: "Turn point-in-time business evidence into governed client conversations, separated value, feasibility and an eight-action coverage plan.",
    openGraph: {
      title: "Corporate Wallet Digital Twin V3.1",
      description: "Business-model evidence · dual value · governed weekly conversations.",
      type: "website",
      images: [{ url: new URL("/og-v31.png", base), width: 1536, height: 1024, alt: "Corporate Wallet Digital Twin V3.1 Decision Twin" }],
    },
    twitter: {
      card: "summary_large_image",
      title: "Corporate Wallet Digital Twin V3.1",
      description: "The eight highest-value governed conversations, with evidence and uncertainty visible.",
      images: [new URL("/og-v31.png", base)],
    },
    icons: { icon: "/favicon.svg", shortcut: "/favicon.svg" },
  };
}

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className={`${geistSans.variable} ${geistMono.variable}`}>{children}</body>
    </html>
  );
}
