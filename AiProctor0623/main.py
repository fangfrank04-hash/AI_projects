import io

import uvicorn
from fastapi import FastAPI, UploadFile, File
from PIL import Image
from AiProctor.Logic.ImageProctor import ImageProctor


app = FastAPI(
    title="111",
    description="AI智能体中心API服务",
    version="1.0.0"
)
# app.include_router(chat.router)
# app.add_exception_handler(ApiException, api_exception_handler)


@app.get("/test")
def root():
    import os
    test_image_path = os.path.join(os.path.dirname(__file__), "AiProctor", "test_images", "person2.jpg")
    exists = os.path.exists(test_image_path)
    if not exists:
        return {
            "code": -1,
            "msg": f"测试图片不存在（{test_image_path}），请放置一张人脸图片后重试",
            "data": None
        }
    stProctor = ImageProctor()
    resource = stProctor.GetImageFaceAngle(test_image_path)
    return {"code": 0, "msg": "识别成功", "data": resource}


@app.get("/ping")
def ping():
    return {"pong": True, "msg": "server is alive"}

# 新增文件上传接口，接收图片流
@app.post("/upload_face")
async def upload_face(file: UploadFile = File(...)):
    stProctor = ImageProctor()

    # 1. 读取上传二进制流
    file_bytes = await file.read()
    # 2. 二进制流转PIL图像（适配你内部处理逻辑）
    img_stream = io.BytesIO(file_bytes)
    pil_img = Image.open(img_stream)

    # 适配你的 GetImageFaceAngle，修改内部方法支持传入图像对象
    # 方式A：新增重载方法 GetImageFaceAngleByImg(pil_img)
    resource = stProctor.GetImageFaceAngleByImg(pil_img)
    return {"code": 0, "msg": "识别成功", "data": resource}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
