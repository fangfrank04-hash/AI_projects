"""
验证脚本：测试 ImageProctor.py 的 5 个动作检测
================================================
对 14 张样本照片逐张调用 GetImageFaceAngleByImg，对比预期结果和实际结果。

运行方式（在项目根目录）：
    .venv\\Scripts\\python.exe verify_actions.py
"""

import os
import sys
import time
from PIL import Image

# 把 AiProctor0623 目录加入 sys.path，让 import AiProctor 能找到
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "AiProctor0623"))

from AiProctor.Logic.ImageProctor import ImageProctor

# 样本目录
SAMPLES_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "AiProctor0623", "AiProctor", "test_images", "samples",
)

# 预期结果表：文件名前缀 → (预期动作关键词, 预期描述)
# 动作关键词会去 m_listText 的文字里查找
EXPECTED = [
    ("normal_front",            None,              "正常（不触发任何动作）"),
    ("normal_side",             None,              "正常（不触发任何动作）"),
    ("turn_head_left",          "视线",            "转头（现有 solvePnP）"),
    ("turn_head_right",         "视线",            "转头（现有 solvePnP）"),
    ("turn_body_left_45",       "视线",            "归入转头（45度无法区分）"),
    ("turn_body_right_45",      "视线",            "归入转头（45度无法区分）"),
    ("turn_body_left_90",       "转身",            "转身90度（新增 Pose）"),
    ("turn_body_right_90",      "转身",            "转身90度（新增 Pose）"),
    ("stand_up",                "站立",            "站立（新增 Pose）"),
    ("stretch_left",            "伸展",            "伸展胳膊（新增 Pose）"),
    ("stretch_right",           "伸展",            "伸展胳膊（新增 Pose）"),
    ("stretch_both",            "伸展",            "伸展胳膊（新增 Pose）"),
    ("phone_call_left",         "电话",            "打电话（新增 Pose）"),
    ("phone_call_right",        "电话",            "打电话（新增 Pose）"),
]


def main():
    if not os.path.exists(SAMPLES_DIR):
        print(f"错误：找不到样本目录 {SAMPLES_DIR}")
        return

    print("=" * 80)
    print("ImageProctor 动作检测验证")
    print(f"样本目录：{SAMPLES_DIR}")
    print("=" * 80)

    # 收集样本文件
    listFiles = sorted(
        f for f in os.listdir(SAMPLES_DIR)
        if f.lower().endswith(('.jpg', '.jpeg', '.png'))
    )

    if not listFiles:
        print("错误：样本目录里没有图片")
        return

    proctor = ImageProctor()

    iPassCount = 0
    iFailCount = 0
    listResults = []

    for strFileName in listFiles:
        # 找到对应的预期结果
        strExpectedKeyword = None
        strExpectedDesc = ""
        for strPrefix, strKeyword, strDesc in EXPECTED:
            if strFileName.startswith(strPrefix):
                strExpectedKeyword = strKeyword
                strExpectedDesc = strDesc
                break

        strFilePath = os.path.join(SAMPLES_DIR, strFileName)

        # 计时
        fStartTime = time.time()
        try:
            pilImg = Image.open(strFilePath)
            listText = proctor.GetImageFaceAngleByImg(pilImg)
        except Exception as e:
            listText = [("异常: " + str(e), (255, 0, 0))]
        fElapsed = time.time() - fStartTime

        # 提取实际检测到的文字
        strActualText = ""
        if listText:
            strActualText = listText[0][0] if listText else ""

        # 判断是否通过
        bPass = False
        if strExpectedKeyword is None:
            # 预期不触发任何动作（正常考试中）
            bPass = ("正常" in strActualText) or ("视线" not in strActualText and "电话" not in strActualText and "伸展" not in strActualText and "站立" not in strActualText and "转身" not in strActualText)
        else:
            bPass = strExpectedKeyword in strActualText

        if bPass:
            iPassCount += 1
            strMark = "PASS"
        else:
            iFailCount += 1
            strMark = "FAIL"

        listResults.append((strFileName, strExpectedDesc, strActualText, strMark, fElapsed))

        print(f"\n[{strMark}] {strFileName}")
        print(f"  预期：{strExpectedDesc}")
        print(f"  实际：{strActualText}")
        print(f"  耗时：{fElapsed:.0f}ms")

    # 汇总
    print("\n" + "=" * 80)
    print("验证汇总")
    print("=" * 80)
    print(f"{'文件名':<36} {'预期':<24} {'实际检测':<24} {'结果':>4} {'耗时':>6}")
    print("-" * 100)
    for strFileName, strExpectedDesc, strActualText, strMark, fElapsed in listResults:
        # 截断过长的文字
        strExp = strExpectedDesc[:22]
        strAct = strActualText[:22]
        print(f"{strFileName:<36} {strExp:<24} {strAct:<24} {strMark:>4} {fElapsed*1000:>5.0f}ms")

    print("-" * 100)
    print(f"通过：{iPassCount}/{len(listResults)}    失败：{iFailCount}/{len(listResults)}")
    print("=" * 80)

    if iFailCount > 0:
        print("\n失败的用例：")
        for strFileName, strExpectedDesc, strActualText, strMark, fElapsed in listResults:
            if strMark == "FAIL":
                print(f"  {strFileName}")
                print(f"    预期：{strExpectedDesc}")
                print(f"    实际：{strActualText}")


if __name__ == "__main__":
    main()
