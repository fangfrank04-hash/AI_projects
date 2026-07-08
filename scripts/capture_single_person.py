"""
单人场景拍照脚本
=================
用途：拍完 5 大类单人场景，共 120 张。

运行方式（项目根目录）：
    .venv\\Scripts\\python.exe scripts\\capture_single_person.py

操作：
    空格 → 拍照（拍完自动跳下一张）
    n 键 → 跳过当前子类，去下一个子类
    b 键 → 回到上一个子类
    r 键 → 重拍当前这张（删掉上一张，计数减1）
    q 键 → 退出

5 大类 / 15 子类 / 共 120 张：
    1. 正常考试（30张）
       - 正面坐姿 10
       - 侧坐 10
       - 低头写字 10
    2. 视线偏移（30张）
       - 脸转开看不到但人在 15
       - 头大幅偏转 15
    3. 离开座位（30张）
       - 人完全消失 8
       - 转身90度（左右各4）8
       - 转头 7
       - 站立 7
    4. 打电话（30张）
       - 左手打电话 10
       - 右手打电话 10
       - 低头看手机 10
    5. 伸胳膊（30张）
       - 左臂伸直 10
       - 右臂伸直 10
       - 双臂伸直 10
"""

import cv2
import os
import datetime
from PIL import Image, ImageDraw, ImageFont
import numpy as np

# 根目录
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAVE_BASE = os.path.join(ROOT_DIR, "assets", "test_images", "samples_v2")

