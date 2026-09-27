import type { Metadata, Viewport } from "next";
import { Instrument_Sans, Newsreader } from "next/font/google";
import Footer from "@/components/Footer";
import Masthead from "@/components/Masthead";
import "./globals.css";

const serif = Newsreader({ subsets: ["latin", "latin-ext"], variable: "--font-serif", display: "swap", axes: ["opsz"] });
const sans = Instrument_Sans({ subsets: ["latin", "latin-ext"], variable: "--font-sans", display: "swap" });

export const metadata: Metadata = {
  title: { default: "Akış · Gündemin derlenmiş hâli", template: "%s · Akış" },
  description: "Gündem, ekonomi, dünya, teknoloji ve spordan onlarca kaynaktan derlenen, sürekli güncellenen haber akışı.",
  alternates: { types: { "application/rss+xml": [{ url: "/rss.xml", title: "Akış" }] } },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f7f5f0" },
    { media: "(prefers-color-scheme: dark)", color: "#181715" },
  ],
};

// Tema seçimi sayfa boyanmadan uygulansın
const themeScript = `try{var t=localStorage.getItem("akis:theme");if(t)document.documentElement.dataset.theme=t}catch(e){}`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="tr" className={`${serif.variable} ${sans.variable}`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>
        <Masthead />
        {children}
        <Footer />
      </body>
    </html>
  );
}
