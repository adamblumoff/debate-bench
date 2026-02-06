import type { Metadata } from "next";
import { Orbitron, Exo_2, Share_Tech_Mono } from "next/font/google";
import "./globals.css";

const display = Orbitron({
  variable: "--font-display",
  subsets: ["latin"],
  weight: ["400", "500", "700", "900"],
});
const body = Exo_2({
  variable: "--font-body",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});
const mono = Share_Tech_Mono({
  variable: "--font-mono-share",
  subsets: ["latin"],
  weight: ["400"],
});

export const metadata: Metadata = {
  title: "DebateBench",
  description: "Interactive, signed-S3-backed view of debate results",
  icons: {
    icon: "/favicon.ico",
    shortcut: "/favicon.ico",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body
        className={`${display.variable} ${body.variable} ${mono.variable} antialiased text-pretty`}
      >
        {children}
      </body>
    </html>
  );
}
