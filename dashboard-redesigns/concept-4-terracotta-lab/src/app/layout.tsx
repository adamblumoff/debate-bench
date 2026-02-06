import type { Metadata } from "next";
import { Fraunces, Nunito, DM_Mono } from "next/font/google";
import "./globals.css";

const display = Fraunces({
  variable: "--font-display",
  subsets: ["latin"],
  weight: ["400", "600", "700"],
});
const body = Nunito({
  variable: "--font-body",
  subsets: ["latin"],
  weight: ["400", "600", "700"],
});
const mono = DM_Mono({
  variable: "--font-mono-dm",
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
