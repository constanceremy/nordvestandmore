import type { Metadata } from "next";
import "./globals.css";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import { Analytics } from "@vercel/analytics/next";

export const metadata: Metadata = {
  title: "NV & more — Nordvest, Copenhagen",
  description: "Events, guides and stories from Nordvest, Copenhagen's most vibrant neighbourhood.",
  openGraph: {
    title: "NV & more",
    description: "Events, guides and stories from Nordvest, Copenhagen.",
    url: "https://nordvestandmore.com",
    siteName: "NV & more",
    locale: "en_DK",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="min-h-screen flex flex-col">
        <Nav />
        <main className="flex-1">{children}</main>
        <Footer />
        <Analytics />
      </body>
    </html>
  );
}
