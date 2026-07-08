"""
验证脚本 v2：测试 6 大类动作检测
================================
对 samples_v2/ 下 180 张照片逐张调用，对比预期结果和实际结果。

运行方式（项目根目录）：
    .venv\\Scripts\\python.exe scripts/verify_actions_v2.py
"""

import os
import sys
import time
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ml.image_proctor import ImageProctor

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLES_DIR = os.path.join(ROOT_DIR, "assets", "test_images", "samples_v2")

# 6 大类 → 预期关键词
# 文件名前缀 → (大类, 预期关键词, 预期描述)
CATEGORY_MAP = {
    # 正常考试
    "normal_front":   ("正常考试", "正常", "正常考试"),
    "normal_side":    ("正常考试", "正常", "正常考试"),
    "normal_writing": ("视线偏移", None,   "视线偏移（低头写字归视线偏移）"),

    # 视线偏移
    "face_hidden":    ("视线偏移", "视线偏移", "视线偏移"),
    "head_turn_large":("视线偏移", "转头",     "视线偏移/转头"),
    "phone_look_down":("视线偏移", None,       "视线偏移（低头看手机）"),

    # 离开座位
    "person_gone":        ("离开座位", "离开座位", "离开座位（人消失）"),
    "turn_body_left_90":  ("离开座位", "转身",   "离开座位（转身90）"),
    "turn_body_right_90": ("离开座位", "转身",   "离开座位（转身90）"),
    "turn_head":          ("离开座位", "转头",   "离开座位（转头）"),
    "stand_up":           ("离开座位", "离开座位", "离开座位（站立→人消失）"),

    # 多人
    "two_persons":        ("多人", "多人", "多人"),
    "person_entering":    ("多人", "多人", "多人"),
    "two_persons_talking":("多人", "多人", "多人"),

    # 打电话
    "phone_left":  ("打电话", "电话", "打电话"),
    "phone_right": ("打电话", "电话", "打电话"),

    # 伸胳膊
    "stretch_left":  ("伸胳膊", "伸展", "伸胳膊"),
    "stretch_right": ("伸胳膊", "伸展", "伸胳膊"),
    "stretch_both":  ("伸胳膊", "伸展", "伸胳膊"),
}


def collect_images():
    listImages = []
    if not os.path.exists(SAMPLES_DIR):
        return listImages
    for cat in sorted(os.listdir(SAMPLES_DIR)):
        cat_dir = os.path.join(SAMPLES_DIR, cat)
        if not os.path.isdir(cat_dir):
            continue
        for f in sorted(os.listdir(cat_dir)):
            if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                listImages.append((cat, f, os.path.join(cat_dir, f)))
    return listImages


def get_expected(filename):
    """根据文件名前缀返回预期结果"""
    for prefix, (cat, keyword, desc) in CATEGORY_MAP.items():
        if filename.startswith(prefix):
            return cat, keyword, desc
    return "未知", None, "未匹配"


def main():
    listImages = collect_images()
    if not listImages:
        print(f"错误：找不到图片 {SAMPLES_DIR}")
        return

    print("=" * 80)
    print("ImageProctor 6 大类验证 v2")
    print(f"样本目录：{SAMPLES_DIR}")
    print(f"共 {len(listImages)} 张图片")
    print("=" * 80)

    proctor = ImageProctor()
    iPass = 0
    iFail = 0
    listByCategory = {}  # {大类: [pass, fail]}

    for i, (cat_dir, filename, filepath) in enumerate(listImages):
        strExpCat, strExpKeyword, strExpDesc = get_expected(filename)

        fStart = time.time()
        try:
            pilImg = Image.open(filepath)
            listText = proctor.GetImageFaceAngleByImg(pilImg)
        except Exception as e:
            listText = [("异常: " + str(e), (255, 0, 0))]
        fElapsed = time.time() - fStart

        strActual = listText[0][0] if listText else ""

        # 判断是否通过
        bPass = False
        if strExpKeyword is None:
            # 预期可能是多种结果，只要不是明显错误的大类就行
            # normal_writing 和 phone_look_down 预期"视线偏移或正常"
            bPass = ("正常" in strActual) or ("视线偏移" in strActual) or ("转头" in strActual)
        else:
            bPass = strExpKeyword in strActual

        if bPass:
            iPass += 1
            strMark = "PASS"
        else:
            iFail += 1
            strMark = "FAIL"

        # 按大类统计
        if strExpCat not in listByCategory:
            listByCategory[strExpCat] = [0, 0]
        if bPass:
            listByCategory[strExpCat][0] += 1
        else:
            listByCategory[strExpCat][1] += 1

        if not bPass:
            print(f"[{strMark}] {filename}")
            print(f"  预期：{strExpDesc}（关键词：{strExpKeyword}）")
            print(f"  实际：{strActual}")
            print(f"  耗时：{fElapsed*1000:.0f}ms")

    # 汇总
    print("\n" + "=" * 80)
    print("验证汇总")
    print("=" * 80)
    print(f"\n{'大类':<10} {'通过':>6} {'失败':>6} {'通过率':>8}")
    print("-" * 40)
    for cat in sorted(listByCategory.keys()):
        p, f = listByCategory[cat]
        rate = p / (p + f) * 100 if (p + f) > 0 else 0
        print(f"{cat:<10} {p:>6} {f:>6} {rate:>7.1f}%")
    print("-" * 40)
    print(f"{'总计':<10} {iPass:>6} {iFail:>6} {iPass/(iPass+iFail)*100:>7.1f}%")
    print("=" * 80)


if __name__ == "__main__":
    main()
