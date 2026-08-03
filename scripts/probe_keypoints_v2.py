"""
关键点探测脚本 v2
==================
适配 6 大类目录结构，扫描 samples_v2/ 下所有子目录，
按大类汇总统计关键点特征值，用于标定阈值。

运行方式（项目根目录）：
    .venv\\Scripts\\python.exe scripts\\probe_keypoints_v2.py

输出：
    1. 终端打印每张图的动作特征值（精简版，不打印原始坐标了，太长）
    2. 保存带关键点标注的图片到 samples_v2_annotated/
    3. 最后按大类打印汇总统计（min/max/avg）

6 大类目录：
    samples_v2/normal/        正常考试
    samples_v2/gaze_away/     视线偏移
    samples_v2/leave_seat/    离开座位
    samples_v2/multi_person/  多人
    samples_v2/phone_call/    打电话
    samples_v2/stretch_arm/   伸胳膊
"""

import cv2
import os
import math
import mediapipe as mp
from collections import defaultdict

# 路径
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLES_DIR = os.path.join(ROOT_DIR, "assets", "test_images", "samples_v2")
ANNOTATED_DIR = os.path.join(ROOT_DIR, "assets", "test_images", "samples_v2_annotated")

# 大类中文名映射
CATEGORY_NAMES = {
    "normal": "正常考试",
    "gaze_away": "视线偏移",
    "leave_seat": "离开座位",
    "multi_person": "多人",
    "phone_call": "打电话",
    "stretch_arm": "伸胳膊",
}

# 要画的关键点
KEYPOINT_INDICES = [0, 7, 8, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26]


# ===== 工具函数 =====

def distance(a, b):
    return math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2)


def angle_three_points(a, b, c):
    ba = (a.x - b.x, a.y - b.y)
    bc = (c.x - b.x, c.y - b.y)
    dot = ba[0] * bc[0] + ba[1] * bc[1]
    norm_ba = math.sqrt(ba[0] ** 2 + ba[1] ** 2)
    norm_bc = math.sqrt(bc[0] ** 2 + bc[1] ** 2)
    if norm_ba < 1e-6 or norm_bc < 1e-6:
        return 0.0
    cos_val = max(-1.0, min(1.0, dot / (norm_ba * norm_bc)))
    return math.degrees(math.acos(cos_val))


