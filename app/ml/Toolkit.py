import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

def WriteChineseText(in_stImage, in_strText, in_stPosition, in_stColor=(0, 255, 0), in_iSize=30):
    if (isinstance(in_stImage, np.ndarray)):  # 判断是否OpenCV图片类型
        in_stImage = Image.fromarray(cv2.cvtColor(in_stImage, cv2.COLOR_BGR2RGB))

    # 创建一个可以在给定图像上绘图的对象
    stDraw = ImageDraw.Draw(in_stImage)

    # 字体的格式（路径改为新目录结构）
    stFontStyle = ImageFont.truetype("assets/fonts/YeZiGongChangAoYeHei-2.ttf", in_iSize, encoding="utf-8")

    # 绘制文本
    stDraw.text(in_stPosition, in_strText, in_stColor, font=stFontStyle)

    # 转换回OpenCV格式
    return cv2.cvtColor(np.asarray(in_stImage), cv2.COLOR_RGB2BGR)

def WriteCenterText(in_stImage, in_strText, in_stColor, in_iY = 50):
     # 获取文本的宽度
    iTextWidth = cv2.getTextSize(in_strText, cv2.FONT_HERSHEY_SIMPLEX, 1, 2)[0][0]

    # 获取图片的宽度
    iImageWidth = in_stImage.shape[1]

    # 计算文本的位置
    iX = (iImageWidth - iTextWidth) / 2

    # 绘制文本
    # cv2.putText(in_stImage, in_strText, (int(iX), in_iY), cv2.FONT_HERSHEY_SIMPLEX, 1, in_stColor, 2, cv2.LINE_AA)
    return WriteChineseText(in_stImage, in_strText, (int(iX), in_iY), in_stColor, 60)