import cv2
import datetime
import os
import numpy as np
import mediapipe as mp
from PIL import Image

from .Toolkit import WriteCenterText


# 基于图片的监考类（逻辑与 FrontCamera 一致，不调用摄像头）
class ImageProctor:
    def __init__(self):
        # 定义角度范围
        self.m_iMaxLeftAngle = 6
        self.m_iMaxRightAngle = -6
        self.m_iMaxUpAngle = 6
        self.m_iMaxDownAngle = -1

        # 周期内看到的方向
        self.m_listDirection = []
        self.m_iWarningCount = 0
        self.m_listText = []
        self.m_stLastTime = datetime.datetime.min

        # ===== Pose 动作检测阈值 v2（基于 180 张真实样本标定，2026-07-03）=====
        # 6 大类：正常考试 / 视线偏移 / 离开座位 / 多人 / 打电话 / 伸胳膊
        self.m_fPhoneWristEarDist = 0.55      # 打电话：腕耳归一化距离 < 0.55
        self.m_fPhoneArmAngle = 30            # 打电话：对应侧臂角 < 30°（手臂弯曲贴头）
        self.m_fStretchArmAngle = 140         # 伸展：肩-肘-腕夹角 > 140°
        self.m_fHorizontalStretchArmAngle = 165
        self.m_fHorizontalStretchVisibility = 0.4
        self.m_fHorizontalStretchArmLength = 1.8
        self.m_fHorizontalStretchWristEarDist = 2.5
        self.m_fTurnBodyShoulderDist = 0.25   # 转身90度：双肩归一化距离 < 0.25
        self.m_fVisibilityThreshold = 0.5     # 关键点 visibility 过滤阈值

    def Start(self, in_strImagePath: str, in_isShowMesh: bool = False, in_bWaitKey: bool = True):
        """处理单张图片并显示监考结果"""
        stImage = cv2.imread(in_strImagePath)
        if stImage is None:
            print(f"无法加载图片: {in_strImagePath}")
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
            print(f"文件夹内未找到图片: {in_strFolderPath}")
            return

        for strFileName in listFiles:
            strImagePath = os.path.join(in_strFolderPath, strFileName)
            print(f"\n===== 处理: {strImagePath} =====")
            self.Start(strImagePath, in_isShowMesh=in_isShowMesh, in_bWaitKey=True)

    def GetImageFaceAngle(self, in_strImageFile: str):
        """分析单张图片并打印监考结果（不弹窗）"""
        stImage = cv2.imread(in_strImageFile)
        if stImage is None:
            print(f"无法加载图片: {in_strImageFile}")
            return

        self.__ResetState()
        self.__ProcessImage(stImage, in_isShowMesh=False)
        print(self.m_listText)
        return self.m_listText

    def GetImageFaceAngleByImg(self, pil_img: Image.Image):
        """
        接收PIL图片流，分析人脸，返回识别文本结果
        对应原方法 GetImageFaceAngle 逻辑
        """
        # PIL(RGB) 转 OpenCV 使用的 BGR 数组
        stImage = np.array(pil_img)
        stImage = cv2.cvtColor(stImage, cv2.COLOR_RGB2BGR)

        if stImage is None:
            print("图片流解析失败")
            return None

        self.__ResetState()
        self.__ProcessImage(stImage, in_isShowMesh=False)
        print(self.m_listText)
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
        # 设为最小时间，使周期判断逻辑在单帧图片上立即生效
        self.m_stLastTime = datetime.datetime.min

    def __ProcessImage(self, in_stImage, in_isShowMesh: bool):
        # 定义解决方案（静态图片模式）
        stSolutionMesh = mp.solutions.face_mesh
        stFaceMesh = stSolutionMesh.FaceMesh(static_image_mode=True,
                                             max_num_faces=5,
                                             refine_landmarks=True,
                                             min_detection_confidence=0.5,
                                             min_tracking_confidence=0.5)

        stSlutionDraw = mp.solutions.drawing_utils
        stRrawStyle = mp.solutions.drawing_styles

        stImage = in_stImage.copy()

        # 转换图片格式
        stImageRGB = cv2.cvtColor(stImage, cv2.COLOR_BGR2RGB)

        # 处理图片
        stResult = stFaceMesh.process(stImageRGB)
        stFaceMesh.close()

        # 检测到场人数
        iCount = 0
        if stResult.multi_face_landmarks:
            iCount = len(stResult.multi_face_landmarks)

            if iCount == 1:
                # 只有一个考生的情况下获取面部方向
                self.__GetFaceAngle(stResult.multi_face_landmarks[0], stImage)

            # 绘制面部标记
            if in_isShowMesh:
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
            stFaceDetectionSolution = mp.solutions.face_detection
            with stFaceDetectionSolution.FaceDetection(
                model_selection=1,
                min_detection_confidence=0.5,
            ) as stFaceDetection:
                stDetectionResult = stFaceDetection.process(stImageRGB)
                if stDetectionResult.detections and len(stDetectionResult.detections) > 1:
                    iCount = len(stDetectionResult.detections)

        # ===== 多人检测优先（iCount > 1 时直接报多人，跳过 Pose）=====
        if iCount > 1:
            self.m_iWarningCount += 1
            self.m_listText = [
                ("警告，多人出现在考场", (255, 0, 0)),
                (str(self.m_iWarningCount), (255, 0, 0)),
            ]
        else:
            # ===== Pose 动作检测（仅在非多人时跑）=====
            bPoseActionDetected = False
            bPosePersonDetected = False
            stPoseSolution = mp.solutions.pose
            with stPoseSolution.Pose(
                static_image_mode=True,
                model_complexity=1,
                min_detection_confidence=0.3,
            ) as stPose:
                stPoseResult = stPose.process(stImageRGB)
                if stPoseResult.pose_landmarks:
                    bPosePersonDetected = True
                    bPoseActionDetected = self.__CheckPoseActions(stPoseResult.pose_landmarks.landmark)

            if bPoseActionDetected:
                pass  # m_listText 已被 __CheckPoseActions 设置
            elif iCount == 0 and bPosePersonDetected:
                # 脸消失但 Pose 检测到人体 → 视线偏移
                self.m_iWarningCount += 1
                self.m_listText = [
                    ("警告，考生视线偏移", (255, 0, 0)),
                    (str(self.m_iWarningCount), (255, 0, 0)),
                ]
            elif iCount == 0 and not bPosePersonDetected:
                # 脸消失且 Pose 无人 → 离开座位
                self.m_iWarningCount += 1
                self.m_listText = [
                    ("警告，考生离开座位", (255, 0, 0)),
                    (str(self.m_iWarningCount), (255, 0, 0)),
                ]
            else:
                # iCount == 1，走现有 solvePnP 转头逻辑
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
            # 只获取 6 个关键点坐标
            if i == 33 or i == 263 or i == 1 or i == 61 or i == 291 or i == 199:
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

        print(f"Angle x:[{x}] y:[{y}] iDirection:[{iDirection}]")

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
        else:
            self.m_iWarningCount += 1
            self.m_listText = [
                ("警告，考生转头", (255, 0, 0)),
                (str(self.m_iWarningCount), (255, 0, 0)),
            ]

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
        le = in_stLandmarks[7]    # 左耳
        re = in_stLandmarks[8]    # 右耳
        ls = in_stLandmarks[11]   # 左肩
        rs = in_stLandmarks[12]   # 右肩
        le_l = in_stLandmarks[13] # 左肘
        re_l = in_stLandmarks[14] # 右肘
        lw = in_stLandmarks[15]   # 左腕
        rw = in_stLandmarks[16]   # 右腕

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
                    return True

        # 都没命中，返回 False 让兜底逻辑处理（视线偏移/离开座位/转头/正常）
        return False
