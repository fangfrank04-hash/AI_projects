"""重复告警规则逻辑验证（不需要启动服务，直接导入项目代码验证核心逻辑）。

适用场景：内网改完代码后、还没启动服务时，先跑这个确认核心逻辑正确。
依赖：只依赖项目本身的运行依赖（fastapi/pillow/numpy），不需要 httpx，
首次导入会加载模型池，等几秒属正常现象。

用法（在 code 目录下，即和 app/ 同级的目录执行）：
    python scripts/verify_repeat_logic.py

规则回顾：
    同一用户同一种违规连续出现：前 3 次返回原编码（黑屏 1001）且 notify=True；
    第 4 次起返回重复编码 1002 且 notify=False；
    中间出现正常画面或别的违规类型则重新计数。
"""
import os
import sys
import unittest
import uuid

# 把 code 根目录加入 sys.path（本脚本位于 code/scripts/ 下）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.schemas.proctor import ActionType, DetectionData
from app.services.proctor_service import (
    BLACK_SCREEN_EXCEPTION_CODE,
    MAX_CONSECUTIVE_REPORTS,
    REPEAT_EXCEPTION_CODE,
    RepeatViolationState,
    _black_screen_response,
    _mark_repeat_status,
)


def _uid(prefix):
    return f"logic-{prefix}-{uuid.uuid4().hex[:8]}"


class StateMachineTest(unittest.TestCase):
    """计数状态机：前 3 次上报、第 4 次起重复。"""

    def test_first_three_report_then_repeat(self):
        state = RepeatViolationState()
        results = [state.record("u", ActionType.TURN_HEAD) for _ in range(6)]
        self.assertEqual([True, True, True, False, False, False], results)

    def test_limit_constant_is_three(self):
        self.assertEqual(3, MAX_CONSECUTIVE_REPORTS)

    def test_type_switch_restarts(self):
        state = RepeatViolationState()
        state.record("u", ActionType.TURN_HEAD)
        state.record("u", ActionType.TURN_HEAD)
        self.assertTrue(state.record("u", ActionType.GAZE_AWAY))
        self.assertTrue(state.record("u", ActionType.TURN_HEAD))

    def test_clear_restarts(self):
        state = RepeatViolationState()
        for _ in range(3):
            state.record("u", ActionType.PHONE_CALL)
        state.clear("u")
        self.assertTrue(state.record("u", ActionType.PHONE_CALL))

    def test_users_independent(self):
        state = RepeatViolationState()
        for _ in range(5):
            state.record("a", ActionType.MULTI_PERSON)
        self.assertTrue(state.record("b", ActionType.MULTI_PERSON))


class BlackScreenResponseTest(unittest.TestCase):
    """黑屏响应：编码 1001 -> 1002。"""

    def test_code_sequence(self):
        uid = _uid("black")
        for i in range(3):
            data = _black_screen_response(uid).data
            self.assertEqual(BLACK_SCREEN_EXCEPTION_CODE, data.exception_code, f"第{i + 1}次")
            self.assertTrue(data.notify)
        for i in range(2):
            data = _black_screen_response(uid).data
            self.assertEqual(REPEAT_EXCEPTION_CODE, data.exception_code, f"第{i + 4}次")
            self.assertFalse(data.notify)
            self.assertEqual("重复告警", data.exception_message)

    def test_repeat_keeps_action_type(self):
        uid = _uid("keep")
        for _ in range(4):
            data = _black_screen_response(uid).data
        self.assertEqual(ActionType.BLACK_SCREEN, data.action_type)


class MarkRepeatTest(unittest.TestCase):
    """模型违规结果：转头/多人等无原编码违规的去重标记。"""

    def test_violation_sequence(self):
        uid = _uid("ml")
        codes, notifies = [], []
        for _ in range(4):
            data = DetectionData(warning=True, action_type=ActionType.TURN_HEAD, user_id=uid)
            _mark_repeat_status(data, uid)
            codes.append(data.exception_code)
            notifies.append(data.notify)
        self.assertEqual([None, None, None, REPEAT_EXCEPTION_CODE], codes)
        self.assertEqual([True, True, True, False], notifies)

    def test_normal_not_marked_and_clears(self):
        uid = _uid("normal")
        for _ in range(3):
            _mark_repeat_status(
                DetectionData(warning=True, action_type=ActionType.TURN_HEAD, user_id=uid), uid
            )
        _mark_repeat_status(
            DetectionData(warning=False, action_type=ActionType.NORMAL, user_id=uid), uid
        )
        data = DetectionData(warning=True, action_type=ActionType.TURN_HEAD, user_id=uid)
        _mark_repeat_status(data, uid)
        self.assertTrue(data.notify)
        self.assertIsNone(data.exception_code)


if __name__ == "__main__":
    unittest.main(verbosity=2)
