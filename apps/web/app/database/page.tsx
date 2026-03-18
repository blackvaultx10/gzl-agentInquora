"use client";

import { CloudUploadOutlined, DownloadOutlined } from "@ant-design/icons";
import { Button, Card, Space, Statistic, Table, Tag, Typography } from "antd";

// 使用 Tailwind 的 grid 替代 Row/Col

const { Title, Text } = Typography;

const mockPrices = [
  { name: "球阀 DN100", category: "阀门", spec: "PN16", material: "不锈钢", unit: "个", price: 850, updated: "2024-03-01" },
  { name: "闸阀 DN150", category: "阀门", spec: "PN25", material: "铸钢", unit: "个", price: 1200, updated: "2024-03-01" },
  { name: "无缝钢管 Φ108", category: "管材", spec: "壁厚4mm", material: "20#钢", unit: "米", price: 45, updated: "2024-02-28" },
  { name: "角钢 50×50", category: "型材", spec: "5#", material: "Q235", unit: "kg", price: 4.5, updated: "2024-02-25" },
  { name: "法兰盘 DN100", category: "管件", spec: "PN16", material: "碳钢", unit: "片", price: 68, updated: "2024-02-20" },
  { name: "螺栓 M16×80", category: "紧固件", spec: "8.8级", material: "45#钢", unit: "套", price: 2.8, updated: "2024-02-18" },
];

export default function DatabasePage() {
  return (
    <>
      <header className="mb-5">
        <Title level={4} className="!m-0 !text-lg !text-ink">价格库</Title>
        <Text className="text-xs text-ink-muted">管理价格库数据</Text>
      </header>

      <div className="grid gap-5 lg:grid-cols-4">
        <div className="lg:col-span-1">
          <Space orientation="vertical" size="middle" className="w-full">
            <Card className="rounded-card border-line backdrop-blur-card" variant="borderless">
              <Statistic title="价格条目" value={1286} valueStyle={{ fontSize: 32 }} />
              <Text className="text-xs text-ink-muted">来自 price_catalog.csv</Text>
            </Card>
            <Card className="rounded-card border-line backdrop-blur-card" variant="borderless">
              <Text className="text-xs font-mono uppercase tracking-wider text-ink-muted">快捷操作</Text>
              <Space orientation="vertical" className="mt-3 w-full">
                <Button type="primary" block icon={<CloudUploadOutlined />}>导入 CSV</Button>
                <Button block icon={<DownloadOutlined />}>导出备份</Button>
              </Space>
            </Card>
          </Space>
        </div>

        <div className="lg:col-span-3">
          <Card className="rounded-card border-line backdrop-blur-card" variant="borderless">
            <div className="mb-4 flex items-center justify-between">
              <Title level={5} className="!m-0 !text-ink">价格库明细</Title>
              <Button type="primary">新增条目</Button>
            </div>
            <Table
              columns={[
                { title: "项目名称", dataIndex: "name", key: "name", fixed: "left", width: 180 },
                { title: "分类", dataIndex: "category", key: "category", width: 100, render: (v: string) => <Tag>{v}</Tag> },
                { title: "规格", dataIndex: "spec", key: "spec", width: 120 },
                { title: "材质", dataIndex: "material", key: "material", width: 100 },
                { title: "单位", dataIndex: "unit", key: "unit", width: 80, align: "center" },
                { title: "单价", dataIndex: "price", key: "price", width: 120, align: "right", render: (v: number) => <span className="font-mono font-semibold">¥{v}</span> },
                { title: "更新日期", dataIndex: "updated", key: "updated", width: 120 },
                { title: "操作", key: "action", width: 120, render: () => (
                  <Space>
                    <Button type="link" size="small">编辑</Button>
                    <Button type="link" size="small" danger>删除</Button>
                  </Space>
                )},
              ]}
              dataSource={mockPrices}
              pagination={{ pageSize: 10 }}
              scroll={{ x: 800 }}
              size="small"
              className="rounded-metric overflow-hidden"
            />
          </Card>
        </div>
      </div>
    </>
  );
}
