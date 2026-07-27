"""接口层测试：验证统一响应体 {code, message, data} 结构与错误码分支。"""
import io
import unittest

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.schemas.proctor import StatusCode

client = TestClient(app)


def _make_image_bytes(fmt="JPEG", size=(64, 64), color=(127, 127, 127)):
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, format=fmt)
    buffer.seek(0)
    return buffer.read()


class ApiResponseStructureTest(unittest.TestCase):
    def test_ping_returns_alive(self):
        resp = client.get("/ping")

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["pong"])
        self.assertIn("message", body)

    def test_test_endpoint_returns_unified_envelope(self):
        resp = client.get("/test")

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("code", body)
        self.assertIn("message", body)
        self.assertIn("data", body)

    def test_upload_valid_image_succeeds(self):
        files = {"file": ("face.jpg", _make_image_bytes(), "image/jpeg")}
        resp = client.post("/upload_face", files=files)

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["code"], StatusCode.SUCCESS)
        self.assertIn("action_type", body["data"])
        self.assertIn("warning", body["data"])

    def test_upload_non_image_type_rejected(self):
        files = {"file": ("note.txt", b"hello world", "text/plain")}
        resp = client.post("/upload_face", files=files)

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["code"], StatusCode.BAD_REQUEST)

    def test_upload_corrupt_image_returns_decode_error(self):
        files = {"file": ("broken.png", b"not-a-real-image", "image/png")}
        resp = client.post("/upload_face", files=files)

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["code"], StatusCode.BAD_REQUEST)


if __name__ == "__main__":
    unittest.main()
