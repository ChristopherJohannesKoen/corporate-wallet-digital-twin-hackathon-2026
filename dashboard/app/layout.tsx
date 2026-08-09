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
    title: "Corporate Wallet Digital Twin V2 · Client Demonstration",
    description: "Governed client demonstration for evidence-first corporate wallet calibration, scenarios and visible uncertainty.",
    openGraph: {
      title: "Corporate Wallet Digital Twin V2",
      description: "Client demonstration · governed data · visible uncertainty.",
      type: "website",
      images: [{ url: new URL("/og.png", base), width: 1728, height: 912, alt: "Corporate Wallet Digital Twin V2 governed client demonstration" }],
    },
    twitter: {
      card: "summary_large_image",
      title: "Corporate Wallet Digital Twin V2",
      description: "Governed client demonstration with visible data provenance and uncertainty.",
      images: [new URL("/og.png", base)],
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
