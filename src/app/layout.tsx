import type { Metadata } from "next";
import "./globals.css";
import Navigation from "@/components/Navigation";
import { Toaster } from 'sonner';

export const metadata: Metadata = {
  title: "Balance - Budget App",
  description: "Your peaceful path to financial clarity",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <Navigation />
        {children}
        <Toaster 
          position="top-right" 
          richColors 
          closeButton
          duration={3000}
        />
      </body>
    </html>
  );
}
