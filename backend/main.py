import os
import uuid
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from .image_service import prepare_image
from .model_service import analyze

load_dotenv(".env.local")
MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", "10485760"))
ALLOWED = {"image/jpeg", "image/png"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="Palmistry Cultural Interpretation API", version="1.0.0", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok", "model": os.environ.get("AI_MODEL", "gpt-5.5")}


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "index.html"))


@app.post("/api/v1/palmistry/analyze")
async def palmistry_analyze(image: UploadFile = File(...)):
    request_id = str(uuid.uuid4())
    if image.content_type not in ALLOWED:
        raise HTTPException(415, {"request_id": request_id, "error": {"code": "UNSUPPORTED_MEDIA_TYPE", "message": "仅支持 JPG、JPEG 或 PNG。", "details": []}})
    data = await image.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, {"request_id": request_id, "error": {"code": "FILE_TOO_LARGE", "message": "图片不能超过 10 MB。", "details": []}})
    try:
        prepared = prepare_image(data, image.content_type)
    except Exception as exc:
        raise HTTPException(422, {"request_id": request_id, "error": {"code": "IMAGE_UNCLEAR", "message": "图片无法解码或不适合分析。", "details": [str(exc)]}})
    if not prepared.hand_detected:
        raise HTTPException(422, {"request_id": request_id, "error": {"code": "IMAGE_UNCLEAR", "message": "没有检测到清晰的掌心，请将掌心正对镜头重新拍摄。", "details": ["未检测到手部"]}})
    if prepared.score < 0.45:
        raise HTTPException(422, {"request_id": request_id, "error": {"code": "IMAGE_UNCLEAR", "message": "无法清晰识别掌心，请重新拍摄。", "details": prepared.issues}})
    try:
        report = await analyze(prepared, prepared.score, prepared.issues)
    except ValueError:
        raise HTTPException(502, {"request_id": request_id, "error": {"code": "MODEL_OUTPUT_INVALID", "message": "解析服务返回了无法验证的结果。", "details": []}})
    except TimeoutError:
        raise HTTPException(504, {"request_id": request_id, "error": {"code": "MODEL_TIMEOUT", "message": "解析服务响应超时，请稍后重试。", "details": []}})
    except Exception:
        raise HTTPException(502, {"request_id": request_id, "error": {"code": "INTERNAL_ERROR", "message": "解析服务暂时不可用，请稍后重试。", "details": []}})
    result = report.model_dump()
    result.update({"request_id": request_id, "model": os.environ.get("AI_MODEL", "gpt-5.5")})
    return result
