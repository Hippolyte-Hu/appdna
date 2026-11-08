import type { Metadata } from "next";
import { Providers } from "@/components/providers";
import "@fontsource/geist/400.css";
import "@fontsource/geist/500.css";
import "@fontsource/geist/600.css";
import "@fontsource/geist/700.css";
import "@fontsource/geist-mono/400.css";
import "../tokens.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "AppDNA — Learn software by doing",
  description:
    "Give an agent a business goal. Observe real software execution, verify outcomes, and keep validated knowledge.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
