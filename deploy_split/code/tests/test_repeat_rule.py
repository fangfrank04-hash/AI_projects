"""重复告警规则专项测试。

规则：同一用户同一种违规连续出现时，前 3 次正常上报（原编码、notify=True），
第 4 次起视为重复（编码 1002、notify=False）；出现不同违规类型或正常画面时重新计数。

运行方式（项目根目录）：
    python -m unittest tests.test_repeat_rule -v
"""
import io
import unittest
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.ml.image_proctor import ProctorResult
from app.schemas.proctor import ActionType, DetectionData
from app.services.proctor_service import (
    BLACK_SCREEN_EXCEPTION_CODE,
    MAX_CONSECUTIVE_REPORTS,
    REPEAT_EXCEPTION_CODE,
    REPEAT_EXCEPTION_MESSAGE,
    RepeatViolationState,
    _black_screen_response,
    _mark_repeat_status,
)

client = TestClient(app)


def _uid(prefix):
    """每个用例用独立用户，避免全局计数状态在用例间串扰。"""
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _image_bytes(color=(0, 0, 0)):
    buffer = io.BytesIO()
    Image.new("RGB", (64, 64), color).save(buffer, format="JPEG")
    return buffer.getvalue()


class RepeatViolationStateTest(unittest.TestCase):
    """纯逻辑层：计数状态机（不依赖模型和 HTTP）。"""

    def test_first_three_report_then_repeat(self):
        state = RepeatViolationState()
        results = [state.record("u", ActionType.TURN_HEAD) for _ in range(6)]
        self.assertEqual([True, True, True, False, False, False], results)

    def test_boundary_exactly_at_limit(self):
        state = RepeatViolationState()
        for _ in range(MAX_CONSECUTIVE_REPORTS):
            self.assertTrue(state.record("u", ActionType.TURN_BODY))
        self.assertFalse(state.record("u", ActionType.TURN_BODY))

    def test_different_type_restarts_count(self):
        state = RepeatViolationState()
        state.record("u", ActionType.TURN_HEAD)
        state.record("u", ActionType.TURN_HEAD)
        # 切到新类型：从 1 重新开始
        self.assertTrue(state.record("u", ActionType.GAZE_AWAY))
        # 切回旧类型：同样从 1 重新开始
        self.assertTrue(state.record("u", ActionType.TURN_HEAD))

    def test_clear_restarts_count(self):
        state = RepeatViolationState()
        for _ in range(MAX_CONSECUTIVE_REPORTS):
            state.record("u", ActionType.PHONE_CALL)
        state.clear("u")
        self.assertTrue(state.record("u", ActionType.PHONE_CALL))

    def test_users_are_independent(self):
        state = RepeatViolationState()
        for _ in range(MAX_CONSECUTIVE_REPORTS + 2):
            state.record("a", ActionType.MULTI_PERSON)
        # a 已重复，但 b 不受影响
        self.assertTrue(state.record("b", ActionType.MULTI_PERSON))
        self.assertFalse(state.record("a", ActionType.MULTI_PERSON))


class BlackScreenResponseTest(unittest.TestCase):
    """黑屏响应函数层：编码 1001 -> 1002 的切换。"""

    def test_code_sequence(self):
        uid = _uid("black")
        # 前 3 次：原编码 1001，notify=True
        for i in range(3):
            data = _black_screen_response(uid).data
            self.assertEqual(BLACK_SCREEN_EXCEPTION_CODE, data.exception_code, f"第{i + 1}次")
            self.assertTrue(data.notify, f"第{i + 1}次")
            self.assertEqual(ActionType.BLACK_SCREEN, data.action_type)
            self.assertTrue(data.warning)
        # 第 4、5 次：重复编码 1002，notify=False
        for i in range(2):
            data = _black_screen_response(uid).data
            self.assertEqual(REPEAT_EXCEPTION_CODE, data.exception_code, f"第{i + 4}次")
            self.assertEqual(REPEAT_EXCEPTION_MESSAGE, data.exception_message)
            self.assertFalse(data.notify)

    def test_action_type_kept_after_repeat(self):
        """重复后 action_type 仍是黑屏，方便上游统计是哪类违规在重复。"""
        uid = _uid("blackkeep")
        for _ in range(4):
            data = _black_screen_response(uid).data
        self.assertEqual(ActionType.BLACK_SCREEN, data.action_type)


