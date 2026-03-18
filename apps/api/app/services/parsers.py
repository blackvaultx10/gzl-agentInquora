from __future__ import annotations

import contextlib
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Iterator

from fastapi import UploadFile

from app.config import get_settings
from app.models import ParsedDocument

if TYPE_CHECKING:
    from PIL.Image import Image as PILImage


SUPPORTED_IMAGE_TYPES = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}
SUPPORTED_TEXT_TYPES = {".txt", ".csv", ".json"}


def _clean_excerpt(text: str, limit: int = 380) -> str:
    sanitized = " ".join(text.split())
    return sanitized[:limit] + ("..." if len(sanitized) > limit else "")


def _is_garbage_text(text: str) -> bool:
    """检测文本是否为乱码或无效内容。"""
    if not text or not text.strip():
        return True

    # 统计有效字符（中英文、数字、常用标点）
    valid_chars = 0
    total_chars = 0
    for char in text:
        if char.isspace():
            continue
        total_chars += 1
        # 中文、英文、数字、常用工程符号
        if (
            "\u4e00" <= char <= "\u9fff"  # CJK
            or char.isalnum()
            or char in ".,;:!?-=_+*/()[]{}<>|\\\"'@#$%&~`"
            or char in "，。；：！？、""''（）【】《》"
        ):
            valid_chars += 1

    if total_chars == 0:
        return True

    # 如果有效字符比例低于40%，认为是乱码
    ratio = valid_chars / total_chars
    return ratio < 0.4


