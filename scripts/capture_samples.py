"""
拍照样本采集脚本（清单引导版 v4）
=================================
用途：调用电脑摄像头，引导你一口气拍完所有 14 张监考动作样本照片。

运行方式（在项目根目录执行）：
    .venv\\Scripts\\python.exe capture_samples.py

操作说明：
    空格键  → 拍当前这张，拍完自动跳到下一个
    n 键    → 跳过当前这张（不想拍可以跳过）
    b 键    → 回到上一张重拍
    q 键    → 退出

14 张拍摄清单（按顺序）：
    1.  正常坐姿（正面，看着屏幕）
    2.  正常坐姿（身体侧一点）
    3.  头转向左（身体不动）
    4.  头转向右（身体不动）
    5.  转身向左 45 度
    6.  转身向右 45 度
    7.  转身向左 90 度（侧脸）
    8.  转身向右 90 度（侧脸）
    9.  站起来（身体入镜）
    10. 伸展左臂（左臂伸直）
    11. 伸展右臂（右臂伸直）
    12. 伸展双臂（双臂伸直）
    13. 左手打电话（左手贴左耳）
    14. 右手打电话（右手贴右耳）
"""

import cv2
import os
import datetime
from PIL import Image, ImageDraw, ImageFont
import numpy as np

# ===== 14 张拍摄清单 =====
# 每一项包含：code（文件名前缀）、name（动作名）、hint（具体怎么摆）
SHOTS = [
    {
        "code": "normal_front",
        "name": "正常坐姿-正面",
        "hint": "看着屏幕，手放桌上，身体正对摄像头",
    },
    {
        "code": "normal_side",
        "name": "正常坐姿-侧一点",
        "hint": "身体稍微侧一点（约15度），仍然坐着",
    },
    {
        "code": "turn_head_left",
        "name": "头转向左",
        "hint": "头转向左肩方向，身体保持不动",
    },
    {
        "code": "turn_head_right",
        "name": "头转向右",
        "hint": "头转向右肩方向，身体保持不动",
    },
    {
        "code": "turn_body_left_45",
        "name": "转身向左 45 度",
        "hint": "上半身向左转约 45 度，能看到半侧脸",
    },
    {
        "code": "turn_body_right_45",
        "name": "转身向右 45 度",
        "hint": "上半身向右转约 45 度，能看到半侧脸",
    },
    {
        "code": "turn_body_left_90",
        "name": "转身向左 90 度",
        "hint": "上半身向左转 90 度，只剩侧脸或后脑勺",
    },
    {
        "code": "turn_body_right_90",
        "name": "转身向右 90 度",
        "hint": "上半身向右转 90 度，只剩侧脸或后脑勺",
    },
    {
        "code": "stand_up",
        "name": "站立",
        "hint": "从座位上站起来，上半身入镜",
    },
    {
        "code": "stretch_left",
        "name": "伸展左臂",
        "hint": "只伸直左臂，水平或向上举",
    },
    {
        "code": "stretch_right",
        "name": "伸展右臂",
        "hint": "只伸直右臂，水平或向上举",
    },
    {
        "code": "stretch_both",
        "name": "伸展双臂",
        "hint": "双臂都伸直，像伸懒腰的姿势",
    },
    {
        "code": "phone_call_left",
        "name": "左手打电话",
        "hint": "左手贴在左耳附近，像打电话的样子",
    },
    {
        "code": "phone_call_right",
        "name": "右手打电话",
        "hint": "右手贴在右耳附近，像打电话的样子",
    },
]

# 保存目录（相对于脚本所在的项目根目录）
SAVE_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "AiProctor0623",
    "AiProctor",
    "test_images",
    "samples",
)


def _find_system_font():
    """在 Windows 系统查找可用的中文字体"""
    font_paths = [
        r"C:\Windows\Fonts\msyh.ttc",       # Microsoft YaHei (常用)
        r"C:\Windows\Fonts\msyhbd.ttc",     # Microsoft YaHei Bold
        r"C:\Windows\Fonts\simhei.ttf",     # SimHei 黑体
        r"C:\Windows\Fonts\simkai.ttf",     # SimKai 楷体
        r"C:\Windows\Fonts\simsun.ttc",     # SimSun 宋体
        r"C:\Windows\Fonts\msgothic.ttc",   # MS Gothic
    ]
    for path in font_paths:
        if os.path.exists(path):
            return path
    return None


def _get_font(size):
    """获取指定字号的中文字体"""
    font_path = _find_system_font()
    if font_path:
        return ImageFont.truetype(font_path, size)
    return ImageFont.load_default()


def draw_text_with_background(img, text, pos, font_size=24, color=(0, 255, 0)):
    """用 PIL 绘制带黑色背景的中文文字"""
    x, y = pos

    # OpenCV BGR → PIL RGB
    img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img_pil)
    font = _get_font(font_size)

    # 计算文字大小
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    # 画黑色背景矩形
    padding = 4
    bg_coords = (x - padding, y - text_h - padding, x + text_w + padding, y + padding)
    draw.rectangle(bg_coords, fill=(0, 0, 0))

    # 画文字
    draw.text((x, y - text_h), text, font=font, fill=color)

    # PIL RGB → OpenCV BGR
    img[:] = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)


