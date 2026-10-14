import type { Metadata } from "next";
import "./globals.css";
import "./intelligence.css";
export const metadata: Metadata = {
  title: "NEXUS | Intelligence Platform",
  description: "Case-isolated intelligence investigation workspace",
};
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="az"><body>{children}</body></html>;
}
