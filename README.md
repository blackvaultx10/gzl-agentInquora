# Inquora Smart Inquiry Agent MVP

一个面向工程图纸询价的前后端分离 MVP。

- `apps/web`: Next.js 15 + Ant Design 工作台，负责上传、结果展示、Excel/Word 下载
- `apps/api`: FastAPI 管道，负责文件解析、OCR、参数抽取、报价匹配与导出
- `apps/api/data/price_catalog.csv`: 样本价格库

## 当前能力

已实现：

1. 上传 `DWG / DXF / PDF / 图片 / TXT / CSV / JSON`
2. PDF 无文本时自动 OCR
3. 用 `OpenAI / DeepSeek / heuristic` 三种模式做参数抽取
4. 用 CSV 价格库做单价匹配、总价计算、异常标记
5. 导出 `Excel / Word`

当前限制：

- `DXF` 可直接解析
- `DWG` 在生产环境应接入专门的 DWG backend，不建议依赖开发机桌面转换器
- 图纸型 PDF 的 OCR 已支持高倍渲染，但系统图/平面图这类文件仍需要更强的区域抽取策略

## 目录结构

```text
apps/
  api/
    app/
      api/
      services/
    data/
  web/
    app/
    components/
    lib/
```

## 后端启动

```powershell
cd D:\Projects\custom10\gzl-agentInquora\apps\api
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r requirements-ocr.txt   # 可选，启用 OCR
Copy-Item .env.example .env
uvicorn app.main:app --reload --port 8000
```

## 前端启动

```powershell
cd D:\Projects\custom10\gzl-agentInquora\apps\web
Copy-Item .env.local.example .env.local
npm install
npm run dev
```

默认前端请求 `http://localhost:8000/api/v1`。

## LLM 配置

后端支持三种抽取模式：

- `LLM_PROVIDER=auto`
  - 优先用 `DeepSeek`
  - 没有 `DeepSeek` 时回退 `OpenAI`
  - 都没有时回退本地规则 `heuristic`
- `LLM_PROVIDER=deepseek`
  - 强制使用 `DeepSeek`
- `LLM_PROVIDER=openai`
  - 强制使用 `OpenAI`
- `LLM_PROVIDER=none`
  - 只用本地规则

### DeepSeek

在 `apps/api/.env` 中配置：

```env
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=your_token
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

### OpenAI

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=your_key
OPENAI_MODEL=gpt-5-mini
```

## API

- `POST /api/v1/inquiry/parse`
  - 表单字段：`files`
  - 返回：结构化询价结果
- `POST /api/v1/inquiry/export?format=xlsx|docx`
  - 请求体：`{"result": <InquiryResult>}`
  - 返回：导出文件流

## 生产化建议

如果继续往上线版本推进，建议按这个方向演进：

1. 把 `DWG` 解析做成独立 backend 适配层，不绑定桌面软件
2. 增加异步任务队列，避免大图纸 OCR 阻塞请求
3. 对系统图/平面图增加区域放大 OCR 和表格抽取
4. 将 CSV 报价库升级为数据库或检索服务
