from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Iterable
from typing import Literal

from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError

from app.config import Settings
from app.config_manager import get_config_manager
from app.models import InquiryItem, ParsedDocument


# 设备清单（需厂家询价，单价高，要技术参数）
EQUIPMENT_CATEGORY_MAP = {
    "插座箱": "电气设备",
    "插座": "电气设备",
    "控制箱": "电气设备",
    "集中电源": "电气设备",
    "泵": "泵组设备",
    "风机": "通风设备",
    "配电箱": "电气设备",
    "灭火器": "消防设备",
    "空调": "暖通设备",
    "机组": "成套设备",
    "控制柜": "电气设备",
    "变压器": "电气设备",
}

# 物料表/材料表（可市场询价，单价低，按规格买）
MATERIAL_CATEGORY_MAP = {
    "阀": "阀门",
    "阀门": "阀门",
    "电缆桥架": "电气辅材",
    "钢管": "管材",
    "风管": "风系统材料",
    "水管": "水系统材料",
    "螺栓": "紧固件",
    "法兰": "管件",
    "弯头": "管件",
    "三通": "管件",
    "保温材料": "绝热材料",
    "支架": "支吊架",
}

# 合并用于识别（保持向后兼容）
NAME_CATEGORY_MAP = {**EQUIPMENT_CATEGORY_MAP, **MATERIAL_CATEGORY_MAP}

UNIT_PATTERN = r"(台|套|个|只|件|具|组|米|m|㎡|m2|项|EA|PCS|pcs)"
QTY_PATTERN = re.compile(
    rf"(?<![A-Za-z0-9])(?P<qty>\d+(?:\.\d+)?)\s*(?P<unit>{UNIT_PATTERN})(?![A-Za-z0-9/])"
)
SPEC_PATTERN = re.compile(r"(DN\d+|Q=\S+|H=\S+|\u03A6\S+|\u03C6\S+|[A-Z]{1,6}-\d+(?:-\d+)?)")
ELECTRICAL_SPEC_PATTERN = re.compile(r"((?:AC|DC)\s*\d+\s*V(?:\s*\d+\s*A)?)", re.IGNORECASE)
CABLE_MODEL_PATTERN = re.compile(
    r"\b[A-Z]{2,}[A-Z0-9./-]*-\d+(?:\.\d+)?(?:[Xx*]\d+(?:\.\d+)?(?:MM2|MM\u00b2|MM\^2)?)?[A-Z0-9./-]*\b",
    re.IGNORECASE,
)
CABLE_RUN_PATTERN = re.compile(
    r"(?P<count>\d+)\s*\u6761\s*(?P<model>[A-Z0-9./-]+(?:\s+[A-Z0-9./-]+)*)",
    re.IGNORECASE,
)
CABLE_LENGTH_PATTERN = re.compile(r"\u7535\u7f06\u957f\u5ea6\s*(?P<count>\d+)\*(?P<length>\d+(?:\.\d+)?)\s*m", re.IGNORECASE)
PUMP_SPEC_PATTERN = re.compile(
    r"Q=(?P<flow>[^,\s]+),H=(?P<head>[^,\s]+),N=(?P<power>\d+(?:\.\d+)?)KW(?:\((?P<remark>[^)]*)\))?",
    re.IGNORECASE,
)
PUMP_GROUP_PATTERN = re.compile(r"(?P<name>.+?\u6cf5\u7ec4)\((?P<duty>\d+)\u7528(?P<standby>\d+)\u5907(?:(?P<aux>\d+)\u8f85)?\)")
PUMP_POWER_SPLIT_PATTERN = re.compile(r"\u4e3b\u6cf5(?P<main>\d+(?:\.\d+)?)KW/\u8f85\u6cf5(?P<aux>\d+(?:\.\d+)?)KW", re.IGNORECASE)
BOX_POWER_PATTERN = re.compile(r"\b\d+(?:\.\d+)?\s*(?:kW|kVA|A)\b", re.IGNORECASE)
CAD_BLOCK_COUNT_PATTERN = re.compile(r"\[CAD_BLOCK_COUNT\]\s+layer=(?P<layer>\S+)\s+block=(?P<block>\S+)\s+count=(?P<count>\d+)")

HEURISTIC_ANNOTATION_KEYWORDS = (
    "备注",
    "图例",
    "说明",
    "设计依据",
    "通信距离",
    "总长度",
    "预留",
    "预埋",
    "敷设",
    "安装高度",
    "安装位置",
    "距地",
    "离地",
    "系统图",
    "原理图",
    "接线图",
)

HEURISTIC_PROCUREMENT_KEYWORDS = (
    "插座",
    "插座箱",
    "配电箱",
    "配电柜",
    "控制箱",
    "控制柜",
    "电源箱",
    "切换箱",
    "双电源",
    "泵",
    "风机",
    "电缆",
    "线缆",
    "导线",
    "电线",
    "桥架",
    "线槽",
    "钢管",
    "风管",
    "水管",
)

HEURISTIC_LENGTH_MATERIAL_KEYWORDS = (
    "电缆",
    "线缆",
    "导线",
    "电线",
    "桥架",
    "线槽",
    "钢管",
    "风管",
    "水管",
)

