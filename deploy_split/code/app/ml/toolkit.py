import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


def write_chinese_text(image, text, position, color=(0, 255, 0), size=30):
    if (isinstance(image, np.ndarray)):  # 判断是否OpenCV图片类型
        image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))

    # 创建一个可以在给定图像上绘图的对象
    draw = ImageDraw.Draw(image)

    # 字体的格式（路径改为新目录结构）
    font_style = ImageFont.truetype("assets/fonts/YeZiGongChangAoYeHei-2.ttf", size, encoding="utf-8")

    # 绘制文本
    draw.text(position, text, color, font=font_style)

    # 转换回OpenCV格式
    return cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)

def write_center_text(image, text, color, y = 50):
     # 获取文本的宽度
    text_width = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 1, 2)[0][0]

    # 获取图片的宽度
    image_width = image.shape[1]

    # 计算文本的位置
    x = (image_width - text_width) / 2

    # 绘制文本
    # cv2.putText(image, text, (int(x), y), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2, cv2.LINE_AA)
    return write_chinese_text(image, text, (int(x), y), color, 60)
