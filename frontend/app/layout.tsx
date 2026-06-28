import type { Metadata } from "next";
import "./globals.css";

// Document-level metadata for the chat application.
export const metadata: Metadata = {
  title: "Customer Support Assistant",
  description: "RAG-powered customer support chatbot",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="h-full">
      <body className="h-full bg-slate-100 text-slate-800 antialiased">{children}</body>
    </html>
  );
}
