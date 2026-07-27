"""
╔══════════════════════════════════════════════════════════════════════════╗
║                                                                          ║
║     ImageProctor.py  逐行详解版 v2.0                                     ║
║     目标读者：后 端 + Python 几乎零基础的小方                              ║
║     阅读方式：把这份文件在 VS Code 里打开，                               ║
║              一边看注释一边看代码，不懂的词 Ctrl+F 搜这篇注释。            ║
║                                                                          ║
╚══════════════════════════════════════════════════════════════════════════╝

═══════════════════════════════════════════════════════════════════════════
   第〇章  Python 小白预备知识（必读，否则后面看不懂）
═══════════════════════════════════════════════════════════════════════════

1.  import 是什么意思？
    ──────────────────────
    import xxx  就是"把别人写好的工具箱拿过来用"。
    比如 import cv2 就是"把 OpenCV 这个图像处理工具箱拿来用"。
    不 import 的话，你就得自己从零写"怎么读图片"的代码，那要几千行。

    类比：你要做饭 → import 锅碗瓢盆，而不是自己捏泥烧陶。

2.  class 是什么意思？
    ────────────────────
    class 就是一个"模板"，用来造"对象"。
    类(class) = 设计图纸
    对象(instance) = 按图纸造出来的实物

    比如 ImageProctor 是一个类（设计图纸）。
    你执行 proctor = ImageProctor() 就造了一个"监考员"对象出来。
    这个对象有自己的"记忆"（变量）和自己的"能力"（方法）。

3.  self 是什么意思？
    ──────────────────
    self 就是"我自己"。在类里面写 self.xxx 就是"我这个对象的 xxx"。

    类比：你在纸上写"我的名字是小方"。
    self.name = "小方"
    → self 就是指"你这个人"，name 是你的属性。

    每个方法（函数）的第一个参数必须是 self，
    这样方法内部才知道"是谁在调用我"。

4.  单下划线 _ 和双下划线 __ 的区别？
    ─────────────────────────────────
    这是 Python 的命名约定（不是语法强制）：
    - 普通方法名：GetImageFaceAngle  → 可以外部调用
    - 双下划线开头：__ResetState      → "私有方法"，暗示"别在外面调"
    - 单下划线开头：_listRotationVector → "这个变量我不关心，占位用"

    实际上 Python 不阻止你在外部调 __ResetState()，
    但这是规矩：两条下划线 = 内部用的，别碰。

5.  print(f"...") 里面的 f 是什么意思？
    ─────────────────────────────────────
    f"..." 是 f-string（格式化字符串）。
    f"你好{name}"  →  花括号里的变量会被替换成实际值。
    比如 name="小方"，就输出 "你好小方"。

6.  def 是什么意思？
    ────────────────
    def 就是"定义一个函数/方法"。
    def 方法名(参数1, 参数2):
        要执行的代码

7.  return 是什么意思？
    ───────────────────
    return 就是"把结果交出去，结束这个函数"。
    比如 def add(a, b): return a + b
    调用 add(1, 2) → 得到 3。

    没有 return 的函数（或只写 return），相当于"做了一堆事情但不给结果"。

8.  None 是什么？
    ─────────────
    None 就是"空/没有/不存在"。等同于其他语言的 null / nil。
    if stImage is None:  意思是"如果 stImage 不存在（读取失败）"

9.  Python 的列表 [ ] 和元组 ( )
    ─────────────────────────────
    [a, b, c]  是列表(list)，里面的内容可以改，可以往里面追加。
    (a, b, c)  是元组(tuple)，里面的内容不能改，定了就是定了。

    这个文件里最常见的是 m_listText，它的每一项是一个元组 (文字, 颜色)：
    ("正常考试中 ...", (0, 255, 0))
     ↑ 第一个元素：要显示的文字
              ↑ 第二个元素：RGB颜色（绿=0,255,0  红=255,0,0）

10. enumerate() 是干什么的？
    ────────────────────────
    for i, item in enumerate(列表):
    → 同时拿到 "编号" 和 "内容"。
    比如 enumerate(["a","b","c"]) 依次给出：
      i=0, item="a"
      i=1, item="b"
      i=2, item="c"

═══════════════════════════════════════════════════════════════════════════
   第〇·五章  这个文件用了哪些"外来工具箱"（import 详解）
═══════════════════════════════════════════════════════════════════════════

cv2        ← OpenCV，最著名的图像处理库，能读图片、转换颜色、计算角度
datetime   ← Python 自带的时间库，提供"现在几点""加1秒"等功能
os         ← Python 自带的系统库，提供"列出文件夹里有哪些文件"等功能
numpy as np ← numpy，科学计算库，能处理矩阵/数组运算，as np 是起别名
mediapipe as mp ← Google 的人脸识别库，能检测 468 个面部关键点
PIL.Image  ← Pillow 库，另一套图片处理工具，读出来的格式和 OpenCV 不一样

为什么有两套图片库（OpenCV 和 PIL）？
→ 历史原因。OpenCV 更擅长图像算法，PIL 更擅长格式转换。
  这个文件里，API 接收 PIL 图片 → 转成 OpenCV 格式 → 用 OpenCV 算法处理。
"""

# ─── 下面这行是实际 import，上面的只是解释 ───
import cv2
import datetime
import os
import numpy as np
import mediapipe as mp
from PIL import Image

from .Toolkit import WriteCenterText  # 一个工具函数：在图片中央写一行文字


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  正式代码开始了                                                      ║
# ╚══════════════════════════════════════════════════════════════════════╝

