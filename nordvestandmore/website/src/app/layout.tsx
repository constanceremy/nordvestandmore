import type { Metadata } from "next";
import "./globals.css";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import { Analytics } from "@vercel/analytics/next";
import GoogleAnalytics from "@/components/GoogleAnalytics";
import ConsentBanner from "@/components/ConsentBanner";

const GA_ID = process.env.NEXT_PUBLIC_GA_ID;

export const metadata: Metadata = {
  title: "NV & more — Nordvest, Copenhagen",
  description: "Events, guides and stories from Nordvest, Copenhagen's most vibrant neighbourhood.",
  icons: { icon: "/icon.png" },
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
        {GA_ID && <GoogleAnalytics gaId={GA_ID} />}
        <Nav />
        <main className="flex-1">{children}</main>
        <Footer />
        <ConsentBanner />
        <Analytics />
      </body>
    </html>
  );
}
