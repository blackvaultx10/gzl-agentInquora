"use client";

import {
  CloudUploadOutlined,
  DownloadOutlined,
  FileSearchOutlined,
  FileTextOutlined,
  CalculatorOutlined,
  WarningOutlined,
} from "@ant-design/icons";
import {
  Alert,
  App,
  Badge,
  Button,
  Card,
  Empty,
  Input,
  Progress,
  Select,
  Space,
  Statistic,
  Table,
  TableProps,
  Typography,
  Upload,
  Steps,
  Tag,
  Divider,
  Row,
  Col,
  Tooltip,
} from "antd";
import type { UploadFile } from "antd";
import { useEffect, useMemo, useRef, useState } from "react";

import { exportInquiry, parseInquiry } from "@/lib/api";
import type { ExportFormat, InquiryItem, InquiryResult } from "@/lib/types";

const API_WS_URL = process.env.NEXT_PUBLIC_API_WS_URL ?? "ws://localhost:8002";

const { Dragger } = Upload;
const { Paragraph, Text, Title } = Typography;
const { Step } = Steps;

const anomalyColorMap: Record<string, string> = {
  no_price_match: "volcano",
  low_match_confidence: "gold",
  unit_mismatch: "purple",
  large_line_amount: "cyan",
  invalid_quantity: "red",
};

const anomalyTextMap: Record<string, string> = {
  no_price_match: "无匹配价格",
  low_match_confidence: "匹配置信度低",
  unit_mismatch: "单位异常",
  large_line_amount: "金额过大",
  invalid_quantity: "数量异常",
};

function downloadBlob(blob: Blob, filename: string) {
  const url = window.URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  window.URL.revokeObjectURL(url);
}

interface ProgressState {
  visible: boolean;
  percent: number;
  current: number;
  total: number;
  step: string;
  detail: string;
  filename: string;
}

