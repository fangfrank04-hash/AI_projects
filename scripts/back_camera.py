import cv2
import datetime
from ultralytics import YOLO
from .toolkit import write_center_text

class BackCamera:
    def __init__(self):
        self.warning_count = 0
        self.texts = []
        self.counts = []

    def start(self, show_mesh: bool = False):
        # 加载模型（路径改为新目录结构）
        model = YOLO("models/weights/yolo11n.pt")

        # 打开摄像头
        camera = cv2.VideoCapture(1)

        # 记录当前时间
        self.last_time = datetime.datetime.now()

        # 定义检测的类别
        class_list = [ 0 ]

        while True:
            # 读取摄像头图片
            _, image = camera.read()
            if image is None:
                continue

            if show_mesh:
                image, results = self._predict_and_detect(model, image, class_list, confidence=0.5)
            else:
                results = self._predict(model, image, class_list, confidence=0.5)

            # 检查房间里所有的人，只有考生一个人存在的时候才认为是正常状态
            self._check_room(results)

            # 显示当前文字
            for i, (text, color) in enumerate(self.texts):
                image = write_center_text(image, text, color, 50 + i * 60)

            cv2.imshow('faces', image)
            key = cv2.waitKey(1)
            if key == ord('q'):
                break

    def _predict(self, model, image, class_list=[], confidence=0.5):
        if class_list:
            results = model.predict(image, classes=class_list, conf=confidence)
        else:
            results = model.predict(image, conf=confidence)

        return results

    def _predict_and_detect(self, model, image, class_list=[],
                           confidence=0.5, box_thickness=2, text_thickness=1):
        results = self._predict(model, image, class_list, confidence=confidence)
        for result in results:
            for box in result.boxes:
                cv2.rectangle(image, (int(box.xyxy[0][0]), int(box.xyxy[0][1])),
                              (int(box.xyxy[0][2]), int(box.xyxy[0][3])),
                              (255, 0, 0), box_thickness)
                cv2.putText(image, f"{result.names[int(box.cls[0])]}",
                            (int(box.xyxy[0][0]), int(box.xyxy[0][1]) - 10),
                            cv2.FONT_HERSHEY_PLAIN, 1, (255, 0, 0), text_thickness)

        return image, results

    def _check_room(self, results):
        # 检查房间里所有的人，只有考生一个人存在的时候才认为是正常状态
        count = 0
        for result in results:
            count += len(result.boxes)

        # 把当前人数添加到列表中
        self.counts.append(count)

        # 每秒判断一次
        now = datetime.datetime.now()
        if now < self.last_time + datetime.timedelta(seconds=1):
            return

        # 记录当前时间
        self.last_time = now

        # 判断周期内的大概率人数
        count = max(set(self.counts), key=self.counts.count)

        if count == 1:
            self.warning_count = 0
            self.texts = [ ("正常考试中 ...", (0, 255, 0)) ]
        elif count == 0:
            self.warning_count += 1
            self.texts = [
                ("警告，考生已经离开了座位", (255, 0, 0)),
                (str(self.warning_count), (255, 0, 0)),
            ]
        else:
            self.warning_count += 1
            self.texts = [
                ("警告, 有其它人出现在考场", (255, 0, 0)),
                (str(self.warning_count), (255, 0, 0)),
            ]

        self.counts.clear()