def _deduplicate_lines(lines: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for line in lines:
        normalized = "".join(line.lower().split())
        if len(normalized) < 2 or normalized in seen:
            continue
        seen.add(normalized)
        result.append(line)
    return result


def _collect_dxf_entities(path: Path) -> tuple[str, list[str]]:
    try:
        import ezdxf
    except ImportError:
        return "", ["`ezdxf` 未安装，无法解析 DXF/DWG。"]

    try:
        document = ezdxf.readfile(path)
    except ezdxf.DXFError as exc:
        return "", [f"DXF 解析失败: {exc}"]

    lines: list[str] = []
    for entity in document.modelspace():
        entity_type = entity.dxftype()
        if entity_type in {"TEXT", "ATTRIB"}:
            text = getattr(entity.dxf, "text", "").strip()
            if text:
                lines.append(text)
        elif entity_type == "MTEXT":
            text = entity.text.replace("\\P", "\n").strip()
            if text:
                lines.append(text)
        elif entity_type == "DIMENSION":
            explicit_text = getattr(entity.dxf, "text", "")
            measurement = getattr(entity.dxf, "actual_measurement", None)
            payload = " ".join(
                part for part in [explicit_text, str(measurement) if measurement else None] if part
            ).strip()
            if payload:
                lines.append(f"尺寸 {payload}")
        elif entity_type == "INSERT":
            for attrib in getattr(entity, "attribs", []):
                text = getattr(attrib.dxf, "text", "").strip()
                if text:
                    lines.append(text)

    warnings: list[str] = []
    if not lines:
        warnings.append("DXF 中未找到可识别的文本或尺寸标注。")
    return "\n".join(lines), warnings


def _collect_dwg_entities(path: Path) -> tuple[str, list[str]]:
    try:
        from ezdxf.addons import odafc
    except ImportError:
        return "", ["DWG 解析依赖 `ezdxf` 的 ODA 转换适配器，当前环境不可用。"]

    try:
        document = odafc.readfile(path)
    except Exception as exc:  # pragma: no cover - depends on local ODA setup
        return "", [f"DWG 暂未成功解析，请安装 ODA File Converter 或改传 DXF/PDF: {exc}"]

    lines: list[str] = []
    for entity in document.modelspace():
        entity_type = entity.dxftype()
        if entity_type in {"TEXT", "ATTRIB"}:
            text = getattr(entity.dxf, "text", "").strip()
            if text:
                lines.append(text)
        elif entity_type == "MTEXT":
            text = entity.text.replace("\\P", "\n").strip()
            if text:
                lines.append(text)

    warnings: list[str] = []
    if not lines:
        warnings.append("DWG 已打开，但未提取到文本标注。")
    return "\n".join(lines), warnings


def _collect_pdf_text(path: Path) -> tuple[str, list[str]]:
    try:
        import pdfplumber
    except ImportError:
        return "", ["`pdfplumber` 未安装，无法解析 PDF。"]

    chunks: list[str] = []
    warnings: list[str] = []
    with pdfplumber.open(path) as pdf:
        for index, page in enumerate(pdf.pages, start=1):
            text = (page.extract_text() or "").strip()
            if text:
                chunks.append(f"[第 {index} 页]\n{text}")
    if not chunks:
        warnings.append("PDF 未提取到可复制文本，已自动尝试 OCR。")
    return "\n\n".join(chunks), warnings


@lru_cache(maxsize=1)
def _get_easyocr_reader():
    settings = get_settings()
    try:
        import easyocr  # type: ignore
    except ImportError:
        return None

    return easyocr.Reader(settings.ocr_languages, gpu=False)


def _enhance_for_ocr(image: "PILImage", upscale_factor: float) -> "PILImage":
    from PIL import Image, ImageEnhance, ImageFilter, ImageOps

    grayscale = image.convert("L")
    grayscale = ImageOps.autocontrast(grayscale)
    grayscale = ImageEnhance.Contrast(grayscale).enhance(1.7)
    grayscale = ImageEnhance.Sharpness(grayscale).enhance(2.2)
    grayscale = grayscale.filter(ImageFilter.SHARPEN)

    if upscale_factor > 1:
        width, height = grayscale.size
        grayscale = grayscale.resize(
            (max(1, int(width * upscale_factor)), max(1, int(height * upscale_factor))),
            Image.Resampling.LANCZOS,
        )

    return grayscale.convert("RGB")


def _tile_positions(length: int, tile_size: int, overlap: int) -> Iterator[int]:
    if length <= tile_size:
        yield 0
        return

    step = max(1, tile_size - overlap)
    cursor = 0
    while True:
        yield cursor
        if cursor + tile_size >= length:
            break
        cursor = min(cursor + step, length - tile_size)


def _sample_positions(
    length: int,
    tile_size: int,
    overlap: int,
    max_slices: int,
) -> list[int]:
    positions = list(_tile_positions(length, tile_size, overlap))
    if len(positions) <= max_slices:
        return positions

    if max_slices <= 1:
        return [positions[0]]

    result: list[int] = []
    last_index = len(positions) - 1
    for slot in range(max_slices):
        index = round((slot / (max_slices - 1)) * last_index)
        position = positions[index]
        if not result or result[-1] != position:
            result.append(position)
    return result


def _tile_has_content(image: "PILImage") -> bool:
    grayscale = image.convert("L")
    low, high = grayscale.getextrema()
    return (high - low) >= 12


def _iter_tile_images(image: "PILImage") -> Iterator["PILImage"]:
    settings = get_settings()
    width, height = image.size
    x_positions = _sample_positions(
        width,
        settings.ocr_tile_size_px,
        settings.ocr_tile_overlap_px,
        settings.ocr_tile_max_slices,
    )
    y_positions = _sample_positions(
        height,
        settings.ocr_tile_size_px,
        settings.ocr_tile_overlap_px,
        settings.ocr_tile_max_slices,
    )

    for top in y_positions:
        for left in x_positions:
            tile = image.crop(
                (
                    left,
                    top,
                    min(left + settings.ocr_tile_size_px, width),
                    min(top + settings.ocr_tile_size_px, height),
                )
            )
            if not _tile_has_content(tile):
                continue
            yield _enhance_for_ocr(tile, settings.ocr_tile_upscale_factor)


def _is_sufficient_ocr_text(text: str) -> bool:
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) >= 6:
        return True
    return len("".join(lines)) >= 90


