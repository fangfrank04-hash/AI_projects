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

        # 考生离开座位和多人检查
        self.__Checkindependence(iCount)

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
                ("警告，考生离开了座位", (255, 0, 0)),
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
                ("警告，考生的视线离开了屏幕", (255, 0, 0)),
                (str(self.m_iWarningCount), (255, 0, 0)),
            ]
