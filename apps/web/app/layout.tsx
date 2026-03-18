import type { Metadata } from "next";
import { AntdRegistry } from "@ant-design/nextjs-registry";
import { App, ConfigProvider } from "antd";
import { IBM_Plex_Mono, Noto_Sans_SC } from "next/font/google";

import "./globals.css";
import { Sidebar } from "./components/Sidebar";

const bodyFont = Noto_Sans_SC({
  variable: "--font-body",
  weight: ["400", "500", "700"],
  preload: false,
});

const monoFont = IBM_Plex_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  weight: ["400", "500", "600"],
});

export const metadata: Metadata = {
  title: "Inquora Smart Inquiry Agent",
  description: "智能询价 Agent MVP 工作台",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body className={`${bodyFont.variable} ${monoFont.variable}`}>
        <AntdRegistry>
          <ConfigProvider
            theme={{
              token: {
                colorPrimary: "#e4572e",
                colorInfo: "#e4572e",
                borderRadius: 22,
                colorTextBase: "#211f1a",
                fontFamily: "var(--font-body)",
              },
            }}
          >
            <App>
              <div className="flex min-h-screen bg-page">
                <Sidebar />
                <main className="flex-1 overflow-auto px-6 py-5">
                  {children}
                </main>
              </div>
            </App>
          </ConfigProvider>
        </AntdRegistry>
      </body>
    </html>
  );
}