export function InquiryClient() {
  const { message } = App.useApp();
  const [currentStep, setCurrentStep] = useState(0);
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [result, setResult] = useState<InquiryResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState<ExportFormat | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<ProgressState>({
    visible: false,
    percent: 0,
    current: 0,
    total: 0,
    step: "",
    detail: "",
    filename: "",
  });
  const wsRef = useRef<WebSocket | null>(null);

  const columns: NonNullable<TableProps<InquiryItem>["columns"]> = useMemo(
    () => [
      { title: "序号", key: "index", width: 60, render: (_, __, index) => index + 1 },
      {
        title: "项目名称",
        dataIndex: "name",
        key: "name",
        fixed: "left",
        width: 200,
        render: (value: string, record) => (
          <div>
            <Text strong className="text-ink">{value}</Text>
            {record.category && <div className="text-xs text-ink-muted">{record.category}</div>}
          </div>
        ),
      },
      { title: "规格型号", dataIndex: "specification", key: "specification", width: 160, render: (v?: string | null) => v || "-" },
      { title: "材质", dataIndex: "material", key: "material", width: 100, render: (v?: string | null) => v || "-" },
      { title: "数量", key: "quantity", width: 100, align: "right", render: (_, r) => <span className="font-mono">{r.quantity} {r.unit}</span> },
      { title: "单价", dataIndex: "unit_price", key: "unit_price", width: 120, align: "right", render: (v?: number | null) =>
        v == null ? <span className="text-ink-muted">-</span> : <span className="font-mono text-ink">¥{v.toLocaleString("zh-CN")}</span>
      },
      { title: "合价", dataIndex: "total_price", key: "total_price", width: 130, align: "right", render: (v?: number | null) =>
        v == null ? <span className="text-ink-muted">-</span> : <span className="font-mono font-semibold text-primary">¥{v.toLocaleString("zh-CN")}</span>
      },
      { title: "状态", dataIndex: "anomalies", key: "anomalies", width: 120, render: (anomalies: string[]) =>
        anomalies.length ? (
          <Space size={[0, 4]} wrap>
            {anomalies.map((a) => <Tag size="small" color={anomalyColorMap[a] ?? "default"} key={a}>{anomalyTextMap[a] || a}</Tag>)}
          </Space>
        ) : <Tag size="small" color="success">已匹配</Tag>
      },
    ],
    []
  );

  async function handleParse() {
    const files = fileList.flatMap((f) => f.originFileObj ? [f.originFileObj as File] : []);
    if (!files.length) { setError("请先上传图纸或清单文件"); return; }

    setLoading(true);
    setError(null);
    setProgress({
      visible: true,
      percent: 0,
      current: 0,
      total: files.length,
      step: "准备处理",
      detail: "",
      filename: "",
    });

    // 使用 WebSocket 获取实时进度
    const ws = new WebSocket(`${API_WS_URL}/ws/inquiry`);
    wsRef.current = ws;

    ws.onopen = () => {
      // 发送文件信息（简化处理，实际应发送base64内容）
      ws.send(JSON.stringify({
        action: "start_processing",
        files: files.map((f, i) => ({ filename: f.name, index: i })),
      }));
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      switch (data.type) {
        case "file_start":
          setProgress(prev => ({
            ...prev,
            current: data.current,
            total: data.total,
            percent: data.percent,
            filename: data.filename,
            step: "正在解析",
          }));
          break;

        case "step_update":
          setProgress(prev => ({
            ...prev,
            step: data.step,
            detail: data.detail,
            percent: data.percent,
          }));
          break;

        case "file_complete":
          if (data.success) {
            message.success(`${data.filename} 解析完成`);
          } else {
            message.warning(`${data.filename} 解析失败`);
          }
          break;

        case "complete":
          setProgress(prev => ({ ...prev, percent: 100 }));
          ws.close();
          break;

        case "error":
          setError(data.message);
          message.error(data.message);
          ws.close();
          break;
      }
    };

    ws.onerror = () => {
      // WebSocket 失败时回退到普通 HTTP 请求
      fallbackParse(files);
    };

    ws.onclose = () => {
      setLoading(false);
      setTimeout(() => {
        setProgress(prev => ({ ...prev, visible: false }));
      }, 500);
    };
  }

  // 回退到普通 HTTP 请求
  async function fallbackParse(files: File[]) {
    try {
      const payload = await parseInquiry(files);
      setResult(payload);
      setCurrentStep(2);
      message.success(`解析完成，识别 ${payload.summary.item_count} 条项目`);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "解析请求失败";
      setError(msg);
      message.error(msg);
    } finally {
      setLoading(false);
    }
  }

  async function handleExport(format: ExportFormat) {
    if (!result) return;
    setExporting(format);
    try {
      const blob = await exportInquiry(result, format);
      downloadBlob(blob, `${result.request_id}.${format}`);
      message.success(`已导出 ${format.toUpperCase()}`);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "导出失败";
      message.error(msg);
    } finally { setExporting(null); }
  }

  const summaryPercent = result
    ? Math.round((result.summary.matched_count / Math.max(result.summary.item_count, 1)) * 100)
    : 0;

  const steps = [
    { title: "上传图纸", icon: <FileTextOutlined /> },
    { title: "智能解析", icon: <FileSearchOutlined /> },
    { title: "询价匹配", icon: <CalculatorOutlined /> },
    { title: "审核确认", icon: <CloudUploadOutlined /> },
  ];

  return (
    <>
      {/* Header */}
      <header className="mb-5 flex items-center justify-between">
        <div>
          <Title level={4} className="!m-0 !text-lg !text-ink">询价工作台</Title>
          <Text className="text-xs text-ink-muted">{result ? `当前任务: ${result.request_id}` : "等待导入图纸文件"}</Text>
        </div>
        <Badge status={result ? "processing" : "default"} text={result ? "处理中" : "就绪"} />
      </header>

      {/* Steps */}
      {/* <Card className="mb-5 rounded-card border-line backdrop-blur-card" variant="borderless">
        <Steps current={currentStep} className="max-w-4xl">
          {steps.map((s, i) => (
            <Step key={i} title={s.title} icon={s.icon} onClick={() => { if (i <= currentStep || (result && i <= 2)) setCurrentStep(i); }}
              className={currentStep >= i || (result && i <= 2) ? "cursor-pointer" : ""} />
          ))}
        </Steps>
      </Card> */}

      {/* Main Content */}
      <div className="grid gap-5 lg:grid-cols-3">
        {/* Left: Upload */}
        <div className="lg:col-span-1">
          <Space orientation="vertical" size="middle" className="w-full">
            <Card className="rounded-card border-line backdrop-blur-card" variant="borderless"
              title={<div className="flex items-center gap-2"><CloudUploadOutlined className="text-primary" /><span className="text-ink">图纸上传</span></div>}>
              <Dragger accept=".dwg,.dxf,.pdf,.png,.jpg,.jpeg,.bmp,.tif,.tiff,.webp,.txt,.csv,.json" beforeUpload={() => false} fileList={fileList} multiple
                onChange={({ fileList: next }) => { setFileList(next); if (next.length > 0 && currentStep === 0) setCurrentStep(1); }}
                className="rounded-metric border-line bg-uploader-gradient hover:border-primary">
                <p className="ant-upload-drag-icon text-primary"><CloudUploadOutlined /></p>
                <p className="ant-upload-text text-sm text-ink">拖拽文件到此处，或点击上传</p>
                <p className="ant-upload-hint text-xs text-ink-muted">支持 DXF、PDF、图片、文本文件</p>
              </Dragger>
              {fileList.length > 0 && <div className="mt-4"><Text className="text-xs text-ink-muted">已选择 {fileList.length} 个文件</Text></div>}
              {error && <Alert className="mt-4" type="error" message={error} showIcon closable onClose={() => setError(null)} />}
            </Card>

            <Card className="rounded-card border-line backdrop-blur-card" variant="borderless">
              <Space orientation="vertical" className="w-full">
                <Button type="primary" icon={<FileSearchOutlined />} loading={loading} onClick={handleParse} disabled={fileList.length === 0 || progress.visible}
                  size="large" block className="rounded-metric shadow-button">{loading ? "解析中..." : "开始智能解析"}</Button>

                {/* 进度条 */}
                {progress.visible && (
                  <div className="mt-4 rounded-lg bg-primary/5 p-4">
                    <div className="flex items-center justify-between mb-2">
                      <Text className="text-sm font-medium text-ink">{progress.step}</Text>
                      <Text className="text-xs text-ink-muted">{progress.current} / {progress.total}</Text>
                    </div>
                    <Progress
                      percent={progress.percent}
                      strokeColor="#e4572e"
                      railColor="rgba(68, 57, 43, 0.12)"
                      showInfo={false}
                    />
                    {progress.filename && (
                      <Text className="text-xs text-ink-muted mt-2 block truncate">
                        正在处理: {progress.filename}
                      </Text>
                    )}
                    {progress.detail && (
                      <Text className="text-xs text-ink-light mt-1 block">
                        {progress.detail}
                      </Text>
                    )}
                  </div>
                )}

                <Divider className="!my-3">导出报告</Divider>
                <Space className="w-full">
                  <Button icon={<DownloadOutlined />} disabled={!result} loading={exporting === "xlsx"} onClick={() => handleExport("xlsx")} className="flex-1">Excel</Button>
                  <Button icon={<DownloadOutlined />} disabled={!result} loading={exporting === "docx"} onClick={() => handleExport("docx")} className="flex-1">Word</Button>
                </Space>
              </Space>
            </Card>

            {result && (
              <Card className="rounded-card border-line backdrop-blur-card bg-metric-gradient" variant="borderless">
                <div className="text-center">
                  <Text className="text-xs font-mono uppercase tracking-wider text-ink-muted">报价命中率</Text>
                  <div className="my-2 text-4xl font-bold text-primary">{summaryPercent}%</div>
                  <Progress percent={summaryPercent} showInfo={false} strokeColor="#e4572e" railColor="rgba(68, 57, 43, 0.12)" size="small" />
                </div>
              </Card>
            )}
          </Space>
        </div>

        {/* Right: Results */}
        <div className="lg:col-span-2">
          <Card className="h-full min-h-[600px] rounded-card border-line backdrop-blur-card" variant="borderless"
            title={
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <CalculatorOutlined className="text-primary" />
                  <span className="text-ink">工程量清单</span>
                  {result && <Tag color="processing" className="ml-2">{result.extraction_mode === "openai" ? "AI 识别" : "规则识别"}</Tag>}
                </div>
                {result && <div className="text-right"><Text className="text-sm text-ink-muted">合计</Text><div className="text-xl font-bold text-primary">¥{result.summary.subtotal.toLocaleString("zh-CN")}</div></div>}
              </div>
            }>
            {result ? (
              <Space orientation="vertical" size="large" className="w-full">
                <Row gutter={16}>
                  <Col span={8}><Card className="rounded-metric border-line bg-paper" variant="borderless"><Statistic title="识别项目" value={result.summary.item_count} valueStyle={{ color: "#211f1a", fontSize: 24 }} /></Card></Col>
                  <Col span={8}><Card className="rounded-metric border-line bg-paper" variant="borderless"><Statistic title="已匹配" value={result.summary.matched_count} valueStyle={{ color: "#52c41a", fontSize: 24 }} /></Card></Col>
                  <Col span={8}><Card className="rounded-metric border-line bg-paper" variant="borderless"><Statistic title="异常标记" value={result.summary.flagged_count} valueStyle={{ color: result.summary.flagged_count > 0 ? "#fa8c16" : "#211f1a", fontSize: 24 }} /></Card></Col>
                </Row>

                {result.warnings.length > 0 && <Alert type="warning" showIcon message="解析提示" description={<Space size={[4, 8]} wrap>{result.warnings.map((w) => <Tag key={w}>{w}</Tag>)}</Space>} />}

                <Table<InquiryItem> rowKey={(r, i) => `${r.name}-${r.specification ?? "na"}-${i}`} columns={columns} dataSource={result.items}
                  pagination={{ pageSize: 8, hideOnSinglePage: true, showSizeChanger: false }} scroll={{ x: 1000 }} size="small" className="rounded-metric overflow-hidden" />

                <div>
                  <Text className="mb-3 block text-xs font-mono uppercase tracking-wider text-ink-muted">来源文件</Text>
                  <Row gutter={[12, 12]}>
                    {result.documents.map((doc) => (
                      <Col xs={24} md={12} key={doc.filename}>
                        <Card className="rounded-metric border-line bg-paper" variant="borderless" size="small">
                          <div className="flex items-start justify-between">
                            <div>
                              <Text strong className="text-ink">{doc.filename}</Text>
                              <div className="text-xs text-ink-muted">{doc.file_type.toUpperCase()} · {doc.parser}</div>
                            </div>
                            {doc.warnings.length > 0 && <Tooltip title={doc.warnings.join(", ")}><WarningOutlined className="text-amber-500" /></Tooltip>}
                          </div>
                          <Paragraph ellipsis={{ rows: 2 }} className="!mb-0 mt-2 text-xs text-ink-light">{doc.text_excerpt}</Paragraph>
                        </Card>
                      </Col>
                    ))}
                  </Row>
                </div>
              </Space>
            ) : (
              <div className="flex h-[400px] flex-col items-center justify-center rounded-metric border border-dashed border-line bg-paper/50">
                <Empty image={<FileTextOutlined className="text-6xl text-line-strong" />} description={<div className="text-center"><Text className="block text-ink">暂无数据</Text><Text className="text-sm text-ink-muted">上传图纸文件后，系统将自动解析并生成工程量清单</Text></div>} />
              </div>
            )}
          </Card>
        </div>
      </div>
    </>
  );
}
