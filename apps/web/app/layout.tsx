import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Homage1.0 BakeBoard",
  description: "Transparent AI factory dashboard skeleton.",
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
