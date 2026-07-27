import contextlib
import datetime
import logging
import os
import threading
from dataclasses import dataclass

import cv2
import mediapipe as mp
import numpy as np
from PIL import Image

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
        self.m_iMaxLeftAngle = DEFAULT_MAX_LEFT_ANGLE
        self.m_iMaxRightAngle = DEFAULT_MAX_RIGHT_ANGLE
        self.m_iMaxUpAngle = DEFAULT_MAX_UP_ANGLE
        self.m_iMaxDownAngle = DEFAULT_MAX_DOWN_ANGLE

        # 周期内看到的方向
        self.m_listDirection = []
        self.m_iWarningCount = 0
        self.m_listText = []
        self.m_stResult = ProctorResult()
        self.m_stLastTime = datetime.datetime.min

        # ===== Pose 动作检测阈值 v2（基于 180 张真实样本标定，2026-07-03）=====
        # 6 大类：正常考试 / 视线偏移 / 离开座位 / 多人 / 打电话 / 伸胳膊
        self.m_fPhoneWristEarDist = 0.55      # 打电话：腕耳归一化距离 < 0.55
        self.m_fPhoneArmAngle = 30            # 打电话：对应侧臂角 < 30°（手臂弯曲贴头）
        self.m_fStretchArmAngle = 140         # 伸展：肩-肘-腕夹角 > 140°
        self.m_fHorizontalStretchArmAngle = 155   # 水平/斜下伸展：臂角 ≥ 155°（胳膊伸直）
        # 门槛用肩+肘+腕三点可见度，过滤掉低可见度的幻觉手腕（否则正常/离座姿势会误报）。
        self.m_fHorizontalStretchVisibility = 0.4
        self.m_fHorizontalStretchArmLength = 1.05   # 腕-肩距/肩宽 ≥ 1.05（正常弯臂 <1.0）
        self.m_fHorizontalStretchWristEarDist = 1.6  # 腕-耳距/肩宽 ≥ 1.6（手远离头部，排除打电话）
        self.m_fTurnBodyShoulderDist = 0.25   # 转身90度：双肩归一化距离 < 0.25
        self.m_fVisibilityThreshold = 0.5     # 关键点 visibility 过滤阈值

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

    def close(self):
        """释放 MediaPipe 模型资源（进程退出或不再使用时调用）。"""
        for model in (self._face_mesh, self._face_detection, self._pose):
            with contextlib.suppress(Exception):
                model.close()

    def Start(self, in_strImagePath: str, in_isShowMesh: bool = False, in_bWaitKey: bool = True):
        """处理单张图片并显示监考结果"""
        stImage = cv2.imread(in_strImagePath)
        if stImage is None:
            logger.warning("无法加载图片: %s", in_strImagePath)
            return

        self.__ResetState()
        stImage = self.__ProcessImage(stImage, in_isShowMesh)

        cv2.imshow('faces', stImage)
        if in_bWaitKey:
            print("按任意键关闭窗口，或按 q 退出")
            while True:
                key = cv2.waitKey(0) & 0xFF
                if key == ord('q') or key != 255:
                    break
        cv2.destroyAllWindows()

    def StartFolder(self, in_strFolderPath: str, in_isShowMesh: bool = False):
        """批量处理文件夹内的图片"""
        listExtensions = ('.jpg', '.jpeg', '.png', '.bmp', '.webp')
        listFiles = sorted(
            f for f in os.listdir(in_strFolderPath)
            if f.lower().endswith(listExtensions)
        )

        if not listFiles:
            logger.warning("文件夹内未找到图片: %s", in_strFolderPath)
            return

        for strFileName in listFiles:
            strImagePath = os.path.join(in_strFolderPath, strFileName)
            print(f"\n===== 处理: {strImagePath} =====")
            self.Start(strImagePath, in_isShowMesh=in_isShowMesh, in_bWaitKey=True)

    def GetImageFaceAngle(self, in_strImageFile: str):
        """分析单张图片并打印监考结果（不弹窗）"""
        stImage = cv2.imread(in_strImageFile)
        if stImage is None:
            logger.warning("无法加载图片: %s", in_strImageFile)
            return

        with self._lock:
            self.__ResetState()
            self.__ProcessImage(stImage, in_isShowMesh=False)
            logger.debug("检测结果: %s", self.m_listText)
            return self.m_listText

    def analyze(self, pil_img: Image.Image, face_angles: "FaceAngleThresholds | None" = None) -> ProctorResult:
        """接收 PIL 图片，分析后返回结构化检测结果（对外主入口）。

        face_angles 为 None 时用默认阈值；传入时只对本次请求生效（不污染共享实例）。
        """
        # PIL(RGB) 转 OpenCV 使用的 BGR 数组
        stImage = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

        # 模型实例是共享的且非线程安全，这里用锁把单次分析串行化（阈值覆盖也在锁内，互不干扰）。
        with self._lock:
            self.__ApplyFaceAngles(face_angles)
            self.__ResetState()
            self.__ProcessImage(stImage, in_isShowMesh=False)
            logger.debug("检测结果: %s", self.m_stResult)
            return self.m_stResult

    def __ApplyFaceAngles(self, face_angles: "FaceAngleThresholds | None") -> None:
        """把本次请求要用的面部角度阈值写入实例属性。

        每次调用都重新赋值（None 则回默认值），避免上一次请求的自定义值残留。
        """
        stAngles = face_angles or FaceAngleThresholds()
        self.m_iMaxLeftAngle = stAngles.max_left_angle
        self.m_iMaxRightAngle = stAngles.max_right_angle
        self.m_iMaxUpAngle = stAngles.max_up_angle
        self.m_iMaxDownAngle = stAngles.max_down_angle

    def GetImageFaceAngleByImg(self, pil_img: Image.Image):
        """
        接收PIL图片流，分析人脸，返回识别文本结果（向后兼容旧调用方）。
        新代码请优先使用 analyze()，它返回结构化 ProctorResult。
        """
        self.analyze(pil_img)
        return self.m_listText

    # 原有读取文件方法不动
    # def GetImageFaceAngle(self, strImagePath):
    #     stImage = Image.open(strImagePath)
    #     return self.GetImageFaceAngleByImg(stImage)

    def __ResetState(self):
        """每张图片处理前重置状态"""
        self.m_listDirection.clear()
        self.m_listText.clear()
        self.m_iWarningCount = 0
        self.m_stResult = ProctorResult()
        # 设为最小时间，使周期判断逻辑在单帧图片上立即生效
        self.m_stLastTime = datetime.datetime.min

    def __SetResult(self, in_actionType, in_strLabel, in_bWarning, in_iPersonCount=1):
        """同步设置结构化结果（与 m_listText 并行维护，供 API 层使用）。"""
        self.m_stResult = ProctorResult(
            action_type=in_actionType,
            action_label=in_strLabel,
            warning=in_bWarning,
            warning_count=self.m_iWarningCount,
            person_count=in_iPersonCount,
        )

    def __ProcessImage(self, in_stImage, in_isShowMesh: bool):
        stImage = in_stImage.copy()

        # 转换图片格式
        stImageRGB = cv2.cvtColor(stImage, cv2.COLOR_BGR2RGB)

        # 复用 __init__ 里创建好的 FaceMesh 模型（不再每张图重建/close）
        stResult = self._face_mesh.process(stImageRGB)

        # 检测到场人数
        iCount = 0
        if stResult.multi_face_landmarks:
            iCount = len(stResult.multi_face_landmarks)

            if iCount == 1:
                # 只有一个考生的情况下获取面部方向
                self.__GetFaceAngle(stResult.multi_face_landmarks[0], stImage)

            # 绘制面部标记
            if in_isShowMesh:
                stSolutionMesh = mp.solutions.face_mesh
                stSlutionDraw = mp.solutions.drawing_utils
                stRrawStyle = mp.solutions.drawing_styles
                for stFaceLandmarks in stResult.multi_face_landmarks:
                    stSlutionDraw.draw_landmarks(image=stImage,
                                                 landmark_list=stFaceLandmarks,
                                                 connections=stSolutionMesh.FACEMESH_TESSELATION,
                                                 landmark_drawing_spec=None,
                                                 connection_drawing_spec=stRrawStyle.get_default_face_mesh_tesselation_style())

                    stSlutionDraw.draw_landmarks(image=stImage,
                                                 landmark_list=stFaceLandmarks,
                                                 connections=stSolutionMesh.FACEMESH_CONTOURS,
                                                 landmark_drawing_spec=None,
                                                 connection_drawing_spec=stRrawStyle.get_default_face_mesh_contours_style())

                    stSlutionDraw.draw_landmarks(image=stImage,
                                                 landmark_list=stFaceLandmarks,
                                                 connections=stSolutionMesh.FACEMESH_IRISES,
                                                 landmark_drawing_spec=None,
                                                 connection_drawing_spec=stRrawStyle.get_default_face_mesh_iris_connections_style())

        # FaceMesh 对半入镜/侧脸的第二个人不够敏感，使用 FaceDetection 做多人兜底。
        if iCount <= 1:
            # 复用共享的 FaceDetection 模型做多人兜底
            stDetectionResult = self._face_detection.process(stImageRGB)
            if stDetectionResult.detections and len(stDetectionResult.detections) > 1:
                iCount = len(stDetectionResult.detections)

        # ===== 多人检测优先（iCount > 1 时直接报多人，跳过 Pose）=====
        if iCount > 1:
            self.m_iWarningCount += 1
            self.m_listText = [
                ("警告，多人出现在考场", (255, 0, 0)),
                (str(self.m_iWarningCount), (255, 0, 0)),
            ]
            self.__SetResult(ActionType.MULTI_PERSON, "多人出现在考场", True, in_iPersonCount=iCount)
        else:
            # ===== Pose 动作检测（仅在非多人时跑）=====
            bPoseActionDetected = False
            bPosePersonDetected = False
            # 复用共享的 Pose 模型（仅在非多人时跑）
            stPoseResult = self._pose.process(stImageRGB)
            if stPoseResult.pose_landmarks:
                bPosePersonDetected = True
                bPoseActionDetected = self.__CheckPoseActions(stPoseResult.pose_landmarks.landmark)

            if bPoseActionDetected:
                pass  # m_listText 与 m_stResult 已被 __CheckPoseActions 设置
            elif iCount == 0 and bPosePersonDetected:
                # 脸消失但 Pose 检测到人体 → 视线偏移
                self.m_iWarningCount += 1
                self.m_listText = [
                    ("警告，考生视线偏移", (255, 0, 0)),
                    (str(self.m_iWarningCount), (255, 0, 0)),
                ]
                self.__SetResult(ActionType.GAZE_AWAY, "考生视线偏移", True, in_iPersonCount=1)
            elif iCount == 0 and not bPosePersonDetected:
                # 脸消失且 Pose 无人 → 离开座位
                self.m_iWarningCount += 1
                self.m_listText = [
                    ("警告，考生离开座位", (255, 0, 0)),
                    (str(self.m_iWarningCount), (255, 0, 0)),
                ]
                self.__SetResult(ActionType.LEAVE_SEAT, "考生离开座位", True, in_iPersonCount=0)
            else:
                # iCount == 1，走现有 solvePnP 转头逻辑（结果由 __CheckDirection 设置）
                pass

        # 绘制当前文字
        # for i, (strText, stColor) in enumerate(self.m_listText):
             #stImage = WriteCenterText(stImage, strText, stColor, 50 + i * 60)

        return stImage

    def __GetFaceAngle(self, in_stFaceLandmarks, in_stImage):
        # 获取图片尺寸
        iHeight, iWidth, _ = in_stImage.shape

        # 获取标识坐标
        listFace2d = []
        listFace3d = []
        for i, stPoint in enumerate(in_stFaceLandmarks.landmark):
            # 只获取 solvePnP 需要的 6 个关键点坐标
            if i in FACE_PNP_LANDMARKS:
                x, y = int(stPoint.x * iWidth), int(stPoint.y * iHeight)

                listFace2d.append((x, y))
                listFace3d.append((x, y, stPoint.z))

        listFace2d = np.array(listFace2d, dtype=np.float64)
        listFace3d = np.array(listFace3d, dtype=np.float64)

        listCameraMatrix = np.array([
            [iWidth, 0, iWidth / 2],
            [0, iWidth, iHeight / 2],
            [0, 0, 1]])

        listDistCoeffs = np.zeros((4, 1), dtype=np.float64)

        _, listRotationVector, _ = cv2.solvePnP(listFace3d, listFace2d, listCameraMatrix, listDistCoeffs)

        listRotationMatrix, _ = cv2.Rodrigues(listRotationVector)

        listAngles, _, _, _, _, _ = cv2.RQDecomp3x3(listRotationMatrix)

        x = listAngles[0] * 57.3
        y = listAngles[1] * 57.3

        if y < self.m_iMaxRightAngle:
            iDirection = 1
        elif y > self.m_iMaxLeftAngle:
            iDirection = 3
        elif x < self.m_iMaxDownAngle:
            iDirection = 2
        elif x > self.m_iMaxUpAngle:
            iDirection = 4
        else:
            iDirection = 0

        logger.debug("Angle x=%s y=%s direction=%s", x, y, iDirection)

        self.m_listDirection.append(iDirection)

        self.__CheckDirection()

    def __Checkindependence(self, in_iCount):
        if in_iCount == 1:
            return

        stNowTime = datetime.datetime.now()
        if stNowTime < self.m_stLastTime + datetime.timedelta(seconds=1):
            return

        self.m_stLastTime = stNowTime

        if in_iCount == 0:
            self.m_iWarningCount += 1
            self.m_listText = [
                ("警告，考生离开座位", (255, 0, 0)),
                (str(self.m_iWarningCount), (255, 0, 0)),
            ]
        else:
            self.m_iWarningCount += 1
            self.m_listText = [
                ("警告，多人出现在考场", (255, 0, 0)),
                (str(self.m_iWarningCount), (255, 0, 0)),
            ]

        self.m_listDirection.clear()

    def __CheckDirection(self):
        stNowTime = datetime.datetime.now()
        if stNowTime < self.m_stLastTime + datetime.timedelta(seconds=1):
            return

        self.m_stLastTime = stNowTime

        if not self.m_listDirection:
            return

        iDirection = max(set(self.m_listDirection), key=self.m_listDirection.count)

        self.m_listDirection.clear()

        if iDirection == 0:
            self.m_iWarningCount = 0
            self.m_listText = [("正常考试中 ...", (0, 255, 0))]
            self.__SetResult(ActionType.NORMAL, "正常考试中", False, in_iPersonCount=1)
        else:
            self.m_iWarningCount += 1
            self.m_listText = [
                ("警告，考生转头", (255, 0, 0)),
                (str(self.m_iWarningCount), (255, 0, 0)),
            ]
            self.__SetResult(ActionType.TURN_HEAD, "考生转头", True, in_iPersonCount=1)

    # ===== Pose 动作检测（2026-07-01 新增）=====

    def __IsVisible(self, in_stPoint):
        """判断关键点是否可见（visibility > 阈值才算可信）"""
        return in_stPoint.visibility > self.m_fVisibilityThreshold

    def __Distance(self, a, b):
        """计算两个关键点之间的归一化欧氏距离"""
        return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5

    def __Angle3(self, a, b, c):
        """计算三点夹角（b 是顶点），返回角度 0~180"""
        import math
        ba_x, ba_y = a.x - b.x, a.y - b.y
        bc_x, bc_y = c.x - b.x, c.y - b.y
        fDot = ba_x * bc_x + ba_y * bc_y
        fNormBA = (ba_x ** 2 + ba_y ** 2) ** 0.5
        fNormBC = (bc_x ** 2 + bc_y ** 2) ** 0.5
        if fNormBA < 1e-6 or fNormBC < 1e-6:
            return 0.0
        fCos = max(-1.0, min(1.0, fDot / (fNormBA * fNormBC)))
        return math.degrees(math.acos(fCos))

    def __IsHorizontalStretchArm(self, in_stShoulder, in_stElbow, in_stWrist, in_stEar, in_stOtherShoulder):
        """Check horizontal or low arm extension missed by the above-shoulder stretch rule."""
        # 门槛用肩+肘+腕三点可见度：低可见度的幻觉手腕会在正常/离座姿势误触发，必须过滤。
        fPointVisibility = min(
            in_stShoulder.visibility,
            in_stElbow.visibility,
            in_stWrist.visibility,
        )
        if fPointVisibility < self.m_fHorizontalStretchVisibility:
            return False

        fShoulderDist = self.__Distance(in_stShoulder, in_stOtherShoulder)
        if fShoulderDist < 1e-6:
            return False

        fArmAngle = self.__Angle3(in_stShoulder, in_stElbow, in_stWrist)
        fArmLength = self.__Distance(in_stShoulder, in_stWrist) / fShoulderDist
        fWristEarDist = self.__Distance(in_stWrist, in_stEar) / fShoulderDist
        fWristShoulderY = in_stWrist.y - in_stShoulder.y

        return (
            fArmAngle >= self.m_fHorizontalStretchArmAngle
            and fArmLength >= self.m_fHorizontalStretchArmLength
            and fWristEarDist >= self.m_fHorizontalStretchWristEarDist
            and 0 <= fWristShoulderY <= 1.0
        )

    def __CheckPoseActions(self, in_stLandmarks):
        """
        检测 4 个 Pose 动作（转头由现有 solvePnP 处理，不在此方法内）。
        检测优先级：打电话 → 伸展胳膊 → 转身90度。
        命中任一动作则设置 m_listText 并返回 True；都没命中返回 False。

        6 大类对应关系：
        - 打电话 → "打电话"大类
        - 伸展胳膊 → "伸胳膊"大类
        - 转身90度 → "离开座位"大类（子类：转身）
        - 转头 → "离开座位"大类（子类：转头，由现有 solvePnP 处理）
        - 站立/人消失 → "离开座位"大类（由兜底逻辑处理）
        - 脸消失但人在 → "视线偏移"大类（由兜底逻辑处理）
        - 多人 → "多人"大类（由现有 __Checkindependence 处理）

        关键点编号（MediaPipe Pose 33 点）：
            7=左耳 8=右耳  11=左肩 12=右肩  13=左肘 14=右肘
            15=左腕 16=右腕  23=左髋 24=右髋
        """
        # 提取关键点
        le = in_stLandmarks[POSE_LM_LEFT_EAR]        # 左耳
        re = in_stLandmarks[POSE_LM_RIGHT_EAR]       # 右耳
        ls = in_stLandmarks[POSE_LM_LEFT_SHOULDER]   # 左肩
        rs = in_stLandmarks[POSE_LM_RIGHT_SHOULDER]  # 右肩
        le_l = in_stLandmarks[POSE_LM_LEFT_ELBOW]    # 左肘
        re_l = in_stLandmarks[POSE_LM_RIGHT_ELBOW]   # 右肘
        lw = in_stLandmarks[POSE_LM_LEFT_WRIST]      # 左腕
        rw = in_stLandmarks[POSE_LM_RIGHT_WRIST]     # 右腕

        # ===== 1. 打电话（腕耳距<0.55 + 如果肘可见则臂角<30°）=====
        # 左手打电话
        if self.__IsVisible(lw) and self.__IsVisible(le):
            fDist = self.__Distance(lw, le)
            if fDist < self.m_fPhoneWristEarDist:
                # 肘可见时加臂角条件（排除伸胳膊），肘不可见时只信腕耳距
                bPhoneConfirmed = True
                if self.__IsVisible(le_l) and self.__IsVisible(ls):
                    fArmAngle = self.__Angle3(ls, le_l, lw)
                    if fArmAngle >= self.m_fPhoneArmAngle:
                        bPhoneConfirmed = False  # 臂角大，是伸胳膊不是打电话
                if bPhoneConfirmed:
                    self.m_iWarningCount += 1
                    self.m_listText = [
                        ("警告，考生疑似打电话", (255, 0, 0)),
                        (str(self.m_iWarningCount), (255, 0, 0)),
                    ]
                    self.__SetResult(ActionType.PHONE_CALL, "考生疑似打电话", True, in_iPersonCount=1)
                    return True

        # 右手打电话
        if self.__IsVisible(rw) and self.__IsVisible(re):
            fDist = self.__Distance(rw, re)
            if fDist < self.m_fPhoneWristEarDist:
                bPhoneConfirmed = True
                if self.__IsVisible(re_l) and self.__IsVisible(rs):
                    fArmAngle = self.__Angle3(rs, re_l, rw)
                    if fArmAngle >= self.m_fPhoneArmAngle:
                        bPhoneConfirmed = False
                if bPhoneConfirmed:
                    self.m_iWarningCount += 1
                    self.m_listText = [
                        ("警告，考生疑似打电话", (255, 0, 0)),
                        (str(self.m_iWarningCount), (255, 0, 0)),
                    ]
                    self.__SetResult(ActionType.PHONE_CALL, "考生疑似打电话", True, in_iPersonCount=1)
                    return True

        # ===== 2. 伸展胳膊（腕高于肩 + 臂角>120°）=====
        # 必须腕高于肩：180张数据里伸展时腕都在肩上方
        # 左臂伸展
        if self.__IsVisible(ls) and self.__IsVisible(le_l) and self.__IsVisible(lw):
            if lw.y < ls.y:  # 腕高于肩（y 越小越高）
                fAngle = self.__Angle3(ls, le_l, lw)
                if fAngle > 120:
                    self.m_iWarningCount += 1
                    self.m_listText = [
                        ("警告，考生伸展胳膊", (255, 0, 0)),
                        (str(self.m_iWarningCount), (255, 0, 0)),
                    ]
                    self.__SetResult(ActionType.STRETCH_ARM, "考生伸展胳膊", True, in_iPersonCount=1)
                    return True

        # 右臂伸展
        if self.__IsVisible(rs) and self.__IsVisible(re_l) and self.__IsVisible(rw):
            if rw.y < rs.y:
                fAngle = self.__Angle3(rs, re_l, rw)
                if fAngle > 120:
                    self.m_iWarningCount += 1
                    self.m_listText = [
                        ("警告，考生伸展胳膊", (255, 0, 0)),
                        (str(self.m_iWarningCount), (255, 0, 0)),
                    ]
                    self.__SetResult(ActionType.STRETCH_ARM, "考生伸展胳膊", True, in_iPersonCount=1)
                    return True

        # Horizontal or low arm stretch: wrist may be below shoulder, but the arm must
        # be straight, long, and far from the ear to avoid phone-call false positives.
        if self.__IsVisible(ls) and self.__IsVisible(rs):
            if (
                self.__IsHorizontalStretchArm(ls, le_l, lw, le, rs)
                or self.__IsHorizontalStretchArm(rs, re_l, rw, re, ls)
            ):
                self.m_iWarningCount += 1
                self.m_listText = [
                    ("警告，考生伸展胳膊", (255, 0, 0)),
                    (str(self.m_iWarningCount), (255, 0, 0)),
                ]
                self.__SetResult(ActionType.STRETCH_ARM, "考生伸展胳膊", True, in_iPersonCount=1)
                return True

        # ===== 3. 转身 90 度（2条件：双肩距<0.25 + 排除双臂伸直）=====
        # 排除条件：如果双臂角都 > 140° 则是伸胳膊不是转身
        if self.__IsVisible(ls) and self.__IsVisible(rs):
            fShoulderDist = self.__Distance(ls, rs)
            if fShoulderDist < self.m_fTurnBodyShoulderDist:
                # 检查是否双臂都伸直（排除伸胳膊误判）
                bLeftArmStraight = False
                bRightArmStraight = False
                if self.__IsVisible(le_l) and self.__IsVisible(lw):
                    if self.__Angle3(ls, le_l, lw) > self.m_fStretchArmAngle:
                        bLeftArmStraight = True
                if self.__IsVisible(re_l) and self.__IsVisible(rw):
                    if self.__Angle3(rs, re_l, rw) > self.m_fStretchArmAngle:
                        bRightArmStraight = True
                # 不是双臂都伸直，才算转身
                if not (bLeftArmStraight and bRightArmStraight):
                    self.m_iWarningCount += 1
                    self.m_listText = [
                        ("警告，考生转身", (255, 0, 0)),
                        (str(self.m_iWarningCount), (255, 0, 0)),
                    ]
                    self.__SetResult(ActionType.TURN_BODY, "考生转身", True, in_iPersonCount=1)
                    return True

        # 都没命中，返回 False 让兜底逻辑处理（视线偏移/离开座位/转头/正常）
        return False