class MarkRepeatOnDetectionTest(unittest.TestCase):
    """模型违规结果层：转头/多人等无原编码的违规走 _mark_repeat_status。"""

    def test_ml_violation_repeat_sequence(self):
        uid = _uid("ml")
        codes, notifies = [], []
        for _ in range(4):
            data = DetectionData(warning=True, action_type=ActionType.TURN_HEAD, user_id=uid)
            _mark_repeat_status(data, uid)
            codes.append(data.exception_code)
            notifies.append(data.notify)
        # 转头没有原编码，前 3 次为 None；第 4 次变 1002
        self.assertEqual([None, None, None, REPEAT_EXCEPTION_CODE], codes)
        self.assertEqual([True, True, True, False], notifies)

    def test_normal_detection_not_marked(self):
        uid = _uid("normal")
        data = DetectionData(warning=False, action_type=ActionType.NORMAL, user_id=uid)
        _mark_repeat_status(data, uid)
        self.assertFalse(data.notify)
        self.assertIsNone(data.exception_code)

    def test_normal_clears_ongoing_count(self):
        uid = _uid("clear")
        for _ in range(MAX_CONSECUTIVE_REPORTS):
            data = DetectionData(warning=True, action_type=ActionType.TURN_HEAD, user_id=uid)
            _mark_repeat_status(data, uid)
        # 正常画面打断
        _mark_repeat_status(
            DetectionData(warning=False, action_type=ActionType.NORMAL, user_id=uid), uid
        )
        # 再来同种违规：重新从第 1 次计
        data = DetectionData(warning=True, action_type=ActionType.TURN_HEAD, user_id=uid)
        _mark_repeat_status(data, uid)
        self.assertTrue(data.notify)
        self.assertIsNone(data.exception_code)

    def test_type_switch_midway_restarts(self):
        uid = _uid("switch")
        for _ in range(2):
            _mark_repeat_status(
                DetectionData(warning=True, action_type=ActionType.MULTI_PERSON, user_id=uid), uid
            )
        data = DetectionData(warning=True, action_type=ActionType.PHONE_CALL, user_id=uid)
        _mark_repeat_status(data, uid)
        self.assertTrue(data.notify)


class RepeatRuleApiTest(unittest.TestCase):
    """接口层：走完整 HTTP 流程验证。"""

    def test_black_screen_via_http(self):
        uid = _uid("api")
        files = {"file": ("black.jpg", _image_bytes(), "image/jpeg")}
        codes, notifies = [], []
        for _ in range(4):
            body = client.post("/upload_face", files=files, data={"user_id": uid}).json()
            self.assertEqual(200, body["code"])
            codes.append(body["data"]["exception_code"])
            notifies.append(body["data"]["notify"])
        self.assertEqual([1001, 1001, 1001, 1002], codes)
        self.assertEqual([True, True, True, False], notifies)

    def test_users_isolated_via_http(self):
        uid_a = _uid("isoa")
        uid_b = _uid("isob")
        files = {"file": ("black.jpg", _image_bytes(), "image/jpeg")}
        for _ in range(4):
            client.post("/upload_face", files=files, data={"user_id": uid_a})
        # a 已进入重复状态，b 首次仍正常报
        body_b = client.post("/upload_face", files=files, data={"user_id": uid_b}).json()
        self.assertEqual(1001, body_b["data"]["exception_code"])
        self.assertTrue(body_b["data"]["notify"])

    @patch("app.services.proctor_service._proctor_pool.analyze")
    def test_turn_head_via_http(self, analyze):
        analyze.return_value = ProctorResult(
            warning=True, action_type=ActionType.TURN_HEAD, action_label="转头"
        )
        uid = _uid("turn")
        files = {"file": ("face.jpg", _image_bytes((127, 127, 127)), "image/jpeg")}
        codes, notifies = [], []
        for _ in range(4):
            body = client.post("/upload_face", files=files, data={"user_id": uid}).json()
            codes.append(body["data"]["exception_code"])
            notifies.append(body["data"]["notify"])
        self.assertEqual([None, None, None, 1002], codes)
        self.assertEqual([True, True, True, False], notifies)

    @patch("app.services.proctor_service._proctor_pool.analyze")
    def test_normal_interrupt_via_http(self, analyze):
        """黑屏 3 次 -> 正常画面 -> 再黑屏应重新报 1001。"""
        analyze.return_value = ProctorResult()
        uid = _uid("interrupt")
        black = {"file": ("black.jpg", _image_bytes(), "image/jpeg")}
        normal = {"file": ("normal.jpg", _image_bytes((60, 60, 60)), "image/jpeg")}
        for _ in range(3):
            client.post("/upload_face", files=black, data={"user_id": uid})
        body = client.post("/upload_face", files=normal, data={"user_id": uid}).json()
        self.assertEqual(200, body["code"])
        again = client.post("/upload_face", files=black, data={"user_id": uid}).json()
        self.assertEqual(1001, again["data"]["exception_code"])
        self.assertTrue(again["data"]["notify"])


if __name__ == "__main__":
    unittest.main()
