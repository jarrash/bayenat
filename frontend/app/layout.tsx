import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Bayenat | منصة التحقق من الأدلة",
  description: "AI-assisted evidence transcription and verification platform",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ar" dir="rtl">
      <body>{children}</body>
    </html>
  );
}
