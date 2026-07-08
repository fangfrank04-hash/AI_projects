"""
关键点探测脚本
================
用途：对你拍的 14 张照片跑 MediaPipe Pose，打印关键点坐标和动作特征值，
      用来标定 ImageProctor.py 改造时的阈值。

运行方式（在项目根目录）：
    .venv\\Scripts\\python.exe probe_keypoints.py

输出：
    1. 终端打印每张图的关键点坐标 + 计算指标
    2. 保存带关键点标注的图片到 samples_annotated/ 目录
    3. 最后打印 14 张图的汇总对比表

关键点编号速查（MediaPipe Pose 33 点，只看上半身）：
    0  = 鼻子
    7  = 左耳    8  = 右耳
    11 = 左肩    12 = 右肩
    13 = 左肘    14 = 右肘
    15 = 左腕    16 = 右腕
    23 = 左髋    24 = 右髋
    25 = 左膝    26 = 右膝
"""

import cv2
import os
import math
import mediapipe as mp
import numpy as np

# ===== 配置 =====
SAMPLES_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "AiProctor0623",
    "AiProctor",
    "test_images",
    "samples",
)
ANNOTATED_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "AiProctor0623",
    "AiProctor",
    "test_images",
    "samples_annotated",
)

# 要打印的关键点编号 → 中文名
KEYPOINT_NAMES = {
    0:  "鼻",
    7:  "左耳",  8:  "右耳",
    11: "左肩",  12: "右肩",
    13: "左肘",  14: "右肘",
    15: "左腕",  16: "右腕",
    23: "左髋",  24: "右髋",
    25: "左膝",  26: "右膝",
}


# ===== 工具函数 =====

def distance(a, b):
    """计算两个关键点之间的欧氏距离（归一化坐标）"""
    return math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2)


def angle_three_points(a, b, c):
    """计算三点夹角（b 是顶点），返回角度（0~180）"""
    ba = (a.x - b.x, a.y - b.y)
    bc = (c.x - b.x, c.y - b.y)
    dot = ba[0] * bc[0] + ba[1] * bc[1]
    norm_ba = math.sqrt(ba[0] ** 2 + ba[1] ** 2)
    norm_bc = math.sqrt(bc[0] ** 2 + bc[1] ** 2)
    if norm_ba < 1e-6 or norm_bc < 1e-6:
        return 0.0
    cos_val = max(-1.0, min(1.0, dot / (norm_ba * norm_bc)))
    return math.degrees(math.acos(cos_val))


def shoulder_line_angle(ls, rs):
    """双肩连线与水平线的夹角（度），用于判断歪头/侧身"""
    angle = math.degrees(math.atan2(rs.y - ls.y, rs.x - ls.x))
    return angle


def torso_angle(ls, rs, lh, rh):
    """躯干角：肩中点→髋中点的向量与垂直方向的夹角（度）"""
    shoulder_mid_x = (ls.x + rs.x) / 2
    shoulder_mid_y = (ls.y + rs.y) / 2
    hip_mid_x = (lh.x + rh.x) / 2
    hip_mid_y = (lh.y + rh.y) / 2
    # 躯干向量（从肩指向髋）
    tx = hip_mid_x - shoulder_mid_x
    ty = hip_mid_y - shoulder_mid_y
    # 垂直向量 (0, 1)
    # 夹角
    norm = math.sqrt(tx ** 2 + ty ** 2)
    if norm < 1e-6:
        return 0.0
    cos_val = max(-1.0, min(1.0, ty / norm))  # tx*0 + ty*1 / norm
    return math.degrees(math.acos(cos_val))


