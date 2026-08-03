import contextlib
import datetime
import logging
import os
import queue
import threading
from dataclasses import dataclass

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python as mp_tasks
from mediapipe.tasks.python import vision as mp_vision
from PIL import Image

from app.core.config import settings
from app.schemas.proctor import ActionType

logger = logging.getLogger(__name__)

# ===== MediaPipe Face Mesh 关键点索引（solvePnP 用的 6 个点）=====
FACE_LM_LEFT_EYE = 33     # 左眼外角
FACE_LM_RIGHT_EYE = 263   # 右眼外角
FACE_LM_NOSE_TIP = 1      # 鼻尖
FACE_LM_MOUTH_LEFT = 61   # 左嘴角
FACE_LM_MOUTH_RIGHT = 291  # 右嘴角
FACE_LM_CHIN = 199        # 下巴
FACE_PNP_LANDMARKS = (
    FACE_LM_LEFT_EYE,
    FACE_LM_RIGHT_EYE,
    FACE_LM_NOSE_TIP,
    FACE_LM_MOUTH_LEFT,
    FACE_LM_MOUTH_RIGHT,
    FACE_LM_CHIN,
)

# ===== MediaPipe Pose 关键点索引（33 点里用到的几个）=====
POSE_LM_LEFT_EAR = 7
POSE_LM_RIGHT_EAR = 8
POSE_LM_LEFT_SHOULDER = 11
POSE_LM_RIGHT_SHOULDER = 12
POSE_LM_LEFT_ELBOW = 13
POSE_LM_RIGHT_ELBOW = 14
POSE_LM_LEFT_WRIST = 15
POSE_LM_RIGHT_WRIST = 16


# ===== 面部角度判定阈值默认值（判断视线偏移/转头方向用）=====
# solvePnP 算出头部 yaw(左右)/pitch(上下) 角度后，超过这些阈值就判定为看向对应方向。
# 这 4 个值可由接口参数覆盖（Java 不传则用默认）。
DEFAULT_MAX_LEFT_ANGLE = 6      # yaw > 该值 → 向左看
DEFAULT_MAX_RIGHT_ANGLE = -6    # yaw < 该值 → 向右看
DEFAULT_MAX_UP_ANGLE = 6        # pitch > 该值 → 向上看
DEFAULT_MAX_DOWN_ANGLE = -1     # pitch < 该值 → 向下看


@dataclass
class ProctorResult:
    """单张图片的结构化检测结果（供 service 层映射为 API 响应的 data）。"""

    action_type: ActionType = ActionType.NORMAL
    action_label: str = "正常考试中"
    warning: bool = False
    warning_count: int = 0
    person_count: int = 1


@dataclass
class FaceAngleThresholds:
    """面部角度判定阈值（单次请求可覆盖）。

    字段默认值 = 代码里写死的标定值；Java 不传参数时就用这些默认值。
    """

    max_left_angle: float = DEFAULT_MAX_LEFT_ANGLE
    max_right_angle: float = DEFAULT_MAX_RIGHT_ANGLE
    max_up_angle: float = DEFAULT_MAX_UP_ANGLE
    max_down_angle: float = DEFAULT_MAX_DOWN_ANGLE


