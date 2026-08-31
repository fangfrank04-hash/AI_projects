"""接口层测试：验证统一响应体 {code, message, data} 结构与错误码分支。"""
import io
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.ml.image_proctor import ProctorResult
from app.schemas.proctor import ActionType, StatusCode
from app.services.proctor_service import is_black_screen

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

    @patch("app.services.proctor_service._proctor_pool.analyze")
    def test_upload_valid_image_succeeds(self, analyze):
        analyze.return_value = ProctorResult()
        files = {"file": ("face.jpg", _make_image_bytes(), "image/jpeg")}
        resp = client.post("/upload_face", files=files, data={"user_id": "user001"})

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["code"], StatusCode.SUCCESS)
        self.assertIn("action_type", body["data"])
        self.assertIn("warning", body["data"])
        self.assertEqual("user001", body["data"]["user_id"])

    def test_upload_non_image_type_rejected(self):
        files = {"file": ("note.txt", b"hello world", "text/plain")}
        resp = client.post("/upload_face", files=files, data={"user_id": "user001"})

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["code"], StatusCode.BAD_REQUEST)

    def test_upload_corrupt_image_returns_decode_error(self):
        files = {"file": ("broken.png", b"not-a-real-image", "image/png")}
        resp = client.post("/upload_face", files=files, data={"user_id": "user001"})

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["code"], StatusCode.BAD_REQUEST)

    def test_upload_requires_user_id(self):
        files = {"file": ("face.jpg", _make_image_bytes(), "image/jpeg")}
        resp = client.post("/upload_face", files=files)

        self.assertEqual(resp.status_code, 422)
        self.assertEqual(StatusCode.BAD_REQUEST, resp.json()["code"])

    def test_upload_rejects_blank_user_id(self):
        files = {"file": ("face.jpg", _make_image_bytes(), "image/jpeg")}
        resp = client.post("/upload_face", files=files, data={"user_id": "   "})

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(StatusCode.BAD_REQUEST, resp.json()["code"])

    def test_black_screen_reports_first_three_then_repeat_code(self):
        black_image = _make_image_bytes(color=(0, 0, 0))
        files = {"file": ("black.jpg", black_image, "image/jpeg")}

        # 连续 3 次黑屏：正常上报，编码 1001
        for _ in range(3):
            body = client.post(
                "/upload_face", files=files, data={"user_id": "black-user"}
            ).json()
            self.assertEqual(StatusCode.SUCCESS, body["code"])
            self.assertEqual("检测到黑屏！", body["message"])
            self.assertEqual(1001, body["data"]["exception_code"])
            self.assertTrue(body["data"]["notify"])

        # 第 4 次黑屏：视为重复，编码 1002 且不再上报
        fourth = client.post(
            "/upload_face", files=files, data={"user_id": "black-user"}
        ).json()
        self.assertEqual(1002, fourth["data"]["exception_code"])
        self.assertEqual("重复告警", fourth["data"]["exception_message"])
        self.assertFalse(fourth["data"]["notify"])

        # 出现正常画面后再次黑屏：重新计数
        with patch("app.services.proctor_service._proctor_pool.analyze", return_value=ProctorResult()):
            normal = client.post(
                "/upload_face",
                files={"file": ("normal.jpg", _make_image_bytes(color=(60, 60, 60)), "image/jpeg")},
                data={"user_id": "black-user"},
            )
        self.assertEqual(StatusCode.SUCCESS, normal.json()["code"])
        self.assertIsNone(normal.json()["data"]["exception_code"])

        fifth = client.post(
            "/upload_face", files=files, data={"user_id": "black-user"}
        ).json()
        self.assertEqual(1001, fifth["data"]["exception_code"])
        self.assertTrue(fifth["data"]["notify"])

    @patch("app.services.proctor_service._proctor_pool.analyze")
    def test_repeated_violation_reports_three_times_then_repeat_code(self, analyze):
        analyze.return_value = ProctorResult(
            warning=True, action_type=ActionType.TURN_HEAD, action_label="转头"
        )
        files = {"file": ("face.jpg", _make_image_bytes(), "image/jpeg")}
        results = []
        for _ in range(4):
            body = client.post(
                "/upload_face", files=files, data={"user_id": "turn-user"}
            ).json()
            results.append((body["data"]["exception_code"], body["data"]["notify"]))

        # 前 3 次正常上报（转头无原编码），第 4 次重复返回 1002
        self.assertEqual(
            [(None, True), (None, True), (None, True), (1002, False)], results
        )

    def test_black_screen_uses_a_conservative_near_black_threshold(self):
        self.assertTrue(is_black_screen(Image.new("RGB", (100, 100), (3, 3, 3))))
        self.assertFalse(is_black_screen(Image.new("RGB", (100, 100), (60, 60, 60))))


if __name__ == "__main__":
    unittest.main()
