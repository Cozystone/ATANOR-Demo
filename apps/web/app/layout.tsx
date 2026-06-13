import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ATANOR",
  description: "Transparent Anomy neuro-symbolic local AI engine.",
  icons: {
    icon: "/favicon.ico",
    shortcut: "/favicon.ico",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
