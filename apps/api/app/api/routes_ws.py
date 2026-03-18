from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import async_session_maker
from app.models_db import ProviderConfig
from app.security import decrypt_value
from app.services.extractor import ParameterExtractor
from app.services.parsers import parse_upload
from app.services.pricing import PricingEngine

router = APIRouter()


class ProgressTracker:
    """进度追踪器，用于向WebSocket发送进度更新。"""

    def __init__(self, websocket: WebSocket, total_files: int):
        self.websocket = websocket
        self.total_files = total_files
        self.current_file = 0
        self.current_step = ""

    async def send_progress(self, message: dict[str, Any]) -> None:
        """发送进度消息。"""
        try:
            await self.websocket.send_json(message)
        except Exception:
            pass  # WebSocket可能已关闭

    async def start_file(self, filename: str, index: int) -> None:
        """开始处理新文件。"""
        self.current_file = index + 1
        self.current_step = "解析文件"
        await self.send_progress({
            "type": "file_start",
            "filename": filename,
            "current": self.current_file,
            "total": self.total_files,
            "percent": int((self.current_file - 1) / self.total_files * 100),
            "step": self.current_step,
        })

    async def update_step(self, step: str, detail: str = "") -> None:
        """更新当前步骤。"""
        self.current_step = step
        await self.send_progress({
            "type": "step_update",
            "step": step,
            "detail": detail,
            "current": self.current_file,
            "total": self.total_files,
            "percent": int((self.current_file - 0.5) / self.total_files * 100),
        })

    async def complete_file(self, filename: str, success: bool = True) -> None:
        """完成当前文件。"""
        await self.send_progress({
            "type": "file_complete",
            "filename": filename,
            "success": success,
            "current": self.current_file,
            "total": self.total_files,
            "percent": int(self.current_file / self.total_files * 100),
        })

    async def complete_all(self, result: dict) -> None:
        """所有文件处理完成。"""
        await self.send_progress({
            "type": "complete",
            "percent": 100,
            "result": result,
        })

    async def error(self, message: str) -> None:
        """发送错误信息。"""
        await self.send_progress({
            "type": "error",
            "message": message,
        })


@router.websocket("/ws/inquiry")
async def websocket_inquiry(websocket: WebSocket) -> None:
    """WebSocket接口：实时推送询价处理进度。"""
    await websocket.accept()

    try:
        # 接收上传的文件信息（文件已在客户端暂存，这里接收文件元数据和临时路径）
        data = await websocket.receive_json()

        if data.get("action") != "start_processing":
            await websocket.send_json({"type": "error", "message": "无效的操作"})
            await websocket.close()
            return

        files_data = data.get("files", [])
        if not files_data:
            await websocket.send_json({"type": "error", "message": "没有文件需要处理"})
            await websocket.close()
            return

        total_files = len(files_data)
        tracker = ProgressTracker(websocket, total_files)

        settings = get_settings()
        extractor = ParameterExtractor(settings)
        pricing = PricingEngine(settings)

        documents = []
        raw_texts = []
        warnings: list[str] = []

        # 处理每个文件
        for index, file_info in enumerate(files_data):
            filename = file_info.get("filename", f"文件{index+1}")
            file_content = file_info.get("content", "")  # base64编码的文件内容

            await tracker.start_file(filename, index)

            try:
                # 这里简化处理，实际应该解码base64并创建UploadFile
                # 由于WebSocket不直接支持UploadFile，需要特殊处理
                await tracker.update_step("正在解析", "OCR识别中...")

                # 模拟处理时间
                await asyncio.sleep(0.5)

                await tracker.complete_file(filename, success=True)

            except Exception as e:
                await tracker.complete_file(filename, success=False)
                warnings.append(f"{filename}: 处理失败 - {e}")

        # 完成
        await tracker.update_step("提取参数", "AI分析中...")
        await asyncio.sleep(0.5)

        await tracker.update_step("价格匹配", "查询价格库...")
        await asyncio.sleep(0.5)

        # 发送最终结果
        result = {
            "request_id": f"inq-{asyncio.get_event_loop().time():.0f}",
            "item_count": 0,
            "message": "处理完成（演示模式）",
        }
        await tracker.complete_all(result)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
