from __future__ import annotations

import os
import re
from pathlib import Path

from app.models import InquiryItem, ParsedDocument


COMMON_NAME_SPLIT_PATTERN = re.compile(r"[-_\s()（）\[\]【】]+")

SOCKET_TRAITS = (
    "单相三孔加两孔",
    "单相三孔",
    "三相四孔",
    "防溅式",
)


def normalize_token(value: str | None) -> str:
    if not value:
        return ""
    return "".join(ch.lower() for ch in value if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")


def dedupe_parts(parts: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for part in parts:
        normalized = normalize_token(part)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(part)
    return deduped


def split_specification_parts(specification: str | None) -> list[str]:
    if not specification:
        return []
    return [part.strip() for part in specification.split(" / ") if part.strip()]


class ProjectBoqBuilder:
    def infer_project_name(self, documents: list[ParsedDocument], explicit_name: str | None = None) -> str:
        if explicit_name and explicit_name.strip():
            return explicit_name.strip()

        stems = [Path(document.filename).stem.strip() for document in documents if document.filename]
        if not stems:
            return "未命名项目"
        if len(stems) == 1:
            return stems[0]

        common_prefix = os.path.commonprefix(stems).strip("-_ .")
        if len(common_prefix) >= 4:
            return common_prefix

        token_groups = [
            [token for token in COMMON_NAME_SPLIT_PATTERN.split(stem) if token]
            for stem in stems
        ]
        shared_tokens = token_groups[0][:]
        for tokens in token_groups[1:]:
            shared_tokens = [token for token in shared_tokens if token in tokens]
            if not shared_tokens:
                break

        if shared_tokens:
            return " ".join(shared_tokens[:3])

        return f"{stems[0]} 等{len(stems)}份图纸"

    def build(
        self,
        items: list[InquiryItem],
        documents: list[ParsedDocument],
        raw_texts: list[str],
    ) -> tuple[list[InquiryItem], list[str]]:
        aggregated: dict[tuple[str, str, str, str], InquiryItem] = {}
        warnings: list[str] = []

        for item in items:
            boq_item = self._map_item(item, documents, raw_texts)
            key = (
                boq_item.boq_code or "",
                normalize_token(boq_item.name),
                normalize_token(boq_item.specification),
                normalize_token(boq_item.unit),
            )
            existing = aggregated.get(key)
            if existing is None:
                aggregated[key] = boq_item
                continue

            existing.quantity = round(existing.quantity + boq_item.quantity, 4)
            existing.source_documents = sorted(set(existing.source_documents) | set(boq_item.source_documents))
            existing.source_snippet = self._merge_text(existing.source_snippet, boq_item.source_snippet, 320)
            existing.confidence = max(existing.confidence, boq_item.confidence)
            existing.anomalies = sorted(set(existing.anomalies) | set(boq_item.anomalies))

        result_items = list(aggregated.values())
        unmapped_count = sum(1 for item in result_items if item.boq_code is None)
        if unmapped_count:
            warnings.append(f"{unmapped_count} 项未能自动套用清单编码，请人工复核。")

        return result_items, warnings

    def _map_item(
        self,
        item: InquiryItem,
        documents: list[ParsedDocument],
        raw_texts: list[str],
    ) -> InquiryItem:
        seed_text = " ".join(part for part in (item.name, item.category, item.specification, item.material) if part)
        source_documents = self._resolve_source_documents(item, documents, raw_texts)

        if any(token in seed_text for token in ("控制箱", "控制柜", "控制屏", "控制台")):
            return self._build_standard_item(
                item,
                boq_code="030404014",
                name="控制箱",
                category="控制、保护、直流装置安装",
                unit="台",
                inquiry_method="厂家询价",
                source_documents=source_documents,
                extra_spec_parts=[
                    self._feature("\u7bb1\u4f53\u540d\u79f0", item.name),
                    *self._expand_spec_parts(item.specification, "\u7bb1\u5185\u914d\u7f6e"),
                ],
            )

        if any(token in seed_text for token in ("插座箱", "配电箱", "配电柜", "电源箱", "切换箱", "双电源")) and "控制" not in seed_text:
            return self._build_standard_item(
                item,
                boq_code="030402011",
                name="成套配电箱",
                category="配电装置安装",
                unit="台",
                inquiry_method="厂家询价",
                source_documents=source_documents,
                extra_spec_parts=[
                    self._feature("\u7bb1\u4f53\u540d\u79f0", item.name),
                    *self._expand_spec_parts(item.specification, "\u7bb1\u5185\u914d\u7f6e"),
                ],
            )

        if any(token in seed_text for token in ("\u98ce\u673a", "\u8fdb\u98ce", "\u6392\u98ce", "\u8865\u98ce", "\u9001\u98ce", "\u6392\u70df")):
            return item.model_copy(
                update={
                    "inquiry_method": item.inquiry_method or "\u5382\u5bb6\u8be2\u4ef7",
                    "source_documents": source_documents,
                    "anomalies": sorted(set(item.anomalies) | {"unmapped_boq_item"}),
                }
            )

        if "泵" in seed_text and "控制" not in seed_text:
            return self._build_standard_item(
                item,
                boq_code="030109001",
                name="泵",
                category="泵安装",
                unit="台",
                inquiry_method="厂家询价",
                source_documents=source_documents,
                extra_spec_parts=[
                    self._feature("\u8bbe\u5907\u540d\u79f0", item.name),
                    *self._expand_spec_parts(item.specification, "\u89c4\u683c\u53c2\u6570"),
                ],
            )

        if "插座" in seed_text and "插座箱" not in seed_text:
            socket_traits = self._extract_socket_traits(seed_text)
            electrical_spec = self._extract_electrical_spec(item.specification)
            return self._build_standard_item(
                item,
                boq_code="030413014",
                name="插座",
                category="照明器具安装",
                unit="套",
                inquiry_method="市场询价",
                source_documents=source_documents,
                extra_spec_parts=[
                    self._feature("额定参数", electrical_spec),
                    self._feature("插座型式", "、".join(socket_traits) if socket_traits else None),
                ],
            )

        if any(
            token in seed_text
            for token in (
                "\u706f\u5177",
                "\u7167\u660e\u706f",
                "\u5e94\u6025\u7167\u660e\u706f",
                "\u758f\u6563\u6307\u793a\u706f",
            )
        ):
            return self._build_standard_item(
                item,
                boq_code="030413001",
                name="\u706f\u5177",
                category="\u7167\u660e\u5668\u5177\u5b89\u88c5",
                unit="\u5957",
                inquiry_method="\u5e02\u573a\u8be2\u4ef7",
                source_documents=source_documents,
                extra_spec_parts=[
                    self._feature("\u706f\u5177\u540d\u79f0", item.name),
                    *self._expand_spec_parts(item.specification, "\u9879\u76ee\u7279\u5f81"),
                ],
            )

        if "\u7167\u660e\u5f00\u5173" in seed_text:
            return self._build_standard_item(
                item,
                boq_code="030413013",
                name="\u7167\u660e\u5f00\u5173",
                category="\u7167\u660e\u5668\u5177\u5b89\u88c5",
                unit="\u5957",
                inquiry_method="\u5e02\u573a\u8be2\u4ef7",
                source_documents=source_documents,
                extra_spec_parts=[
                    self._feature("\u5f00\u5173\u540d\u79f0", item.name),
                    *self._expand_spec_parts(item.specification, "\u9879\u76ee\u7279\u5f81"),
                ],
            )

        if "桥架" in seed_text:
            return self._build_standard_item(
                item,
                boq_code="030412003",
                name="桥架",
                category="配管、配线",
                unit="米",
                inquiry_method="市场询价",
                source_documents=source_documents,
                extra_spec_parts=[self._feature("\u578b\u53f7\u89c4\u683c", item.specification or item.name)],
            )

        if any(token in seed_text for token in ("钢管", "线管", "套管", "配管", "穿线管")):
            return self._build_standard_item(
                item,
                boq_code="030412001",
                name="配管",
                category="配管、配线",
                unit="米",
                inquiry_method="市场询价",
                source_documents=source_documents,
                extra_spec_parts=[self._feature("\u578b\u53f7\u89c4\u683c", item.specification or item.name)],
            )

        if any(token in seed_text for token in ("电缆", "线缆", "导线", "电线")):
            code = "030409002" if "控制" in seed_text else "030409001"
            name = "控制电缆" if code == "030409002" else "电力电缆"
            return self._build_standard_item(
                item,
                boq_code=code,
                name=name,
                category="电缆安装",
                unit="米",
                inquiry_method="市场询价",
                source_documents=source_documents,
                extra_spec_parts=[self._feature("\u578b\u53f7\u89c4\u683c", item.specification or item.name)],
            )

        fallback_anomalies = sorted(set(item.anomalies) | {"unmapped_boq_item"})
        return item.model_copy(
            update={
                "inquiry_method": item.inquiry_method or self._infer_inquiry_method(item),
                "source_documents": source_documents,
                "anomalies": fallback_anomalies,
            }
        )

    def _expand_spec_parts(self, specification: str | None, fallback_label: str | None = None) -> list[str]:
        parts = split_specification_parts(specification)
        if not parts:
            return []

        result: list[str] = []
        unlabeled: list[str] = []
        for part in parts:
            if "=" in part:
                result.append(part)
            else:
                unlabeled.append(part)

        if unlabeled:
            merged = " / ".join(unlabeled)
            if fallback_label:
                feature = self._feature(fallback_label, merged)
                if feature:
                    result.append(feature)
            else:
                result.append(merged)
        return result

    def _build_standard_item(
        self,
        item: InquiryItem,
        *,
        boq_code: str,
        name: str,
        category: str,
        unit: str,
        inquiry_method: str,
        source_documents: list[str],
        extra_spec_parts: list[str],
    ) -> InquiryItem:
        specification_parts = []
        specification_parts.extend(extra_spec_parts)
        if item.material:
            specification_parts.append(self._feature("材质", item.material))

        specification = " / ".join(dedupe_parts([part for part in specification_parts if part])) or None

        return item.model_copy(
            update={
                "boq_code": boq_code,
                "name": name,
                "category": category,
                "specification": specification,
                "unit": unit,
                "inquiry_method": inquiry_method,
                "source_documents": source_documents,
                "anomalies": list(item.anomalies),
            }
        )

    def _resolve_source_documents(
        self,
        item: InquiryItem,
        documents: list[ParsedDocument],
        raw_texts: list[str],
    ) -> list[str]:
        if item.source_documents:
            return sorted(set(item.source_documents))

        snippets = [part.strip() for part in item.source_snippet.split("|") if part.strip()]
        matched_documents: list[str] = []
        for document, raw_text in zip(documents, raw_texts):
            if any(snippet in raw_text for snippet in snippets):
                matched_documents.append(document.filename)

        if matched_documents:
            return sorted(set(matched_documents))
        if len(documents) == 1:
            return [documents[0].filename]
        return []

    def _infer_inquiry_method(self, item: InquiryItem) -> str:
        seed_text = " ".join(part for part in (item.name, item.category, item.specification) if part)
        if any(token in seed_text for token in ("箱", "柜", "屏", "台", "泵", "风机", "机组")):
            return "厂家询价"
        return "市场询价"

    def _extract_socket_traits(self, seed_text: str) -> list[str]:
        traits: list[str] = []
        if "单相三孔加两孔" in seed_text:
            traits.append("单相三孔加两孔")
        elif "单相三孔" in seed_text:
            traits.append("单相三孔")

        if "三相四孔" in seed_text:
            traits.append("三相四孔")
        if "防溅式" in seed_text:
            traits.append("防溅式")
        return traits

    def _extract_electrical_spec(self, specification: str | None) -> str | None:
        if not specification:
            return None
        compact = specification.replace(" ", "")
        if compact:
            return compact
        return None

    def _feature(self, label: str, value: str | None) -> str | None:
        if not value:
            return None
        normalized = value.replace(" ", "").strip("/")
        if not normalized:
            return None
        return f"{label}={normalized}"

    def _merge_text(self, left: str, right: str, limit: int) -> str:
        merged = " | ".join(part for part in (left, right) if part)
        return merged[:limit]