class ImageProctor:
    """
    ┌─────────────────────────────────────────────────────────────┐
    │  ImageProctor = "图片监考员"                                 │
    │                                                             │
    │  这个类就是一个监考员的"设计图纸"。                           │
    │  造出来的监考员对象能：                                       │
    │    ① 接收一张图片                                            │
    │    ② 用 AI 检测图片里有几张脸                                 │
    │    ③ 如果只有一张脸，判断这个人在看哪个方向                   │
    │    ④ 判断是否违规（离开座位 / 多人 / 视线偏移）               │
    │    ⑤ 返回文字结果（正常 / 警告）                              │
    │                                                             │
    │  使用方法：                                                   │
    │    proctor = ImageProctor()           ← 造一个监考员         │
    │    result = proctor.GetImageFaceAngle("test.jpg")  ← 让它干活│
    │    print(result)  →  [("正常考试中 ...", (0, 255, 0))]       │
    └─────────────────────────────────────────────────────────────┘
    """

    # ════════════════════════════════════════════════════════════
    #  方法 ①：__init__   —   初始化（造监考员时自动执行）
    # ════════════════════════════════════════════════════════════
    def __init__(self):
        """
        __init__ 是 Python 的特殊方法。
        当你写 proctor = ImageProctor() 时，Python 会自动调用这个方法。
        你可以把它理解为"出厂设置"。

        这个 __init__ 做了两件事：
        ┌─────────────────────────────────────────────────────────┐
        │ 【大事 A】设定角度门槛（4个阈值）                         │
        │ 【大事 B】准备空白的"记录本"（4个运行时变量）             │
        └─────────────────────────────────────────────────────────┘

        先讲【大事 A】：角度门槛是什么？

        想象你在考试，电脑摄像头对着你的脸。
        AI 能算出你的头上下转了 x 度，左右转了 y 度。
        那怎么算"偏离屏幕"呢？需要一个人为设定的标准。

        这个标准就是 4 个阈值：
        ┌──────────────────────────┬───────┬────────────────────────┐
        │ 变量名                   │ 值    │ 大白话含义              │
        ├──────────────────────────┼───────┼────────────────────────┤
        │ self.m_iMaxLeftAngle     │   6   │ 左转头超过6度 → 算偏离 │
        │ self.m_iMaxRightAngle    │  -6   │ 右转头超过6度 → 算偏离 │
        │ self.m_iMaxUpAngle       │   6   │ 抬头超过6度   → 算偏离 │
        │ self.m_iMaxDownAngle     │  -1   │ 低头超过1度   → 算偏离 │
        └──────────────────────────┴───────┴────────────────────────┘

        两个容易搞混的地方：

        ❶ "左转头"为什么是 y > 6 而不是 y < 某值？
          → 这是 solvePnP 的坐标系决定的，不是直觉决定的。
            对 AI 来说：y 变大 = 头向左转，y 变小 = 头向右转。
            你不需要理解为什么，只需要记住这个映射关系。

        ❷ 为什么低头阈值(-1)比其他的(6)低那么多？
          → 因为低头看键盘的角度本来就很小（谁低头看键盘会低45度？），
            如果设成 -6，考生稍微低个头 AI 都发现不了。
            设成 -1 更灵敏，稍微一低头就能抓到。

        变量名里的命名规律（匈牙利命名法，不用管，知道意思就行）：
          m_  = member（成员变量，属于这个类的）
          i   = integer（整数）
          st  = structure（结构/对象）
          list = 列表
          str = 字符串

        再讲【大事 B】：准备"记录本"（4个运行时变量）

        监考员需要记东西，这 4 个变量就是它的"笔记本"：

        ┌─────────────────────┬──────┬──────────────────────────────┐
        │ 变量                │ 初始 │ 作用                         │
        ├─────────────────────┼──────┼──────────────────────────────┤
        │ m_listDirection     │ []   │ 存检测到的方向，如[0,1,0,3]  │
        │ m_iWarningCount     │ 0    │ 警告计数器：今天警告了几次   │
        │ m_listText          │ []   │ 最终输出：[(文本, 颜色), ...] │
        │ m_stLastTime        │ 最小 │ 上次输出的时间（防刷屏用）   │
        └─────────────────────┴──────┴──────────────────────────────┘

        m_listDirection 存什么？
        → 每检测一帧（一张图），就算出一个 Direction（0~4），
          把这个数字追加到列表里。后面取"众数"用。

        m_stLastTime 为什么设成"公元1年"（datetime.datetime.min）？
        → 这是故意设成最早的时间。后面 __CheckDirection 和
          __Checkindependence 里有一行 "如果距上次输出不到1秒就跳过"。
          设成最小时间，保证第一帧不会被跳过。
          如果设成"当前时间" → 第一帧和后一帧间隔0秒 → 第一帧就被跳过了。

        内存里的状态大概是这样的：
        ┌─────────────────────────────────────────────┐
        │  self (这个监考员对象)                       │
        │  ├── m_iMaxLeftAngle  = 6                   │
        │  ├── m_iMaxRightAngle = -6                  │
        │  ├── m_iMaxUpAngle    = 6                   │
        │  ├── m_iMaxDownAngle  = -1                  │
        │  ├── m_listDirection  = []   ← 空的         │
        │  ├── m_iWarningCount  = 0                   │
        │  ├── m_listText       = []   ← 空的         │
        │  └── m_stLastTime     = 0001-01-01 00:00:00 │
        └─────────────────────────────────────────────┘
        """

        # ─── 【大事 A】设定角度门槛 ───
        self.m_iMaxLeftAngle = 6       # 左看：y 超过 6 度 → 算偏离
        self.m_iMaxRightAngle = -6     # 右看：y 低于 -6 度 → 算偏离
        self.m_iMaxUpAngle = 6         # 上看：x 超过 6 度 → 算偏离
        self.m_iMaxDownAngle = -1      # 下看：x 低于 -1 度 → 算偏离

        # ─── 【大事 B】准备空白的记录本 ───
        self.m_listDirection = []                  # 空列表，等会儿往里塞 Direction
        self.m_iWarningCount = 0                   # 警告次数，从0开始
        self.m_listText = []                       # 输出文字，空的
        self.m_stLastTime = datetime.datetime.min   # datetime.min = "公元1年1月1日"


    # ════════════════════════════════════════════════════════════
    #  方法 ②：Start   —   桌面版入口（弹窗显示，调试用）
    # ════════════════════════════════════════════════════════════
    def Start(self, in_strImagePath: str, in_isShowMesh: bool = False, in_bWaitKey: bool = True):
        """
        ┌─────────────────────────────────────────────────────────┐
        │  这个方法不是给 API 用的！它是给桌面调试用的。           │
        │  效果：读一张图 → 分析 → 弹出一个窗口显示结果。          │
        │                                                         │
        │  参数说明：                                               │
        │    in_strImagePath      图片的文件路径（如 "test.jpg"）   │
        │    in_isShowMesh        是否在脸上画密密麻麻的网格         │
        │    in_bWaitKey          是否等用户按键后才关窗口           │
        └─────────────────────────────────────────────────────────┘

        调用链：Start → __ResetState → __ProcessImage → 弹窗

        这个方法和 GetImageFaceAngle 的核心处理一模一样，
        区别只是最后"弹窗口"而不是"返回文字"。
        """

        # ── 步骤1：把图片从硬盘读到内存 ──
        # cv2.imread(路径)：OpenCV 提供的"读图片"函数。
        # 返回的是一个 numpy 数组（可以理解为"一张巨大的数字表格"，
        # 每个格子里存一个颜色值）。
        # OpenCV 读进来的是 BGR 格式（蓝-绿-红），不是常见的 RGB。
        # 为什么？→ 历史原因，OpenCV 诞生时 BGR 是主流。
        stImage = cv2.imread(in_strImagePath)

        # 如果文件不存在或格式不对，cv2.imread 返回 None（空）
        if stImage is None:
            print(f"无法加载图片: {in_strImagePath}")
            return  # ← return 后面没东西 = "别往下走了，结束"

        # ── 步骤2：清空上一张图的"记忆" ──
        # 调用私有方法 __ResetState（方法⑥），清空所有运行时变量
        self.__ResetState()

        # ── 步骤3：核心处理 ──
        # 调用私有方法 __ProcessImage（方法⑦），这是整个类的核心
        # 返回的 stImage 是画了标注的原图副本
        stImage = self.__ProcessImage(stImage, in_isShowMesh)

        # ── 步骤4：弹窗显示结果 ──
        # cv2.imshow(窗口标题, 图片)：弹出一个窗口显示图片
        cv2.imshow('faces', stImage)

        # in_bWaitKey：是否需要等用户按键才关闭
        if in_bWaitKey:
            print("按任意键关闭窗口，或按 q 退出")
            # 一个死循环，直到用户按键
            while True:
                # cv2.waitKey(0)：等用户按一个键，返回按键的 ASCII 码
                # & 0xFF：只取低8位（兼容性问题，不用深究）
                key = cv2.waitKey(0) & 0xFF
                # ord('q') = 'q' 这个字符的 ASCII 码（113）
                # key != 255 的意思是"用户按了任意键"（255 是"没按键"）
                if key == ord('q') or key != 255:
                    break  # 跳出死循环

        # cv2.destroyAllWindows()：关闭所有 OpenCV 弹出来的窗口
        cv2.destroyAllWindows()


    # ════════════════════════════════════════════════════════════
    #  方法 ③：StartFolder   —   批量处理整个文件夹
    # ════════════════════════════════════════════════════════════
    def StartFolder(self, in_strFolderPath: str, in_isShowMesh: bool = False):
        """
        批量版 Start：把一个文件夹里的所有图片逐一处理。
        比如文件夹里有 100 张截图，就逐张弹窗显示结果。

        这个方法的逻辑很简单：
        ① 列出文件夹里所有图片文件
        ② 对每张图片调 Start()（方法②）
        """

        # 哪些后缀名算是"图片文件"
        # 注意：这是元组 ( )，不是列表 [ ]，内容不可修改
        listExtensions = ('.jpg', '.jpeg', '.png', '.bmp', '.webp')

        # os.listdir(路径)：列出文件夹里所有的文件和子文件夹名
        # f.lower()：把文件名转成小写（因为 Windows 不区分大小写）
        # f.endswith(...)：判断文件名是否以指定后缀结尾
        # sorted(...)：按字母顺序排好
        #
        # 这一行的完整意思：
        #  "把文件夹里所有名称为 .jpg/.png 等的图片文件找出来，按名字排序"
        listFiles = sorted(
            f for f in os.listdir(in_strFolderPath)
            if f.lower().endswith(listExtensions)
        )

        # 如果文件夹里一张图片都没有
        if not listFiles:
            print(f"文件夹内未找到图片: {in_strFolderPath}")
            return

        # 遍历每一张图片
        for strFileName in listFiles:
            # os.path.join(文件夹, 文件名)：把文件夹路径和文件名拼起来
            # 比如 os.path.join("C:/pics", "test.jpg") → "C:/pics/test.jpg"
            strImagePath = os.path.join(in_strFolderPath, strFileName)
            print(f"\n===== 处理: {strImagePath} =====")
            self.Start(strImagePath, in_isShowMesh=in_isShowMesh, in_bWaitKey=True)


    # ════════════════════════════════════════════════════════════
    #  方法 ④：GetImageFaceAngle   —   API入口（从文件路径读取）
    # ════════════════════════════════════════════════════════════
    def GetImageFaceAngle(self, in_strImageFile: str):
        """
        ★★★★★ 这是外部调用的主方法！★★★★★

        在 main.py 里，FastAPI 接口 /test 最终调的就是这个方法。

        你给它一个图片路径，它还你一个列表，列表里是监考结果。

        整个处理流程（5步，像工厂流水线一样线性）：

        图片文件路径
           │
           ▼
        ① cv2.imread()：从硬盘读到内存（变成一张"数字表格"）
           │
           ▼
        ② __ResetState()：擦掉黑板上上次写的字，准备记录新结果
           │
           ▼
        ③ __ProcessImage()：核心流水线
           ├── 检测有几张脸
           ├── 如果只有一张脸→算角度→判断方向→判断是否违规
           └── 把结果写到 self.m_listText（监考员笔记本的最后一页）
           │
           ▼
        ④ print()：打印到控制台（方便调试）
           │
           ▼
        ⑤ return self.m_listText：把结果交给调用方

        返回值长什么样？

        正常情况：
          [("正常考试中 ...", (0, 255, 0))]
           ↑ 文字              ↑ 颜色：绿色（0红 255绿 0蓝 = 纯绿）

        异常情况（视线偏移）：
          [("警告，考生的视线离开了屏幕", (255, 0, 0)),   ← 第一项
           ("3", (255, 0, 0))]                           ← 第二项：第3次警告
           ↑ 文字                                ↑ 颜色：红色（255红 0绿 0蓝 = 纯红）

        异常情况（离开座位）：
          [("警告，考生离开了座位", (255, 0, 0)),
           ("1", (255, 0, 0))]

        异常情况（多人）：
          [("警告，多人出现在考场", (255, 0, 0)),
           ("2", (255, 0, 0))]
        """

        # ── 步骤1：读图片（和 Start 方法一样） ──
        stImage = cv2.imread(in_strImageFile)
        if stImage is None:
            print(f"无法加载图片: {in_strImageFile}")
            return  # 读失败了就不往下走了

        # ── 步骤2：重置状态 ──
        self.__ResetState()

        # ── 步骤3：核心处理 ──
        # in_isShowMesh=False：不画网格（API 不需要可视化）
        self.__ProcessImage(stImage, in_isShowMesh=False)

        # ── 步骤4：打印（方便调试） ──
        print(self.m_listText)

        # ── 步骤5：返回结果 ──
        return self.m_listText


    # ════════════════════════════════════════════════════════════
    #  方法 ⑤：GetImageFaceAngleByImg   —   API入口（接收PIL图片）
    # ════════════════════════════════════════════════════════════
    def GetImageFaceAngleByImg(self, pil_img: Image.Image):
        """
        和 GetImageFaceAngle 功能完全一样，唯一的区别是：
        ┌─────────────────────────────────────────────────────────┐
        │ GetImageFaceAngle      输入：文件路径 "test.jpg"        │
        │ GetImageFaceAngleByImg 输入：一个 PIL 图片对象（在内存里）│
        └─────────────────────────────────────────────────────────┘

        为什么需要两个版本？

        场景1：调试/测试 → 硬盘上有图片文件
          → 用 GetImageFaceAngle("test.jpg")

        场景2：Web API 收到用户上传的图片 → 图片在内存里，没有存盘
          → 用户上传 → Python的io模块在内存里读取 → 得到一个PIL图片对象
          → 用 GetImageFaceAngleByImg(pil图片对象)
          → 省去"先存盘再读盘"的步骤

        这两种图片格式不一样！所以需要多一步转换：
        ┌──────────┐      np.array()       ┌──────────┐
        │ PIL 图片  │  ─────────────────→   │ numpy数组 │
        │ (RGB格式) │                       │ (RGB格式) │
        └──────────┘                       └─────┬────┘
                                                 │ cv2.cvtColor(..., COLOR_RGB2BGR)
                                                 ▼
                                          ┌──────────┐
                                          │ numpy数组 │
                                          │ (BGR格式) │ ← OpenCV 只认这个
                                          └──────────┘
        """

        # ── 步骤1：PIL图片 → numpy 数组 ──
        # np.array(pil_img)：把 PIL 图片对象变成一个巨大的多维数组
        # 数组形状大概是 (高度, 宽度, 3)，3 代表 R/G/B 三个通道
        # 比如一张 800×600 的图 → 数组是 600×800×3 = 144万个数字
        stImage = np.array(pil_img)

        # ── 步骤2：RGB → BGR ──
        # cv2.cvtColor(图片, 转换方式)：转换颜色通道顺序
        # cv2.COLOR_RGB2BGR：把 R,G,B 的顺序改成 B,G,R
        # 为什么？因为 PIL 读出来是 RGB，但 OpenCV 的算法期望 BGR。
        # 不转的话 → 红色变蓝色，蓝色变红色 → AI 认不出人脸。
        stImage = cv2.cvtColor(stImage, cv2.COLOR_RGB2BGR)

        if stImage is None:
            print("图片流解析失败")
            return None

        # ── 之后和 GetImageFaceAngle 完全一样 ──
        self.__ResetState()
        self.__ProcessImage(stImage, in_isShowMesh=False)
        print(self.m_listText)
        return self.m_listText


    # ════════════════════════════════════════════════════════════
    #  方法 ⑥：__ResetState   —   清空所有运行时状态
    # ════════════════════════════════════════════════════════════
    def __ResetState(self):
        """
        这个方法的作用很简单：把黑板擦干净。

        类比：你做完一道数学题，要做下一道了。
        你不会把上一道的草稿留在黑板上吧？
        这就是 __ResetState 做的事：把"笔记本"的每一页都恢复成空白。

        具体擦掉了什么：
        ┌──────────────────────┬───────────────────────────────┐
        │ 操作                 │ 效果                          │
        ├──────────────────────┼───────────────────────────────┤
        │ m_listDirection.clear() │ 方向记录清空（之前记的0,1,3全删） │
        │ m_listText.clear()      │ 输出文字清空                  │
        │ m_iWarningCount = 0     │ 警告次数归零                  │
        │ m_stLastTime = min      │ 设为"公元1年1月1日"           │
        └──────────────────────┴───────────────────────────────┘

        为什么 m_stLastTime 不设成 datetime.datetime.now()（当前时间）？

        想象一下：后面 __CheckDirection 和 __Checkindependence 里
        有一行代码：
            if 当前时间 < 上次时间 + 1秒:  跳过！
        如果设成"当前时间" → 当前时间永远不大于"当前时间+1秒" → 永远被跳过。
        所以故意设成"古代" → 当前时间肯定大于"古代+1秒" → 不会被跳过。

        这个技巧只对"单张图片模式"有意义。
        摄像头模式下，帧和帧之间本来就间隔几十毫秒，不存在这个问题。
        但代码是同一套，所以单图模式需要这个 trick。
        """

        # list.clear()：清空列表，变成 []
        self.m_listDirection.clear()
        self.m_listText.clear()

        # 直接赋值 0，覆盖原来的值
        self.m_iWarningCount = 0

        # datetime.datetime.min：Python 能表示的最早时间
        # 也就是 0001-01-01 00:00:00（公元1年1月1日）
        self.m_stLastTime = datetime.datetime.min


    # ════════════════════════════════════════════════════════════
    #  方法 ⑦：__ProcessImage   —   整个类的心脏
    # ════════════════════════════════════════════════════════════
    def __ProcessImage(self, in_stImage, in_isShowMesh: bool):
        """
        ★★★★★ 这是整个文件的灵魂方法 ★★★★★

        它就像一个工厂的生产线，图片从左边进去，结果从右边出来。

        ┌──────┐    ┌─────────────┐    ┌─────────────┐    ┌──────┐
        │ 图片 │ → │ AI 检测人脸  │ → │ 算角度+判断  │ → │ 结果 │
        └──────┘    └─────────────┘    └─────────────┘    └──────┘

        具体分4个阶段，逐个来看：

        【阶段1】初始化 AI 模型（MediaPipe FaceMesh）
          → 加载 Google 训练好的人脸关键点检测模型
          → 这个模型能在每张脸上标出 468 个点（眼睛、鼻子、嘴、脸的轮廓……）

        【阶段2】把图片喂给模型
          → 先把 BGR 转成 RGB（模型只吃 RGB）
          → 把图片送进模型 → 得到所有脸的 468 个关键点坐标
          → 用完马上关闭模型（释放显存/内存）

        【阶段3】数一数有几张脸 → iCount
          → 0 张脸 → 后面触发 "离开座位"
          → 1 张脸 → 正常 → 调 __GetFaceAngle 算角度
          → 多张脸 → 后面触发 "多人出现在考场"

        【阶段4】后续处理
          → 如果是调试模式 → 在图片上画 mesh 网格
          → 任何情况 → 调 __Checkindependence 检查人数

        ════════════════════════════════════════════════════════
        附：MediaPipe FaceMesh 是什么？
        ════════════════════════════════════════════════════════

        你可以把 MediaPipe FaceMesh 想象成一个"已经训练好的侦探"。
        你给它一张照片，它就会在照片上找出每张脸，然后在脸上标 468 个点。

        这 468 个点不是随便标的，每个点有固定的编号和位置：
        - 编号 0~10：脸的轮廓
        - 编号 33, 133, 362, 263：眼睛周围（我们这个代码用的是 33 和 263）
        - 编号 1：鼻尖
        - 编号 61, 291：嘴角
        - 编号 199：下巴尖
        ...等等

        我们只用了 468 个点里的 6 个（33, 263, 1, 61, 291, 199），
        为什么？因为这 6 个点就已经够算头部旋转角度了。
        """

        # ═════════ 【阶段1】初始化 AI 模型 ═════

        # mp.solutions.face_mesh：MediaPipe 库提供的人脸关键点检测功能
        # 这句话相当于 "从 MediaPipe 工具箱里拿出人脸关键点检测器"
        stSolutionMesh = mp.solutions.face_mesh

        # 创建一个具体的人脸检测器实例
        # FaceMesh(...) 的参数含义：
        #
        # static_image_mode=True
        #   → 告诉模型"我给的是一张一张独立的图片，不是连续的视频帧"
        #   → 模型会每张图独立检测，不会尝试追踪"上一帧的脸去哪了"
        #
        # max_num_faces=5
        #   → 最多检测 5 张脸（多于 5 张会被忽略）
        #   → 考试场景下 1 张脸正常，>1 张就算作弊了
        #
        # refine_landmarks=True
        #   → "精炼模式"：花更多算力，把 468 个点标得更准
        #   → 还会额外标出虹膜（眼球）的关键点
        #   → 我们虽然只用 6 个点，但精炼模式让这 6 个点也更准
        #
        # min_detection_confidence=0.5
        #   → "置信度"是 AI 对自己判断的把握程度，范围 0.0~1.0
        #   → 0.5 的意思是：AI 至少有 50% 把握才认为"这里有一张脸"
        #   → 设太低 → 容易误判（把墙上的画当成人脸）
        #   → 设太高 → 容易漏判（光线不好的照片检测不到）
        #
        # min_tracking_confidence=0.5
        #   → 追踪置信度（视频模式用，静态图片模式不太用到）
        #   → 保留这个参数是为了兼容性
        stFaceMesh = stSolutionMesh.FaceMesh(
            static_image_mode=True,
            max_num_faces=5,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )

        # 画图工具箱（只在调试时用到，用来在脸上画网格线）
        stSlutionDraw = mp.solutions.drawing_utils    # 画图工具
        stRrawStyle = mp.solutions.drawing_styles      # 画图样式（颜色、粗细等）

        # .copy()：复制一份图片
        # 为什么要复制？→ 防止修改原始数据。
        # Python 里，如果不复制，直接 stImage = in_stImage，
        # 那 stImage 和 in_stImage 指向的是同一块内存，
        # 改了 stImage 就等于改了原始图片。
        stImage = in_stImage.copy()

        # ═════════ 【阶段2】把图片喂给模型 ═════

        # cv2.cvtColor(图片, cv2.COLOR_BGR2RGB)
        # 把 BGR 颜色格式转换成 RGB。
        #
        # BGR vs RGB 到底是什么？
        # 一张彩色图片的每个像素由 3 个数表示（红、绿、蓝各一个数）。
        # "格式"的不同在于这 3 个数的排列顺序：
        #   RGB：红、绿、蓝（网页/手机/媒体播放器的标准）
        #   BGR：蓝、绿、红（OpenCV 的历史标准）
        #
        # 如果你把一张 BGR 图片当 RGB 显示 → 红色变蓝色，蓝色变红色，
        # 看着像阿凡达。AI 也一样，喂错格式它就认不出来了。
        stImageRGB = cv2.cvtColor(stImage, cv2.COLOR_BGR2RGB)

        # ★ 核心操作：把 RGB 图片送进 FaceMesh 模型
        # stFaceMesh.process(图片) 会返回一个结果对象，
        # 里面包含了每张脸的 468 个关键点坐标。
        # 这个操作可能要吃 GPU 算力，所以比较"重"。
        stResult = stFaceMesh.process(stImageRGB)

        # ★ 用完模型马上关闭！释放 GPU 显存/内存
        # 不关的话，显存一直占着，多跑几次图片就爆了。
        stFaceMesh.close()

        # ═════════ 【阶段3】统计人脸数量 → iCount ═════

        # stResult.multi_face_landmarks 是什么？
        #
        # 它是一个列表（list），每一项代表一张脸的 468 个关键点。
        # 如果图片里检测到 2 张脸 → 这个列表有 2 项
        # 如果图片里没有脸 → 这个值是 None（空）
        #
        # 每一项的内部结构（以第一张脸为例）：
        #   stResult.multi_face_landmarks[0].landmark  ← 这是一个列表，有 468 个元素
        #   每个元素是一个对象，有 .x .y .z 三个属性（3D 坐标）
        #
        iCount = 0  # 先假设没脸
        if stResult.multi_face_landmarks:
            # len(列表) = 列表里有多少项 → 就是有多少张脸
            iCount = len(stResult.multi_face_landmarks)

        # ── 如果恰好 1 个人 → 计算他的头部角度 ──
        if iCount == 1:
            # stResult.multi_face_landmarks[0] = 第一张脸（也是唯一一张脸）
            # 把这个脸的关键点数据和原图一起传给 __GetFaceAngle（方法⑧）
            self.__GetFaceAngle(stResult.multi_face_landmarks[0], stImage)
            # 注意：__GetFaceAngle 内部会计算出 Direction，
            #       然后追加到 self.m_listDirection 列表，
            #       最后调用 __CheckDirection 来判断是否违规。

        # ═════════ 【阶段4】画 mesh 网格（调试时才画）═════

        # 如果 isShowMesh=True（调试模式），就在图片上画网格
        if in_isShowMesh:
            # 遍历检测到的每一张脸
            for stFaceLandmarks in stResult.multi_face_landmarks:
                # 画第①组线：细密的三角形网格（覆盖整个脸）
                # FACEMESH_TESSELATION → 把脸上相邻的关键点连成三角形
                # 效果：脸被密密麻麻的小三角形覆盖
                stSlutionDraw.draw_landmarks(
                    image=stImage,
                    landmark_list=stFaceLandmarks,
                    connections=stSolutionMesh.FACEMESH_TESSELATION,
                    landmark_drawing_spec=None,     # 不画点，只画线
                    connection_drawing_spec=stRrawStyle.get_default_face_mesh_tesselation_style()
                )

                # 画第②组线：面部轮廓（脸型 + 五官边缘）
                # FACEMESH_CONTOURS → 画眼睛、鼻子、嘴、脸的轮廓线
                stSlutionDraw.draw_landmarks(
                    image=stImage,
                    landmark_list=stFaceLandmarks,
                    connections=stSolutionMesh.FACEMESH_CONTOURS,
                    landmark_drawing_spec=None,
                    connection_drawing_spec=stRrawStyle.get_default_face_mesh_contours_style()
                )

                # 画第③组线：虹膜（瞳孔区域）
                # FACEMESH_IRISES → 标出眼球的虹膜关键点
                stSlutionDraw.draw_landmarks(
                    image=stImage,
                    landmark_list=stFaceLandmarks,
                    connections=stSolutionMesh.FACEMESH_IRISES,
                    landmark_drawing_spec=None,
                    connection_drawing_spec=stRrawStyle.get_default_face_mesh_iris_connections_style()
                )

        # ═════════ 人数异常检查 ═════
        # ★ 无论 iCount 是几，都会走到这里！
        # iCount==1 → __Checkindependence 直接 return（什么都不做）
        # iCount==0 → __Checkindependence 输出"离开座位"
        # iCount>1  → __Checkindependence 输出"多人出现在考场"
        self.__Checkindependence(iCount)

        # 返回处理过的图片（如果没画 mesh，就是原图的副本）
        return stImage


    # ════════════════════════════════════════════════════════════
    #  方法 ⑧：__GetFaceAngle   —   计算头部旋转角度（最难的部分）
    # ════════════════════════════════════════════════════════════
    def __GetFaceAngle(self, in_stFaceLandmarks, in_stImage):
        """
        ★★★★★ 整个项目最核心的算法 ★★★★★

        目标：给你一张脸上 468 个关键点的坐标，算出这个人头转了多大角度。

        ════════════════════════════════════════════════════════
        基本思路（先把框架理解透，再抠细节）
        ════════════════════════════════════════════════════════

        想象你在拍一张人脸照片：
        - 如果这个人正对着镜头 → 两个眼睛一样大，鼻子在正中间
        - 如果这个人把头转向右边 → 左眼变大了，鼻子偏右了
        - 如果这个人低头 → 下巴变小了，额头变大了

        这些变化都是有规律的。AI 的工作就是：
        已知"6个关键点在照片上的2D位置" +
        已知"这6个关键点在人脸上的3D空间关系" →
        反推出"头转了多大角度"。

        这就像你看一张照片，能一眼看出照片里的人是正脸还是侧脸——
        你其实也在做"反推旋转角度"，只是你不需要数学公式，凭经验就行。

        ════════════════════════════════════════════════════════
        用了哪 6 个关键点？
        ════════════════════════════════════════════════════════

        FaceMesh 在每张脸上标了 468 个点，但全用上的话计算太慢。
        我们只挑 6 个最有代表性的：

        ┌──────┬─────────────────┬─────────────────────────────┐
        │ 编号 │ 在人脸上的位置   │ 为什么选它                   │
        ├──────┼─────────────────┼─────────────────────────────┤
        │  33  │ 左眼外眼角       │ 标定眼睛的水平位置          │
        │ 263  │ 右眼外眼角       │ 和左眼角一起确定"水平线"    │
        │   1  │ 鼻尖             │ 面部正中心，最重要的参考点  │
        │  61  │ 左嘴角           │ 标定嘴巴的水平位置          │
        │ 291  │ 右嘴角           │ 和左嘴角一起确定嘴的"水平"  │
        │ 199  │ 下巴尖           │ 标定脸部垂直方向的最低点    │
        └──────┴─────────────────┴─────────────────────────────┘

        为什么挑这6个？因为它们在人脸上是相对固定的"骨骼点"，
        不会因为做表情而大幅移动（和眉毛、脸颊的肉不一样）。

        ════════════════════════════════════════════════════════
        solvePnP + Rodrigues + RQDecomp3x3 是干嘛的？
        ════════════════════════════════════════════════════════

        这三步组成了"旋转角度计算流水线"：

        输入：6个点的 2D 坐标 + 3D 坐标 + 相机参数
                │
                ▼
        ① solvePnP：解算旋转向量
           "PnP" = Perspective-n-Point（透视 n 点定位）
           输入 2D 点和 3D 点的对应关系，输出一个"旋转向量"。
           旋转向量只用了 3 个数来表示旋转，很紧凑但不直观。
                │
                ▼
        ② Rodrigues：旋转向量 → 旋转矩阵（3×3）
           旋转矩阵用了 9 个数来表示旋转，虽然"浪费"但方便下一步分解。
                │
                ▼
        ③ RQDecomp3x3：旋转矩阵 → 欧拉角
           把 3×3 矩阵拆成绕 X/Y/Z 三个轴分别转了多少度。
                │
                ▼
        输出：x(上下角度), y(左右角度), z(倾斜角度)

        ════════════════════════════════════════════════════════
        欧拉角是啥？
        ════════════════════════════════════════════════════════

        欧拉角 = 用 3 个数描述 3D 旋转的方式。

        想象你的头是一个球，有三根轴穿过它：
        ┌─────┬───────────────────────────────────────────────┐
        │ X轴 │ 从左耳穿到右耳 → 绕X轴转 = 点头/抬头(上下)   │
        │ Y轴 │ 从头顶穿到下巴 → 绕Y轴转 = 摇头/转头(左右)   │
        │ Z轴 │ 从鼻尖穿到后脑 → 绕Z轴转 = 歪头(倾斜)        │
        └─────┴───────────────────────────────────────────────┘

        这个代码里：
        - x = listAngles[0] → 绕X轴转了多少 → 上下角度（点头/抬头）
        - y = listAngles[1] → 绕Y轴转了多少 → 左右角度（摇头/转头）
        - z = listAngles[2] → 我们不用（歪头不影响监考判断）

        ════════════════════════════════════════════════════════
        弧度 × 57.3 = 角度
        ════════════════════════════════════════════════════════

        计算机算出来的角度是"弧度"（radian），不是我们日常说的"度"（degree）。
        转换公式：角度 = 弧度 × (180 ÷ π) ≈ 弧度 × 57.3

        为什么用弧度？→ 因为数学和计算机底层用弧度更方便。
        但我们人类习惯角度 → 所以要乘 57.3 转换。

        举例：
        - 1 弧度 ≈ 57.3 度
        - 0.1 弧度 ≈ 5.73 度 → 头转了约 6 度
        - π 弧度 ≈ 180 度 → 头完全转到背面

        ════════════════════════════════════════════════════════
        怎么判断方向（Direction 0~4）
        ════════════════════════════════════════════════════════

        拿到 x（上下角度）和 y（左右角度）后，用一个 if-elif 链判断：

        ┌──────────────┬───────────────┬───────────┐
        │ 条件          │ 大白话         │ Direction │
        ├──────────────┼───────────────┼───────────┤
        │ y < -6        │ 头明显向右偏   │     1     │
        │ y > 6         │ 头明显向左偏   │     3     │
        │ x < -1        │ 头明显向下低   │     2     │
        │ x > 6         │ 头明显向上抬   │     4     │
        │ 以上都不满足   │ 基本正对着屏幕 │     0     │
        └──────────────┴───────────────┴───────────┘

        注意顺序！先判断 y（左右），再判断 x（上下）。
        为什么？因为 if y 写在了前面。
        这意味着如果一个人"同时向右看又向上看"，代码会先判断 y < -6
        → 命中 → Direction = 1（右看）→ 不会再去判断 x 了。

        这个顺序的选择是程序员决定的，不是数学决定的。
        你可以改成先判断 x 再判断 y，那就是另一套优先级。

        ════════════════════════════════════════════════════════
        这个方法最后做了什么？
        ════════════════════════════════════════════════════════

        ① 把算出的 Direction 追加到 self.m_listDirection 列表
        ② 调 self.__CheckDirection() → 判断是否违规 → 写 m_listText
        ③ 打印 x, y, Direction 到控制台（方便你调试）
        """

        # ─── 步骤1：获取图片尺寸 ───
        # in_stImage.shape 返回 (高度, 宽度, 通道数)
        # 通道数 = 3（彩色图片有 R/G/B 三个通道）
        # 用 _ 忽略第三个值，因为我们只需要高和宽
        iHeight, iWidth, _ = in_stImage.shape

        # ─── 步骤2：提取6个关键点的坐标 ───
        listFace2d = []   # 准备一个空列表，装 2D 坐标
        listFace3d = []   # 准备一个空列表，装 3D 坐标

        # in_stFaceLandmarks.landmark 是一个列表，有 468 个元素。
        # enumerate() 同时给我们 "序号 i" 和 "点的数据 stPoint"。
        for i, stPoint in enumerate(in_stFaceLandmarks.landmark):

            # stPoint 是 MediaPipe 返回的关键点对象，有3个属性：
            #   stPoint.x → 归一化的 x 坐标（0.0 到 1.0 之间的小数）
            #   stPoint.y → 归一化的 y 坐标（0.0 到 1.0 之间的小数）
            #   stPoint.z → 深度值（鼻尖是原点=0，远离相机是负数）
            #
            # "归一化"是什么意思？
            # → MediaPipe 不给你实际的像素值，而是给你"比例"。
            #    比如 stPoint.x = 0.5 → 在图片正中间（不管图片是100像素宽还是1000像素宽）
            #    你需要自己乘上图片宽度来得到实际像素值。

            # 只处理我们选的 6 个关键点
            # "or" 的意思是"任意一个满足条件就通过"
            if i == 33 or i == 263 or i == 1 or i == 61 or i == 291 or i == 199:

                # 归一化坐标 × 图片宽/高 = 实际像素坐标
                # int() 强制转成整数（像素坐标必须是整数，没有第 3.7 个像素）
                x = int(stPoint.x * iWidth)
                y = int(stPoint.y * iHeight)

                # list.append(元素)：把元素追加到列表末尾
                # 2D 坐标只有 (x, y)
                listFace2d.append((x, y))
                # 3D 坐标有 (x, y, z)，z 是深度
                listFace3d.append((x, y, stPoint.z))

        # ─── 步骤3：转成 numpy 数组 ───
        # np.array(list, dtype=np.float64)
        #   → 把 Python 列表转成 numpy 数组（矩阵）
        #   → dtype=np.float64：数据类型=64位浮点数（高精度小数）
        #   → 为什么需要numpy？因为后面的 solvePnP 只接受 numpy 格式
        #
        # 转换前：listFace2d = [(100,200), (300,200), ...]   ← Python 列表
        # 转换后：listFace2d = [[100. 200.]                   ← numpy 矩阵
        #                       [300. 200.]
        #                       ...      ]
        listFace2d = np.array(listFace2d, dtype=np.float64)
        listFace3d = np.array(listFace3d, dtype=np.float64)

        # ─── 步骤4：构造相机内参矩阵 ───
        # 相机内参矩阵 = 描述"相机怎么把三维世界映射到二维照片"的数学矩阵
        #
        # 真实摄影需要复杂的畸变校正（镜头会让直线变弯），
        # 但这里用简化模型：假设相机完美无畸变。
        #
        # 矩阵的样子：
        #   [ fx   0   cx ]     [ iWidth   0   iWidth/2  ]
        #   [ 0   fy   cy ]  =  [   0   iWidth iHeight/2 ]
        #   [ 0    0   1  ]     [   0      0      1     ]
        #
        # fx, fy = 焦距（这里用图片宽度近似）
        # cx, cy = 主点（光轴穿过传感器的位置，这里取图片正中心）
        listCameraMatrix = np.array([
            [iWidth, 0, iWidth / 2],
            [0, iWidth, iHeight / 2],
            [0, 0, 1]
        ])

        # 畸变系数 → 全为0（假设没有镜头畸变）
        # np.zeros((4,1))：创建一个4行1列的零矩阵
        listDistCoeffs = np.zeros((4, 1), dtype=np.float64)

        # ─── 步骤5：solvePnP 算旋转向量 ───
        # cv2.solvePnP(3D点, 2D点, 相机矩阵, 畸变系数)
        #   返回三个值：(成功标志, 旋转向量, 平移向量)
        #   我们用 _ 忽略不需要的返回值（成功标志和平移向量）
        #
        # solvePnP 本质上是在解这个方程：
        #   照片上的2D点 = 相机矩阵 × (旋转×3D点 + 平移)
        # 已知 2D点、3D点、相机矩阵 → 反求旋转和平移
        _, listRotationVector, _ = cv2.solvePnP(
            listFace3d, listFace2d, listCameraMatrix, listDistCoeffs
        )

        # ─── 步骤6：Rodrigues 旋转向量 → 旋转矩阵 ───
        # 旋转向量 = [rx, ry, rz]，3个数，紧凑但不好分解
        # 旋转矩阵 = 3×3 的矩阵，9个数，容易分解成绕各轴的角度
        # cv2.Rodrigues() 负责这个转换
        listRotationMatrix, _ = cv2.Rodrigues(listRotationVector)

        # ─── 步骤7：RQDecomp3x3 旋转矩阵 → 欧拉角 ───
        # 把 3×3 的旋转矩阵，拆成绕 X/Y/Z 三个轴分别转了多少
        # listAngles[0] = 绕X轴旋转（上下：点头/抬头）
        # listAngles[1] = 绕Y轴旋转（左右：摇头/转头）
        # listAngles[2] = 绕Z轴旋转（倾斜：歪头）—— 我们不用
        #
        # 这个函数返回6个值，我们只关心第一个（欧拉角），其余用 _ 忽略
        listAngles, _, _, _, _, _ = cv2.RQDecomp3x3(listRotationMatrix)

        # ─── 步骤8：弧度→角度 ───
        # 计算机用弧度（radian），人类用角度（degree）
        # 角度 = 弧度 × 180/π ≈ 弧度 × 57.3
        #
        # 为什么是 57.3？
        # → 180 ÷ 3.14159... ≈ 57.29578 ≈ 57.3
        x = listAngles[0] * 57.3   # 上下角度（绕X轴）
        y = listAngles[1] * 57.3   # 左右角度（绕Y轴）

        # ─── 步骤9：判断方向 ───
        # 现在 x 和 y 都是我们能看懂的角度了（单位：度）
        # 用之前 __init__ 里设置的阈值来判断：
        #
        # 注意：if-elif 是从上到下依次判断的！
        # 第一个满足的条件会被执行，后面的全部跳过。
        # 所以这里：y 优先于 x
        if y < self.m_iMaxRightAngle:       # y < -6  → 头向右转得太厉害了
            iDirection = 1
        elif y > self.m_iMaxLeftAngle:      # y > 6   → 头向左转得太厉害了
            iDirection = 3
        elif x < self.m_iMaxDownAngle:      # x < -1  → 头低得太厉害了
            iDirection = 2
        elif x > self.m_iMaxUpAngle:        # x > 6   → 头抬得太厉害了
            iDirection = 4
        else:                               # 都在阈值范围内 → 正对着屏幕
            iDirection = 0

        # ─── 步骤10：打印调试信息 ───
        # 这样你在运行程序时，控制台会一行一行输出类似：
        #   Angle x:[2.3] y:[-8.1] iDirection:[1]
        #   意思：上下角度2.3度（正常），左右角度-8.1度（超出-6的阈值），判定为"右看"
        print(f"Angle x:[{x}] y:[{y}] iDirection:[{iDirection}]")

        # ─── 步骤11：把方向记录到列表 ───
        # list.append(元素)：往列表末尾追加一个元素
        # 比如之前列表是 [0, 0, 1]，现在加个 0 → [0, 0, 1, 0]
        self.m_listDirection.append(iDirection)

        # ─── 步骤12：调 __CheckDirection 判断是否违规 ───
        # __CheckDirection（方法⑩）会取列表里的"众数"，
        # 然后判断：众数=0 → 正常，众数≠0 → 警告
        self.__CheckDirection()


    # ════════════════════════════════════════════════════════════
    #  方法 ⑨：__Checkindependence   —   检查人数是否异常
    # ════════════════════════════════════════════════════════════
    def __Checkindependence(self, in_iCount):
        """
        上个方法 __ProcessImage 算出 iCount（图片里有几张脸）。
        这个方法根据 iCount 判断有没有"人数异常"。

        三种情况：
        ┌──────────┬────────────────────────────────────────────┐
        │ iCount   │ 结果                                       │
        ├──────────┼────────────────────────────────────────────┤
        │ == 1     │ ✅ 正常，直接 return，不输出任何东西        │
        │ == 0     │ ❌ 图片里没有脸 → "警告，考生离开了座位"     │
        │ > 1      │ ❌ 图片里有多张脸 → "警告，多人出现在考场"   │
        └──────────┴────────────────────────────────────────────┘

        ════════════════════════════════════════════════════════
        "防抖"机制（Debounce）是干什么的？
        ════════════════════════════════════════════════════════

        这个文件被设计成既能处理"单张图片"，又能处理"连续视频帧"。
        在视频模式下，每秒可能有 30 帧（30张图），如果每帧都输出
        "警告！多人！"，那日志会爆炸。

        防抖的做法：
        ┌────────────────────────────────────────────────────┐
        │ 记下"上次输出警告的时间"                            │
        │ 每次想输出警告时检查：                               │
        │   if 现在 < 上次时间 + 1秒:                         │
        │       跳过！（刚输出过，别再刷了）                   │
        │   else:                                            │
        │       输出警告 + 更新"上次输出时间"                  │
        └────────────────────────────────────────────────────┘

        对单张图片，__ResetState 把 m_stLastTime 设成了"公元1年"，
        所以"现在"肯定大于"公元1年+1秒" → 防抖不会阻止第一次输出。

        ════════════════════════════════════════════════════════
        为什么最后要 clear() m_listDirection？
        ════════════════════════════════════════════════════════

        因为人数异常时（没人脸或多张脸），角度计算没有意义。
        之前可能存了些方向数据 → 直接清空，避免干扰下次判断。
        """

        # ── 情况1：正常（1个人）→ 啥也不做 ──
        if in_iCount == 1:
            return  # 直接结束，后面代码不执行

        # ── 防抖检查 ──
        # datetime.datetime.now()：拿到当前的日期+时间
        stNowTime = datetime.datetime.now()

        # datetime.timedelta(seconds=1)：表示"1秒的时间长度"
        # self.m_stLastTime + timedelta(seconds=1)：就是"上次时间 + 1秒"
        # 如果当前时间比"上次+1秒"还早 → 跳过去，别刷屏
        if stNowTime < self.m_stLastTime + datetime.timedelta(seconds=1):
            return  # 还没到1秒，不输出

        # 通过防抖检查 → 更新时间戳
        self.m_stLastTime = stNowTime

        # ── 情况2：没人脸 → "离开座位" ──
        if in_iCount == 0:
            # self.m_iWarningCount += 1  相当于  self.m_iWarningCount = self.m_iWarningCount + 1
            # 警告次数加 1
            self.m_iWarningCount += 1

            # 构造输出文字
            # m_listText 是一个列表，里面每个元素是一个元组 (文字, 颜色)
            # (255, 0, 0) = RGB 红色
            # str(self.m_iWarningCount)：把数字转成字符串，比如 3 → "3"
            self.m_listText = [
                ("警告，考生离开了座位", (255, 0, 0)),     # 第0项：警告文字
                (str(self.m_iWarningCount), (255, 0, 0)), # 第1项：警告次数
            ]

        # ── 情况3：多张人脸 → "多人出现" ──
        else:
            self.m_iWarningCount += 1
            self.m_listText = [
                ("警告，多人出现在考场", (255, 0, 0)),
                (str(self.m_iWarningCount), (255, 0, 0)),
            ]

        # 清空方向记录
        # 因为人数本身就不对了，方向数据没有参考价值
        self.m_listDirection.clear()


    # ════════════════════════════════════════════════════════════
    #  方法 ⑩：__CheckDirection   —   检查视线方向是否异常
    # ════════════════════════════════════════════════════════════
    def __CheckDirection(self):
        """
        这个方法检查 m_listDirection（方向记录列表），判断视线是否偏离。

        ════════════════════════════════════════════════════════
        为什么内部能区分 5 种方向，输出只分 2 种？
        ════════════════════════════════════════════════════════

        这是"计算层"和"输出层"分离的设计模式。

        ┌──────────────────────────────────────────────┐
        │                                              │
        │  计算层（__GetFaceAngle）                      │
        │  ┌─────────────────────────────────────┐     │
        │  │ Direction 0 = 正面                   │     │
        │  │ Direction 1 = 右看  ──┐              │     │
        │  │ Direction 2 = 下看  ──┤  精细区分    │     │
        │  │ Direction 3 = 左看  ──┤  5 种状态    │     │
        │  │ Direction 4 = 上看  ──┘              │     │
        │  └─────────────────────────────────────┘     │
        │          │                                    │
        │          │  数据传递（m_listDirection 列表）    │
        │          ▼                                    │
        │  输出层（__CheckDirection）                     │
        │  ┌─────────────────────────────────────┐     │
        │  │ Direction==0 → "正常考试中"          │     │
        │  │ Direction!=0 → "警告，视线离开了屏幕" │     │
        │  └─────────────────────────────────────┘     │
        │                                              │
        └──────────────────────────────────────────────┘

        为什么要这样设计？

        ① 当前需求简单：监考只需要知道"正常"还是"异常"
        ② 但数据保留得细：m_listDirection 里存的是 0~4 的精确值
        ③ 将来要改需求时，只需要改 __CheckDirection 里的 if：
           - 想区分"左看 3 次，右看 5 次" → 读 m_listDirection 就行
           - 想对"低头"和"抬头"给不同警告等级 → 改 3 行代码
           - 如果一开始就只存"正常/异常"，将来就没法统计细分了

        这叫"数据采集颗粒度要细，业务判断颗粒度可以粗"。

        ════════════════════════════════════════════════════════
        "众数投票"是什么意思？
        ════════════════════════════════════════════════════════

        在视频模式下，m_listDirection 里可能攒了好几个方向数据，
        比如：[0, 0, 1, 0, 3, 0]。
        这里面 0 出现了 4 次，1 出现 1 次，3 出现 1 次。

        用众数投票：
            iDirection = max(set(...), key=count)
            → 取出现次数最多的那个 → Direction = 0

        为什么不用"最新一个"而用"众数"？
        → 摄像头可能有抖动导致某一帧误判，众数能过滤掉偶发性错误。
           比如连续 5 帧都是 0（正面），突然一帧抖成 3（左看），
           取众数 → 还是 0 → 不会因为一帧的误判而触发假警告。

        ════════════════════════════════════════════════════════
        为什么 Direction==0 时要把 m_iWarningCount 归零？
        ════════════════════════════════════════════════════════

        这是一个"纠错机制"。
        假设考生看了屏幕 10 分钟，一共警告了 3 次。
        现在考生转回来正对着屏幕了 → 警告计数器归零。
        意思是"你现在表现正常了，之前的警告就不累计了"。

        如果不归零，今天考3小时会累计几百次警告，没有任何区分度。
        """

        # ── 步骤1：防抖（和 __Checkindependence 用的同一套逻辑）──
        stNowTime = datetime.datetime.now()
        if stNowTime < self.m_stLastTime + datetime.timedelta(seconds=1):
            return  # 还没到1秒，跳过
        self.m_stLastTime = stNowTime

        # ── 步骤2：如果列表是空的，什么都不做 ──
        # not self.m_listDirection 等价于 len(self.m_listDirection) == 0
        # 为什么可能是空的？→ 可能 __Checkindependence 刚才把它清空了
        if not self.m_listDirection:
            return

        # ── 步骤3：众数投票 ──
        # 这条语句拆开来看：
        #   set(self.m_listDirection)           → {0, 1, 3}  去重
        #   max(集合, key=self.m_listDirection.count) →
        #       对于集合里的每个值，用 count() 算它在原始列表里出现了几次
        #       取出现次数最多的那个
        #
        # 举例：m_listDirection = [0, 0, 1, 0, 3, 0]
        #   set → {0, 1, 3}
        #   count(0) = 4, count(1) = 1, count(3) = 1
        #   max → 0（出现了4次，最多）
        iDirection = max(set(self.m_listDirection), key=self.m_listDirection.count)

        # ── 步骤4：清空列表（这批数据已经消费了）──
        self.m_listDirection.clear()

        # ── 步骤5：根据众数方向判断 ──
        if iDirection == 0:
            # ★ Direction=0 = 正面 = 正常 ★
            self.m_iWarningCount = 0  # 警告计数归零（考生回归正常了）

            # 输出绿色文字：(0, 255, 0) = 纯绿色
            self.m_listText = [("正常考试中 ...", (0, 255, 0))]
        else:
            # ★ Direction=1/2/3/4 = 非正面 = 警告 ★
            self.m_iWarningCount += 1

            # 输出红色文字：(255, 0, 0) = 纯红色
            self.m_listText = [
                ("警告，考生的视线离开了屏幕", (255, 0, 0)),
                (str(self.m_iWarningCount), (255, 0, 0)),
            ]