def draw_pose_on_image(image, landmarks):
    """在图片上画关键点和骨架，返回标注后的图片"""
    h, w, _ = image.shape
    annotated = image.copy()

    # 画骨架连线（上半身）
    connections = [
        (11, 12),  # 左右肩
        (11, 13), (13, 15),  # 左臂
        (12, 14), (14, 16),  # 右臂
        (11, 23), (12, 24),  # 躯干两侧
        (23, 24),  # 左右髋
        (23, 25), (24, 26),  # 左右腿
    ]
    for (i, j) in connections:
        p1 = landmarks[i]
        p2 = landmarks[j]
        x1, y1 = int(p1.x * w), int(p1.y * h)
        x2, y2 = int(p2.x * w), int(p2.y * h)
        cv2.line(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)

    # 画关键点
    for idx in KEYPOINT_NAMES:
        p = landmarks[idx]
        x, y = int(p.x * w), int(p.y * h)
        # visibility 低的用红色，高的用黄色
        color = (0, 255, 255) if p.visibility > 0.5 else (0, 0, 255)
        cv2.circle(annotated, (x, y), 5, color, -1)
        # 标编号
        cv2.putText(annotated, str(idx), (x + 5, y - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

    return annotated


def process_one_image(pose_model, image_path):
    """处理一张图片，返回 (landmarks, annotated_image) 或 (None, image)"""
    image = cv2.imread(image_path)
    if image is None:
        print(f"  读取失败：{image_path}")
        return None, None

    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    results = pose_model.process(image_rgb)

    if results.pose_landmarks is None:
        return None, image

    return results.pose_landmarks.landmark, draw_pose_on_image(image, results.pose_landmarks.landmark)


def print_keypoints(landmarks, filename):
    """打印一张图的所有关键点坐标"""
    print(f"\n  --- 关键点坐标 ({filename}) ---")
    print(f"  {'编号':<4} {'名称':<6} {'x':>8} {'y':>8} {'z':>8} {'visibility':>10}")
    print(f"  {'-'*44}")
    for idx, name in KEYPOINT_NAMES.items():
        p = landmarks[idx]
        print(f"  {idx:<4} {name:<6} {p.x:>8.4f} {p.y:>8.4f} {p.z:>8.4f} {p.visibility:>10.4f}")


def compute_metrics(landmarks):
    """计算动作特征值，返回字典"""
    nose = landmarks[0]
    le, re = landmarks[7], landmarks[8]
    ls, rs = landmarks[11], landmarks[12]
    le_l, re_l = landmarks[13], landmarks[14]  # 左肘/右肘
    lw, rw = landmarks[15], landmarks[16]       # 左腕/右腕
    lh, rh = landmarks[23], landmarks[24]
    lk, rk = landmarks[25], landmarks[26]

    metrics = {}

    # 1. 转头指标：鼻子 x 偏移量（相对双肩中点）
    shoulder_mid_x = (ls.x + rs.x) / 2
    metrics["nose_offset_x"] = nose.x - shoulder_mid_x

    # 2. 转身指标
    metrics["shoulder_dist"] = distance(ls, rs)            # 双肩归一化距离
    metrics["shoulder_line_angle"] = shoulder_line_angle(ls, rs)  # 双肩连线角
    metrics["torso_angle"] = torso_angle(ls, rs, lh, rh)   # 躯干角
    metrics["left_shoulder_vis"] = ls.visibility
    metrics["right_shoulder_vis"] = rs.visibility

    # 3. 站立指标：髋中点 y - 肩中点 y（纵向距离）
    shoulder_mid_y = (ls.y + rs.y) / 2
    hip_mid_y = (lh.y + rh.y) / 2
    metrics["torso_height"] = hip_mid_y - shoulder_mid_y
    # 膝盖 y 坐标（站立时膝盖会下移出画面，y 接近 1）
    metrics["left_knee_y"] = lk.y
    metrics["right_knee_y"] = rk.y

    # 4. 伸展胳膊指标：肩-肘-腕三点夹角
    metrics["left_arm_angle"] = angle_three_points(ls, le_l, lw)
    metrics["right_arm_angle"] = angle_three_points(rs, re_l, rw)
    # 腕到肩距离
    metrics["left_wrist_shoulder_dist"] = distance(lw, ls)
    metrics["right_wrist_shoulder_dist"] = distance(rw, rs)

    # 5. 打电话指标：腕到耳距离 + y 差
    metrics["left_wrist_ear_dist"] = distance(lw, le)
    metrics["right_wrist_ear_dist"] = distance(rw, re)
    metrics["left_wrist_ear_y_diff"] = abs(lw.y - le.y)
    metrics["right_wrist_ear_y_diff"] = abs(rw.y - re.y)

    return metrics


def print_metrics(metrics, filename):
    """打印一张图的动作特征值"""
    print(f"\n  --- 动作特征值 ({filename}) ---")
    print(f"  {'指标':<32} {'值':>10}")
    print(f"  {'-'*44}")
    labels = {
        "nose_offset_x":            "转头-鼻子x偏移",
        "shoulder_dist":            "转身-双肩距离",
        "shoulder_line_angle":      "转身-双肩连线角(°)",
        "torso_angle":              "转身-躯干角(°)",
        "left_shoulder_vis":        "左肩visibility",
        "right_shoulder_vis":       "右肩visibility",
        "torso_height":             "站立-躯干纵向高度",
        "left_knee_y":              "左膝y坐标",
        "right_knee_y":             "右膝y坐标",
        "left_arm_angle":           "伸左臂-夹角(°)",
        "right_arm_angle":          "伸右臂-夹角(°)",
        "left_wrist_shoulder_dist": "左腕到肩距离",
        "right_wrist_shoulder_dist":"右腕到肩距离",
        "left_wrist_ear_dist":      "左打电话-腕耳距",
        "right_wrist_ear_dist":     "右打电话-腕耳距",
        "left_wrist_ear_y_diff":    "左打电话-y差",
        "right_wrist_ear_y_diff":   "右打电话-y差",
    }
    for key, label in labels.items():
        print(f"  {label:<32} {metrics[key]:>10.4f}")


def main():
    os.makedirs(ANNOTATED_DIR, exist_ok=True)

    # 收集所有样本图片（按文件名排序）
    if not os.path.exists(SAMPLES_DIR):
        print(f"错误：找不到样本目录 {SAMPLES_DIR}")
        return

    listFiles = sorted(
        f for f in os.listdir(SAMPLES_DIR)
        if f.lower().endswith(('.jpg', '.jpeg', '.png'))
    )

    if not listFiles:
        print(f"错误：{SAMPLES_DIR} 里没有图片")
        return

    print("=" * 60)
    print(f"关键点探测脚本启动")
    print(f"样本目录：{SAMPLES_DIR}")
    print(f"标注目录：{ANNOTATED_DIR}")
    print(f"共 {len(listFiles)} 张图片待处理")
    print("=" * 60)

    # 初始化 MediaPipe Pose
    # model_complexity: 0=Lite, 1=Full, 2=Heavy
    # static_image_mode=True 表示按静态图片处理（不做时序跟踪）
    mp_pose = mp.solutions.pose
    pose = mp_pose.Pose(
        static_image_mode=True,
        model_complexity=1,
        enable_segmentation=False,
        min_detection_confidence=0.3,
    )

    # 汇总表数据
    listResults = []  # 每个元素: (filename, detected, metrics)

    for filename in listFiles:
        filepath = os.path.join(SAMPLES_DIR, filename)
        print(f"\n{'=' * 60}")
        print(f"处理：{filename}")
        print(f"{'=' * 60}")

        landmarks, annotated = process_one_image(pose, filepath)

        if landmarks is None:
            print(f"  ⚠️ MediaPipe Pose 未检测到人体！")
            listResults.append((filename, False, None))
            # 仍保存原图到标注目录
            if annotated is not None:
                cv2.imwrite(os.path.join(ANNOTATED_DIR, filename), annotated)
            continue

        # 打印关键点坐标
        print_keypoints(landmarks, filename)

        # 计算并打印动作特征值
        metrics = compute_metrics(landmarks)
        print_metrics(metrics, filename)

        # 保存标注图
        if annotated is not None:
            annotated_path = os.path.join(ANNOTATED_DIR, filename)
            cv2.imwrite(annotated_path, annotated)
            print(f"\n  标注图已保存：{annotated_path}")

        listResults.append((filename, True, metrics))

    pose.close()

    # ===== 打印汇总对比表 =====
    print("\n\n" + "=" * 80)
    print("汇总对比表（14 张图横向对比）")
    print("=" * 80)

    # 表头
    print(f"\n{'文件名':<32} {'检测':>4} {'转身双肩距':>10} {'躯干角':>8} {'躯干高':>8} {'左臂角':>8} {'右臂角':>8} {'左腕耳':>8} {'右腕耳':>8}")
    print("-" * 100)

    for filename, detected, metrics in listResults:
        if not detected:
            print(f"{filename:<32} {'失败':>4} {'---':>10} {'---':>8} {'---':>8} {'---':>8} {'---':>8} {'---':>8} {'---':>8}")
            continue

        print(f"{filename:<32} {'成功':>4} "
              f"{metrics['shoulder_dist']:>10.4f} "
              f"{metrics['torso_angle']:>8.2f} "
              f"{metrics['torso_height']:>8.4f} "
              f"{metrics['left_arm_angle']:>8.2f} "
              f"{metrics['right_arm_angle']:>8.2f} "
              f"{metrics['left_wrist_ear_dist']:>8.4f} "
              f"{metrics['right_wrist_ear_dist']:>8.4f}")

    print("\n" + "=" * 80)
    print(f"标注图保存在：{ANNOTATED_DIR}")
    print("请把这个终端的全部输出复制给我，我据此标定阈值")
    print("=" * 80)


if __name__ == "__main__":
    main()
