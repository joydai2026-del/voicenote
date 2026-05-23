import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "VoiceNote — Talk, get a publish-ready article",
  description:
    "Speak for 2-5 minutes, get a polished, publish-ready article powered by Whisper and Claude. No writing required.",
  openGraph: {
    title: "VoiceNote",
    description: "Talk for 5 minutes, get a publish-ready article.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={inter.className}>{children}</body>
    </html>
  );
}
