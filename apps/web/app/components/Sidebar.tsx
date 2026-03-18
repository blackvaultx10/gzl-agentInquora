"use client";

import {
  CalculatorOutlined,
  HistoryOutlined,
  SettingOutlined,
  DatabaseOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
} from "@ant-design/icons";
import { Tooltip } from "antd";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

const menuItems = [
  { key: "/inquiry", icon: CalculatorOutlined, label: "询价工作台" },
  { key: "/history", icon: HistoryOutlined, label: "历史记录" },
  { key: "/database", icon: DatabaseOutlined, label: "价格库" },
  { key: "/settings", icon: SettingOutlined, label: "系统设置" },
];

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const pathname = usePathname();

  return (
    <aside
      className={`relative flex flex-col border-r border-line bg-paper-strong transition-all duration-300 ease-in-out ${
        collapsed ? "w-16" : "w-52"
      }`}
    >
      {/* Logo */}
      <div className="flex h-16 items-center gap-3 border-b border-line px-4">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary text-white shadow-button">
          <CalculatorOutlined className="text-base" />
        </div>
        {!collapsed && (
          <div className="overflow-hidden transition-opacity duration-200">
            <div className="text-sm font-semibold text-ink">智能询价</div>
            <div className="text-[10px] text-ink-muted">Inquora</div>
          </div>
        )}
      </div>

      {/* Menu */}
      <nav className="flex-1 py-4">
        {menuItems.map((item) => {
          const Icon = item.icon;
          const isActive = pathname === item.key || pathname.startsWith(`${item.key}/`);
          return (
            <Link
              key={item.key}
              href={item.key}
              className={`group flex w-full items-center gap-3 px-4 py-3 transition-all hover:bg-primary/5 ${
                isActive
                  ? "border-r-2 border-primary bg-primary/5 text-primary"
                  : "text-ink-light"
              } ${collapsed ? "justify-center" : ""}`}
            >
              <span className={`text-lg ${isActive ? "text-primary" : "text-ink-muted group-hover:text-primary"}`}>
                <Icon />
              </span>
              {!collapsed && (
                <span className="truncate text-sm font-medium transition-opacity duration-200">
                  {item.label}
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      {/* Collapse button */}
      <div className="border-t border-line p-3">
        <Tooltip title={collapsed ? "展开" : "收起"} placement="right">
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="flex h-10 w-full items-center justify-center rounded-lg text-ink-muted transition-colors hover:bg-primary/5 hover:text-primary"
          >
            {collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
          </button>
        </Tooltip>
      </div>
    </aside>
  );
}