def draw_pose_on_image(image, landmarks):
    h, w, _ = image.shape
    annotated = image.copy()
    connections = [
        (11, 12), (11, 13), (13, 15), (12, 14), (14, 16),
        (11, 23), (12, 24), (23, 24), (23, 25), (24, 26),
    ]
    for (i, j) in connections:
        p1, p2 = landmarks[i], landmarks[j]
        x1, y1 = int(p1.x * w), int(p1.y * h)
        x2, y2 = int(p2.x * w), int(p2.y * h)
        cv2.line(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
    for idx in KEYPOINT_INDICES:
        p = landmarks[idx]
        x, y = int(p.x * w), int(p.y * h)
        color = (0, 255, 255) if p.visibility > 0.5 else (0, 0, 255)
        cv2.circle(annotated, (x, y), 5, color, -1)
        cv2.putText(annotated, str(idx), (x + 5, y - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
    return annotated


def compute_metrics(landmarks):
    """计算动作特征值，返回字典"""
    nose = landmarks[0]
    le, re = landmarks[7], landmarks[8]
    ls, rs = landmarks[11], landmarks[12]
    le_l, re_l = landmarks[13], landmarks[14]
    lw, rw = landmarks[15], landmarks[16]
    lh, rh = landmarks[23], landmarks[24]

    m = {}
    # 转头
    shoulder_mid_x = (ls.x + rs.x) / 2
    m["nose_offset_x"] = nose.x - shoulder_mid_x
    # 转身
    m["shoulder_dist"] = distance(ls, rs)
    m["left_shoulder_vis"] = ls.visibility
    m["right_shoulder_vis"] = rs.visibility
    m["min_shoulder_vis"] = min(ls.visibility, rs.visibility)
    # 站立
    shoulder_mid_y = (ls.y + rs.y) / 2
    m["shoulder_mid_y"] = shoulder_mid_y
    m["left_shoulder_y"] = ls.y
    m["right_shoulder_y"] = rs.y
    # 伸展
    m["left_arm_angle"] = angle_three_points(ls, le_l, lw)
    m["right_arm_angle"] = angle_three_points(rs, re_l, rw)
    m["left_wrist_y"] = lw.y
    m["right_wrist_y"] = rw.y
    m["left_wrist_above_shoulder"] = lw.y < ls.y
    m["right_wrist_above_shoulder"] = rw.y < rs.y
    # 打电话
    m["left_wrist_ear_dist"] = distance(lw, le)
    m["right_wrist_ear_dist"] = distance(rw, re)
    m["left_wrist_ear_y_diff"] = abs(lw.y - le.y)
    m["right_wrist_ear_y_diff"] = abs(rw.y - re.y)
    m["min_wrist_ear_dist"] = min(m["left_wrist_ear_dist"], m["right_wrist_ear_dist"])
    return m


def collect_images():
    """递归收集所有图片，返回 [(大类, 子目录, 文件名, 完整路径), ...]"""
    image_list = []
    if not os.path.exists(SAMPLES_DIR):
        print(f"错误：找不到样本目录 {SAMPLES_DIR}")
        return image_list

    for category in sorted(os.listdir(SAMPLES_DIR)):
        cat_dir = os.path.join(SAMPLES_DIR, category)
        if not os.path.isdir(cat_dir):
            continue
        for file_name in sorted(os.listdir(cat_dir)):
            if file_name.lower().endswith(('.jpg', '.jpeg', '.png')):
                image_list.append((category, cat_dir, file_name, os.path.join(cat_dir, file_name)))
    return image_list


def main():
    image_list = collect_images()
    if not image_list:
        print("没有找到图片")
        return

    # 创建标注目录（按大类分）
    for cat in CATEGORY_NAMES:
        os.makedirs(os.path.join(ANNOTATED_DIR, cat), exist_ok=True)

    print("=" * 70)
    print(f"关键点探测 v2")
    print(f"样本目录：{SAMPLES_DIR}")
    print(f"标注目录：{ANNOTATED_DIR}")
    print(f"共 {len(image_list)} 张图片")
    print("=" * 70)

    # 初始化 Pose
    mp_pose = mp.solutions.pose
    pose = mp_pose.Pose(
        static_image_mode=True,
        model_complexity=1,
        enable_segmentation=False,
        min_detection_confidence=0.3,
    )

    # 按大类收集结果
    cat_results = defaultdict(list)  # {大类: [(文件名, detected, metrics)]}

    for i, (cat, cat_dir, filename, filepath) in enumerate(image_list):
        cat_cn = CATEGORY_NAMES.get(cat, cat)
        print(f"\n[{i+1}/{len(image_list)}] [{cat_cn}] {filename}")

        image = cv2.imread(filepath)
        if image is None:
            print(f"  读取失败")
            cat_results[cat].append((filename, False, None))
            continue

        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        results = pose.process(image_rgb)

        if results.pose_landmarks is None:
            print(f"  未检测到人体")
            cat_results[cat].append((filename, False, None))
            # 保存原图
            cv2.imwrite(os.path.join(ANNOTATED_DIR, cat, filename), image)
            continue

        metrics = compute_metrics(results.pose_landmarks.landmark)
        cat_results[cat].append((filename, True, metrics))

        # 打印关键指标（精简）
        print(f"  shoulder_dist={metrics['shoulder_dist']:.3f}  "
              f"shoulder_y={metrics['shoulder_mid_y']:.3f}  "
              f"L_arm={metrics['left_arm_angle']:.0f}°  "
              f"R_arm={metrics['right_arm_angle']:.0f}°  "
              f"min_腕耳距={metrics['min_wrist_ear_dist']:.3f}")

        # 保存标注图
        annotated = draw_pose_on_image(image, results.pose_landmarks.landmark)
        cv2.imwrite(os.path.join(ANNOTATED_DIR, cat, filename), annotated)

    pose.close()

    # ===== 按大类汇总统计 =====
    print("\n\n" + "=" * 100)
    print("按大类汇总统计")
    print("=" * 100)

    # 关键指标列表
    KEY_METRICS = [
        ("shoulder_dist", "双肩距"),
        ("shoulder_mid_y", "肩部y"),
        ("min_shoulder_vis", "最小肩vis"),
        ("left_arm_angle", "左臂角(°)"),
        ("right_arm_angle", "右臂角(°)"),
        ("min_wrist_ear_dist", "最小腕耳距"),
        ("nose_offset_x", "鼻子x偏移"),
    ]

    # 表头
    print(f"\n{'大类':<10} {'图片数':>5} {'检测数':>5} | ", end="")
    for _, label in KEY_METRICS:
        print(f"{label:>12}", end="")
    print()
    print("-" * 110)

    for cat, results in sorted(cat_results.items()):
        cat_cn = CATEGORY_NAMES.get(cat, cat)
        total = len(results)
        detected = sum(1 for _, d, _ in results if d)
        metric_list = [m for _, d, m in results if d and m is not None]

        print(f"{cat_cn:<10} {total:>5} {detected:>5} | ", end="")

        for key, _ in KEY_METRICS:
            if not metric_list:
                print(f"{'---':>12}", end="")
            else:
                values = [m[key] for m in metric_list if key in m]
                if not values:
                    print(f"{'---':>12}", end="")
                else:
                    min_val = min(values)
                    max_val = max(values)
                    print(f"{min_val:.3f}~{max_val:.3f}", end="")
        print()

    print("-" * 110)

    # 详细：每个大类的 min/max 区间
    print("\n\n" + "=" * 100)
    print("阈值标定参考（各指标区间）")
    print("=" * 100)

    for cat, results in sorted(cat_results.items()):
        cat_cn = CATEGORY_NAMES.get(cat, cat)
        metric_list = [m for _, d, m in results if d and m is not None]
        if not metric_list:
            print(f"\n【{cat_cn}】无检测数据")
            continue

        print(f"\n【{cat_cn}】检测到 {len(metric_list)}/{len(results)} 张")
        for key, label in KEY_METRICS:
            values = [m[key] for m in metric_list if key in m]
            if values:
                min_val = min(values)
                max_val = max(values)
                avg_val = sum(values) / len(values)
                print(f"  {label:<14} min={min_val:.4f}  max={max_val:.4f}  avg={avg_val:.4f}")

    print("\n" + "=" * 100)
    print(f"标注图保存在：{ANNOTATED_DIR}")
    print("请把上面的汇总表复制给我，我据此标定新阈值")
    print("=" * 100)


if __name__ == "__main__":
    main()
