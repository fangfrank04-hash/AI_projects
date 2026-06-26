import cv2
import datetime
from ultralytics import YOLO
from .Toolkit import WriteCenterText

class BackCamera:
    def __init__(self):
        self.m_iWarningCount = 0
        self.m_listText = []
        self.m_listCount = []

    def Start(self, in_isShowMesh: bool = False):
        # 加载模型
        stModel = YOLO("Weights/yolo11n.pt")

        # 打开摄像头
        stCamara = cv2.VideoCapture(1)

        # 记录当前时间
        self.m_stLastTime = datetime.datetime.now()

        # 定义检测的类别
        listClass = [ 0 ]

        while True:
            # 读取摄像头图片
            _, stImage = stCamara.read()
            if stImage is None:
                continue

            if in_isShowMesh:
                stImage, listResult = self.__PredictAndDetect(stModel, stImage, listClass, in_fConfidence=0.5)
            else:
                listResult = self.__Predict(stModel, stImage, listClass, in_fConfidence=0.5)

            # 检查房间里所有的人，只有考生一个人存在的时候才认为是正常状态
            self.__CheckRoom(listResult)

            # 显示当前文字
            for i, (strText, stColor) in enumerate(self.m_listText):
                stImage = WriteCenterText(stImage, strText, stColor, 50 + i * 60)

            cv2.imshow('faces', stImage)
            key = cv2.waitKey(1)
            if key == ord('q'):
                break

    def __Predict(self, in_stModel, in_stImage, in_listClass=[], in_fConfidence=0.5):
        if in_listClass:
            listResult = in_stModel.predict(in_stImage, classes=in_listClass, conf=in_fConfidence)
        else:
            listResult = in_stModel.predict(in_stImage, conf=in_fConfidence)

        return listResult

    def __PredictAndDetect(self, in_stModel, in_stImage, in_listClass=[],
                           in_fConfidence=0.5, in_iBoxThickness=2, in_iTextThickness=1):
        listResult = self.__Predict(in_stModel, in_stImage, in_listClass, in_fConfidence=in_fConfidence)
        for stResult in listResult:
            for stBox in stResult.boxes:
                cv2.rectangle(in_stImage, (int(stBox.xyxy[0][0]), int(stBox.xyxy[0][1])),
                              (int(stBox.xyxy[0][2]), int(stBox.xyxy[0][3])),
                              (255, 0, 0), in_iBoxThickness)
                cv2.putText(in_stImage, f"{stResult.names[int(stBox.cls[0])]}",
                            (int(stBox.xyxy[0][0]), int(stBox.xyxy[0][1]) - 10),
                            cv2.FONT_HERSHEY_PLAIN, 1, (255, 0, 0), in_iTextThickness)

        return in_stImage, listResult

    def __CheckRoom(self, in_listInfo):
        # 检查房间里所有的人，只有考生一个人存在的时候才认为是正常状态
        iCount = 0
        for stResult in in_listInfo:
            iCount += len(stResult.boxes)

        # 把当前人数添加到列表中
        self.m_listCount.append(iCount)

        # 每秒判断一次
        stNowTime = datetime.datetime.now()
        if stNowTime < self.m_stLastTime + datetime.timedelta(seconds=1):
            return

        # 记录当前时间
        self.m_stLastTime = stNowTime

        # 判断周期内的大概率人数
        iCount = max(set(self.m_listCount), key=self.m_listCount.count)

        if iCount == 1:
            self.m_iWarningCount = 0
            self.m_listText = [ ("正常考试中 ...", (0, 255, 0)) ]
        elif iCount == 0:
            self.m_iWarningCount += 1
            self.m_listText = [
                ("警告，考生已经离开了座位", (255, 0, 0)),
                (str(self.m_iWarningCount), (255, 0, 0)),
            ]
        else:
            self.m_iWarningCount += 1
            self.m_listText = [
                ("警告, 有其它人出现在考场", (255, 0, 0)),
                (str(self.m_iWarningCount), (255, 0, 0)),
            ]

        self.m_listCount.clear()
