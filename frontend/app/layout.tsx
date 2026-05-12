import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "やんばる あちこーこー たこ焼き 投稿サポート",
  description: "毎朝30秒で営業投稿を作るための支援アプリ",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ja">
      <body>{children}</body>
    </html>
  );
}
