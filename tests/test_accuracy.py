"""
批量测试脚本：遍历 ai_generated/ 目录下所有图片，调用 ImageProctor 检测人脸角度，
对比预期结果，输出准确率统计报告。
使用方法: cd AiProctor0623 && python test_accuracy.py
"""
import io
import os
import re
import sys

from PIL import Image

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from app.ml.image_proctor import ImageProctor

TEST_DIR = os.path.join(ROOT_DIR, "assets", "test_images", "ai_generated")

# 方向名称
DIR_NAMES = {0: "正面", 1: "右看", 2: "下看", 3: "左看", 4: "上看"}

def get_expected(filename):
    """根据文件名推断预期结果。返回 (category, expected_desc)"""
    base = os.path.splitext(filename)[0]  # e.g. "A_01_正常"
    parts = base.split("_")
    if len(parts) < 3:
        return ("未知", "未知")

    letter = parts[0]       # A/B/C/D/E/F/G
    suffix = "_".join(parts[2:])  # e.g. "正常", "左看边界", "左下复合"

    if letter == "A":
        return ("正常", "正常(方向=0)")
    elif letter == "B":
        return ("左看", "警告(方向=3)")
    elif letter == "C":
        return ("右看", "警告(方向=1)")
    elif letter == "D":
        return ("低头", "警告(方向=2)")
    elif letter == "E":
        return ("仰头", "警告(方向=4)")
    elif letter == "F":
        if "无人" in suffix or "背对" in suffix:
            return ("无人/背对", "离开座位(无人脸)")
        elif "多人" in suffix:
            return ("多人", "多人出现在考场")
    elif letter == "G":
        return ("挑战", "挑战场景(可能检测不到)")
    return ("未知", "未知")


def run_single(image_path):
    """运行单张图片检测，返回 (x_angle, y_angle, direction, result_text)
    使用 PIL 加载图片绕过 Windows 下 OpenCV 中文路径问题"""
    old_stdout = sys.stdout
    sys.stdout = captured = io.StringIO()

    try:
        pil_img = Image.open(image_path).convert("RGB")
        proctor = ImageProctor()
        proctor.GetImageFaceAngleByImg(pil_img)
    except Exception as e:
        sys.stdout = old_stdout
        return (None, None, None, f"异常: {e}")

    output = captured.getvalue()
    sys.stdout = old_stdout

    # 解析 "Angle x:[...] y:[...] iDirection:[...]"
    x_angle = y_angle = direction = None
    match = re.search(r"Angle x:\[([-.\d]+)\]\s+y:\[([-.\d]+)\]\s+iDirection:\[(\d+)\]", output)
    if match:
        x_angle = float(match.group(1))
        y_angle = float(match.group(2))
        direction = int(match.group(3))

    # 从 m_listText 获取最终判定
    result_text = "无输出"
    if proctor.m_listText:
        result_text = proctor.m_listText[0][0] if proctor.m_listText[0] else "无输出"

    return (x_angle, y_angle, direction, result_text)


def check_match(expected_desc, result_text, direction, category):
    """判断检测结果是否与预期一致"""
    if category in ("无人/背对",):
        return "离开" in result_text or "无" in result_text
    elif category == "多人":
        return "多人" in result_text
    elif category == "挑战":
        return True  # 挑战场景不判对错
    else:
        # 正常方向类：检查 result_text 是否匹配
        if "正常" in expected_desc:
            return "正常" in result_text
        else:
            # 警告类：只要方向非0就算抓到作弊行为
            return "警告" in result_text or "离开" in result_text or "多人" in result_text


def main():
    if not os.path.isdir(TEST_DIR):
        print(f"测试图片目录不存在: {TEST_DIR}")
        return

    files = sorted(f for f in os.listdir(TEST_DIR) if f.lower().endswith(".png"))
    if not files:
        print(f"目录下没有 PNG 图片: {TEST_DIR}")
        return

    print("=" * 110)
    print("{:<28s} {:>8s} {:>8s} {:>6s} {:>6s} {:>10s} {:>32s} {:>6s}".format(
        "文件名", "x角度", "y角度", "方向", "方向名", "预期类别", "实际结果", "匹配"))
    print("-" * 110)

    stats = {}  # {"正常": [total, correct], ...}
    results = []

    for fname in files:
        image_path = os.path.join(TEST_DIR, fname)
        category, expected_desc = get_expected(fname)
        x_ang, y_ang, direction, result_text = run_single(image_path)

        matched = check_match(expected_desc, result_text, direction, category)

        if x_ang is not None:
            dir_name = DIR_NAMES.get(direction, "?")
            print("{:<28s} {:>8.2f} {:>8.2f} {:>5d} {:>6s} {:>10s} {:>32s} {:>6s}".format(
                fname, x_ang, y_ang, direction, dir_name, category, result_text,
                "PASS" if matched else "FAIL"))
        else:
            print("{:<28s} {:>8s} {:>8s} {:>5s} {:>6s} {:>10s} {:>32s} {:>6s}".format(
                fname, "-", "-", "-", "-", category, result_text,
                "PASS" if matched else "FAIL"))

        results.append((fname, category, x_ang, y_ang, direction, result_text, matched))

        # 统计
        if category not in ("挑战",):
            if category not in stats:
                stats[category] = [0, 0]
            stats[category][0] += 1
            if matched:
                stats[category][1] += 1

    # ---- 分类统计 ----
    print("\n" + "=" * 60)
    print("分类统计")
    print("-" * 60)
    total_imgs = 0
    total_correct = 0
    for cat in ["正常", "左看", "右看", "低头", "仰头", "无人/背对", "多人"]:
        if cat in stats:
            t, c = stats[cat]
            total_imgs += t
            total_correct += c
            pct = c / t * 100 if t > 0 else 0
            print(f"  {cat:<10s}: {c}/{t} 准确率 {pct:.1f}%")
    if total_imgs > 0:
        overall = total_correct / total_imgs * 100
        print(f"  {'总体':<10s}: {total_correct}/{total_imgs} 准确率 {overall:.1f}%")

    # ---- 边界值重点标注 ----
    print("\n" + "=" * 60)
    print("边界值测试表现（最关键）")
    print("-" * 60)
    boundary_keys = {"B_01", "C_01", "D_01", "E_01"}
    boundary_results = []
    for r in results:
        fname = r[0]
        base = os.path.splitext(fname)[0].split("_")
        key = "_".join(base[:2])  # e.g. "B_01"
        if key in boundary_keys:
            boundary_results.append(r)
            mark = "PASS 通过" if r[6] else "FAIL 误判"
            extra = ""
            if not r[6] and r[3] is not None:
                extra = f" (检测为: {DIR_NAMES.get(r[3], '?')})"
            print(f"  {fname}: {mark}{extra}")

    # 边界值总结
    if boundary_results:
        boundary_pass = sum(1 for r in boundary_results if r[6])
        print(f"\n  边界值通过: {boundary_pass}/{len(boundary_results)}")

    # ---- 漏检/误检汇总 ----
    print("\n" + "=" * 60)
    print("漏检 / 误检清单")
    print("-" * 60)
    errors = [r for r in results if not r[6] and r[1] not in ("挑战",)]
    if errors:
        for r in errors:
            print(f"  FAIL {r[0]}  预期={r[1]}  实际={r[5]}  方向={r[3]}({DIR_NAMES.get(r[3], '?')})")
    else:
        print("  无漏检/误检！")

if __name__ == "__main__":
    main()
