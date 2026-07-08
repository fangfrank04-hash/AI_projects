"""
Targeted sample capture assistant for AI proctoring accuracy work.

Run from project root:
    .venv\\Scripts\\python.exe scripts\\capture_targeted_samples.py

Useful options:
    .venv\\Scripts\\python.exe scripts\\capture_targeted_samples.py --plan single
    .venv\\Scripts\\python.exe scripts\\capture_targeted_samples.py --plan multi
    .venv\\Scripts\\python.exe scripts\\capture_targeted_samples.py --plan focused
    .venv\\Scripts\\python.exe scripts\\capture_targeted_samples.py --camera 1
    .venv\\Scripts\\python.exe scripts\\capture_targeted_samples.py --countdown 3

Controls:
    SPACE  start countdown and capture
    n      skip current subtype
    b      go back to previous subtype
    r      mark previous capture as retake and capture this subtype again
    h      print detailed guidance again
    q      quit
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = ROOT_DIR / "assets" / "test_images" / "targeted_samples"
MANIFEST_NAME = "samples_manifest.csv"

MANIFEST_FIELDS = [
    "created_at",
    "split",
    "category",
    "category_dir",
    "code",
    "name",
    "shot_index",
    "filename",
    "relative_path",
    "camera_index",
    "goal",
    "pose_steps",
    "quality_checks",
    "avoid",
]


FOCUSED_PLAN = [
    {
        "category": "伸胳膊",
        "category_dir": "stretch_arm",
        "code": "stretch_left_horizontal",
        "name": "左手水平伸直",
        "count": 10,
        "goal": "补足目前最容易漏检的水平伸左臂样本，观察手腕低于肩膀时的关键点表现。",
        "pose_steps": [
            "坐在考试位置，脸和上半身保持在画面中，不要刻意离开座位。",
            "只伸左手，手臂尽量从肩膀向左侧水平打开，手腕可以略低于肩膀。",
            "右手自然放在桌面或腿上，不要靠近耳朵，避免像打电话。",
            "每拍 2 张换一点角度：正对摄像头、身体微左、身体微右交替。",
        ],
        "quality_checks": [
            "左肩、左肘、左手腕尽量都在画面内。",
            "手臂要伸直，不要弯成打电话或托腮姿势。",
            "脸不要完全消失，否则会混入视线偏移/离开座位因素。",
        ],
        "avoid": [
            "不要把左手贴在脸或耳朵旁。",
            "不要两只手同时举起。",
            "不要站起来或大幅转身。",
        ],
    },
    {
        "category": "伸胳膊",
        "category_dir": "stretch_arm",
        "code": "stretch_right_horizontal",
        "name": "右手水平伸直",
        "count": 10,
        "goal": "继续补水平伸右臂样本，验证新增低位伸展规则是否稳定。",
        "pose_steps": [
            "坐在座位上，身体大致面对摄像头。",
            "只伸右手，手臂向右侧水平打开，肘部尽量伸直。",
            "左手自然放下，不要做打电话、托腮、摸头动作。",
            "每拍几张调整手腕高度：略高于肩、齐肩、略低于肩。",
        ],
        "quality_checks": [
            "右肩、右肘、右手腕要尽量入镜。",
            "手腕离耳朵远一点，形成明确的伸展动作。",
            "背景尽量保持考试环境，不要让第二个人入镜。",
        ],
        "avoid": [
            "不要让手臂被桌子、椅背或身体遮住。",
            "不要把手机拿到耳边。",
            "不要让手腕出画面。",
        ],
    },
    {
        "category": "伸胳膊",
        "category_dir": "stretch_arm",
        "code": "stretch_left_up",
        "name": "左手向上伸直",
        "count": 10,
        "goal": "补足传统高举伸展样本，确保旧规则和新规则不会互相干扰。",
        "pose_steps": [
            "坐姿保持稳定，脸尽量在画面中央。",
            "左手从身体左侧向上伸直，像举手或伸懒腰。",
            "右手保持自然，不要跟着抬起。",
            "拍摄时可以微微低头/正脸交替，但不要完全转身。",
        ],
        "quality_checks": [
            "左手腕最好不要出画面顶部。",
            "左肘不要弯曲太多。",
            "上半身和脸仍在画面里。",
        ],
        "avoid": [
            "不要双手一起举。",
            "不要离开椅子。",
            "不要用手挡住整张脸。",
        ],
    },
    {
        "category": "伸胳膊",
        "category_dir": "stretch_arm",
        "code": "stretch_right_up",
        "name": "右手向上伸直",
        "count": 10,
        "goal": "补足右手高举伸展样本，和右手水平伸展形成对照。",
        "pose_steps": [
            "坐在画面中央，保持考试摄像头常见距离。",
            "右手向上伸直，手腕高于肩膀。",
            "左手放下，脸可以正对或轻微看屏幕下方。",
            "每 2 张改变一点手臂角度：斜上、正上、侧上。",
        ],
        "quality_checks": [
            "右肩、右肘、右腕尽量清楚。",
            "不要让手臂和背景颜色完全融合。",
            "动作要像伸展，不像挠头或摸耳朵。",
        ],
        "avoid": [
            "不要把手贴脸。",
            "不要身体转成 90 度。",
            "不要让另一个人进入画面。",
        ],
    },
    {
        "category": "伸胳膊",
        "category_dir": "stretch_arm",
        "code": "stretch_both_mixed",
        "name": "双手伸展混合",
        "count": 10,
        "goal": "补双手伸展边界样本，避免被误判成转身或正常。",
        "pose_steps": [
            "坐姿稳定，双肩尽量都能看到。",
            "双手同时伸直，可以向上、斜上、水平各拍几张。",
            "保持脸在画面里，不要完全低头或转头。",
            "拍摄时左右手高度可以略有不同，更贴近真实动作。",
        ],
        "quality_checks": [
            "双臂至少大部分在画面内。",
            "手臂明显伸直，动作幅度要大。",
            "身体不要离开座位。",
        ],
        "avoid": [
            "不要只露出手掌看不到肘部。",
            "不要动作太小像正常伸懒腰未完成。",
            "不要让画面中出现第二个人。",
        ],
    },
    {
        "category": "多人",
        "category_dir": "multi_person",
        "code": "person_enter_left_edge",
        "name": "左侧半个人入镜",
        "count": 10,
        "goal": "补 FaceMesh 最容易漏掉的半入镜多人样本。",
        "pose_steps": [
            "主考生坐在正常考试位置，正对摄像头。",
            "第二个人从画面左侧慢慢探入，只露半张脸或半个上半身。",
            "主考生不要做伸手、打电话动作，保持普通考试状态。",
            "第二个人每张换一点位置：只露脸、露肩、露半身。",
        ],
        "quality_checks": [
            "主考生和第二个人都至少有部分脸或头部可见。",
            "第二个人不要完全挡住主考生。",
            "画面要像真实考场异常，不要摆拍得过于夸张。",
        ],
        "avoid": [
            "不要第二个人完全不入镜。",
            "不要两个人贴太近导致看起来像一个人。",
            "不要主考生同时做其他异常动作。",
        ],
    },
    {
        "category": "多人",
        "category_dir": "multi_person",
        "code": "person_enter_right_edge",
        "name": "右侧半个人入镜",
        "count": 10,
        "goal": "补右侧半入镜多人样本，和左侧形成对照。",
        "pose_steps": [
            "主考生保持正常考试坐姿。",
            "第二个人从画面右侧进入，先露半张脸，再露肩或半身。",
            "每张照片保持 1 秒稳定后再按空格。",
            "主考生不要转头看第二个人。",
        ],
        "quality_checks": [
            "右侧入镜的人要足够清楚，不要只露一小块衣服。",
            "主考生脸部仍在画面内。",
            "第二个人尽量不要严重运动模糊。",
        ],
        "avoid": [
            "不要让第二个人站到主考生正后方完全重叠。",
            "不要让光线把第二个人脸照得过暗。",
            "不要让主考生做打电话动作。",
        ],
    },
    {
        "category": "多人",
        "category_dir": "multi_person",
        "code": "two_persons_full",
        "name": "两个人完整入镜",
        "count": 10,
        "goal": "补稳定双人样本，确认多人检测基本盘。",
        "pose_steps": [
            "两个人都坐下或一个坐一个站，尽量都面对摄像头。",
            "两张脸都要在画面中，距离不要太远。",
            "可以拍并排、前后错位、一个人稍微侧脸。",
            "主考生保持正常考试姿态，不要伸手或打电话。",
        ],
        "quality_checks": [
            "两个人的头部都清楚可见。",
            "不要只拍到第二个人身体没有脸。",
            "画面不要过暗。",
        ],
        "avoid": [
            "不要两个人完全重叠。",
            "不要第二个人离摄像头太远只剩小点。",
            "不要主考生离开座位。",
        ],
    },
    {
        "category": "多人",
        "category_dir": "multi_person",
        "code": "person_pass_behind",
        "name": "背后或旁边经过",
        "count": 10,
        "goal": "补真实考场中路过、短暂入镜的多人边界样本。",
        "pose_steps": [
            "主考生保持正常考试状态。",
            "第二个人从后方或侧后方经过，进入画面 1 秒左右时拍照。",
            "尝试不同距离：近一点、远一点、只露上半身。",
            "如果运动模糊严重，停顿一下再拍。",
        ],
        "quality_checks": [
            "第二个人至少能看出头部或上半身。",
            "主考生不要被完全挡住。",
            "画面中确实同时有两个人。",
        ],
        "avoid": [
            "不要只拍到空背景。",
            "不要第二个人动作太快导致完全糊掉。",
            "不要主考生同时转身或伸手。",
        ],
    },
    {
        "category": "正常考试",
        "category_dir": "normal",
        "code": "normal_front_guard",
        "name": "正常正脸保护样本",
        "count": 8,
        "goal": "作为误报保护，确保优化伸胳膊/多人后正常考试不被误伤。",
        "pose_steps": [
            "正对摄像头坐好，像真实考试一样看屏幕。",
            "双手自然放在桌面、键盘或鼠标附近。",
            "可以轻微低头看题，但不要转头离开屏幕。",
            "拍几张不同距离：稍近、正常、稍远。",
        ],
        "quality_checks": [
            "只有一个人在画面内。",
            "不要做明显异常动作。",
            "光线和真实考试尽量一致。",
        ],
        "avoid": [
            "不要把手举起来。",
            "不要让别人入镜。",
            "不要拿手机。",
        ],
    },
    {
        "category": "正常考试",
        "category_dir": "normal",
        "code": "normal_side_guard",
        "name": "正常轻微侧身保护样本",
        "count": 7,
        "goal": "保护正常轻微侧身，避免被新增水平伸展规则误报。",
        "pose_steps": [
            "身体轻微向左或向右侧一点，但仍像在考试。",
            "手可以放桌面，不要伸出画面两侧。",
            "脸部尽量还在画面中，可以稍微看屏幕边缘。",
            "左右侧各拍几张。",
        ],
        "quality_checks": [
            "动作看起来仍是正常考试。",
            "单人入镜。",
            "手臂不要大幅展开。",
        ],
        "avoid": [
            "不要转身 90 度。",
            "不要把手放耳边。",
            "不要伸胳膊。",
        ],
    },
    {
        "category": "打电话",
        "category_dir": "phone_call",
        "code": "phone_left_guard",
        "name": "左手打电话保护样本",
        "count": 8,
        "goal": "保护打电话类别，防止伸胳膊规则抢走打电话样本。",
        "pose_steps": [
            "左手拿手机或空手模拟手机，贴近左耳。",
            "肘部自然弯曲，动作像通话，不是向外伸展。",
            "脸可以略微侧向左边。",
            "右手自然放下。",
        ],
        "quality_checks": [
            "左手腕或手机靠近耳朵。",
            "手臂明显弯曲。",
            "画面中只有一个人。",
        ],
        "avoid": [
            "不要把左手完全水平伸出去。",
            "不要双手同时举起。",
            "不要遮住整张脸。",
        ],
    },
    {
        "category": "打电话",
        "category_dir": "phone_call",
        "code": "phone_right_guard",
        "name": "右手打电话保护样本",
        "count": 7,
        "goal": "保护右手打电话，和右手水平伸展形成对照。",
        "pose_steps": [
            "右手靠近右耳，像在打电话。",
            "右肘弯曲，不要伸直。",
            "身体可以轻微右侧，但不要转身离开摄像头。",
            "左手自然放在桌面。",
        ],
        "quality_checks": [
            "右手腕离右耳近。",
            "动作一眼看起来像通话。",
            "不要出现第二个人。",
        ],
        "avoid": [
            "不要把右手向外伸直。",
            "不要低头到脸完全看不见。",
            "不要同时做伸懒腰动作。",
        ],
    },
]


def build_capture_plan(plan_name: str) -> list[dict]:
    if plan_name == "focused":
        return [dict(item) for item in FOCUSED_PLAN]
    if plan_name == "single":
        return [dict(item) for item in FOCUSED_PLAN if item["category_dir"] != "multi_person"]
    if plan_name == "multi":
        return [dict(item) for item in FOCUSED_PLAN if item["category_dir"] == "multi_person"]
    raise ValueError(f"Unsupported capture plan: {plan_name}")


def find_system_font() -> str | None:
    for path in [
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\msyhbd.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\simsun.ttc",
    ]:
        if Path(path).exists():
            return path
    return None


def get_font(size: int) -> ImageFont.ImageFont:
    font_path = find_system_font()
    if font_path:
        return ImageFont.truetype(font_path, size)
    return ImageFont.load_default()


def draw_text_block(
    frame: np.ndarray,
    lines: Iterable[str],
    origin: tuple[int, int],
    *,
    font_size: int = 22,
    color: tuple[int, int, int] = (255, 255, 255),
    bg_color: tuple[int, int, int] = (0, 0, 0),
    line_gap: int = 8,
) -> None:
    image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(image)
    font = get_font(font_size)
    x, y = origin
    current_y = y

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        padding = 6
        draw.rectangle(
            (
                x - padding,
                current_y - padding,
                x + width + padding,
                current_y + height + padding,
            ),
            fill=bg_color,
        )
        draw.text((x, current_y), line, font=font, fill=color)
        current_y += height + line_gap + padding

    frame[:] = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)


def print_guidance(item: dict, shot_index: int) -> None:
    print("\n" + "=" * 72)
    print(f"类别：{item['category']} | 子类：{item['name']} | 第 {shot_index}/{item['count']} 张")
    print(f"目标：{item['goal']}")
    print("\n怎么摆：")
    for index, step in enumerate(item["pose_steps"], start=1):
        print(f"  {index}. {step}")
    print("\n拍前检查：")
    for index, check in enumerate(item["quality_checks"], start=1):
        print(f"  {index}. {check}")
    print("\n不要这样拍：")
    for index, warning in enumerate(item["avoid"], start=1):
        print(f"  {index}. {warning}")
    print("=" * 72)


def ensure_output_dirs(output_dir: Path, plan: list[dict]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for item in plan:
        (output_dir / item["category_dir"]).mkdir(parents=True, exist_ok=True)


def next_split(shot_index: int, total_count: int) -> str:
    # Later shots are held out for evaluation so tuning does not overfit all captures.
    tune_count = max(1, round(total_count * 0.7))
    return "tune" if shot_index <= tune_count else "eval"


def build_filename(item: dict, shot_index: int) -> str:
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{item['code']}_{shot_index:03d}_{timestamp}.jpg"


def build_manifest_row(
    *,
    item: dict,
    filename: str,
    saved_path: Path,
    shot_index: int,
    split: str,
    camera_index: int,
) -> dict[str, str]:
    try:
        relative_path = saved_path.resolve().relative_to(ROOT_DIR).as_posix()
    except ValueError:
        relative_path = saved_path.as_posix()

    return {
        "created_at": dt.datetime.now().isoformat(timespec="seconds"),
        "split": split,
        "category": item["category"],
        "category_dir": item["category_dir"],
        "code": item["code"],
        "name": item["name"],
        "shot_index": str(shot_index),
        "filename": filename,
        "relative_path": relative_path,
        "camera_index": str(camera_index),
        "goal": item["goal"],
        "pose_steps": " | ".join(item["pose_steps"]),
        "quality_checks": " | ".join(item["quality_checks"]),
        "avoid": " | ".join(item["avoid"]),
    }


def append_manifest(output_dir: Path, row: dict[str, str]) -> None:
    manifest_path = output_dir / MANIFEST_NAME
    file_exists = manifest_path.exists()
    with manifest_path.open("a", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=MANIFEST_FIELDS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def show_countdown(window_name: str, frame: np.ndarray, seconds: int) -> None:
    for remaining in range(seconds, 0, -1):
        preview = frame.copy()
        draw_text_block(
            preview,
            [f"{remaining}", "保持动作不动，准备拍摄"],
            (preview.shape[1] // 2 - 120, preview.shape[0] // 2 - 60),
            font_size=52,
            color=(0, 255, 255),
        )
        cv2.imshow(window_name, preview)
        cv2.waitKey(1000)


def render_overlay(frame: np.ndarray, item: dict, item_index: int, plan_size: int, shot_index: int, total_done: int, total: int) -> None:
    top_lines = [
        f"[{item_index + 1}/{plan_size}] {item['category']} - {item['name']}   {shot_index}/{item['count']}",
        f"目标: {item['goal']}",
        f"总进度: {total_done}/{total}   SPACE=拍照  h=详细说明  r=重拍  n=跳过  b=上一个  q=退出",
    ]
    draw_text_block(frame, top_lines, (12, 12), font_size=20, color=(255, 255, 255))

    guide_lines = [
        "拍前检查:",
        *[f"- {text}" for text in item["quality_checks"][:3]],
        "不要这样拍:",
        *[f"- {text}" for text in item["avoid"][:3]],
    ]
    draw_text_block(frame, guide_lines, (12, frame.shape[0] - 220), font_size=18, color=(0, 255, 255))


def capture_samples(args: argparse.Namespace) -> None:
    plan = build_capture_plan(args.plan)
    output_dir = Path(args.output).resolve()
    ensure_output_dirs(output_dir, plan)
    total_target = sum(item["count"] for item in plan)

    camera = cv2.VideoCapture(args.camera)
    if not camera.isOpened():
        raise RuntimeError(f"Cannot open camera index {args.camera}")

    camera.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)

    window_name = "Targeted Sample Capture"
    item_index = 0
    shot_index = 1
    total_done = 0

    print(f"照片保存目录：{output_dir}")
    print(f"manifest：{output_dir / MANIFEST_NAME}")
    print(f"计划：{args.plan}，共 {len(plan)} 个子类，目标 {total_target} 张")
    print_guidance(plan[item_index], shot_index)

    try:
        while item_index < len(plan):
            ok, frame = camera.read()
            if not ok:
                raise RuntimeError("Failed to read frame from camera")

            if args.mirror:
                frame = cv2.flip(frame, 1)

            item = plan[item_index]
            preview = frame.copy()
            render_overlay(preview, item, item_index, len(plan), shot_index, total_done, total_target)
            cv2.imshow(window_name, preview)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == ord("h"):
                print_guidance(item, shot_index)
                continue
            if key == ord("n"):
                item_index += 1
                shot_index = 1
                if item_index < len(plan):
                    print_guidance(plan[item_index], shot_index)
                continue
            if key == ord("b") and item_index > 0:
                item_index -= 1
                shot_index = 1
                print_guidance(plan[item_index], shot_index)
                continue
            if key == ord("r") and shot_index > 1:
                shot_index -= 1
                total_done = max(0, total_done - 1)
                print(f"已回到 {item['name']} 第 {shot_index} 张，请重新拍。")
                print_guidance(item, shot_index)
                continue
            if key != ord(" "):
                continue

            show_countdown(window_name, frame, args.countdown)
            filename = build_filename(item, shot_index)
            save_path = output_dir / item["category_dir"] / filename
            cv2.imwrite(str(save_path), frame)
            split = next_split(shot_index, item["count"])
            append_manifest(
                output_dir,
                build_manifest_row(
                    item=item,
                    filename=filename,
                    saved_path=save_path,
                    shot_index=shot_index,
                    split=split,
                    camera_index=args.camera,
                ),
            )

            print(f"已保存：{save_path.relative_to(ROOT_DIR)}  split={split}")
            shot_index += 1
            total_done += 1

            if shot_index > item["count"]:
                item_index += 1
                shot_index = 1
                if item_index < len(plan):
                    print_guidance(plan[item_index], shot_index)
                else:
                    print("\n全部计划拍摄完成，可以按 q 退出。")
    finally:
        camera.release()
        cv2.destroyAllWindows()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture targeted AI proctoring samples with detailed guidance.")
    parser.add_argument("--plan", default="single", choices=["single", "multi", "focused"], help="Capture plan to use.")
    parser.add_argument("--camera", type=int, default=0, help="OpenCV camera index.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_DIR), help="Output directory.")
    parser.add_argument("--countdown", type=int, default=2, help="Countdown seconds before saving each photo.")
    parser.add_argument("--width", type=int, default=1280, help="Camera width.")
    parser.add_argument("--height", type=int, default=720, help="Camera height.")
    parser.add_argument("--no-mirror", dest="mirror", action="store_false", help="Disable mirrored preview/save.")
    parser.set_defaults(mirror=True)
    return parser.parse_args()


def main() -> None:
    capture_samples(parse_args())


if __name__ == "__main__":
    main()