# 基于图片的监考类（逻辑与 FrontCamera 一致，不调用摄像头）
class ImageProctor:
    def __init__(self):
        # 面部角度判定阈值（默认值，可被单次请求的参数临时覆盖）
        self.max_left_angle = DEFAULT_MAX_LEFT_ANGLE
        self.max_right_angle = DEFAULT_MAX_RIGHT_ANGLE
        self.max_up_angle = DEFAULT_MAX_UP_ANGLE
        self.max_down_angle = DEFAULT_MAX_DOWN_ANGLE

        # 周期内看到的方向
        self.directions = []
        self.warning_count = 0
        self.texts = []
        self.result = ProctorResult()
        self.last_time = datetime.datetime.min

        # ===== Pose 动作检测阈值 v2（基于 180 张真实样本标定，2026-07-03）=====
        # 6 大类：正常考试 / 视线偏移 / 离开座位 / 多人 / 打电话 / 伸胳膊
        self.phone_wrist_ear_dist = 0.55      # 打电话：腕耳归一化距离 < 0.55
        self.phone_arm_angle = 30            # 打电话：对应侧臂角 < 30°（手臂弯曲贴头）
        self.stretch_arm_angle = 140         # 伸展：肩-肘-腕夹角 > 140°
        self.horizontal_stretch_arm_angle = 155   # 水平/斜下伸展：臂角 ≥ 155°（胳膊伸直）
        # 门槛用肩+肘+腕三点可见度，过滤掉低可见度的幻觉手腕（否则正常/离座姿势会误报）。
        self.horizontal_stretch_visibility = 0.4
        self.horizontal_stretch_arm_length = 1.05   # 腕-肩距/肩宽 ≥ 1.05（正常弯臂 <1.0）
        self.horizontal_stretch_wrist_ear_dist = 1.6  # 腕-耳距/肩宽 ≥ 1.6（手远离头部，排除打电话）
        # 肘部兼底规则（基于 305 张样本标定，2026-07-30）：伸直手臂时手腕 visibility 极低不可靠，
        # 改用“肘接近/高于肩”判断。数据：伸胳膊 elbow_dy(肘肩高度差/肩宽) avg -0.05；
        # 正常/多人/视线偏移/打电话的 elbow_dy 最小都 ≥ 0.69（肘在肩下方）。
        self.elbow_stretch_visibility = 0.25   # 肩、肘可见度下限（肘比腕可靠）
        self.elbow_stretch_max_dy = 0.5         # (肘.y - 肩.y)/肩宽 ≤ 0.5 → 肘齐肩或更高
        self.elbow_stretch_min_reach = 0.7      # 肘-肩距/肩宽 ≥ 0.7（排除肘塌缩到肩上的退化情况）
        self.turn_body_shoulder_dist = 0.25   # 转身90度：双肩归一化距离 < 0.25
        self.visibility_threshold = 0.5     # 关键点 visibility 过滤阈值

        # ===== MediaPipe 模型实例：只创建一次，全生命周期复用 =====
        # 创建模型（加载计算图）是最耗时的一步，放到 __init__ 里，避免每张图重复加载。
        # MediaPipe solution 对象非线程安全，用锁把单次分析串行化，供跨请求共享实例时使用。
        self._lock = threading.Lock()
        self._face_mesh = mp.solutions.face_mesh.FaceMesh(
            static_image_mode=True,
            max_num_faces=5,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self._face_detection = mp.solutions.face_detection.FaceDetection(
            model_selection=1,
            min_detection_confidence=0.5,
        )
        self._pose = mp.solutions.pose.Pose(
            static_image_mode=True,
            model_complexity=1,
            min_detection_confidence=0.3,
        )
        # 多人兜底：PoseLandmarker 检测“身体”，补人脸漏检的背影/侧脸/边缘人。
        # 用 model_asset_buffer（自读字节）而非路径：MediaPipe 在 Windows 下会错误拼接绝对路径。
        # 模型缺失时优雅降级（置 None），不影响其他检测。
        self.multi_person_min_separation = settings.multi_person_min_separation
        self._pose_landmarker = None
        try:
            with open(settings.pose_landmarker_path, "rb") as model_file:
                pose_model_bytes = model_file.read()
            self._pose_landmarker = mp_vision.PoseLandmarker.create_from_options(
                mp_vision.PoseLandmarkerOptions(
                    base_options=mp_tasks.BaseOptions(model_asset_buffer=pose_model_bytes),
                    running_mode=mp_vision.RunningMode.IMAGE,
                    num_poses=settings.multi_person_max_poses,
                    min_pose_detection_confidence=settings.multi_person_pose_confidence,
                )
            )
        except Exception as exc:
            logger.warning("PoseLandmarker 多人兜底模型加载失败，将跳过该兜底：%s", exc)

    def close(self):
        """释放 MediaPipe 模型资源（进程退出或不再使用时调用）。"""
        for model in (self._face_mesh, self._face_detection, self._pose, self._pose_landmarker):
            if model is None:
                continue
            with contextlib.suppress(Exception):
                model.close()

    def _poses_are_separated(self, poses):
        """多个姿态是否水平分开足够远（真·多人）而非单人被误拆。

        用每个身体肩中点 x 的最大跨度衡量；跨度 ≥ 阈值才算多人。
        数据：单人误拆的两体间距 ≤ 0.08，真·多人 ≥ 0.19。
        """
        center_xs = []
        for pose in poses:
            left_shoulder = pose[POSE_LM_LEFT_SHOULDER]
            right_shoulder = pose[POSE_LM_RIGHT_SHOULDER]
            center_xs.append((left_shoulder.x + right_shoulder.x) / 2)
        if len(center_xs) < 2:
            return False
        return (max(center_xs) - min(center_xs)) >= self.multi_person_min_separation

    def start(self, image_path: str, show_mesh: bool = False, wait_key: bool = True):
        """处理单张图片并显示监考结果"""
        image = cv2.imread(image_path)
        if image is None:
            logger.warning("无法加载图片: %s", image_path)
            return

        self._reset_state()
        image = self._process_image(image, show_mesh)

        cv2.imshow('faces', image)
        if wait_key:
            print("按任意键关闭窗口，或按 q 退出")
            while True:
                key = cv2.waitKey(0) & 0xFF
                if key == ord('q') or key != 255:
                    break
        cv2.destroyAllWindows()

    def start_folder(self, folder_path: str, show_mesh: bool = False):
        """批量处理文件夹内的图片"""
        extensions = ('.jpg', '.jpeg', '.png', '.bmp', '.webp')
        files = sorted(
            f for f in os.listdir(folder_path)
            if f.lower().endswith(extensions)
        )

        if not files:
            logger.warning("文件夹内未找到图片: %s", folder_path)
            return

        for file_name in files:
            image_path = os.path.join(folder_path, file_name)
            print(f"\n===== 处理: {image_path} =====")
            self.start(image_path, show_mesh=show_mesh, wait_key=True)

    def get_image_face_angle(self, image_file: str):
        """分析单张图片并打印监考结果（不弹窗）"""
        image = cv2.imread(image_file)
        if image is None:
            logger.warning("无法加载图片: %s", image_file)
            return

        with self._lock:
            self._reset_state()
            self._process_image(image, show_mesh=False)
            logger.debug("检测结果: %s", self.texts)
            return self.texts

    def analyze(self, pil_img: Image.Image, face_angles: "FaceAngleThresholds | None" = None) -> ProctorResult:
        """接收 PIL 图片，分析后返回结构化检测结果（对外主入口）。

        face_angles 为 None 时用默认阈值；传入时只对本次请求生效（不污染共享实例）。
        """
        # PIL(RGB) 转 OpenCV 使用的 BGR 数组
        image = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

        # 模型实例是共享的且非线程安全，这里用锁把单次分析串行化（阈值覆盖也在锁内，互不干扰）。
        with self._lock:
            self._apply_face_angles(face_angles)
            self._reset_state()
            self._process_image(image, show_mesh=False)
            logger.debug("检测结果: %s", self.result)
            return self.result

    def _apply_face_angles(self, face_angles: "FaceAngleThresholds | None") -> None:
        """把本次请求要用的面部角度阈值写入实例属性。

        每次调用都重新赋值（None 则回默认值），避免上一次请求的自定义值残留。
        """
        thresholds = face_angles or FaceAngleThresholds()
        self.max_left_angle = thresholds.max_left_angle
        self.max_right_angle = thresholds.max_right_angle
        self.max_up_angle = thresholds.max_up_angle
        self.max_down_angle = thresholds.max_down_angle

    def get_image_face_angle_by_img(self, pil_img: Image.Image):
        """
        接收PIL图片流，分析人脸，返回识别文本结果（向后兼容旧调用方）。
        新代码请优先使用 analyze()，它返回结构化 ProctorResult。
        """
        self.analyze(pil_img)
        return self.texts

    # 原有读取文件方法不动
    # def get_image_face_angle(self, image_path):
    #     image = Image.open(image_path)
    #     return self.get_image_face_angle_by_img(image)

    def _reset_state(self):
        """每张图片处理前重置状态"""
        self.directions.clear()
        self.texts.clear()
        self.warning_count = 0
        self.result = ProctorResult()
        # 设为最小时间，使周期判断逻辑在单帧图片上立即生效
        self.last_time = datetime.datetime.min

    def _set_result(self, action_type, label, warning, person_count=1):
        """同步设置结构化结果（与 texts 并行维护，供 API 层使用）。"""
        self.result = ProctorResult(
            action_type=action_type,
            action_label=label,
            warning=warning,
            warning_count=self.warning_count,
            person_count=person_count,
        )

    def _process_image(self, image, show_mesh: bool):
        canvas = image.copy()

        # 转换图片格式
        image_rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)

        # 复用 __init__ 里创建好的 FaceMesh 模型（不再每张图重建/close）
        mesh_result = self._face_mesh.process(image_rgb)

        # 检测到场人数
        person_count = 0
        if mesh_result.multi_face_landmarks:
            person_count = len(mesh_result.multi_face_landmarks)

            if person_count == 1:
                # 只有一个考生的情况下获取面部方向
                self._get_face_angle(mesh_result.multi_face_landmarks[0], canvas)

            # 绘制面部标记
            if show_mesh:
                mesh_solution = mp.solutions.face_mesh
                drawing_utils = mp.solutions.drawing_utils
                drawing_styles = mp.solutions.drawing_styles
                for face_landmarks in mesh_result.multi_face_landmarks:
                    drawing_utils.draw_landmarks(image=canvas,
                                                 landmark_list=face_landmarks,
                                                 connections=mesh_solution.FACEMESH_TESSELATION,
                                                 landmark_drawing_spec=None,
                                                 connection_drawing_spec=drawing_styles.get_default_face_mesh_tesselation_style())

                    drawing_utils.draw_landmarks(image=canvas,
                                                 landmark_list=face_landmarks,
                                                 connections=mesh_solution.FACEMESH_CONTOURS,
                                                 landmark_drawing_spec=None,
                                                 connection_drawing_spec=drawing_styles.get_default_face_mesh_contours_style())

                    drawing_utils.draw_landmarks(image=canvas,
                                                 landmark_list=face_landmarks,
                                                 connections=mesh_solution.FACEMESH_IRISES,
                                                 landmark_drawing_spec=None,
                                                 connection_drawing_spec=drawing_styles.get_default_face_mesh_iris_connections_style())

        # FaceMesh 对半入镜/侧脸的第二个人不够敏感，使用 FaceDetection 做多人兜底。
        if person_count <= 1:
            # 复用共享的 FaceDetection 模型做多人兜底
            detection_result = self._face_detection.process(image_rgb)
            if detection_result.detections and len(detection_result.detections) > 1:
                person_count = len(detection_result.detections)

        # 人脸都数不出第二个人时（背影/侧脸/边缘），用 PoseLandmarker 数“身体”做最后兜底。
        if person_count <= 1 and self._pose_landmarker is not None:
            with contextlib.suppress(Exception):
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image_rgb)
                multi_pose_result = self._pose_landmarker.detect(mp_image)
                # 护栏：两个身体必须水平分开够远，排除单人转头/侧身被误拆成两体。
                if (
                    multi_pose_result.pose_landmarks
                    and len(multi_pose_result.pose_landmarks) > 1
                    and self._poses_are_separated(multi_pose_result.pose_landmarks)
                ):
                    person_count = len(multi_pose_result.pose_landmarks)

        # ===== 多人检测优先（person_count > 1 时直接报多人，跳过 Pose）=====
        if person_count > 1:
            self.warning_count += 1
            self.texts = [
                ("警告，多人出现在考场", (255, 0, 0)),
                (str(self.warning_count), (255, 0, 0)),
            ]
            self._set_result(ActionType.MULTI_PERSON, "多人出现在考场", True, person_count=person_count)
        else:
            # ===== Pose 动作检测（仅在非多人时跑）=====
            pose_action_detected = False
            pose_person_detected = False
            # 复用共享的 Pose 模型（仅在非多人时跑）
            pose_result = self._pose.process(image_rgb)
            if pose_result.pose_landmarks:
                pose_person_detected = True
                pose_action_detected = self._check_pose_actions(pose_result.pose_landmarks.landmark)

            if pose_action_detected:
                pass  # texts 与 result 已被 _check_pose_actions 设置
            elif person_count == 0 and pose_person_detected:
                # 脸消失但 Pose 检测到人体 → 视线偏移
                self.warning_count += 1
                self.texts = [
                    ("警告，考生视线偏移", (255, 0, 0)),
                    (str(self.warning_count), (255, 0, 0)),
                ]
                self._set_result(ActionType.GAZE_AWAY, "考生视线偏移", True, person_count=1)
            elif person_count == 0 and not pose_person_detected:
                # 脸消失且 Pose 无人 → 离开座位
                self.warning_count += 1
                self.texts = [
                    ("警告，考生离开座位", (255, 0, 0)),
                    (str(self.warning_count), (255, 0, 0)),
                ]
                self._set_result(ActionType.LEAVE_SEAT, "考生离开座位", True, person_count=0)
            else:
                # person_count == 1，走现有 solvePnP 转头逻辑（结果由 _check_direction 设置）
                pass

        # 绘制当前文字
        # for i, (text, color) in enumerate(self.texts):
             #canvas = write_center_text(canvas, text, color, 50 + i * 60)

        return canvas

    def _get_face_angle(self, face_landmarks, image):
        # 获取图片尺寸
        height, width, _ = image.shape

        # 获取标识坐标
        face_2d = []
        face_3d = []
        for i, point in enumerate(face_landmarks.landmark):
            # 只获取 solvePnP 需要的 6 个关键点坐标
            if i in FACE_PNP_LANDMARKS:
                x, y = int(point.x * width), int(point.y * height)

                face_2d.append((x, y))
                face_3d.append((x, y, point.z))

        face_2d = np.array(face_2d, dtype=np.float64)
        face_3d = np.array(face_3d, dtype=np.float64)

        camera_matrix = np.array([
            [width, 0, width / 2],
            [0, width, height / 2],
            [0, 0, 1]])

        dist_coeffs = np.zeros((4, 1), dtype=np.float64)

        _, rotation_vector, _ = cv2.solvePnP(face_3d, face_2d, camera_matrix, dist_coeffs)

        rotation_matrix, _ = cv2.Rodrigues(rotation_vector)

        angles, _, _, _, _, _ = cv2.RQDecomp3x3(rotation_matrix)

        x = angles[0] * 57.3
        y = angles[1] * 57.3

        if y < self.max_right_angle:
            direction = 1
        elif y > self.max_left_angle:
            direction = 3
        elif x < self.max_down_angle:
            direction = 2
        elif x > self.max_up_angle:
            direction = 4
        else:
            direction = 0

        logger.debug("Angle x=%s y=%s direction=%s", x, y, direction)

        self.directions.append(direction)

        self._check_direction()

    def _check_independence(self, count):
        if count == 1:
            return

        now = datetime.datetime.now()
        if now < self.last_time + datetime.timedelta(seconds=1):
            return

        self.last_time = now

        if count == 0:
            self.warning_count += 1
            self.texts = [
                ("警告，考生离开座位", (255, 0, 0)),
                (str(self.warning_count), (255, 0, 0)),
            ]
        else:
            self.warning_count += 1
            self.texts = [
                ("警告，多人出现在考场", (255, 0, 0)),
                (str(self.warning_count), (255, 0, 0)),
            ]

        self.directions.clear()

    def _check_direction(self):
        now = datetime.datetime.now()
        if now < self.last_time + datetime.timedelta(seconds=1):
            return

        self.last_time = now

        if not self.directions:
            return

        direction = max(set(self.directions), key=self.directions.count)

        self.directions.clear()

        if direction == 0:
            self.warning_count = 0
            self.texts = [("正常考试中 ...", (0, 255, 0))]
            self._set_result(ActionType.NORMAL, "正常考试中", False, person_count=1)
        else:
            self.warning_count += 1
            self.texts = [
                ("警告，考生转头", (255, 0, 0)),
                (str(self.warning_count), (255, 0, 0)),
            ]
            self._set_result(ActionType.TURN_HEAD, "视线偏移(考生转头)", True, person_count=1)

    # ===== Pose 动作检测（2026-07-01 新增）=====

    def _is_visible(self, point):
        """判断关键点是否可见（visibility > 阈值才算可信）"""
        return point.visibility > self.visibility_threshold

    def _distance(self, a, b):
        """计算两个关键点之间的归一化欧氏距离"""
        return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5

    def _angle3(self, a, b, c):
        """计算三点夹角（b 是顶点），返回角度 0~180"""
        import math
        ba_x, ba_y = a.x - b.x, a.y - b.y
        bc_x, bc_y = c.x - b.x, c.y - b.y
        dot = ba_x * bc_x + ba_y * bc_y
        norm_ba = (ba_x ** 2 + ba_y ** 2) ** 0.5
        norm_bc = (bc_x ** 2 + bc_y ** 2) ** 0.5
        if norm_ba < 1e-6 or norm_bc < 1e-6:
            return 0.0
        cos_val = max(-1.0, min(1.0, dot / (norm_ba * norm_bc)))
        return math.degrees(math.acos(cos_val))

    def _is_horizontal_stretch_arm(self, shoulder, elbow, wrist, ear, other_shoulder):
        """Check horizontal or low arm extension missed by the above-shoulder stretch rule."""
        # 门槛用肩+肘+腕三点可见度：低可见度的幻觉手腕会在正常/离座姿势误触发，必须过滤。
        point_visibility = min(
            shoulder.visibility,
            elbow.visibility,
            wrist.visibility,
        )
        if point_visibility < self.horizontal_stretch_visibility:
            return False

        shoulder_dist = self._distance(shoulder, other_shoulder)
        if shoulder_dist < 1e-6:
            return False

        arm_angle = self._angle3(shoulder, elbow, wrist)
        arm_length = self._distance(shoulder, wrist) / shoulder_dist
        wrist_ear_dist = self._distance(wrist, ear) / shoulder_dist
        wrist_shoulder_y = wrist.y - shoulder.y

        return (
            arm_angle >= self.horizontal_stretch_arm_angle
            and arm_length >= self.horizontal_stretch_arm_length
            and wrist_ear_dist >= self.horizontal_stretch_wrist_ear_dist
            and 0 <= wrist_shoulder_y <= 1.0
        )

    def _is_elbow_stretch_arm(self, shoulder, elbow, other_shoulder):
        """仅用肩+肘判定伸展：兼底伸直手臂（手腕 visibility 太低、两条手腕规则都漏掉）的情况。

        判据：肘齐肩或更高（elbow_dy ≤ 0.5）且肘确实伸出（reach ≥ 0.7）。
        数据依据见 __init__ 里的阈值注释。
        """
        if min(shoulder.visibility, elbow.visibility) < self.elbow_stretch_visibility:
            return False

        shoulder_dist = self._distance(shoulder, other_shoulder)
        if shoulder_dist < 1e-6:
            return False

        elbow_dy = (elbow.y - shoulder.y) / shoulder_dist
        elbow_reach = self._distance(shoulder, elbow) / shoulder_dist

        return elbow_dy <= self.elbow_stretch_max_dy and elbow_reach >= self.elbow_stretch_min_reach

    def _check_pose_actions(self, landmarks):
        """
        检测 4 个 Pose 动作（转头由现有 solvePnP 处理，不在此方法内）。
        检测优先级：打电话 → 伸展胳膊 → 转身90度。
        命中任一动作则设置 texts 并返回 True；都没命中返回 False。

        6 大类对应关系：
        - 打电话 → "打电话"大类
        - 伸展胳膊 → "伸胳膊"大类
        - 转身90度 → "离开座位"大类（子类：转身）
        - 转头 → "离开座位"大类（子类：转头，由现有 solvePnP 处理）
        - 站立/人消失 → "离开座位"大类（由兜底逻辑处理）
        - 脸消失但人在 → "视线偏移"大类（由兜底逻辑处理）
        - 多人 → "多人"大类（由现有 _check_independence 处理）

        关键点编号（MediaPipe Pose 33 点）：
            7=左耳 8=右耳  11=左肩 12=右肩  13=左肘 14=右肘
            15=左腕 16=右腕  23=左髋 24=右髋
        """
        # 提取关键点
        le = landmarks[POSE_LM_LEFT_EAR]        # 左耳
        re = landmarks[POSE_LM_RIGHT_EAR]       # 右耳
        ls = landmarks[POSE_LM_LEFT_SHOULDER]   # 左肩
        rs = landmarks[POSE_LM_RIGHT_SHOULDER]  # 右肩
        le_l = landmarks[POSE_LM_LEFT_ELBOW]    # 左肘
        re_l = landmarks[POSE_LM_RIGHT_ELBOW]   # 右肘
        lw = landmarks[POSE_LM_LEFT_WRIST]      # 左腕
        rw = landmarks[POSE_LM_RIGHT_WRIST]     # 右腕

        # ===== 1. 打电话（腕耳距<0.55 + 如果肘可见则臂角<30°）=====
        # 左手打电话
        if self._is_visible(lw) and self._is_visible(le):
            dist = self._distance(lw, le)
            if dist < self.phone_wrist_ear_dist:
                # 肘可见时加臂角条件（排除伸胳膊），肘不可见时只信腕耳距
                phone_confirmed = True
                if self._is_visible(le_l) and self._is_visible(ls):
                    arm_angle = self._angle3(ls, le_l, lw)
                    if arm_angle >= self.phone_arm_angle:
                        phone_confirmed = False  # 臂角大，是伸胳膊不是打电话
                if phone_confirmed:
                    self.warning_count += 1
                    self.texts = [
                        ("警告，考生疑似打电话", (255, 0, 0)),
                        (str(self.warning_count), (255, 0, 0)),
                    ]
                    self._set_result(ActionType.PHONE_CALL, "考生疑似打电话", True, person_count=1)
                    return True

        # 右手打电话
        if self._is_visible(rw) and self._is_visible(re):
            dist = self._distance(rw, re)
            if dist < self.phone_wrist_ear_dist:
                phone_confirmed = True
                if self._is_visible(re_l) and self._is_visible(rs):
                    arm_angle = self._angle3(rs, re_l, rw)
                    if arm_angle >= self.phone_arm_angle:
                        phone_confirmed = False
                if phone_confirmed:
                    self.warning_count += 1
                    self.texts = [
                        ("警告，考生疑似打电话", (255, 0, 0)),
                        (str(self.warning_count), (255, 0, 0)),
                    ]
                    self._set_result(ActionType.PHONE_CALL, "考生疑似打电话", True, person_count=1)
                    return True

        # ===== 2. 伸展胳膊（腕高于肩 + 臂角>120°）=====
        # 必须腕高于肩：180张数据里伸展时腕都在肩上方
        # 左臂伸展
        if self._is_visible(ls) and self._is_visible(le_l) and self._is_visible(lw):
            if lw.y < ls.y:  # 腕高于肩（y 越小越高）
                angle = self._angle3(ls, le_l, lw)
                if angle > 120:
                    self.warning_count += 1
                    self.texts = [
                        ("警告，考生伸展胳膊", (255, 0, 0)),
                        (str(self.warning_count), (255, 0, 0)),
                    ]
                    self._set_result(ActionType.STRETCH_ARM, "考生伸展胳膊", True, person_count=1)
                    return True

        # 右臂伸展
        if self._is_visible(rs) and self._is_visible(re_l) and self._is_visible(rw):
            if rw.y < rs.y:
                angle = self._angle3(rs, re_l, rw)
                if angle > 120:
                    self.warning_count += 1
                    self.texts = [
                        ("警告，考生伸展胳膊", (255, 0, 0)),
                        (str(self.warning_count), (255, 0, 0)),
                    ]
                    self._set_result(ActionType.STRETCH_ARM, "考生伸展胳膊", True, person_count=1)
                    return True

        # Horizontal or low arm stretch: wrist may be below shoulder, but the arm must
        # be straight, long, and far from the ear to avoid phone-call false positives.
        if self._is_visible(ls) and self._is_visible(rs):
            if (
                self._is_horizontal_stretch_arm(ls, le_l, lw, le, rs)
                or self._is_horizontal_stretch_arm(rs, re_l, rw, re, ls)
            ):
                self.warning_count += 1
                self.texts = [
                    ("警告，考生伸展胳膊", (255, 0, 0)),
                    (str(self.warning_count), (255, 0, 0)),
                ]
                self._set_result(ActionType.STRETCH_ARM, "考生伸展胳膊", True, person_count=1)
                return True

        # 肘部兼底：手腕 visibility 太低、上面两条手腕规则都漏掉时，改用“肘齐肩/高于肩”判定伸展。
        if (
            self._is_elbow_stretch_arm(ls, le_l, rs)
            or self._is_elbow_stretch_arm(rs, re_l, ls)
        ):
            self.warning_count += 1
            self.texts = [
                ("警告，考生伸展胳膊", (255, 0, 0)),
                (str(self.warning_count), (255, 0, 0)),
            ]
            self._set_result(ActionType.STRETCH_ARM, "考生伸展胳膊", True, person_count=1)
            return True

        # ===== 3. 转身 90 度（2条件：双肩距<0.25 + 排除双臂伸直）=====
        # 排除条件：如果双臂角都 > 140° 则是伸胳膊不是转身
        if self._is_visible(ls) and self._is_visible(rs):
            shoulder_dist = self._distance(ls, rs)
            if shoulder_dist < self.turn_body_shoulder_dist:
                # 检查是否双臂都伸直（排除伸胳膊误判）
                left_arm_straight = False
                right_arm_straight = False
                if self._is_visible(le_l) and self._is_visible(lw):
                    if self._angle3(ls, le_l, lw) > self.stretch_arm_angle:
                        left_arm_straight = True
                if self._is_visible(re_l) and self._is_visible(rw):
                    if self._angle3(rs, re_l, rw) > self.stretch_arm_angle:
                        right_arm_straight = True
                # 不是双臂都伸直，才算转身
                if not (left_arm_straight and right_arm_straight):
                    self.warning_count += 1
                    self.texts = [
                        ("警告，考生转身", (255, 0, 0)),
                        (str(self.warning_count), (255, 0, 0)),
                    ]
                    self._set_result(ActionType.TURN_BODY, "离开座位(考生转身)", True, person_count=1)
                    return True

        # 都没命中，返回 False 让兼底逻辑处理（视线偏移/离开座位/转头/正常）
        return False


