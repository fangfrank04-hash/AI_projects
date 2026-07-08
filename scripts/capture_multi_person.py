"""
多人场景拍照脚本（快速版）
==========================
同事马上要走，快速拍完 30 张多人场景照片。

运行方式（项目根目录）：
    .venv\\Scripts\\python.exe scripts\\capture_multi_person.py

操作：
    空格 → 拍照（拍完自动跳下一张）
    r 键 → 重拍当前这张
    q 键 → 退出

3 个子类，每个 10 张，共 30 张：
    1. 两人同框（10张）—— 两人并排坐着
    2. 他人闯入（10张）—— 你先坐着，同事从画面外走入
    3. 两人交流（10张）—— 两人转头说话或传东西
"""

import cv2
import os
import datetime
from PIL import Image, ImageDraw, ImageFont
import numpy as np

# 保存目录
SAVE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "assets", "test_images", "samples_v2", "multi_person",
)

# 3 个子类
SHOTS = [
    {
        "code": "two_persons",
        "name": "两人同框",
        "hint": "两人并排坐着，都面对摄像头",
        "count": 10,
    },
    {
        "code": "person_entering",
        "name": "他人闯入",
        "hint": "你先坐着，同事从画面侧面走入画面",
        "count": 10,
    },
    {
        "code": "two_persons_talking",
        "name": "两人交流",
        "hint": "两人转头说话，或传递物品",
        "count": 10,
    },
]


def _find_system_font():
    font_paths = [
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\msyhbd.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\simkai.ttf",
        r"C:\Windows\Fonts\simsun.ttc",
    ]
    for path in font_paths:
        if os.path.exists(path):
            return path
    return None


def _get_font(size):
    font_path = _find_system_font()
    if font_path:
        return ImageFont.truetype(font_path, size)
    return ImageFont.load_default()


def draw_text(img, text, pos, font_size=24, color=(0, 255, 0)):
    x, y = pos
    img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img_pil)
    font = _get_font(font_size)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    padding = 4
    draw.rectangle((x - padding, y - text_h - padding, x + text_w + padding, y + padding), fill=(0, 0, 0))
    draw.text((x, y - text_h), text, font=font, fill=color)
    img[:] = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)


def main():
    os.makedirs(SAVE_DIR, exist_ok=True)
    print(f"照片将保存到：{SAVE_DIR}")

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("错误：打不开摄像头")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    # 当前状态
    iCategoryIndex = 0     # 当前子类索引（0/1/2）
    iCurrentShot = 0       # 当前子类已拍张数
    iTotalShot = 0         # 总已拍张数

    print("=" * 50)
    print("多人场景拍照（同事快下班了，赶紧拍）")
    print("=" * 50)
    print(f"子类【1/3】：{SHOTS[0]['name']}")
    print(f"拍摄建议：{SHOTS[0]['hint']}")
    print(f"目标：{SHOTS[0]['count']} 张")
    print("-" * 50)
    print("空格=拍照  r=重拍当前  q=退出")
    print("=" * 50)

    while True:
        bSuccess, frame = cap.read()
        if not bSuccess:
            print("错误：读取画面失败")
            break

        frame = cv2.flip(frame, 1)

        # 画面提示
        strLine1 = f"[{iCategoryIndex + 1}/3] {SHOTS[iCategoryIndex]['name']}  {iCurrentShot}/{SHOTS[iCategoryIndex]['count']}"
        color1 = (0, 255, 0) if iCurrentShot >= SHOTS[iCategoryIndex]['count'] else (0, 255, 255)
        draw_text(frame, strLine1, (10, 40), font_size=30, color=color1)

        strLine2 = f"提示: {SHOTS[iCategoryIndex]['hint']}"
        draw_text(frame, strLine2, (10, 80), font_size=20, color=(0, 255, 255))

        strLine3 = "[SPACE]拍照  [R]重拍当前  [Q]退出"
        draw_text(frame, strLine3, (10, 115), font_size=18, color=(255, 255, 255))

        strLine4 = f"总计: {iTotalShot}/30"
        draw_text(frame, strLine4, (10, frame.shape[0] - 20), font_size=20, color=(200, 200, 200))

        # 完成提示
        if iCategoryIndex >= len(SHOTS):
            draw_text(frame, "全部拍完！按 q 退出", (frame.shape[1] // 2 - 200, frame.shape[0] // 2), font_size=40, color=(0, 255, 0))

        cv2.imshow("Multi-Person Capture", frame)

        key = cv2.waitKey(1) & 0xFF

        if key == ord('q'):
            print("\n退出")
            break

        elif key == ord('r') and iCurrentShot > 0:
            # 重拍当前：删除最后一张，计数减1
            iCurrentShot -= 1
            iTotalShot -= 1
            print(f"  重拍，回到第 {iCurrentShot + 1} 张")

        elif key == ord(' ') and iCategoryIndex < len(SHOTS):
            # 拍照
            strTime = datetime.datetime.now().strftime("%H%M%S")
            strFileName = f"{SHOTS[iCategoryIndex]['code']}_{iCurrentShot + 1:02d}_{strTime}.jpg"
            strFilePath = os.path.join(SAVE_DIR, strFileName)
            cv2.imwrite(strFilePath, frame)
            iCurrentShot += 1
            iTotalShot += 1
            print(f"  已保存：{strFileName}  ({iCurrentShot}/{SHOTS[iCategoryIndex]['count']})")

            # 当前子类拍完，跳到下一个
            if iCurrentShot >= SHOTS[iCategoryIndex]['count']:
                iCategoryIndex += 1
                iCurrentShot = 0
                if iCategoryIndex < len(SHOTS):
                    print(f"\n子类【{iCategoryIndex + 1}/3】：{SHOTS[iCategoryIndex]['name']}")
                    print(f"拍摄建议：{SHOTS[iCategoryIndex]['hint']}")
                    print(f"目标：{SHOTS[iCategoryIndex]['count']} 张")
                else:
                    print("\n全部 30 张拍完了！按 q 退出")

    cap.release()
    cv2.destroyAllWindows()

    print("\n" + "=" * 50)
    print("拍摄汇总：")
    print("-" * 50)
    for i, shot in enumerate(SHOTS):
        listFiles = [f for f in os.listdir(SAVE_DIR) if f.startswith(shot['code'])]
        print(f"  {i + 1}. {shot['name']:<10s} ({shot['code']:<24s}) → {len(listFiles)} 张")
    print("-" * 50)
    print(f"总计 {iTotalShot} 张")
    print(f"保存在：{SAVE_DIR}")
    print("=" * 50)


if __name__ == "__main__":
    main()