BOX_IDENTIFIER_PATTERN = re.compile(
    r"^[A-Z]\d[A-Z0-9-]*?(?:ALE|AL|AP)[A-Za-z0-9-]*$",
    re.IGNORECASE,
)

BOX_PARAMETER_KEYWORDS = (
    "Fn",
    "Kc",
    "Pc",
    "COS",
    "Sc",
    "Ic",
    "\u5bb9\u91cf",
    "\u65f6\u95f4",
    "\u5b89\u88c5\u65b9\u5f0f",
    "\u4e2d\u5fc3\u8ddd\u5730",
    "\u8ddd\u5730",
    "\u6302\u5899",
    "\u58c1\u88c5",
    "\u843d\u5730",
)

BOX_COMPONENT_KEYWORDS = (
    "MCB",
    "MCCB",
    "RCBO",
    "ATS",
    "CM6-",
    "IS",
    "\u76d1\u63a7\u6a21\u5757",
    "\u5f00\u5173\u578b\u53f7",
    "\u6574\u5b9a\u503c",
    "\u8d1f\u8377\u5f00\u5173",
    "\u6f0f\u7535\u7535\u6d41",
)



CABLE_MODEL_KEYWORDS = (
    "YJV",
    "YJY",
    "BYJ",
    "RYJ",
    "RYJS",
    "KVV",
    "KYJ",
    "RVV",
    "BTT",
    "BTW",
    "BBTR",
    "BTTR",
    "NH",
    "ZR",
    "WDZ",
    "WD",
)

INVALID_CABLE_MODEL_PREFIXES = (
    "MCB",
    "MCCB",
    "RCBO",
    "ATS",
    "CM",
    "CJ",
    "IS",
    "DS-",
)

FAN_DESCRIPTOR_KEYWORDS = (
    "\u8fdb\u98ce",
    "\u6392\u98ce",
    "\u8865\u98ce",
    "\u9001\u98ce",
    "\u6392\u70df",
    "\u65b0\u98ce",
    "\u4e8b\u6545\u6392\u98ce",
    "\u98ce\u673a\u76d8\u7ba1",
)


