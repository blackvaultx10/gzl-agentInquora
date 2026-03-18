"use client";

import { DownloadOutlined } from "@ant-design/icons";
import { Button, Card, Space, Table, Tag, Typography } from "antd";

const { Title, Text } = Typography;

// 模拟数据 - 实际应用中可从 API 获取
const mockHistory = [
  { id: "inq-a1b2c3d4e5", date: "2024-03-15 14:30", filename: "工程图纸_v1.dxf", items: 12, matched: 10, total: 158000 },
  { id: "inq-f6g7h8i9j0", date: "2024-03-14 09:15", filename: "设备清单.pdf", items: 8, matched: 6, total: 86000 },
  { id: "inq-k1l2m3n4o5", date: "2024-03-13 16:45", filename: "管道系统.dwg", items: 25, matched: 20, total: 324000 },
  { id: "inq-p6q7r8s9t0", date: "2024-03-12 11:20", filename: "阀门清单.xlsx", items: 15, matched: 15, total: 125000 },
  { id: "inq-u1v2w3x4y5", date: "2024-03-11 15:00", filename: "电气图纸.pdf", items: 32, matched: 28, total: 456000 },
];

export default function HistoryPage() {
  return (
    <>
      <header className="mb-5 flex items-center justify-between">
        <div>
          <Title level={4} className="!m-0 !text-lg !text-ink">历史记录</Title>
          <Text className="text-xs text-ink-muted">查看历史询价记录</Text>
        </div>
        <Button icon={<DownloadOutlined />}>导出全部</Button>
      </header>

      <Card className="rounded-card border-line backdrop-blur-card" variant="borderless">
        <Table
          columns={[
            { title: "任务ID", dataIndex: "id", key: "id", render: (v: string) => <Text copyable className="font-mono text-xs">{v}</Text> },
            { title: "日期", dataIndex: "date", key: "date", width: 160 },
            { title: "文件名", dataIndex: "filename", key: "filename" },
            { title: "识别项", dataIndex: "items", key: "items", align: "center", width: 100 },
            { title: "匹配项", dataIndex: "matched", key: "matched", align: "center", width: 100 },
            { title: "总价", dataIndex: "total", key: "total", align: "right", width: 150, render: (v: number) => <span className="font-mono font-semibold text-primary">¥{v.toLocaleString()}</span> },
            { title: "操作", key: "action", width: 120, render: () => (
              <Space>
                <Button type="link" size="small">查看</Button>
                <Button type="link" size="small">下载</Button>
              </Space>
            )},
          ]}
          dataSource={mockHistory}
          pagination={{ pageSize: 10 }}
          className="rounded-metric overflow-hidden"
        />
      </Card>
    </>
  );
}