# ╔══════════════════════════════════════════════════════════════════════╗
# ║                                                                      ║
# ║   附：完整数据流图（从入口到出口，一目了然）                           ║
# ║                                                                      ║
# ║   GetImageFaceAngle(文件路径)  或  GetImageFaceAngleByImg(PIL图片)    ║
# ║          │                                                           ║
# ║          ▼                                                           ║
# ║   【步骤1】__ResetState()                                             ║
# ║          清空：m_listDirection, m_listText, m_iWarningCount           ║
# ║          设置：m_stLastTime = 公元1年（保证第一帧不被防抖跳过）         ║
# ║          │                                                           ║
# ║          ▼                                                           ║
# ║   【步骤2】__ProcessImage(图片)                                       ║
# ║          │                                                           ║
# ║          ├─ 初始化 FaceMesh 模型                                      ║
# ║          ├─ 图片 BGR→RGB → 送进模型                                   ║
# ║          ├─ 得到 iCount（几张脸？）                                    ║
# ║          │                                                           ║
# ║          ├── iCount==1 ──→ 【步骤2a】__GetFaceAngle(第一张脸的468个点) ║
# ║          │                      │                                    ║
# ║          │                      ├─ 提取6个关键点                      ║
# ║          │                      │   (33左眼角, 263右眼角, 1鼻尖,      ║
# ║          │                      │    61左嘴角, 291右嘴角, 199下巴)    ║
# ║          │                      │                                    ║
# ║          │                      ├─ solvePnP → 旋转向量               ║
# ║          │                      ├─ Rodrigues → 旋转矩阵               ║
# ║          │                      ├─ RQDecomp3x3 → 欧拉角(x上下,y左右)   ║
# ║          │                      ├─ 弧度→角度（×57.3）                 ║
# ║          │                      ├─ if-elif 判断 → Direction (0~4)    ║
# ║          │                      ├─ 追加到 m_listDirection 列表        ║
# ║          │                      │                                    ║
# ║          │                      └─ 【步骤2a-1】__CheckDirection()     ║
# ║          │                            ├─ 防抖检查（1秒内不重复）       ║
# ║          │                            ├─ 众数投票                     ║
# ║          │                            ├─ Direction=0 → 正常（绿色）   ║
# ║          │                            └─ Direction≠0 → 警告（红色）   ║
# ║          │                                                           ║
# ║          └─ 任何情况 ──→ 【步骤2b】__Checkindependence(iCount)        ║
# ║                               ├─ iCount=0 → "离开座位"（红色）        ║
# ║                               ├─ iCount=1 → 什么都不做                ║
# ║                               └─ iCount>1 → "多人出现"（红色）        ║
# ║                                    │                                 ║
# ║                                    ▼                                 ║
# ║                              m_listText                               ║
# ║                              （最终的监考结果文字 + 颜色）             ║
# ║                                    │                                 ║
# ║                                    ▼                                 ║
# ║                              return m_listText                        ║
# ║                                                                      ║
# ╚══════════════════════════════════════════════════════════════════════╝
