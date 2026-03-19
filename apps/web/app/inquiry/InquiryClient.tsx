"use client";

import {
  CalculatorOutlined,
  CloudUploadOutlined,
  DownloadOutlined,
  FileSearchOutlined,
  FileTextOutlined,
  FolderAddOutlined,
  FolderOpenOutlined,
  WarningOutlined,
} from "@ant-design/icons";
import {
  Alert,
  App,
  Badge,
  Button,
  Card,
  Col,
  Divider,
  Empty,
  Form,
  Input,
  Modal,
  Progress,
  Row,
  Select,
  Space,
  Statistic,
  Table,
  Tag,
  Tooltip,
  Typography,
  Upload,
} from "antd";
import type { TableProps, UploadFile } from "antd";
import { useEffect, useMemo, useState } from "react";

import {
  createInquiryJob,
  createProject,
  exportInquiry,
  getInquiryJob,
  listProjects,
} from "@/lib/api";
import type {
  ExportFormat,
  InquiryItem,
  InquiryJobSnapshot,
  InquiryResult,
  ProjectSummary,
} from "@/lib/types";

const { Dragger } = Upload;
const { Paragraph, Text, Title } = Typography;

const anomalyColorMap: Record<string, string> = {
  unmapped_boq_item: "volcano",
  reference_low_confidence: "gold",
  invalid_quantity: "red",
};

const anomalyTextMap: Record<string, string> = {
  unmapped_boq_item: "未套用清单编码",
  reference_low_confidence: "参考价置信度低",
  invalid_quantity: "数量异常",
};

interface ProgressState {
  visible: boolean;
  percent: number;
  total: number;
  current: number;
  step: string;
  currentFileName?: string | null;
}

interface CreateProjectForm {
  name: string;
  description?: string;
}

function downloadBlob(blob: Blob, filename: string) {
  const url = window.URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  window.URL.revokeObjectURL(url);
}

function formatCurrency(value?: number | null) {
  if (value == null) {
    return "-";
  }
  return `¥${value.toLocaleString("zh-CN")}`;
}

