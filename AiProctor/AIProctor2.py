from Logic.ImageProctor import ImageProctor

# 图片方式监考（不调用摄像头，逻辑与 AiProctor.py 一致）
stProctor = ImageProctor()

# 单张图片：修改为你的图片路径
#stProctor.Start('test_images/person2.jpg', in_isShowMesh=False)

# 批量处理文件夹内所有图片
#stProctor.StartFolder('test_images', in_isShowMesh=False)

# 仅分析并打印结果，不弹窗
str = stProctor.GetImageFaceAngle('test_images/person2.jpg')
print(f"###################{str}")

