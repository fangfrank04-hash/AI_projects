"""图片监考演示脚本（不调用摄像头）

运行方式（在项目根目录执行）：
    uv run python scripts/aiproctor2_demo.py
"""
from app.ml.image_proctor import ImageProctor

# 图片方式监考（不调用摄像头，逻辑与 aiproctor_demo.py 一致）
stProctor = ImageProctor()

# 单张图片：修改为你的图片路径
#stProctor.Start('assets/test_images/person2.jpg', in_isShowMesh=False)

# 批量处理文件夹内所有图片
#stProctor.StartFolder('assets/test_images', in_isShowMesh=False)

# 仅分析并打印结果，不弹窗
# 注意：原代码用 str 当变量名会覆盖内置函数，已修复为 result
result = stProctor.GetImageFaceAngle('assets/test_images/person2.jpg')
print(f"###################{result}")