def main():
    # 创建保存目录
    os.makedirs(SAVE_DIR, exist_ok=True)
    print(f"照片将保存到：{SAVE_DIR}")

    # 打开摄像头
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("错误：打不开摄像头，请检查：")
        print("  1. 摄像头是否被其他程序占用（比如微信视频、钉钉会议）")
        print("  2. 摄像头权限是否允许 Python 访问")
        print("  3. 笔记本摄像头开关是否打开（有些笔记本有物理开关）")
        return

    # 设置摄像头分辨率
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    iCurrentIndex = 0        # 当前拍摄任务索引（0~13）
    iShotCount = 0           # 已拍总张数
    listShotStatus = [False] * len(SHOTS)  # 每个任务是否已拍

    print("=" * 60)
    print(f"摄像头已打开，共 {len(SHOTS)} 张要拍")
    print("=" * 60)
    print(f"当前第 1 张：{SHOTS[0]['name']}")
    print(f"拍摄建议：{SHOTS[0]['hint']}")
    print("-" * 60)
    print("操作：")
    print("  空格键 → 拍照（拍完自动跳下一张）")
    print("  n 键   → 跳过当前这张")
    print("  b 键   → 回到上一张重拍")
    print("  q 键   → 退出")
    print("=" * 60)

    while True:
        # 读取一帧画面
        bSuccess, frame = cap.read()
        if not bSuccess:
            print("错误：读取画面失败")
            break

        # 镜像翻转
        frame = cv2.flip(frame, 1)

        # ===== 在画面上画提示信息 =====

        # 顶部第一行：第几张/共几张 + 动作名 + 是否已拍标记
        strMark = " [已拍]" if listShotStatus[iCurrentIndex] else ""
        strLine1 = f"[{iCurrentIndex + 1}/{len(SHOTS)}] {SHOTS[iCurrentIndex]['name']}{strMark}"
        # 已拍的用绿色，没拍的用红色提醒
        colorLine1 = (0, 255, 0) if listShotStatus[iCurrentIndex] else (0, 255, 255)
        draw_text_with_background(frame, strLine1, (10, 40), font_size=30, color=colorLine1)

        # 顶部第二行：拍摄建议（黄色，醒目）
        strLine2 = f"提示: {SHOTS[iCurrentIndex]['hint']}"
        draw_text_with_background(frame, strLine2, (10, 80), font_size=20, color=(0, 255, 255))

        # 顶部第三行：操作说明（白色）
        strLine3 = "[SPACE]拍照自动下一张  [N]跳过  [B]上一张  [Q]退出"
        draw_text_with_background(frame, strLine3, (10, 115), font_size=18, color=(255, 255, 255))

        # 底部：总进度条
        iDone = sum(listShotStatus)
        strLine4 = f"进度: {iDone}/{len(SHOTS)} 已拍  |  Total shots: {iShotCount}"
        draw_text_with_background(frame, strLine4, (10, frame.shape[0] - 20), font_size=20, color=(200, 200, 200))

        # 显示画面
        cv2.imshow("Capture Samples - press SPACE to shot, Q to quit", frame)

        # 等待按键
        key = cv2.waitKey(1) & 0xFF

        if key == ord('q'):
            print("\n退出拍照")
            break

        elif key == ord('n'):
            # 跳过当前，跳到下一张
            if iCurrentIndex < len(SHOTS) - 1:
                iCurrentIndex += 1
                print(f"\n跳过，进入第 {iCurrentIndex + 1} 张：{SHOTS[iCurrentIndex]['name']}")
                print(f"拍摄建议：{SHOTS[iCurrentIndex]['hint']}")
            else:
                print("\n已经是最后一张了，按空格拍照或按 q 退出")

        elif key == ord('b'):
            # 回到上一张
            if iCurrentIndex > 0:
                iCurrentIndex -= 1
                print(f"\n回到第 {iCurrentIndex + 1} 张：{SHOTS[iCurrentIndex]['name']}")
                print(f"拍摄建议：{SHOTS[iCurrentIndex]['hint']}")
            else:
                print("\n已经是第一张了")

        elif key == ord(' '):
            # 空格键拍照
            strTime = datetime.datetime.now().strftime("%H%M%S")
            strFileName = f"{SHOTS[iCurrentIndex]['code']}_{strTime}.jpg"
            strFilePath = os.path.join(SAVE_DIR, strFileName)
            cv2.imwrite(strFilePath, frame)
            iShotCount += 1
            listShotStatus[iCurrentIndex] = True
            print(f"  已保存：{strFileName}  (总计第 {iShotCount} 张)")

            # 拍完自动跳到下一张
            if iCurrentIndex < len(SHOTS) - 1:
                iCurrentIndex += 1
                print(f"  → 自动进入第 {iCurrentIndex + 1} 张：{SHOTS[iCurrentIndex]['name']}")
                print(f"  拍摄建议：{SHOTS[iCurrentIndex]['hint']}")
            else:
                print("\n  全部 14 张拍完了！按 q 退出")

    # 释放资源
    cap.release()
    cv2.destroyAllWindows()

    # 打印总结
    print("\n" + "=" * 60)
    print("拍摄完成！汇总：")
    print("-" * 60)
    for i, shot in enumerate(SHOTS):
        strStatus = "已拍" if listShotStatus[i] else "未拍"
        print(f"  {i + 1:2d}. {shot['name']:<18s} ({shot['code']:<22s})  →  {strStatus}")
    print("-" * 60)
    iDone = sum(listShotStatus)
    print(f"共拍了 {iShotCount} 张照片，清单完成 {iDone}/{len(SHOTS)}")
    print(f"保存在：{SAVE_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
