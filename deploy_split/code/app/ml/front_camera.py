import datetime

import cv2
import mediapipe as mp
import numpy as np

from .toolkit import write_center_text


# 前置摄像头类
class FrontCamera:
    def __init__(self):
        # 定义角度范围
        self.max_left_angle = 6
        self.max_right_angle = -6
        self.max_up_angle = 6
        self.max_down_angle = -1

        # 周期内看到的方向
        self.directions = []
        self.warning_count = 0
        self.texts = []
        self.last_time = datetime.datetime.min

    def start(self, show_mesh: bool = False):
        # 定义解决方案
        mesh_solution = mp.solutions.face_mesh
        face_mesh = mesh_solution.FaceMesh(static_image_mode=False,
                                             max_num_faces=5,
                                             refine_landmarks=True,
                                             min_detection_confidence=0.5,
                                             min_tracking_confidence=0.5)

        drawing_utils = mp.solutions.drawing_utils
        drawing_styles = mp.solutions.drawing_styles

        # 打开摄像头
        camera = cv2.VideoCapture(0)

        # 记录当前时间
        self.last_time = datetime.datetime.now()

        while True:
            # 读取摄像头图片
            _, image = camera.read()

            # 转换图片格式
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            # 如果调用 iPhone 的摄像头，需要注释掉上面的代码，使用下面的代码
            # image_rgb = image

            # 处理图片
            mesh_result = face_mesh.process(image_rgb)

            # 检测到场人数
            count = 0
            if mesh_result.multi_face_landmarks:
                count = len(mesh_result.multi_face_landmarks)

                if count == 1:
                    # 只有一个考生的情况下获取面部方向
                    self._get_face_angle(mesh_result.multi_face_landmarks[0], image)

                # 绘制面部标记
                if show_mesh:
                    for face_landmarks in mesh_result.multi_face_landmarks:
                        # 绘制面部网格
                        drawing_utils.draw_landmarks(image=image,
                                                     landmark_list=face_landmarks,
                                                     connections=mesh_solution.FACEMESH_TESSELATION,
                                                     landmark_drawing_spec=None,
                                                     connection_drawing_spec=drawing_styles.get_default_face_mesh_tesselation_style())

                        # 绘制面部轮廓
                        drawing_utils.draw_landmarks(image=image,
                                                     landmark_list=face_landmarks,
                                                     connections=mesh_solution.FACEMESH_CONTOURS,
                                                     landmark_drawing_spec=None,
                                                     connection_drawing_spec=drawing_styles.get_default_face_mesh_contours_style())

                        # 绘制虹膜轮廓
                        drawing_utils.draw_landmarks(image=image,
                                                     landmark_list=face_landmarks,
                                                     connections=mesh_solution.FACEMESH_IRISES,
                                                     landmark_drawing_spec=None,
                                                     connection_drawing_spec=drawing_styles.get_default_face_mesh_iris_connections_style())

            # 考生离开座位和多人检查
            self._check_independence(count)

            # 当前文字
            #for i, (text, color) in enumerate(self.texts):
                #image = write_center_text(image, text, color, 50 + i * 60)

            cv2.imshow('faces', image)
            key = cv2.waitKey(1)
            if key == ord('q'):
                break

    def get_image_face_angle(self, image_file: str):
        # 定义解决方案
        mesh_solution = mp.solutions.face_mesh
        face_mesh = mesh_solution.FaceMesh(static_image_mode=False,
                                             max_num_faces=5,
                                             refine_landmarks=True,
                                             min_detection_confidence=0.5,
                                             min_tracking_confidence=0.5)

        image = cv2.imread(image_file)

        # 转换图片格式
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        # 处理图片
        mesh_result = face_mesh.process(image_rgb)

        # 检测到场人数
        count = 0
        if mesh_result.multi_face_landmarks:
            count = len(mesh_result.multi_face_landmarks)

            if count == 1:
                # 只有一个考生的情况下获取面部方向
                self._get_face_angle(mesh_result.multi_face_landmarks[0], image)
        print(self.texts)
    def _get_face_angle(self, face_landmarks, image):
        # 获取图片尺寸
        height, width, _ = image.shape

        # 获取标识坐标
        face_2d = []
        face_3d = []
        for i, point in enumerate(face_landmarks.landmark):
            # 只获取 6 个关键点坐标
            if i == 33 or i == 263 or i == 1 or i == 61 or i == 291 or i == 199:
                x, y = int(point.x * width), int(point.y * height)

                # 添加到列表
                face_2d.append((x, y))
                face_3d.append((x, y, point.z))

                # print(f"Point x:[{x}] y:[{y}] z:[{point.z}]")

        # 转换为 numpy 数组
        face_2d = np.array(face_2d, dtype=np.float64)
        face_3d = np.array(face_3d, dtype=np.float64)

        # 获取摄像头矩阵
        camera_matrix = np.array([
            [width, 0, width / 2],
            [0, width, height / 2],
            [0, 0, 1] ])

        # 获取畸变系数
        dist_coeffs = np.zeros((4, 1), dtype=np.float64)

        # 计算旋转向量
        _, rotation_vector, _ = cv2.solvePnP(face_3d, face_2d, camera_matrix, dist_coeffs)

        # 获取旋转矩阵
        rotation_matrix, _ = cv2.Rodrigues(rotation_vector)

        # 计算角度
        angles, _, _, _, _, _ = cv2.RQDecomp3x3(rotation_matrix)

        # 获取 y 轴的旋转角度
        x = angles[0] * 57.3
        y = angles[1] * 57.3


        # 计算头部方向
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

        print(f"Angle x:[{x}] y:[{y}] direction:[{direction}]")

        # 添加到列表
        self.directions.append(direction)

        # 检查方向
        self._check_direction()

    def _check_independence(self, count):
        if count == 1:
            return

        # 每秒判断一次
        now = datetime.datetime.now()
        if now < self.last_time + datetime.timedelta(seconds=1):
            return

        self.last_time = now

        if count == 0:
            self.warning_count += 1
            self.texts = [
                ("警告，考生离开了座位", (255, 0, 0)),
                (str(self.warning_count), (255, 0, 0)),
            ]
        else:
            self.warning_count += 1
            self.texts = [
                ("警告，多人出现在考场", (255, 0, 0)),
                (str(self.warning_count), (255, 0, 0)),
            ]

         # 清空列表
        self.directions.clear()

    def _check_direction(self):
        # 每秒判断一次
        now = datetime.datetime.now()
        if now < self.last_time + datetime.timedelta(seconds=1):
            return

        # 记录当前时间
        self.last_time = now

        # 获取最多的方向
        direction = max(set(self.directions), key=self.directions.count)

        # 清空列表
        self.directions.clear()

        # 如果方向不是正面，则在图像上绘制警告信息，如果是正面则绘制“正常考试中“
        if direction == 0:
            self.warning_count = 0
            self.texts = [ ("正常考试中 ...", (0, 255, 0)) ]
        else:
            self.warning_count += 1
            self.texts = [
                ("警告，考生的视线离开了屏幕", (255, 0, 0)),
                (str(self.warning_count), (255, 0, 0)),
            ]
