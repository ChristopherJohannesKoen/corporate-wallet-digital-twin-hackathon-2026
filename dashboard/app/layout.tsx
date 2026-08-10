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
    title: "Corporate Wallet Digital Twin V3 · Latent Decision Lab",
    description: "Reconstruct latent corporate wallets, detect change and optimize governed RM and evidence capacity under visible uncertainty.",
    openGraph: {
      title: "Corporate Wallet Digital Twin V3",
      description: "Latent wallet reconstruction · robust decisions · governed evidence.",
      type: "website",
      images: [{ url: new URL("/og.png", base), width: 1721, height: 914, alt: "Corporate Wallet Digital Twin V3 latent decision lab" }],
    },
    twitter: {
      card: "summary_large_image",
      title: "Corporate Wallet Digital Twin V3",
      description: "Latent wallet reconstruction and robust decision intelligence with visible claim boundaries.",
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