def _ocr_with_easyocr(image: "PILImage") -> tuple[str, list[str]]:
    warnings: list[str] = []
    reader = _get_easyocr_reader()
    if reader is None:
        return "", ["未安装 EasyOCR。"]

    try:
        import numpy as np
    except ImportError:
        return "", ["未安装 `numpy`，无法执行 EasyOCR。"]

    try:
        full_image = _enhance_for_ocr(image, get_settings().ocr_full_upscale_factor)
        results = reader.readtext(
            np.array(full_image),
            detail=0,
            paragraph=True,
            mag_ratio=1.6,
            text_threshold=0.55,
            low_text=0.3,
            canvas_size=4096,
        )
        lines = [item.strip() for item in results if item and item.strip()]

        full_text = "\n".join(_deduplicate_lines(lines))
        if _is_sufficient_ocr_text(full_text):
            return full_text, warnings

        tile_lines = list(lines)
        if max(full_image.size) > get_settings().ocr_tile_size_px:
            for candidate in _iter_tile_images(full_image):
                tile_results = reader.readtext(
                    np.array(candidate),
                    detail=0,
                    paragraph=True,
                    mag_ratio=1.7,
                    text_threshold=0.5,
                    low_text=0.25,
                    canvas_size=4096,
                )
                tile_lines.extend(item.strip() for item in tile_results if item and item.strip())
    except Exception as exc:  # pragma: no cover - native stack varies by host
        return "", [f"EasyOCR 执行失败: {exc}"]

    deduplicated = _deduplicate_lines(tile_lines if "tile_lines" in locals() else lines)
    return "\n".join(deduplicated), warnings


def _ocr_with_tesseract(image: "PILImage") -> tuple[str, list[str]]:
    try:
        import pytesseract  # type: ignore
    except ImportError:
        return "", ["未安装 Tesseract OCR。"]

    try:
        text = pytesseract.image_to_string(image, lang="chi_sim+eng")
    except Exception as exc:  # pragma: no cover - external binary
        return "", [f"Tesseract OCR 执行失败: {exc}"]

    return text.strip(), []


# 百度OCR Token 缓存
_baidu_ocr_token_cache: dict[str, tuple[str, float]] = {}


def _get_baidu_token(api_key: str, secret_key: str) -> str | None:
    """获取百度OCR Access Token（带缓存，29天内有效）。"""
    import time
    import requests

    cache_key = f"{api_key[:8]}..."
    now = time.time()

    # 检查缓存（25小时内有效）
    if cache_key in _baidu_ocr_token_cache:
        token, expiry = _baidu_ocr_token_cache[cache_key]
        if now < expiry - 3600:  # 提前1小时过期
            return token

    # 重新获取
    token_url = f"https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id={api_key}&client_secret={secret_key}"
    try:
        token_response = requests.post(token_url, timeout=10)
        token_data = token_response.json()
        access_token = token_data.get("access_token")
        expires_in = token_data.get("expires_in", 2592000)  # 默认30天

        if access_token:
            _baidu_ocr_token_cache[cache_key] = (access_token, now + expires_in)
            return access_token
    except Exception:
        pass
    return None