class ProctorPool:
    """识别器实例池：预创建 N 个 ImageProctor，多请求借用不同实例以真正并行。

    为什么能并行：MediaPipe 推理在 C++ 层执行并释放 GIL，多个线程各拿一个
    独立模型实例时能真并行（而单实例+全局锁只能串行）。

    用 queue.Queue 做借还：天然线程安全；池空时 acquire() 阻塞等待，形成自然背压。
    """

    def __init__(self, size: int | None = None):
        pool_size = size if size is not None else settings.proctor_pool_size
        pool_size = max(1, pool_size)
        self._pool: "queue.Queue[ImageProctor]" = queue.Queue()
        self._all_proctors: list[ImageProctor] = []
        for _ in range(pool_size):
            proctor = ImageProctor()
            self._all_proctors.append(proctor)
            self._pool.put(proctor)
        logger.info("ProctorPool 初始化完成，池大小=%d", pool_size)

    @property
    def size(self) -> int:
        return len(self._all_proctors)

    def analyze(self, pil_img: Image.Image, face_angles: "FaceAngleThresholds | None" = None) -> ProctorResult:
        """从池借一个实例处理，用完归还（即使异常也归还，避免池泄漏）。"""
        proctor = self._pool.get()  # 池空则阻塞等待空闲实例
        try:
            return proctor.analyze(pil_img, face_angles=face_angles)
        finally:
            self._pool.put(proctor)

    def close(self):
        """释放池内所有实例的模型资源。"""
        for proctor in self._all_proctors:
            with contextlib.suppress(Exception):
                proctor.close()