# 5 大类，每类含若干子类
CATEGORIES = [
    {
        "name": "正常考试",
        "dir": "normal",
        "sub_shots": [
            {"code": "normal_front",    "name": "正面坐姿",       "hint": "看着屏幕，手放桌上，身体正对摄像头", "count": 10},
            {"code": "normal_side",     "name": "侧坐",           "hint": "身体稍微侧一点（约15度），仍然坐着", "count": 10},
            {"code": "normal_writing",  "name": "低头写字",       "hint": "低头看桌面/键盘，像在打字写字", "count": 10},
        ],
    },
    {
        "name": "视线偏移",
        "dir": "gaze_away",
        "sub_shots": [
            {"code": "face_hidden_in_frame", "name": "脸转开看不到但人在", "hint": "头/身体转开到脸完全看不到，但人还在画面里（侧脸/后脑勺）", "count": 15},
            {"code": "head_turn_large",      "name": "头大幅偏转",     "hint": "头转向左或右很大角度，脸还在但视线明显离开屏幕", "count": 15},
        ],
    },
    {
        "name": "离开座位",
        "dir": "leave_seat",
        "sub_shots": [
            {"code": "person_gone",        "name": "人完全消失",     "hint": "离开摄像头范围，画面里没有人", "count": 8},
            {"code": "turn_body_left_90",  "name": "转身向左90度",   "hint": "上半身向左转90度，只剩侧脸或后脑勺", "count": 4},
            {"code": "turn_body_right_90", "name": "转身向右90度",   "hint": "上半身向右转90度，只剩侧脸或后脑勺", "count": 4},
            {"code": "turn_head",          "name": "转头",         "hint": "头转向左或右，身体不动（左右交替拍）", "count": 7},
            {"code": "stand_up",           "name": "站立",         "hint": "从座位上站起来，上半身入镜", "count": 7},
        ],
    },
    {
        "name": "打电话",
        "dir": "phone_call",
        "sub_shots": [
            {"code": "phone_left",    "name": "左手打电话", "hint": "左手贴左耳附近，像打电话", "count": 10},
            {"code": "phone_right",   "name": "右手打电话", "hint": "右手贴右耳附近，像打电话", "count": 10},
            {"code": "phone_look_down", "name": "低头看手机", "hint": "低头看手里的手机，手在桌面以下", "count": 10},
        ],
    },
    {
        "name": "伸胳膊",
        "dir": "stretch_arm",
        "sub_shots": [
            {"code": "stretch_left",  "name": "左臂伸直", "hint": "只伸直左臂，水平或向上举", "count": 10},
            {"code": "stretch_right", "name": "右臂伸直", "hint": "只伸直右臂，水平或向上举", "count": 10},
            {"code": "stretch_both",  "name": "双臂伸直", "hint": "双臂都伸直，像伸懒腰", "count": 10},
        ],
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


def flatten_shots():
    """把所有子类展平成一个列表，每项含大类信息"""
    flat = []
    for cat in CATEGORIES:
        for sub in cat["sub_shots"]:
            flat.append({
                "category": cat["name"],
                "dir": cat["dir"],
                "code": sub["code"],
                "name": sub["name"],
                "hint": sub["hint"],
                "count": sub["count"],
            })
    return flat


def main():
    listShots = flatten_shots()
    iTotalTarget = sum(s["count"] for s in listShots)

    # 创建所有子目录
    for shot in listShots:
        os.makedirs(os.path.join(SAVE_BASE, shot["dir"]), exist_ok=True)

    print(f"照片将保存到：{SAVE_BASE}")
    print(f"共 {len(CATEGORIES)} 大类，{len(listShots)} 子类，{iTotalTarget} 张")

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("错误：打不开摄像头")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    iCurrent = 0          # 当前子类索引
    iCurrentShot = 0      # 当前子类已拍张数
    iTotalShot = 0        # 总已拍张数

    print("=" * 60)
    print("单人场景拍照")
    print("=" * 60)
    print(f"大类【{listShots[0]['category']}】子类【1/{len(listShots)}】：{listShots[0]['name']}")
    print(f"提示：{listShots[0]['hint']}")
    print(f"目标：{listShots[0]['count']} 张")
    print("-" * 60)
    print("空格=拍照  n=跳过子类  b=上一子类  r=重拍  q=退出")
    print("=" * 60)

    while True:
        bSuccess, frame = cap.read()
        if not bSuccess:
            print("错误：读取画面失败")
            break

        frame = cv2.flip(frame, 1)

        if iCurrent >= len(listShots):
            draw_text(frame, "全部拍完！按 q 退出", (frame.shape[1] // 2 - 200, frame.shape[0] // 2), font_size=40, color=(0, 255, 0))
        else:
            shot = listShots[iCurrent]
            # 大类 + 子类 + 进度
            strLine1 = f"[{shot['category']}] {iCurrent + 1}/{len(listShots)} {shot['name']}  {iCurrentShot}/{shot['count']}"
            color1 = (0, 255, 0) if iCurrentShot >= shot['count'] else (0, 255, 255)
            draw_text(frame, strLine1, (10, 40), font_size=26, color=color1)

            strLine2 = f"提示: {shot['hint']}"
            draw_text(frame, strLine2, (10, 80), font_size=18, color=(0, 255, 255))

        strLine3 = "[SPACE]拍照  [N]跳过子类  [B]上一子类  [R]重拍  [Q]退出"
        draw_text(frame, strLine3, (10, 115), font_size=16, color=(255, 255, 255))

        strLine4 = f"总计: {iTotalShot}/{iTotalTarget}"
        draw_text(frame, strLine4, (10, frame.shape[0] - 20), font_size=18, color=(200, 200, 200))

        cv2.imshow("Single Person Capture", frame)

        key = cv2.waitKey(1) & 0xFF

        if key == ord('q'):
            print("\n退出")
            break

        elif key == ord('n') and iCurrent < len(listShots):
            # 跳过当前子类
            iCurrent += 1
            iCurrentShot = 0
            if iCurrent < len(listShots):
                shot = listShots[iCurrent]
                print(f"\n跳过，进入大类【{shot['category']}】子类【{iCurrent + 1}/{len(listShots)}】：{shot['name']}")
                print(f"提示：{shot['hint']}  目标：{shot['count']} 张")
            else:
                print("\n全部子类处理完了！按 q 退出")

        elif key == ord('b') and iCurrent > 0:
            iCurrent -= 1
            iCurrentShot = 0
            shot = listShots[iCurrent]
            print(f"\n回到大类【{shot['category']}】子类【{iCurrent + 1}/{len(listShots)}】：{shot['name']}")
            print(f"提示：{shot['hint']}  目标：{shot['count']} 张")

        elif key == ord('r') and iCurrent < len(listShots) and iCurrentShot > 0:
            iCurrentShot -= 1
            iTotalShot -= 1
            print(f"  重拍，回到第 {iCurrentShot + 1} 张")

        elif key == ord(' ') and iCurrent < len(listShots):
            shot = listShots[iCurrent]
            strTime = datetime.datetime.now().strftime("%H%M%S")
            strFileName = f"{shot['code']}_{iCurrentShot + 1:02d}_{strTime}.jpg"
            strFilePath = os.path.join(SAVE_BASE, shot["dir"], strFileName)
            cv2.imwrite(strFilePath, frame)
            iCurrentShot += 1
            iTotalShot += 1
            print(f"  已保存：{shot['dir']}/{strFileName}  ({iCurrentShot}/{shot['count']})")

            # 当前子类拍完，跳下一个
            if iCurrentShot >= shot['count']:
                iCurrent += 1
                iCurrentShot = 0
                if iCurrent < len(listShots):
                    next_shot = listShots[iCurrent]
                    print(f"\n→ 进入大类【{next_shot['category']}】子类【{iCurrent + 1}/{len(listShots)}】：{next_shot['name']}")
                    print(f"提示：{next_shot['hint']}  目标：{next_shot['count']} 张")
                else:
                    print("\n全部拍完了！按 q 退出")

    cap.release()
    cv2.destroyAllWindows()

    # 汇总
    print("\n" + "=" * 60)
    print("拍摄汇总：")
    print("-" * 60)
    for cat in CATEGORIES:
        iCatCount = 0
        for sub in cat["sub_shots"]:
            strDir = os.path.join(SAVE_BASE, cat["dir"])
            listFiles = [f for f in os.listdir(strDir) if f.startswith(sub["code"])]
            iCatCount += len(listFiles)
            print(f"  {cat['name']:<6s} / {sub['name']:<14s} → {len(listFiles)}/{sub['count']} 张")
        print(f"  {cat['name']:<6s} 小计：{iCatCount} 张")
        print("-" * 60)
    print(f"总计 {iTotalShot} 张（目标 {iTotalTarget}）")
    print(f"保存在：{SAVE_BASE}")
    print("=" * 60)


if __name__ == "__main__":
    main()
