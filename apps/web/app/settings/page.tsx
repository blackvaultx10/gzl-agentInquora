"use client";

import { DeleteOutlined, EditOutlined, EyeInvisibleOutlined, EyeOutlined, PlusOutlined, SaveOutlined } from "@ant-design/icons";
import { App, Button, Card, Form, Input, Modal, Select, Space, Switch, Table, Tag, Typography } from "antd";
import { useEffect, useMemo, useState } from "react";

import { createConfig, deleteConfig, getConfigs, getProviderTypes, updateConfig } from "@/lib/api";
import type { ProviderConfig } from "@/lib/types";

const { Title, Text } = Typography;
const { Option } = Select;

interface ProviderType {
  type: string;
  name: string;
  description: string;
  fields: string[];
}

const defaultProviderNames: Record<string, string> = {
  deepseek: "DeepSeek",
  openai: "OpenAI",
  baidu_ocr: "百度智能云 OCR",
  tencent_ocr: "腾讯云 OCR",
  aliyun_ocr: "阿里云 OCR",
};

export default function SettingsPage() {
  const { message } = App.useApp();
  const [configs, setConfigs] = useState<ProviderConfig[]>([]);
  const [providerTypes, setProviderTypes] = useState<ProviderType[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingConfig, setEditingConfig] = useState<ProviderConfig | null>(null);
  const [form] = Form.useForm();
  const [showApiKey, setShowApiKey] = useState(false);
  const [showSecretKey, setShowSecretKey] = useState(false);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [configsData, typesData] = await Promise.all([
        getConfigs(),
        getProviderTypes(),
      ]);
      setConfigs(configsData);
      setProviderTypes(typesData);
    } catch (e) {
      message.error("加载配置失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleAdd = () => {
    setEditingConfig(null);
    form.resetFields();
    setShowApiKey(false);
    setShowSecretKey(false);
    setModalVisible(true);
  };

  const handleEdit = (config: ProviderConfig) => {
    setEditingConfig(config);
    form.setFieldsValue({
      provider_type: config.provider_type,
      name: config.name,
      api_key: config.api_key || "",
      secret_key: "", // 编辑时不回填密钥，需重新输入
      base_url: config.base_url || "",
      model: config.model || "",
      is_active: config.is_active,
    });
    setShowApiKey(false);
    setShowSecretKey(false);
    setModalVisible(true);
  };

  const handleDelete = async (providerType: string) => {
    Modal.confirm({
      title: "确认删除",
      content: `确定要删除 ${defaultProviderNames[providerType] || providerType} 的配置吗？`,
      onOk: async () => {
        try {
          await deleteConfig(providerType);
          message.success("删除成功");
          fetchData();
        } catch (e) {
          message.error("删除失败");
        }
      },
    });
  };

  const handleSubmit = async (values: any) => {
    try {
      const data = {
        ...values,
        // 编辑时如果密钥为空，保持原值
        api_key: values.api_key || (editingConfig?.api_key ? undefined : ""),
        secret_key: values.secret_key || undefined,
      };

      if (editingConfig) {
        await updateConfig(editingConfig.provider_type, data);
        message.success("更新成功");
      } else {
        await createConfig(data);
        message.success("创建成功");
      }
      setModalVisible(false);
      fetchData();
    } catch (e) {
      message.error(editingConfig ? "更新失败" : "创建失败");
    }
  };

  const selectedProviderType = Form.useWatch("provider_type", form);
  const selectedProvider = useMemo(
    () => providerTypes.find((p) => p.type === selectedProviderType),
    [providerTypes, selectedProviderType]
  );

  const columns = [
    {
      title: "服务类型",
      dataIndex: "provider_type",
      key: "provider_type",
      render: (v: string) => (
        <div>
          <Text strong>{defaultProviderNames[v] || v}</Text>
          <div className="text-xs text-ink-muted">{v}</div>
        </div>
      ),
    },
    {
      title: "显示名称",
      dataIndex: "name",
      key: "name",
    },
    {
      title: "API Key",
      dataIndex: "api_key",
      key: "api_key",
      render: (v: string | null) => v ? <Tag color="success">已配置</Tag> : <Tag>未配置</Tag>,
    },
    {
      title: "状态",
      dataIndex: "is_active",
      key: "is_active",
      render: (v: boolean) => (
        <Tag color={v ? "success" : "default"}>{v ? "启用" : "禁用"}</Tag>
      ),
    },
    {
      title: "更新时间",
      dataIndex: "updated_at",
      key: "updated_at",
      render: (v: string) => new Date(v).toLocaleString("zh-CN"),
    },
    {
      title: "操作",
      key: "action",
      render: (_: any, record: ProviderConfig) => (
        <Space>
          <Button type="link" icon={<EditOutlined />} onClick={() => handleEdit(record)}>
            编辑
          </Button>
          <Button type="link" danger icon={<DeleteOutlined />} onClick={() => handleDelete(record.provider_type)}>
            删除
          </Button>
        </Space>
      ),
    },
  ];

  // 根据选择的提供商自动填充名称
  const handleProviderChange = (value: string) => {
    const provider = providerTypes.find((p) => p.type === value);
    if (provider && !editingConfig) {
      form.setFieldValue("name", provider.name);
    }
  };

  return (
    <>
      <header className="mb-5">
        <Title level={4} className="!m-0 !text-lg !text-ink">系统设置</Title>
        <Text className="text-xs text-ink-muted">管理第三方服务配置（API Key 加密存储）</Text>
      </header>

      <div className="grid gap-5">
        <Card
          className="rounded-card border-line backdrop-blur-card"
          variant="borderless"
          title={<span className="text-ink">第三方服务配置</span>}
          extra={
            <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>
              新增配置
            </Button>
          }
        >
          <Table
            columns={columns}
            dataSource={configs}
            rowKey="id"
            loading={loading}
            pagination={false}
            className="rounded-metric overflow-hidden"
          />

          <div className="mt-4 rounded-lg bg-amber-50 p-4">
            <Text className="text-sm text-amber-700">
              <strong>安全提示：</strong>API Key 和 Secret Key 使用 AES 加密存储，
              数据库中不会保存明文。删除配置后密钥将无法恢复。
            </Text>
          </div>
        </Card>
      </div>

      <Modal
        title={editingConfig ? "编辑配置" : "新增配置"}
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        footer={null}
        width={600}
      >
        <Form form={form} layout="vertical" onFinish={handleSubmit} className="mt-4">
          <Form.Item
            name="provider_type"
            label="服务类型"
            rules={[{ required: true, message: "请选择服务类型" }]}
          >
            <Select
              placeholder="选择服务类型"
              disabled={!!editingConfig}
              onChange={handleProviderChange}
            >
              {providerTypes.map((p) => (
                <Option key={p.type} value={p.type}>
                  {p.name} ({p.description})
                </Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            name="name"
            label="显示名称"
            rules={[{ required: true, message: "请输入显示名称" }]}
          >
            <Input placeholder="例如：生产环境 DeepSeek" />
          </Form.Item>

          {selectedProvider?.fields.includes("api_key") && (
            <Form.Item
              name="api_key"
              label="API Key"
              rules={[{ required: !editingConfig, message: "请输入 API Key" }]}
            >
              <Input.Password
                placeholder={editingConfig ? "留空保持原值" : "请输入 API Key"}
                visibilityToggle={{
                  visible: showApiKey,
                  onVisibleChange: setShowApiKey,
                }}
                iconRender={(visible) => (visible ? <EyeOutlined /> : <EyeInvisibleOutlined />)}
              />
            </Form.Item>
          )}

          {selectedProvider?.fields.includes("secret_key") && (
            <Form.Item
              name="secret_key"
              label="Secret Key"
              rules={[{ required: !editingConfig, message: "请输入 Secret Key" }]}
            >
              <Input.Password
                placeholder={editingConfig ? "留空保持原值" : "请输入 Secret Key"}
                visibilityToggle={{
                  visible: showSecretKey,
                  onVisibleChange: setShowSecretKey,
                }}
                iconRender={(visible) => (visible ? <EyeOutlined /> : <EyeInvisibleOutlined />)}
              />
            </Form.Item>
          )}

          {selectedProvider?.fields.includes("base_url") && (
            <Form.Item name="base_url" label="基础 URL">
              <Input placeholder="例如：https://api.deepseek.com" />
            </Form.Item>
          )}

          {selectedProvider?.fields.includes("model") && (
            <Form.Item name="model" label="模型名称">
              <Input placeholder="例如：deepseek-chat" />
            </Form.Item>
          )}

          <Form.Item name="is_active" label="启用状态" valuePropName="checked">
            <Switch checkedChildren="启用" unCheckedChildren="禁用" defaultChecked />
          </Form.Item>

          <Form.Item className="mb-0">
            <Space className="w-full justify-end">
              <Button onClick={() => setModalVisible(false)}>取消</Button>
              <Button type="primary" htmlType="submit" icon={<SaveOutlined />}>
                保存
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}
