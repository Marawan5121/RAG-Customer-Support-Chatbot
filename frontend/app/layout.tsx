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
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
