import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "../context/AuthContext";
import { Toaster } from 'sonner';

// 1. Define the fonts here so TypeScript knows what they are
const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

// 2. The SEO Metadata
export const metadata: Metadata = {
  title: {
    default: "CinematicAI | Turn Listing Links into Luxury Video Tours",
    template: "%s | CinematicAI Real Estate Marketing"
  },
  description: "The ultimate AI video generator for real estate agents. Convert Zillow and MLS links into stunning cinematic property tours with lifelike AI voiceovers and dynamic camera effects in under 5 minutes. No video editing skills required.",
  keywords: [
    "real estate video generator",
    "AI property tours",
    "Zillow to video",
    "MLS video maker",
    "realtor marketing tools",
    "AI voiceover real estate",
    "cinematic listing videos",
    "real estate lead generation",
    "free real estate video maker",
    "real estate video marketing",
    "AI real estate content creation",
  ],
  authors: [{ name: "CinematicAI" }],
  creator: "CinematicAI",
  openGraph: {
    type: "website",
    locale: "en_US",
    url: "https://cineo.ai", // Update this when you get your domain
    title: "CinematicAI | AI Video Maker for Realtors",
    description: "Stop paying for expensive videographers. Paste a listing link and instantly generate a market-ready, cinematic property tour.",
    siteName: "CinematicAI",
    images: [
      {
        url: "https://cineo.ai/og-image.jpg", // Update this URL
        width: 1200,
        height: 630,
        alt: "CinematicAI Dashboard showing a generated real estate video",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "CinematicAI | AI Video Maker for Realtors",
    description: "Paste a Zillow link. Get a cinematic video tour in minutes.",
    images: ["https://cineo.ai/og-image.jpg"], // Update this URL
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-video-preview": -1,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },
};

// 3. The main layout wrapper
export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <AuthProvider>{children}</AuthProvider>
        <Toaster position="top-right" richColors />
      </body>
    </html>
  );
}