def _ocr_with_baidu(image: "PILImage") -> tuple[str, list[str]]:
    """使用百度智能云 OCR 识别图片。"""
    import asyncio
    from app.config_manager import get_config_manager

    warnings: list[str] = []

    try:
        config_manager = get_config_manager()
        ocr_config = asyncio.run(config_manager.get_ocr_config())

        if not ocr_config or ocr_config.get("provider") != "baidu_ocr":
            return "", ["未配置百度 OCR"]

        api_key = ocr_config.get("api_key")
        secret_key = ocr_config.get("secret_key")

        if not api_key or not secret_key:
            return "", ["百度 OCR API Key 或 Secret Key 未配置"]

        # 获取 access token（带缓存）
        access_token = _get_baidu_token(api_key, secret_key)
        if not access_token:
            return "", ["百度 OCR 获取 Token 失败"]

        # 调用通用文字识别（高精度版）- 工程图纸需要高精度
        import base64
        import io
        import requests
        ocr_url = f"https://aip.baidubce.com/rest/2.0/ocr/v1/accurate_basic?access_token={access_token}"

        # 压缩图片以加快上传速度，但不要过度压缩影响识别
        buffered = io.BytesIO()
        img = image.convert("RGB")
        # 百度OCR支持最大4096x4096，最小15x15
        max_size = 2000  # 保持足够分辨率以识别工程图纸上的小字
        if img.width > max_size or img.height > max_size:
            ratio = min(max_size / img.width, max_size / img.height)
            new_size = (int(img.width * ratio), int(img.height * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
        img.save(buffered, format="JPEG", quality=90)  # 提高质量以改善识别率
        img_base64 = base64.b64encode(buffered.getvalue()).decode()

        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        params = {
            "image": img_base64,
            "language_type": "CHN_ENG",
            "detect_direction": "true",  # 检测文字方向
            "paragraph": "true",  # 段落合并
        }

        response = requests.post(ocr_url, headers=headers, data=params, timeout=30)
        result = response.json()

        if "words_result" in result:
            lines = [item["words"] for item in result["words_result"]]
            full_text = "\n".join(lines)
            # 添加调试信息
            warnings.append(f"百度OCR识别成功: {len(lines)} 行文字")
            return full_text, warnings
        elif "error_msg" in result:
            return "", [f"百度 OCR 识别失败: {result['error_msg']}"]
        else:
            return "", ["百度 OCR 返回结果为空"]

    except Exception as exc:
        return "", [f"百度 OCR 执行失败: {exc}"]


def _ocr_pil_image(image: "PILImage") -> tuple[str, list[str]]:
    # 优先尝试百度 OCR（如果配置了）
    baidu_text, baidu_warnings = _ocr_with_baidu(image)
    if baidu_text.strip():
        return baidu_text, baidu_warnings

    easyocr_text, easyocr_warnings = _ocr_with_easyocr(image)
    if easyocr_text.strip():
        return easyocr_text, easyocr_warnings

    tesseract_text, tesseract_warnings = _ocr_with_tesseract(
        _enhance_for_ocr(image, get_settings().ocr_full_upscale_factor)
    )
    if tesseract_text.strip():
        return tesseract_text, easyocr_warnings + tesseract_warnings

    return "", baidu_warnings + easyocr_warnings + tesseract_warnings


def _collect_image_text(path: Path) -> tuple[str, list[str]]:
    try:
        from PIL import Image
    except ImportError:
        return "", ["Pillow 未安装，图片暂时无法解析。"]

    try:
        image = Image.open(path)
    except Exception as exc:
        return "", [f"图片打开失败: {exc}"]

    return _ocr_pil_image(image)


def _ocr_pdf_page(page, index: int, settings) -> tuple[int, str, list[str]]:
    """OCR单个PDF页面，返回(页码, 文本, 警告)。"""
    page_warnings: list[str] = []
    try:
        width, height = page.get_size()
        render_scale = settings.pdf_ocr_render_scale
        longest_side = max(width, height)
        if longest_side * render_scale > settings.pdf_ocr_max_side_px:
            render_scale = max(1.5, settings.pdf_ocr_max_side_px / longest_side)

        # 限制单页最大渲染尺寸以避免内存问题
        max_render_pixels = 4000 * 4000  # 1600万像素上限
        render_pixels = (width * render_scale) * (height * render_scale)
        if render_pixels > max_render_pixels:
            render_scale = (max_render_pixels / (width * height)) ** 0.5

        bitmap = page.render(scale=render_scale)
        image = bitmap.to_pil()
        text, ocr_warnings = _ocr_pil_image(image)
        bitmap.close()

        if ocr_warnings:
            page_warnings.extend(f"第 {index} 页: {w}" for w in ocr_warnings)

        return index, text.strip() if text else "", page_warnings
    except Exception as exc:
        return index, "", [f"第 {index} 页 OCR 失败: {exc}"]


def _collect_pdf_ocr_text(path: Path) -> tuple[str, list[str]]:
    settings = get_settings()
    try:
        import pypdfium2 as pdfium
    except ImportError:
        return "", ["未安装 PDF OCR 渲染依赖 `pypdfium2`。"]

    warnings: list[str] = []

    try:
        pdf = pdfium.PdfDocument(str(path))
    except Exception as exc:
        return "", [f"PDF OCR 打开失败: {exc}"]

    try:
        # 收集所有页面
        pages = list(enumerate(pdf, start=1))
        total_pages = len(pages)
        warnings.append(f"PDF共 {total_pages} 页，开始OCR识别...")

        # 大文件警告：超过5页的PDF处理会很慢
        if total_pages > 5:
            warnings.append(f"PDF页数较多({total_pages}页)，OCR识别可能需要几分钟时间...")

        # 最多3页并行（避免OCR服务限流）
        max_workers = min(3, len(pages))

        if max_workers > 1:
            from concurrent.futures import ThreadPoolExecutor

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(_ocr_pdf_page, page, idx, settings) for idx, page in pages]
                results = [f.result() for f in futures]
        else:
            results = [_ocr_pdf_page(page, idx, settings) for idx, page in pages]

        # 按页码排序结果
        results.sort(key=lambda x: x[0])

        chunks: list[str] = []
        total_chars = 0
        for index, text, page_warnings in results:
            warnings.extend(page_warnings)
            if text:
                chunks.append(f"[第 {index} 页 OCR]\n{text}")
                total_chars += len(text)

        if chunks:
            warnings.append(f"OCR识别完成，共 {len(chunks)}/{total_pages} 页有内容，总字符数: {total_chars}")
    finally:
        with contextlib.suppress(Exception):
            pdf.close()

    if not chunks:
        warnings.append("PDF OCR 未识别到有效文本。")

    return "\n\n".join(chunks), warnings


def _collect_plain_text(path: Path) -> tuple[str, list[str]]:
    try:
        return path.read_text(encoding="utf-8"), []
    except UnicodeDecodeError:
        return path.read_text(encoding="gb18030", errors="ignore"), []


async def parse_upload(upload: UploadFile) -> tuple[ParsedDocument, str]:
    suffix = Path(upload.filename or "upload.bin").suffix.lower()
    if not upload.filename:
        raise ValueError("上传文件缺少文件名。")

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_path = Path(temp_file.name)
        content = await upload.read()
        temp_file.write(content)

    text = ""
    warnings: list[str] = []
    parser_name = "unknown"

    try:
        if suffix == ".pdf":
            # 尝试直接提取文本
            try:
                text, warnings = _collect_pdf_text(temp_path)
                parser_name = "pdfplumber"
            except Exception as pdf_exc:
                warnings.append(f"PDF 解析失败: {pdf_exc}，尝试 OCR...")
                text = ""
                parser_name = "ocr-fallback"

            # 无文本、乱码或解析失败时，自动回退到 OCR
            if not text.strip() or _is_garbage_text(text):
                if text.strip():
                    warnings.append("PDF 文本提取结果异常（可能为乱码），已自动使用 OCR 重新识别。")
                ocr_text, ocr_warnings = _collect_pdf_ocr_text(temp_path)
                warnings.extend(ocr_warnings)
                if ocr_text.strip():
                    text = ocr_text
                    parser_name = "pdfplumber+ocr" if parser_name == "pdfplumber" else "ocr"
        elif suffix == ".dxf":
            try:
                text, warnings = _collect_dxf_entities(temp_path)
                parser_name = "ezdxf"
            except Exception as e:
                text, warnings = "", [f"DXF 解析失败: {e}"]
                parser_name = "error"
        elif suffix == ".dwg":
            try:
                text, warnings = _collect_dwg_entities(temp_path)
                parser_name = "odafc"
            except Exception as e:
                text, warnings = "", [f"DWG 解析失败: {e}"]
                parser_name = "error"
        elif suffix in SUPPORTED_IMAGE_TYPES:
            try:
                text, warnings = _collect_image_text(temp_path)
                parser_name = "ocr"
            except Exception as e:
                text, warnings = "", [f"图片 OCR 失败: {e}"]
                parser_name = "error"
        elif suffix in SUPPORTED_TEXT_TYPES:
            try:
                text, warnings = _collect_plain_text(temp_path)
                parser_name = "text"
            except Exception as e:
                text, warnings = "", [f"文本读取失败: {e}"]
                parser_name = "error"
        else:
            try:
                text, warnings = _collect_plain_text(temp_path)
                parser_name = "fallback"
                warnings.append(f"未识别的扩展名 `{suffix}`，已按文本尝试读取。")
            except Exception as e:
                text, warnings = "", [f"文件读取失败: {e}"]
                parser_name = "error"
    except Exception as e:
        text = ""
        warnings = [f"处理文件时发生错误: {e}"]
        parser_name = "error"
    finally:
        with contextlib.suppress(FileNotFoundError):
            temp_path.unlink()

    return ParsedDocument(
        filename=upload.filename,
        file_type=suffix.lstrip(".") or "unknown",
        parser=parser_name,
        text_excerpt=_clean_excerpt(text),
        warnings=warnings,
    ), text
