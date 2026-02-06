import type { Metadata } from "next";
import { Cormorant_Garamond, Fira_Code } from "next/font/google";
import "./globals.css";

const display = Cormorant_Garamond({
  variable: "--font-display",
  subsets: ["latin"],
  weight: ["300", "400", "600", "700"],
});
const mono = Fira_Code({
  variable: "--font-mono-fira",
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
      <head>
        <link
          href="https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;500;600&display=swap"
          rel="stylesheet"
        />
        <style>{`
          :root { --font-body: 'Instrument Sans', system-ui, -apple-system, sans-serif; }
        `}</style>
      </head>
      <body
        className={`${display.variable} ${mono.variable} antialiased text-pretty`}
      >
        {children}
      </body>
    </html>
  );
}
