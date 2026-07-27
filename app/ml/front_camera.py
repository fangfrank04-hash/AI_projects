import datetime

import cv2
import mediapipe as mp
import numpy as np

from .Toolkit import WriteCenterText


# 前置摄像头类
class FrontCamera:
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

    def Start(self, in_isShowMesh: bool = False):
        # 定义解决方案
        stSolutionMesh = mp.solutions.face_mesh
        stFaceMesh = stSolutionMesh.FaceMesh(static_image_mode=False,
                                             max_num_faces=5,
                                             refine_landmarks=True,
                                             min_detection_confidence=0.5,
                                             min_tracking_confidence=0.5)

        stSlutionDraw = mp.solutions.drawing_utils
        stRrawStyle = mp.solutions.drawing_styles

        # 打开摄像头
        stCamara = cv2.VideoCapture(0)

        # 记录当前时间
        self.m_stLastTime = datetime.datetime.now()

        while True:
            # 读取摄像头图片
            _, stImage = stCamara.read()

            # 转换图片格式
            stImageRGB = cv2.cvtColor(stImage, cv2.COLOR_BGR2RGB)
            # 如果调用 iPhone 的摄像头，需要注释掉上面的代码，使用下面的代码
            # stImageRGB = stImage

            # 处理图片
            stResult = stFaceMesh.process(stImageRGB)

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
                        # 绘制面部网格
                        stSlutionDraw.draw_landmarks(image=stImage,
                                                     landmark_list=stFaceLandmarks,
                                                     connections=stSolutionMesh.FACEMESH_TESSELATION,
                                                     landmark_drawing_spec=None,
                                                     connection_drawing_spec=stRrawStyle.get_default_face_mesh_tesselation_style())

                        # 绘制面部轮廓
                        stSlutionDraw.draw_landmarks(image=stImage,
                                                     landmark_list=stFaceLandmarks,
                                                     connections=stSolutionMesh.FACEMESH_CONTOURS,
                                                     landmark_drawing_spec=None,
                                                     connection_drawing_spec=stRrawStyle.get_default_face_mesh_contours_style())

                        # 绘制虹膜轮廓
                        stSlutionDraw.draw_landmarks(image=stImage,
                                                     landmark_list=stFaceLandmarks,
                                                     connections=stSolutionMesh.FACEMESH_IRISES,
                                                     landmark_drawing_spec=None,
                                                     connection_drawing_spec=stRrawStyle.get_default_face_mesh_iris_connections_style())

            # 考生离开座位和多人检查
            self.__Checkindependence(iCount)

            # 当前文字
            #for i, (strText, stColor) in enumerate(self.m_listText):
                #stImage = WriteCenterText(stImage, strText, stColor, 50 + i * 60)

            cv2.imshow('faces', stImage)
            key = cv2.waitKey(1)
            if key == ord('q'):
                break

    def GetImageFaceAngle(self, in_strImageFile: str):
        # 定义解决方案
        stSolutionMesh = mp.solutions.face_mesh
        stFaceMesh = stSolutionMesh.FaceMesh(static_image_mode=False,
                                             max_num_faces=5,
                                             refine_landmarks=True,
                                             min_detection_confidence=0.5,
                                             min_tracking_confidence=0.5)

        stImage = cv2.imread(in_strImageFile)

        # 转换图片格式
        stImageRGB = cv2.cvtColor(stImage, cv2.COLOR_BGR2RGB)

        # 处理图片
        stResult = stFaceMesh.process(stImageRGB)

        # 检测到场人数
        iCount = 0
        if stResult.multi_face_landmarks:
            iCount = len(stResult.multi_face_landmarks)

            if iCount == 1:
                # 只有一个考生的情况下获取面部方向
                self.__GetFaceAngle(stResult.multi_face_landmarks[0], stImage)
        print(self.m_listText)
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

                # 添加到列表
                listFace2d.append((x, y))
                listFace3d.append((x, y, stPoint.z))

                # print(f"Point x:[{x}] y:[{y}] z:[{stPoint.z}]")

        # 转换为 numpy 数组
        listFace2d = np.array(listFace2d, dtype=np.float64)
        listFace3d = np.array(listFace3d, dtype=np.float64)

        # 获取摄像头矩阵
        listCameraMatrix = np.array([
            [iWidth, 0, iWidth / 2],
            [0, iWidth, iHeight / 2],
            [0, 0, 1] ])

        # 获取畸变系数
        listDistCoeffs = np.zeros((4, 1), dtype=np.float64)

        # 计算旋转向量
        _, listRotationVector, _ = cv2.solvePnP(listFace3d, listFace2d, listCameraMatrix, listDistCoeffs)

        # 获取旋转矩阵
        listRotationMatrix, _ = cv2.Rodrigues(listRotationVector)

        # 计算角度
        listAngles, _, _, _, _, _ = cv2.RQDecomp3x3(listRotationMatrix)

        # 获取 y 轴的旋转角度
        x = listAngles[0] * 57.3
        y = listAngles[1] * 57.3


        # 计算头部方向
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

        # 添加到列表
        self.m_listDirection.append(iDirection)

        # 检查方向
        self.__CheckDirection()

    def __Checkindependence(self, in_iCount):
        if in_iCount == 1:
            return

        # 每秒判断一次
        stNowTime = datetime.datetime.now()
        if stNowTime < self.m_stLastTime + datetime.timedelta(seconds=1):
            return

        self.m_stLastTime = stNowTime

        if in_iCount == 0:
            self.m_iWarningCount += 1
            self.m_listText = [
                ("警告，考生离开了座位", (255, 0, 0)),
                (str(self.m_iWarningCount), (255, 0, 0)),
            ]
        else:
            self.m_iWarningCount += 1
            self.m_listText = [
                ("警告，多人出现在考场", (255, 0, 0)),
                (str(self.m_iWarningCount), (255, 0, 0)),
            ]

         # 清空列表
        self.m_listDirection.clear()

    def __CheckDirection(self):
        # 每秒判断一次
        stNowTime = datetime.datetime.now()
        if stNowTime < self.m_stLastTime + datetime.timedelta(seconds=1):
            return

        # 记录当前时间
        self.m_stLastTime = stNowTime

        # 获取最多的方向
        iDirection = max(set(self.m_listDirection), key=self.m_listDirection.count)

        # 清空列表
        self.m_listDirection.clear()

        # 如果方向不是正面，则在图像上绘制警告信息，如果是正面则绘制“正常考试中“
        if iDirection == 0:
            self.m_iWarningCount = 0
            self.m_listText = [ ("正常考试中 ...", (0, 255, 0)) ]
        else:
            self.m_iWarningCount += 1
            self.m_listText = [
                ("警告，考生的视线离开了屏幕", (255, 0, 0)),
                (str(self.m_iWarningCount), (255, 0, 0)),
            ]