class ExtractionPayload(BaseModel):
    items: list[InquiryItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class StructuredExtractionResponse(BaseModel):
    items: list[InquiryItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ParameterExtractor:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.config_manager = get_config_manager()
        # 优先从环境变量加载
        self.openai_client = None
        self.deepseek_client = None
        if settings.openai_api_key:
            self.openai_client = OpenAI(api_key=settings.openai_api_key)
        if settings.deepseek_api_key:
            self.deepseek_client = OpenAI(
                api_key=settings.deepseek_api_key,
                base_url=settings.deepseek_base_url,
            )
        # 如果环境变量没有，尝试从数据库加载
        if not self.openai_client and not self.deepseek_client:
            try:
                self._load_clients_from_db()
            except Exception:
                pass  # 数据库未初始化或出错，保持 None

    def _load_clients_from_db(self) -> None:
        """从数据库同步加载LLM客户端配置。"""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        llm_config = loop.run_until_complete(self.config_manager.get_llm_config())
        if not llm_config:
            return

        api_key = llm_config.get("api_key")
        base_url = llm_config.get("base_url") or "https://api.deepseek.com"
        provider = llm_config.get("provider")
        model = llm_config.get("model")

        if not api_key:
            return

        # 保存模型名称供后续使用
        self._db_model = model
        self._db_provider = provider

        if provider == "deepseek":
            self.deepseek_client = OpenAI(api_key=api_key, base_url=base_url)
        elif provider == "openai":
            self.openai_client = OpenAI(api_key=api_key, base_url=base_url)

    def extract(self, documents: list[ParsedDocument], raw_texts: list[str]) -> tuple[ExtractionPayload, str]:
        heuristic_payload = self._heuristic_extract(documents, raw_texts)
        backend = self._resolve_backend()
        prefer_llm = self._should_prefer_llm(documents)

        if self._should_force_local_heuristic(documents):
            heuristic_payload.warnings.append("多份 CAD 图纸项目已按分图本地规则抽取，跳过整包 LLM 识别。")
            return heuristic_payload, "heuristic"

        if len(heuristic_payload.items) >= 3 and not prefer_llm:
            heuristic_payload.warnings.append(f"已使用本地规则提取 {len(heuristic_payload.items)} 项。")
            return heuristic_payload, "heuristic"

        if prefer_llm and heuristic_payload.items:
            heuristic_payload.warnings.append(
                f"检测到 OCR 来源的 PDF，优先尝试 {backend or 'LLM'} 抽取，再以本地规则兜底。"
            )

        if backend is None:
            if not heuristic_payload.items:
                heuristic_payload.warnings.append("未配置可用 LLM，已使用本地规则抽取。")
            return heuristic_payload, "heuristic"

        try:
            if backend == "openai":
                llm_payload = self._openai_extract(documents, raw_texts)
            else:
                llm_payload = self._deepseek_extract(documents, raw_texts)
        except Exception as exc:
            if heuristic_payload.items:
                heuristic_payload.warnings.append(
                    f"{backend} 抽取失败，使用本地规则结果: {exc}"
                )
                return heuristic_payload, "heuristic"
            heuristic_payload.warnings.append(
                f"{backend} 抽取失败，已回退本地规则: {exc}"
            )
            return heuristic_payload, "heuristic"

        if not llm_payload.items:
            if heuristic_payload.items:
                heuristic_payload.warnings.append(
                    f"{backend} 未返回可用清单，使用本地规则结果。"
                )
                return heuristic_payload, "heuristic"
            heuristic_payload.warnings.append(
                f"{backend} 未返回可用清单，已回退本地规则。"
            )
            return heuristic_payload, "heuristic"

        return llm_payload, backend

    def _should_prefer_llm(self, documents: list[ParsedDocument]) -> bool:
        return any(
            document.file_type == "pdf" and "ocr" in document.parser.lower()
            for document in documents
        )

    def _should_force_local_heuristic(self, documents: list[ParsedDocument]) -> bool:
        cad_types = {"dxf", "dwg"}
        return len(documents) > 1 and all(document.file_type in cad_types for document in documents)

    def _resolve_backend(self) -> Literal["openai", "deepseek"] | None:
        provider = self.settings.llm_provider
        if provider == "none":
            return None
        if provider == "openai":
            return "openai" if self.openai_client else None
        if provider == "deepseek":
            return "deepseek" if self.deepseek_client else None

        # 自动模式：检查数据库配置的provider
        if hasattr(self, '_db_provider'):
            if self._db_provider == "deepseek" and self.deepseek_client:
                return "deepseek"
            if self._db_provider == "openai" and self.openai_client:
                return "openai"

        if self.deepseek_client:
            return "deepseek"
        if self.openai_client:
            return "openai"
        return None

    def _get_model(self, default_model: str) -> str:
        """获取模型名称，优先使用数据库配置。"""
        if hasattr(self, '_db_model') and self._db_model:
            return self._db_model
        return default_model

    def _openai_extract(
        self,
        documents: list[ParsedDocument],
        raw_texts: list[str],
    ) -> ExtractionPayload:
        if not self.openai_client:
            raise RuntimeError("OpenAI client is not configured.")

        model = self._get_model(self.settings.openai_model)
        response = self.openai_client.responses.parse(
            model=model,
            reasoning={"effort": "none"},
            input=[
                {"role": "system", "content": self._build_system_prompt()},
                {
                    "role": "user",
                    "content": self._build_user_prompt(documents, raw_texts, include_json_hint=False),
                },
            ],
            text={"verbosity": "low"},
            text_format=StructuredExtractionResponse,
        )
        if response.output_parsed:
            return ExtractionPayload(**response.output_parsed.model_dump())
        raise RuntimeError("OpenAI structured output is empty.")

    def _deepseek_extract(
        self,
        documents: list[ParsedDocument],
        raw_texts: list[str],
    ) -> ExtractionPayload:
        if not self.deepseek_client:
            raise RuntimeError("DeepSeek client is not configured.")

        model = self._get_model(self.settings.deepseek_model)
        collected_items: list[InquiryItem] = []
        collected_warnings: list[str] = []
        success_count = 0

        for label, prompt in self._iter_deepseek_chunks(documents, raw_texts):
            try:
                response = self.deepseek_client.chat.completions.create(
                    model=model,
                    messages=[
                        {
                            "role": "system",
                            "content": self._build_system_prompt(include_json_output_rules=True),
                        },
                        {
                            "role": "user",
                            "content": prompt,
                        },
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.1,
                    max_tokens=3000,
                )
                content = response.choices[0].message.content or ""
                if not content.strip():
                    raise RuntimeError("DeepSeek returned empty content.")

                validated, repaired = self._coerce_deepseek_payload(content)
                collected_items.extend(validated.items)
                collected_warnings.extend(validated.warnings)
                if repaired:
                    collected_warnings.append(f"{label}: DeepSeek 返回了非严格 JSON，系统已自动修复。")
                success_count += 1
            except Exception as exc:
                collected_warnings.append(f"{label}: DeepSeek 抽取失败: {exc}")

        if success_count == 0:
            raise RuntimeError("; ".join(collected_warnings[:3]) or "DeepSeek extraction failed.")

        return ExtractionPayload(
            items=self._deduplicate(collected_items),
            warnings=collected_warnings,
        )

    def _iter_deepseek_chunks(
        self,
        documents: list[ParsedDocument],
        raw_texts: list[str],
    ) -> list[tuple[str, str]]:
        chunks: list[tuple[str, str]] = []

        for document, raw_text in zip(documents, raw_texts):
            for index, chunk in enumerate(self._split_text_for_llm(raw_text), start=1):
                label = f"{document.filename}#chunk-{index}"
                prompt = (
                    f"# 文件: {document.filename}\n"
                    f"解析器: {document.parser}\n"
                    f"分段: {index}\n"
                    f"内容:\n{chunk}\n\n"
                    '请只输出 json，例如：{"items":[{"name":"离心泵","category":"泵组设备","specification":"Q=20m3/h H=30m","material":null,"quantity":2,"unit":"台","source_snippet":"离心泵 Q=20m3/h H=30m 2台","confidence":0.8}],"warnings":[]}'
                )
                chunks.append((label, prompt))

        return chunks

    def _split_text_for_llm(self, text: str) -> list[str]:
        page_chunks = [
            chunk.strip()
            for chunk in re.split(r"(?=\[\u7b2c\s*\d+\s*\u9875(?:\s*OCR)?\])", text)
            if chunk.strip()
        ]
        if not page_chunks:
            page_chunks = [text.strip()]

        max_chars = self.settings.llm_max_input_chars
        result: list[str] = []
        buffer: list[str] = []
        current_length = 0

        for chunk in page_chunks:
            chunk = chunk[:max_chars]
            additional_length = len(chunk) + (2 if buffer else 0)
            if buffer and current_length + additional_length > max_chars:
                result.append("\n\n".join(buffer))
                buffer = [chunk]
                current_length = len(chunk)
            else:
                buffer.append(chunk)
                current_length += additional_length

        if buffer:
            result.append("\n\n".join(buffer))

        return result

    def _coerce_deepseek_payload(
        self,
        content: str,
    ) -> tuple[StructuredExtractionResponse, bool]:
        direct_error: Exception | None = None
        candidates = [content]

        extracted_object = self._extract_first_json_object(content)
        if extracted_object and extracted_object != content:
            candidates.append(extracted_object)

        for candidate in candidates:
            try:
                parsed = json.loads(candidate)
                return StructuredExtractionResponse.model_validate(parsed), False
            except (json.JSONDecodeError, ValidationError) as exc:
                direct_error = exc

        repaired = self._repair_json_with_deepseek(content)
        try:
            parsed = json.loads(repaired)
            return StructuredExtractionResponse.model_validate(parsed), True
        except (json.JSONDecodeError, ValidationError) as exc:
            raise RuntimeError(f"DeepSeek JSON parse failed: {exc}") from (direct_error or exc)

    def _extract_first_json_object(self, text: str) -> str | None:
        start = text.find("{")
        if start < 0:
            return None

        depth = 0
        in_string = False
        escape = False
        for index in range(start, len(text)):
            char = text[index]
            if in_string:
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == '"':
                    in_string = False
                continue

            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return text[start : index + 1]
        return None

    def _repair_json_with_deepseek(self, broken_json: str) -> str:
        if not self.deepseek_client:
            raise RuntimeError("DeepSeek client is not configured.")

        response = self.deepseek_client.chat.completions.create(
            model=self.settings.deepseek_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是 JSON 修复器。"
                        "请把用户给出的无效 JSON 修复为严格合法的 JSON 对象。"
                        "只输出 JSON。"
                        "顶层字段必须是 items 和 warnings。"
                    ),
                },
                {
                    "role": "user",
                    "content": broken_json[:20000],
                },
            ],
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=4000,
        )
        content = response.choices[0].message.content or ""
        if not content.strip():
            raise RuntimeError("DeepSeek JSON repair returned empty content.")
        return content

    def _build_system_prompt(self, include_json_output_rules: bool = False) -> str:
        prompt = (
            "你是工程询价助理。请从 CAD、DWG、DXF、PDF、OCR 文本中提取可以用于报价的设备和材料清单。"
            "只保留与采购或询价有关的条目。"
            "输出字段必须包含：name, category, specification, material, quantity, unit, source_snippet, confidence。"
            "quantity 必须是数字，无法判断时填 1；unit 缺失时填 项；"
            "不要编造供应商、单价或总价。"
        )
        if include_json_output_rules:
            prompt += (
                "你必须输出 json 对象，且根字段为 items 和 warnings。"
                "items 是数组，warnings 是字符串数组。"
            )
        return prompt

    def _build_user_prompt(
        self,
        documents: list[ParsedDocument],
        raw_texts: list[str],
        include_json_hint: bool,
    ) -> str:
        prompt_parts: list[str] = []
        for document, text in zip(documents, raw_texts):
            prompt_parts.append(
                f"# 文件: {document.filename}\n"
                f"解析器: {document.parser}\n"
                f"内容:\n{text[: self.settings.llm_max_input_chars]}\n"
            )

        if include_json_hint:
            prompt_parts.append(
                '请输出 json，例如：{"items":[{"name":"离心泵","category":"泵组设备","specification":"Q=20m3/h H=30m","material":null,"quantity":2,"unit":"台","source_snippet":"离心泵 Q=20m3/h H=30m 2台","confidence":0.8}],"warnings":[]}'
            )
        return "\n\n".join(prompt_parts)

    def _should_skip_document_role(self, document: ParsedDocument) -> bool:
        return document.document_role in {"legend", "spec"}

    def _attach_source_document(self, item: InquiryItem, filename: str) -> InquiryItem:
        return item.model_copy(update={"source_documents": sorted(set(item.source_documents + [filename]))})

    def _clean_line_body(self, raw_line: str) -> str:
        return raw_line.split("] ", 1)[-1].strip(" -:：,，;；")

    def _make_feature(self, label: str, value: str) -> str | None:
        normalized = value.replace(" ", "").strip("/")
        if not normalized:
            return None
        return f"{label}={normalized}"

    def _split_feature_spec(self, specification: str | None) -> list[str]:
        if not specification:
            return []
        return [part.strip() for part in specification.split(" / ") if part.strip()]

    def _looks_like_box_parameter(self, text: str) -> bool:
        return BOX_POWER_PATTERN.search(text) is not None or any(keyword in text for keyword in BOX_PARAMETER_KEYWORDS)

    def _looks_like_box_component(self, text: str) -> bool:
        return any(keyword in text for keyword in BOX_COMPONENT_KEYWORDS)

    def _extract_cable_models(self, text: str) -> list[str]:
        models: list[str] = []
        for match in CABLE_MODEL_PATTERN.finditer(text):
            candidate = match.group(0).replace(" ", "").upper()
            if not self._is_valid_cable_model(candidate):
                continue
            models.append(candidate)
        return list(dict.fromkeys(models))

    def _is_valid_cable_model(self, candidate: str) -> bool:
        if any(candidate.startswith(prefix) for prefix in INVALID_CABLE_MODEL_PREFIXES):
            return False
        if re.fullmatch(r"YJ-\d+", candidate):
            return False
        if not any(keyword in candidate for keyword in CABLE_MODEL_KEYWORDS):
            return False
        if not any(token in candidate for token in ("X", "MM", "KV", "/")):
            return False
        return True

    def _build_box_context_specification(self, identifier: str, box_name: str, lines: list[str], index: int) -> str | None:
        features: list[str] = []
        box_type_feature = self._make_feature("\u7bb1\u4f53\u7c7b\u522b", box_name)
        if box_type_feature:
            features.append(box_type_feature)

        parameter_lines: list[str] = []
        component_lines: list[str] = []
        cable_models: list[str] = []

        start = max(0, index - 8)
        end = min(len(lines), index + 24)
        for raw_line in lines[start:end]:
            body = self._clean_line_body(raw_line)
            if not body or body == identifier:
                continue
            if body.startswith(f"{identifier}:"):
                continue
            if self._looks_like_annotation(body):
                continue
            if body.startswith(("\u7531", "\u4ece", "\u81f3", "\u63a5")) and identifier in body:
                continue

            models = self._extract_cable_models(body)
            if models:
                cable_models.extend(models)

            if self._looks_like_box_parameter(body):
                parameter_lines.append(body)
                continue

            if self._looks_like_box_component(body):
                component_lines.append(body)

        if parameter_lines:
            feature = self._make_feature("\u7bb1\u4f53\u53c2\u6570", ";".join(dict.fromkeys(parameter_lines[:8])))
            if feature:
                features.append(feature)
        if component_lines:
            feature = self._make_feature("\u7bb1\u5185\u5143\u5668\u4ef6", ";".join(dict.fromkeys(component_lines[:8])))
            if feature:
                features.append(feature)
        if cable_models:
            feature = self._make_feature("\u51fa\u7ebf\u7535\u7f06\u578b\u53f7", "\u3001".join(dict.fromkeys(cable_models[:8])))
            if feature:
                features.append(feature)

        return " / ".join(dict.fromkeys(part for part in features if part)) or None

    def _extract_box_identifier_item(self, lines: list[str], index: int, document: ParsedDocument) -> InquiryItem | None:
        if document.document_role != "system":
            return None

        raw_line = lines[index]
        body = self._clean_line_body(raw_line)
        if not body:
            return None
        if ":" in body or "：" in body or " " in body:
            return None
        if body.startswith(("\u7531", "\u4ece", "\u81f3", "\u63a5", "\u8fdb", "\u51fa")):
            return None
        if any(token in body for token in ("\u5f15\u6765", "\u5f15\u81f3", "\u63a5\u81f3", "\u56de\u8def", "\u7cfb\u7edf", "\u56fe\u4f8b")):
            return None
        if not BOX_IDENTIFIER_PATTERN.fullmatch(body.upper()):
            return None

        box_name = self._infer_box_name_from_identifier(body)
        if not box_name:
            return None

        specification = self._build_box_context_specification(body, box_name, lines, index)
        return InquiryItem(
            name=body,
            category="\u7535\u6c14\u8bbe\u5907",
            specification=specification,
            quantity=1.0,
            unit="\u53f0",
            source_documents=[document.filename],
            source_snippet=raw_line[:180],
            confidence=0.9,
        )

    def _extract_cable_run_item(self, lines: list[str], index: int, document: ParsedDocument) -> InquiryItem | None:
        if document.document_role != "plan":
            return None

        body = self._clean_line_body(lines[index])
        run_match = CABLE_RUN_PATTERN.search(body)
        if not run_match:
            return None

        count = float(run_match.group("count"))
        model = run_match.group("model").replace(" ", "")
        length_value: float | None = None
        source_parts = [body]
        for raw_line in lines[index : min(len(lines), index + 6)]:
            nearby = self._clean_line_body(raw_line)
            length_match = CABLE_LENGTH_PATTERN.search(nearby)
            if not length_match:
                continue
            run_count = float(length_match.group("count"))
            length_value = float(length_match.group("length")) * (run_count if run_count > 0 else count)
            source_parts.append(nearby)
            break

        if length_value is None:
            return None

        return InquiryItem(
            name="\u7535\u529b\u7535\u7f06",
            category="\u7535\u6c14\u8f85\u6750",
            specification=model,
            quantity=round(length_value, 4),
            unit="m",
            source_documents=[document.filename],
            source_snippet=" | ".join(source_parts)[:220],
            confidence=0.86,
        )

    def _extract_pump_group_items(self, lines: list[str], index: int, document: ParsedDocument) -> list[InquiryItem]:
        if document.document_role != "plan":
            return []

        body = self._clean_line_body(lines[index])
        group_match = PUMP_GROUP_PATTERN.search(body)
        if not group_match:
            return []

        main_power = None
        aux_power = None
        power_line = None
        for raw_line in lines[index : min(len(lines), index + 6)]:
            nearby = self._clean_line_body(raw_line)
            power_match = PUMP_POWER_SPLIT_PATTERN.search(nearby)
            if power_match:
                main_power = power_match.group("main")
                aux_power = power_match.group("aux")
                power_line = nearby
                break
        duty = f"{group_match.group('duty')}用{group_match.group('standby')}备"
        aux_count = int(group_match.group("aux") or "0")
        main_count = int(group_match.group("duty")) + int(group_match.group("standby"))
        source = body if power_line is None else f"{body} | {power_line}"
        base_name = group_match.group("name")
        items: list[InquiryItem] = []

        if main_power is not None and main_count > 0:
            items.append(
                InquiryItem(
                    name=f"{base_name}\u4e3b\u6cf5",
                    category="\u6cf5\u7ec4\u8bbe\u5907",
                    specification=f"\u7ec4\u6210={duty} / \u529f\u7387={main_power}KW",
                    quantity=float(main_count),
                    unit="\u53f0",
                    source_documents=[document.filename],
                    source_snippet=source[:220],
                    confidence=0.82,
                )
            )
        if aux_power is not None and aux_count > 0:
            items.append(
                InquiryItem(
                    name=f"{base_name}\u8f85\u6cf5",
                    category="\u6cf5\u7ec4\u8bbe\u5907",
                    specification=f"\u7ec4\u6210={duty}{aux_count}\u8f85 / \u529f\u7387={aux_power}KW",
                    quantity=float(aux_count),
                    unit="\u53f0",
                    source_documents=[document.filename],
                    source_snippet=source[:220],
                    confidence=0.8,
                )
            )
        return items

    def _infer_pump_name_from_context(self, context: str) -> str:
        if "\u6c61\u6c34\u63d0\u5347" in context:
            return "\u6c61\u6c34\u63d0\u5347\u6cf5"
        if "\u751f\u6d3b\u6c34\u6cf5" in context:
            return "\u751f\u6d3b\u6c34\u6cf5"
        if "\u70ed\u7164\u5faa\u73af" in context:
            return "\u70ed\u7164\u5faa\u73af\u6cf5"
        if "\u70ed\u6c34\u5faa\u73af" in context:
            return "\u70ed\u6c34\u5faa\u73af\u6cf5"
        return "\u6cf5"

    def _extract_pump_item(self, lines: list[str], index: int, document: ParsedDocument) -> InquiryItem | None:
        if document.document_role != "plan":
            return None

        body = self._clean_line_body(lines[index])
        spec_match = PUMP_SPEC_PATTERN.search(body)
        if not spec_match:
            return None

        window = [self._clean_line_body(raw_line) for raw_line in lines[max(0, index - 3) : min(len(lines), index + 4)]]
        context = " ".join(part for part in window if part)
        quantity = 1.0
        remark = spec_match.group("remark") or ""
        if any(token in remark or token in context for token in ("1用一1备", "一用一备")):
            quantity = 2.0
        elif any(token in remark or token in context for token in ("2用一1备", "二用一备")):
            quantity = 3.0

        specification_parts = [body]
        if "\u4e24\u53f0\u53ef\u540c\u65f6\u542f\u52a8" in context:
            specification_parts.append("\u5907\u6ce8=\u4e24\u53f0\u53ef\u540c\u65f6\u542f\u52a8")

        return InquiryItem(
            name=self._infer_pump_name_from_context(context),
            category="\u6cf5\u7ec4\u8bbe\u5907",
            specification=" / ".join(specification_parts),
            quantity=quantity,
            unit="\u53f0",
            source_documents=[document.filename],
            source_snippet=" | ".join(dict.fromkeys(part for part in window if part))[:220],
            confidence=0.78,
        )

    def _extract_fan_item(self, lines: list[str], index: int, document: ParsedDocument) -> InquiryItem | None:
        if document.document_role != "plan":
            return None

        body = self._clean_line_body(lines[index])
        power_match = re.search(r"N=(?P<power>\d+(?:\.\d+)?)kW", body, re.IGNORECASE)
        if not power_match:
            return None

        window = [self._clean_line_body(raw_line) for raw_line in lines[max(0, index - 3) : min(len(lines), index + 4)]]
        context = [part for part in window if part]
        descriptor = next((part for part in context if any(token in part for token in FAN_DESCRIPTOR_KEYWORDS)), None)
        if not descriptor or "\u63a7\u5236\u7535\u7f06" in descriptor:
            return None

        airflow = next((part for part in context if part.startswith("L=") and "CMH" in part.upper()), None)
        name = descriptor if "\u98ce\u673a" in descriptor else f"{descriptor}\u673a"
        spec_parts = [f"\u529f\u7387={power_match.group('power')}kW"]
        if airflow:
            spec_parts.append(f"\u98ce\u91cf={airflow.replace(' ', '')}")

        return InquiryItem(
            name=name,
            category="\u901a\u98ce\u8bbe\u5907",
            specification=" / ".join(spec_parts),
            quantity=1.0,
            unit="\u53f0",
            source_documents=[document.filename],
            source_snippet=" | ".join(dict.fromkeys(context))[:220],
            confidence=0.72,
        )

    def _infer_box_name_from_identifier(self, identifier: str) -> str | None:
        upper = identifier.upper()
        if "ALE" in upper:
            return "应急照明配电箱"
        if "AP" in upper:
            return "电力配电箱"
        if "AL" in upper:
            return "照明配电箱"
        return None

    def _looks_like_annotation(self, text: str) -> bool:
        normalized = text.strip()
        if not normalized:
            return True
        if any(keyword in normalized for keyword in HEURISTIC_ANNOTATION_KEYWORDS):
            return True
        if normalized.startswith(("由", "从", "在", "沿", "当", "其", "应")) and any(
            token in normalized for token in ("引来", "引至", "接至", "通信距离", "总长度", "预留", "敷设", "安装位置")
        ):
            return True
        return False

    def _looks_like_procurement_item(self, text: str) -> bool:
        return any(keyword in text for keyword in HEURISTIC_PROCUREMENT_KEYWORDS)

    def _looks_like_length_material(self, text: str) -> bool:
        return any(keyword in text for keyword in HEURISTIC_LENGTH_MATERIAL_KEYWORDS)

    def _infer_project_scope(self, documents: list[ParsedDocument]) -> str:
        seed = " ".join(f"{document.filename} {document.document_role}" for document in documents)
        if any(
            keyword in seed
            for keyword in (
                "电气",
                "照明",
                "配电",
                "插座",
                "应急照明",
            )
        ):
            return "electrical"
        return "general"

    def _is_non_electrical_equipment_text(self, text: str) -> bool:
        compact = text.replace(" ", "")
        if any(
            keyword in compact
            for keyword in (
                "控制箱",
                "控制柜",
                "配电箱",
                "配电柜",
                "插座箱",
                "电缆",
                "桥架",
                "配管",
            )
        ):
            return False
        return any(
            keyword in compact
            for keyword in (
                "泵",
                "风机",
                "机组",
                "冷却塔",
                "盘管",
            )
        )

    def _is_non_electrical_item(self, item: InquiryItem) -> bool:
        seed = " ".join(part for part in (item.name, item.category, item.specification, item.source_snippet) if part)
        return item.category in {
            "泵组设备",
            "通风设备",
            "暖通设备",
        } or self._is_non_electrical_equipment_text(seed)

    def _socket_spec_parts_from_block(self, block_name: str) -> list[str]:
        upper = block_name.upper()
        parts = [self._make_feature("图例块", upper)]
        if "1P-5" in upper:
            parts.append(self._make_feature("插座型式", "单相三孔加两孔"))
        elif "3P-4" in upper:
            parts.append(self._make_feature("插座型式", "三相四孔"))
        elif "1P-3" in upper:
            parts.append(self._make_feature("插座型式", "单相三孔"))
        elif "1P-2" in upper:
            parts.append(self._make_feature("插座型式", "单相两孔"))
        if upper.endswith("EN"):
            parts.append(self._make_feature("电源属性", "应急"))
        if upper.startswith("R-Z-"):
            parts.append(self._make_feature("用途代号", upper.split("-")[-1]))
        return [part for part in parts if part]

    def _switch_spec_parts_from_block(self, block_name: str) -> list[str]:
        upper = block_name.upper()
        parts = [self._make_feature("图例块", upper)]
        if "-11" in upper:
            parts.append(self._make_feature("联数", "1联"))
        elif "-21" in upper:
            parts.append(self._make_feature("联数", "2联"))
        elif "-31" in upper:
            parts.append(self._make_feature("联数", "3联"))
        if upper.endswith("EX"):
            parts.append(self._make_feature("特殊类别", "EX"))
        return [part for part in parts if part]

    def _lighting_spec_parts_from_block(self, layer: str, block_name: str) -> tuple[str, list[str]]:
        upper = block_name.upper()
        parts = [self._make_feature("图例块", upper)]
        if layer == "D-设备-应急照明":
            if any(token in upper for token in ("EXIT", "EXPORT")) or upper == "EL-F":
                parts.append(self._make_feature("灯具类别", "疏散指示"))
                return "疏散指示灯", [part for part in parts if part]
            parts.append(self._make_feature("灯具类别", "消防应急照明"))
            return "应急照明灯", [part for part in parts if part]
        parts.append(self._make_feature("灯具类别", "普通照明"))
        return "普通灯具", [part for part in parts if part]

    def _extract_cad_block_count_item(self, lines: list[str], index: int, document: ParsedDocument) -> InquiryItem | None:
        if document.document_role != "plan":
            return None

        raw_line = lines[index].strip()
        match = CAD_BLOCK_COUNT_PATTERN.search(raw_line)
        if not match:
            return None

        layer = match.group("layer")
        block_name = match.group("block")
        quantity = float(match.group("count"))
        specification_parts: list[str]
        name: str
        unit = "套"

        if layer == "D-设备-插座":
            name = "插座"
            specification_parts = self._socket_spec_parts_from_block(block_name)
        elif layer == "D-设备-开关":
            name = "照明开关"
            specification_parts = self._switch_spec_parts_from_block(block_name)
        elif layer in {"D-设备-普通照明", "D-设备-应急照明"}:
            name, specification_parts = self._lighting_spec_parts_from_block(layer, block_name)
        else:
            return None

        specification = " / ".join(part for part in specification_parts if part) or None
        return InquiryItem(
            name=name,
            category="电气设备",
            specification=specification,
            quantity=quantity,
            unit=unit,
            source_documents=[document.filename],
            source_snippet=raw_line[:180],
            confidence=0.95,
        )

    def _heuristic_extract(self, documents: list[ParsedDocument], raw_texts: Iterable[str]) -> ExtractionPayload:
        items: list[InquiryItem] = []
        warnings: list[str] = []
        project_scope = self._infer_project_scope(documents)

        for document, text in zip(documents, raw_texts):
            if self._should_skip_document_role(document):
                continue

            lines = text.splitlines()
            for index, line in enumerate(lines):
                normalized = " ".join(line.split()).strip(" -:\uFF1A,\uFF0C;\uFF1B")
                if len(normalized) < 2:
                    continue

                cad_block_item = self._extract_cad_block_count_item(lines, index, document)
                if cad_block_item is not None:
                    items.append(cad_block_item)
                    continue

                box_item = self._extract_box_identifier_item(lines, index, document)
                if box_item is not None:
                    items.append(box_item)
                    continue

                cable_item = self._extract_cable_run_item(lines, index, document)
                if cable_item is not None:
                    items.append(cable_item)
                    continue

                if project_scope != "electrical":
                    pump_group_items = self._extract_pump_group_items(lines, index, document)
                    if pump_group_items:
                        items.extend(pump_group_items)
                        continue

                    pump_item = self._extract_pump_item(lines, index, document)
                    if pump_item is not None:
                        items.append(pump_item)
                        continue

                    fan_item = self._extract_fan_item(lines, index, document)
                    if fan_item is not None:
                        items.append(fan_item)
                        continue
                elif self._is_non_electrical_equipment_text(normalized):
                    continue

                if self._looks_like_annotation(normalized):
                    continue

                qty_matches = list(QTY_PATTERN.finditer(normalized))
                if not qty_matches:
                    continue
                qty_match = qty_matches[-1]

                prefix = normalized[: qty_match.start()].strip(" -:\uFF1A,\uFF0C;\uFF1B")
                if not prefix:
                    continue
                if self._looks_like_annotation(prefix):
                    continue
                if project_scope == "electrical" and self._is_non_electrical_equipment_text(prefix):
                    continue
                if "\u7535\u7f06\u957f\u5ea6" in normalized:
                    continue
                if "\u957f\u5ea6" in prefix and not self._extract_cable_models(prefix):
                    continue
                if not self._looks_like_procurement_item(prefix):
                    continue

                segments = [segment.strip() for segment in re.split(r"[,\uFF0C;\uFF1B]+", prefix) if segment.strip()]
                head = segments[0]
                name_tokens = re.split(r"\s+", head)
                name = name_tokens[0]
                spec_tokens = name_tokens[1:]

                extra_spec_matches = SPEC_PATTERN.findall(prefix)
                if extra_spec_matches:
                    spec_tokens.extend(extra_spec_matches)
                electrical_spec_matches = ELECTRICAL_SPEC_PATTERN.findall(prefix)
                if electrical_spec_matches:
                    spec_tokens.extend(match.replace(" ", "") for match in electrical_spec_matches)

                specification = " / ".join(
                    dict.fromkeys(token for token in spec_tokens if token and token != name)
                ) or None
                category = self._infer_category(prefix)
                quantity = float(qty_match.group("qty"))
                unit = qty_match.group("unit")
                if unit in {"\u7c73", "m"} and not self._looks_like_length_material(prefix):
                    continue
                confidence = 0.58 if specification else 0.5

                items.append(
                    InquiryItem(
                        name=name,
                        category=category,
                        specification=specification,
                        quantity=quantity,
                        unit=unit,
                        material=self._infer_material(prefix),
                        source_documents=[document.filename],
                        source_snippet=normalized[:180],
                        confidence=confidence,
                    )
                )

        if project_scope == "electrical":
            items = [item for item in items if not self._is_non_electrical_item(item)]

        if not items:
            warnings.append("未从解析文本中识别到数量明确的询价条目。")

        return ExtractionPayload(items=self._deduplicate(items), warnings=warnings)

    def _infer_category(self, text: str) -> str | None:
        for token, category in NAME_CATEGORY_MAP.items():
            if token in text:
                return category
        return None

    def _infer_material(self, text: str) -> str | None:
        for material in ("不锈钢", "碳钢", "铜", "PVC", "镀锌钢", "铸铁"):
            if material in text:
                return material
        return None

    def _deduplicate(self, items: list[InquiryItem]) -> list[InquiryItem]:
        seen: dict[tuple[str, str | None, float, str], InquiryItem] = {}
        for item in items:
            key = (item.name, item.specification, item.quantity, item.unit)
            if key not in seen:
                seen[key] = item
                continue
            current = seen[key]
            current.source_documents = sorted(set(current.source_documents) | set(item.source_documents))
            current.source_snippet = f"{current.source_snippet} | {item.source_snippet}"[:280]
            current.confidence = max(current.confidence, item.confidence)
            current.anomalies = sorted(set(current.anomalies) | set(item.anomalies))
        return list(seen.values())
