import io

from PIL import Image
from fastapi.testclient import TestClient

from backend.main import app


def _png_bytes() -> bytes:
    image = Image.new("RGB", (80, 80), (220, 180, 150))
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def test_rejects_spoofed_mime():
    client = TestClient(app)
    response = client.post("/api/v1/palmistry/analyze", files={"image": ("hand.png", b"not an image", "image/png")})
    assert response.status_code == 422
    assert response.json()["detail"]["error"]["code"] == "IMAGE_UNCLEAR"


def test_health_exposes_configured_model():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["model"]
