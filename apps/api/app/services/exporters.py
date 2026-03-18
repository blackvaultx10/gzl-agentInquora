from __future__ import annotations

from io import BytesIO

import pandas as pd
from docx import Document

from app.models import InquiryResult
from app.services.extractor import EQUIPMENT_CATEGORY_MAP, MATERIAL_CATEGORY_MAP


def _is_equipment(category: str | None) -> bool:
    """判断是否为设备（需要厂家询价）还是材料（市场询价）。"""
    if not category:
        return False
    # 如果分类在设备清单里，返回True
    return category in EQUIPMENT_CATEGORY_MAP.values()


def _items_to_frame(result: InquiryResult) -> pd.DataFrame:
    rows = []
    for item in result.items:
        # 判断是设备还是材料
        item_type = "设备" if _is_equipment(item.category) else "材料"
        # 建议询价方式
        inquiry_method = "厂家询价" if item_type == "设备" else "市场询价"

        rows.append(
            {
                "类型": item_type,
                "设备/材料": item.name,
                "分类": item.category or "",
                "规格": item.specification or "",
                "材质": item.material or "",
                "数量": item.quantity,
                "单位": item.unit,
                "询价方式": inquiry_method,
                "供应商": item.vendor or "",
                "单价": item.unit_price or "",
                "总价": item.total_price or "",
                "依据": item.price_basis or "",
                "异常": ", ".join(item.anomalies),
                "来源摘录": item.source_snippet,
            }
        )
    return pd.DataFrame(rows)


def export_xlsx(result: InquiryResult) -> BytesIO:
    workbook = BytesIO()
    items_frame = _items_to_frame(result)

    # 分开设备和材料
    equipment_df = items_frame[items_frame["类型"] == "设备"].drop(columns=["类型"])
    material_df = items_frame[items_frame["类型"] == "材料"].drop(columns=["类型"])

    summary_frame = pd.DataFrame(
        [
            {
                "项目数": result.summary.item_count,
                "命中报价": result.summary.matched_count,
                "异常项": result.summary.flagged_count,
                "小计": result.summary.subtotal,
                "币种": result.summary.currency,
                "抽取方式": result.extraction_mode,
            }
        ]
    )

    with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
        summary_frame.to_excel(writer, sheet_name="汇总", index=False)

        if not equipment_df.empty:
            equipment_df.to_excel(writer, sheet_name="设备清单（厂家询价）", index=False)

        if not material_df.empty:
            material_df.to_excel(writer, sheet_name="物料表（市场询价）", index=False)

        # 全部明细
        items_frame.to_excel(writer, sheet_name="全部明细", index=False)

    workbook.seek(0)
    return workbook


def export_docx(result: InquiryResult) -> BytesIO:
    document = Document()
    document.add_heading("智能询价报告", level=0)
    document.add_paragraph(f"请求编号: {result.request_id}")
    document.add_paragraph(f"抽取方式: {result.extraction_mode}")
    document.add_paragraph(
        f"共 {result.summary.item_count} 项，命中报价 {result.summary.matched_count} 项，"
        f"异常 {result.summary.flagged_count} 项，小计 {result.summary.subtotal:.2f} {result.summary.currency}"
    )

    document.add_heading("来源文件", level=1)
    for source in result.documents:
        document.add_paragraph(
            f"{source.filename} | {source.file_type} | {source.parser} | {source.text_excerpt}",
            style="List Bullet",
        )

    document.add_heading("询价明细", level=1)
    table = document.add_table(rows=1, cols=6)
    table.style = "Light List Accent 1"
    header_cells = table.rows[0].cells
    headers = ["名称", "规格", "数量", "单价", "总价", "异常"]
    for cell, header in zip(header_cells, headers):
        cell.text = header

    for item in result.items:
        row = table.add_row().cells
        row[0].text = item.name
        row[1].text = item.specification or "-"
        row[2].text = f"{item.quantity:g} {item.unit}"
        row[3].text = f"{item.unit_price:.2f}" if item.unit_price is not None else "-"
        row[4].text = f"{item.total_price:.2f}" if item.total_price is not None else "-"
        row[5].text = ", ".join(item.anomalies) or "-"

    buffer = BytesIO()
    document.save(buffer)
    buffer.seek(0)
    return buffer