function sleep(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function buildProgressState(snapshot: InquiryJobSnapshot): ProgressState {
  return {
    visible: true,
    percent: snapshot.progress.percent,
    total: snapshot.progress.total,
    current: snapshot.progress.current,
    step: snapshot.progress.step,
    currentFileName: snapshot.progress.current_file_name,
  };
}

export function InquiryClient() {
  const { message } = App.useApp();
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<number | undefined>();
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [projectsLoading, setProjectsLoading] = useState(false);
  const [creatingProject, setCreatingProject] = useState(false);
  const [result, setResult] = useState<InquiryResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState<ExportFormat | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<ProgressState>({
    visible: false,
    percent: 0,
    total: 0,
    current: 0,
    step: "",
    currentFileName: null,
  });
  const [projectForm] = Form.useForm<CreateProjectForm>();

  const selectedProject = useMemo(
    () => projects.find((project) => project.id === selectedProjectId) ?? null,
    [projects, selectedProjectId],
  );

  const columns: NonNullable<TableProps<InquiryItem>["columns"]> = useMemo(
    () => [
      {
        title: "序号",
        key: "index",
        width: 64,
        render: (_, __, index) => index + 1,
      },
      {
        title: "清单编码",
        dataIndex: "boq_code",
        key: "boq_code",
        width: 130,
        render: (value?: string | null) => value || "-",
      },
      {
        title: "清单项目",
        dataIndex: "name",
        key: "name",
        fixed: "left",
        width: 180,
        render: (value: string, record) => (
          <div>
            <Text strong className="text-ink">
              {value}
            </Text>
            {record.category && (
              <div className="text-xs text-ink-muted">{record.category}</div>
            )}
          </div>
        ),
      },
      {
        title: "项目特征",
        dataIndex: "specification",
        key: "specification",
        width: 240,
        render: (value?: string | null) => value || "-",
      },
      {
        title: "工程量",
        key: "quantity",
        width: 110,
        align: "right",
        render: (_, record) => (
          <span className="font-mono">
            {record.quantity} {record.unit}
          </span>
        ),
      },
      {
        title: "询价方式",
        dataIndex: "inquiry_method",
        key: "inquiry_method",
        width: 120,
        render: (value?: string | null) => value || "待定",
      },
      {
        title: "来源图纸",
        dataIndex: "source_documents",
        key: "source_documents",
        width: 220,
        render: (value: string[]) =>
          value.length ? value.join("、") : <span className="text-ink-muted">-</span>,
      },
      {
        title: "参考单价",
        dataIndex: "reference_unit_price",
        key: "reference_unit_price",
        width: 130,
        align: "right",
        render: (value?: number | null) => (
          <span className="font-mono text-ink">{formatCurrency(value)}</span>
        ),
      },
      {
        title: "参考合价",
        dataIndex: "reference_total_price",
        key: "reference_total_price",
        width: 140,
        align: "right",
        render: (value?: number | null) => (
          <span className="font-mono font-semibold text-primary">
            {formatCurrency(value)}
          </span>
        ),
      },
      {
        title: "状态",
        dataIndex: "anomalies",
        key: "anomalies",
        width: 180,
        render: (anomalies: string[], record) => {
          if (anomalies.length) {
            return (
              <Space size={[0, 4]} wrap>
                {anomalies.map((anomaly) => (
                  <Tag
                    className="text-xs"
                    color={anomalyColorMap[anomaly] ?? "default"}
                    key={anomaly}
                  >
                    {anomalyTextMap[anomaly] || anomaly}
                  </Tag>
                ))}
              </Space>
            );
          }
          if (record.reference_unit_price != null) {
            return <Tag color="success">有参考价</Tag>;
          }
          return <Tag>待询价</Tag>;
        },
      },
    ],
    [],
  );

  useEffect(() => {
    void loadProjectOptions();
  }, []);

  async function loadProjectOptions() {
    setProjectsLoading(true);
    try {
      const projectList = await listProjects();
      setProjects(projectList);
      setSelectedProjectId((current) => current ?? projectList[0]?.id);
    } catch (currentError) {
      const messageText =
        currentError instanceof Error ? currentError.message : "项目列表加载失败";
      setError(messageText);
    } finally {
      setProjectsLoading(false);
    }
  }

  async function handleCreateProject(values: CreateProjectForm) {
    setCreatingProject(true);
    try {
      const project = await createProject(values);
      setProjects((current) => [project, ...current.filter((item) => item.id !== project.id)]);
      setSelectedProjectId(project.id);
      setResult(null);
      setFileList([]);
      setError(null);
      setCreateModalOpen(false);
      projectForm.resetFields();
      message.success(`已创建项目 ${project.name}`);
    } catch (currentError) {
      const messageText =
        currentError instanceof Error ? currentError.message : "项目创建失败";
      message.error(messageText);
    } finally {
      setCreatingProject(false);
    }
  }

  async function pollInquiryJob(jobId: string): Promise<InquiryResult> {
    for (;;) {
      const snapshot = await getInquiryJob(jobId);
      setProgress(buildProgressState(snapshot));

      if (snapshot.status === "completed" && snapshot.result) {
        return snapshot.result;
      }

      if (snapshot.status === "failed") {
        throw new Error(snapshot.error || "任务处理失败");
      }

      await sleep(1000);
    }
  }

  async function handleParse() {
    const files = fileList.flatMap((file) =>
      file.originFileObj ? [file.originFileObj as File] : [],
    );
    if (!selectedProjectId) {
      setError("请先创建或选择项目。");
      return;
    }
    if (!files.length) {
      setError("请先上传项目图纸。");
      return;
    }

    setLoading(true);
    setError(null);
    setProgress({
      visible: true,
      percent: 2,
      total: files.length,
      current: 0,
      step: "正在提交任务",
      currentFileName: null,
    });

    try {
      const snapshot = await createInquiryJob(files, selectedProjectId);
      setProgress(buildProgressState(snapshot));
      const payload = await pollInquiryJob(snapshot.job_id);
      setResult(payload);
      setProgress({
        visible: true,
        percent: 100,
        total: files.length,
        current: files.length,
        step: "项目清单已生成",
        currentFileName: null,
      });
      void loadProjectOptions();
      message.success(`已生成 ${payload.summary.item_count} 项项目清单`);
    } catch (currentError) {
      const messageText =
        currentError instanceof Error ? currentError.message : "解析请求失败";
      setError(messageText);
      message.error(messageText);
    } finally {
      setLoading(false);
      window.setTimeout(() => {
        setProgress((current) => ({ ...current, visible: false }));
      }, 1000);
    }
  }

  async function handleExport(format: ExportFormat) {
    if (!result) {
      return;
    }
    setExporting(format);
    try {
      const blob = await exportInquiry(result, format);
      downloadBlob(blob, `${result.project_name || result.request_id}.${format}`);
      message.success(`已导出 ${format.toUpperCase()}`);
    } catch (currentError) {
      const messageText =
        currentError instanceof Error ? currentError.message : "导出失败";
      message.error(messageText);
    } finally {
      setExporting(null);
    }
  }

  const referencePercent = result
    ? Math.round(
        (result.summary.reference_count / Math.max(result.summary.item_count, 1)) *
          100,
      )
    : 0;

  const currentProjectLabel =
    selectedProject?.name ?? result?.project_name ?? "请先创建并选择项目";

  return (
    <>
      <header className="mb-5 flex items-center justify-between">
        <div>
          <Title level={4} className="!m-0 !text-lg !text-ink">
            项目询价工作台
          </Title>
          <Text className="text-xs text-ink-muted">当前项目: {currentProjectLabel}</Text>
        </div>
        <Badge
          status={loading ? "processing" : result ? "success" : "default"}
          text={
            loading ? "正在处理" : result ? "项目清单已生成" : "等待创建项目"
          }
        />
      </header>

      <div className="grid gap-5 lg:grid-cols-3">
        <div className="lg:col-span-1">
          <Space orientation="vertical" size="middle" className="w-full">
            <Card
              className="rounded-card border-line backdrop-blur-card"
              variant="borderless"
              title={
                <div className="flex items-center gap-2">
                  <FolderOpenOutlined className="text-primary" />
                  <span className="text-ink">项目归档</span>
                </div>
              }
            >
              <Space direction="vertical" size="middle" className="w-full">
                <div>
                  <Text className="mb-2 block text-sm text-ink">项目</Text>
                  <Space.Compact className="w-full">
                    <Select
                      placeholder="先选择项目"
                      value={selectedProjectId}
                      loading={projectsLoading}
                      options={projects.map((project) => ({
                        value: project.id,
                        label: project.name,
                      }))}
                      onChange={(value) => {
                        setSelectedProjectId(value);
                        setResult(null);
                        setFileList([]);
                        setError(null);
                      }}
                      className="w-full"
                      showSearch
                      optionFilterProp="label"
                    />
                    <Button
                      icon={<FolderAddOutlined />}
                      onClick={() => setCreateModalOpen(true)}
                    >
                      新建
                    </Button>
                  </Space.Compact>
                </div>

                {!projectsLoading && projects.length === 0 && (
                  <Alert
                    type="info"
                    showIcon
                    message="还没有项目"
                    description="先创建项目，再上传系统图、设计说明、平面图和图例文件。"
                  />
                )}

                <Dragger
                  accept=".dwg,.dxf,.pdf,.png,.jpg,.jpeg,.bmp,.tif,.tiff,.webp,.txt,.csv,.json"
                  beforeUpload={() => false}
                  fileList={fileList}
                  multiple
                  disabled={!selectedProjectId || loading}
                  onChange={({ fileList: nextFileList }) => setFileList(nextFileList)}
                  className="rounded-metric border-line bg-uploader-gradient hover:border-primary"
                >
                  <p className="ant-upload-drag-icon text-primary">
                    <CloudUploadOutlined />
                  </p>
                  <p className="ant-upload-text text-sm text-ink">
                    按项目上传图纸与说明文件
                  </p>
                  <p className="ant-upload-hint text-xs text-ink-muted">
                    建议同一批次上传配电系统图、设计说明、平面图、图例符号说明
                  </p>
                </Dragger>

                <Button
                  type="primary"
                  icon={<FileSearchOutlined />}
                  loading={loading}
                  onClick={handleParse}
                  disabled={!selectedProjectId || fileList.length === 0 || progress.visible}
                  size="large"
                  block
                  className="rounded-metric shadow-button"
                >
                  {loading ? "处理中..." : "生成项目清单"}
                </Button>

                {progress.visible && (
                  <div className="rounded-lg bg-primary/5 p-4">
                    <div className="mb-2 flex items-center justify-between gap-3">
                      <div>
                        <Text className="block text-sm font-medium text-ink">
                          {progress.step}
                        </Text>
                        {progress.currentFileName && (
                          <Text className="text-xs text-ink-muted">
                            当前文件: {progress.currentFileName}
                          </Text>
                        )}
                      </div>
                      <Text className="text-xs text-ink-muted">
                        {progress.current}/{progress.total || 0}
                      </Text>
                    </div>
                    <Progress
                      percent={progress.percent}
                      strokeColor="#e4572e"
                      railColor="rgba(68, 57, 43, 0.12)"
                      showInfo={false}
                    />
                  </div>
                )}

                {error && (
                  <Alert
                    type="error"
                    message={error}
                    showIcon
                    closable
                    onClose={() => setError(null)}
                  />
                )}

                <Divider className="!my-2">导出</Divider>
                <Space className="w-full">
                  <Button
                    icon={<DownloadOutlined />}
                    disabled={!result}
                    loading={exporting === "xlsx"}
                    onClick={() => handleExport("xlsx")}
                    className="flex-1"
                  >
                    Excel
                  </Button>
                  <Button
                    icon={<DownloadOutlined />}
                    disabled={!result}
                    loading={exporting === "docx"}
                    onClick={() => handleExport("docx")}
                    className="flex-1"
                  >
                    Word
                  </Button>
                </Space>
              </Space>
            </Card>

            {result && (
              <Card
                className="rounded-card border-line backdrop-blur-card bg-metric-gradient"
                variant="borderless"
              >
                <div className="text-center">
                  <Text className="text-xs font-mono uppercase tracking-wider text-ink-muted">
                    参考价覆盖率
                  </Text>
                  <div className="my-2 text-4xl font-bold text-primary">
                    {referencePercent}%
                  </div>
                  <Progress
                    percent={referencePercent}
                    showInfo={false}
                    strokeColor="#e4572e"
                    railColor="rgba(68, 57, 43, 0.12)"
                    size="small"
                  />
                </div>
              </Card>
            )}
          </Space>
        </div>

        <div className="lg:col-span-2">
          <Card
            className="h-full min-h-[600px] rounded-card border-line backdrop-blur-card"
            variant="borderless"
            title={
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <CalculatorOutlined className="text-primary" />
                  <span className="text-ink">项目询价清单</span>
                  {result && (
                    <>
                      <Tag color="processing">{result.extraction_mode}</Tag>
                      <Tag color="blue">
                        {result.pricing_mode === "reference_only"
                          ? "参考价模式"
                          : result.pricing_mode}
                      </Tag>
                    </>
                  )}
                </div>
                {result && (
                  <div className="text-right">
                    <Text className="text-sm text-ink-muted">参考合计</Text>
                    <div className="text-xl font-bold text-primary">
                      {formatCurrency(result.summary.reference_subtotal)}
                    </div>
                  </div>
                )}
              </div>
            }
          >
            {result ? (
              <Space orientation="vertical" size="large" className="w-full">
                <Row gutter={16}>
                  <Col span={8}>
                    <Card
                      className="rounded-metric border-line bg-paper"
                      variant="borderless"
                    >
                      <Statistic
                        title="清单项数"
                        value={result.summary.item_count}
                        valueStyle={{ color: "#211f1a", fontSize: 24 }}
                      />
                    </Card>
                  </Col>
                  <Col span={8}>
                    <Card
                      className="rounded-metric border-line bg-paper"
                      variant="borderless"
                    >
                      <Statistic
                        title="参考价项"
                        value={result.summary.reference_count}
                        valueStyle={{ color: "#52c41a", fontSize: 24 }}
                      />
                    </Card>
                  </Col>
                  <Col span={8}>
                    <Card
                      className="rounded-metric border-line bg-paper"
                      variant="borderless"
                    >
                      <Statistic
                        title="待询价项"
                        value={result.summary.pending_count}
                        valueStyle={{ color: "#fa8c16", fontSize: 24 }}
                      />
                    </Card>
                  </Col>
                </Row>

                {result.warnings.length > 0 && (
                  <Alert
                    type="warning"
                    showIcon
                    message="处理提示"
                    description={
                      <Space size={[4, 8]} wrap>
                        {result.warnings.map((warning) => (
                          <Tag key={warning}>{warning}</Tag>
                        ))}
                      </Space>
                    }
                  />
                )}

                <Table<InquiryItem>
                  rowKey={(record, index) =>
                    `${record.boq_code ?? "na"}-${record.name}-${record.specification ?? "na"}-${index}`
                  }
                  columns={columns}
                  dataSource={result.items}
                  pagination={{
                    pageSize: 50,
                    hideOnSinglePage: true,
                    showSizeChanger: true,
                    pageSizeOptions: [20, 50, 100],
                    showTotal: (total) => `共 ${total} 项`,
                  }}
                  scroll={{ x: 1500 }}
                  size="small"
                  className="rounded-metric overflow-hidden"
                />

                <div>
                  <Text className="mb-3 block text-xs font-mono uppercase tracking-wider text-ink-muted">
                    来源文件
                  </Text>
                  <Row gutter={[12, 12]}>
                    {result.documents.map((document) => (
                      <Col xs={24} md={12} key={document.filename}>
                        <Card
                          className="rounded-metric border-line bg-paper"
                          variant="borderless"
                          size="small"
                        >
                          <div className="flex items-start justify-between">
                            <div>
                              <Text strong className="text-ink">
                                {document.filename}
                              </Text>
                              <div className="text-xs text-ink-muted">
                                {document.file_type.toUpperCase()} · {document.parser}
                              </div>
                            </div>
                            {document.warnings.length > 0 && (
                              <Tooltip title={document.warnings.join("，")}>
                                <WarningOutlined className="text-amber-500" />
                              </Tooltip>
                            )}
                          </div>
                          <Paragraph
                            ellipsis={{ rows: 2 }}
                            className="!mb-0 mt-2 text-xs text-ink-light"
                          >
                            {document.text_excerpt}
                          </Paragraph>
                        </Card>
                      </Col>
                    ))}
                  </Row>
                </div>
              </Space>
            ) : (
              <div className="flex h-[400px] flex-col items-center justify-center rounded-metric border border-dashed border-line bg-paper/50">
                <Empty
                  image={<FileTextOutlined className="text-6xl text-line-strong" />}
                  description={
                    <div className="text-center">
                      <Text className="block text-ink">暂无项目清单</Text>
                      <Text className="text-sm text-ink-muted">
                        先创建项目，再上传系统图、设计说明、平面图和图例说明文件
                      </Text>
                    </div>
                  }
                />
              </div>
            )}
          </Card>
        </div>
      </div>

      <Modal
        title="创建项目"
        open={createModalOpen}
        onCancel={() => setCreateModalOpen(false)}
        onOk={() => projectForm.submit()}
        confirmLoading={creatingProject}
        okText="创建"
        destroyOnHidden
      >
        <Form<CreateProjectForm>
          form={projectForm}
          layout="vertical"
          onFinish={handleCreateProject}
        >
          <Form.Item<CreateProjectForm>
            name="name"
            label="项目名称"
            rules={[{ required: true, message: "请输入项目名称" }]}
          >
            <Input placeholder="例如：罗湖美术馆升级改造项目" maxLength={200} />
          </Form.Item>
          <Form.Item<CreateProjectForm> name="description" label="项目备注">
            <Input.TextArea
              placeholder="可选，用于记录项目阶段、专业范围或批次说明"
              rows={3}
              maxLength={2000}
            />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}
