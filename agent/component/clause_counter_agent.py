import re
import logging
from pydantic import BaseModel, Field
from agno.agent import Agent
from agno.tools import tool
from config.settings import config
from app.utils.tools import get_agno_model
from api import settings

# 仿照组长的规范，定义输出的结构模型（虽然这里主要是为了规范 Agent 思考，最终我们取其中的字符串）
class ClauseCountModel(BaseModel):
    count: int = Field(description="扫描出的准确条款数量")
    prompt_hint: str = Field(description="提供给主模型的最终提示词文案")

class ClauseCounterService:
    
    @staticmethod
    async def generate(user_question: str, embd_mdl, tenant_ids, kb_ids, doc_ids) -> str:
        # 1. 意图前置拦截：不是统计问题直接 fast fail，不浪费性能
        if not re.search(r"(多少|几|共.*)(个)?(条款|条)", user_question):
            return ""
        if not doc_ids:
            return ""

        # =========================================================
        # 核心亮点：闭包定义 Tool
        # 这样写的好处是 scan_and_count 工具能直接使用外层的 embd_mdl 等变量
        # 避免了大模型调用工具时无法传递复杂 Python 对象的报错天坑！
        # =========================================================
        @tool()
        async def scan_and_count() -> int:
            """当用户问题中问到文档包含多少条、总共几条条款时，必须调用此工具进行全量扫描统计"""
            try:
                # 调用底层检索获取全部切片
                all_chunks = await settings.retriever.retrieval(
                    question="第 条",
                    embd_mdl=embd_mdl,
                    tenant_ids=tenant_ids,
                    kb_ids=kb_ids,
                    doc_ids=doc_ids,
                    page=1,
                    page_size=200, 
                    similarity_threshold=0.0, 
                    vector_similarity_weight=0.3,
                    top=1024,
                    aggs=False
                )

                chunks_data = all_chunks.get("chunks", []) if isinstance(all_chunks, dict) else all_chunks
                if not chunks_data:
                    return 0

                # 拼接全文并执行正则“理科”数数
                full_text = "".join([str(c.get("content_with_weight", "")) for c in chunks_data])
                pattern = re.compile(r"第([一二三四五六七八九十百千\d]+)条")
                max_article_num = 0
                
                # 简易中文转数字
                def zh2digit(zh_str):
                    if zh_str.isdigit(): return int(zh_str)
                    num_dict = {'零':0, '一':1, '二':2, '三':3, '四':4, '五':5, '六':6, '七':7, '八':8, '九':9}
                    unit_dict = {'十':10, '百':100, '千':1000}
                    res, tmp = 0, 0
                    for char in zh_str:
                        if char in num_dict: tmp = num_dict[char]
                        elif char in unit_dict:
                            if tmp == 0: tmp = 1
                            res += tmp * unit_dict[char]
                            tmp = 0
                    return res + tmp
                    
                for m in pattern.findall(full_text):
                    num = zh2digit(m)
                    if num > max_article_num:
                        max_article_num = num
                        
                return max_article_num
            except Exception as e:
                logging.warning(f"Tool scan_and_count 运行异常: {e}")
                return 0

        # =========================================================
        # 仿照组长代码，初始化 Agno Agent
        # =========================================================
        agent = Agent(
            role="数据统计员",
            name="条款统计器",
            output_schema=ClauseCountModel,
            use_json_mode=True,
            model=get_agno_model(),  # 直接复用内网的统一模型出口
            tools=[scan_and_count],  # 挂载我们上面定义的统计工具
            markdown=True,
            instructions=[
                "你是一个专业的数据统计分析师。",
                "当用户询问条款总数时，请严格调用 scan_and_count 工具进行核实。",
                "拿到具体的数字结果后，请将该数字填入 count 字段。",
                "并在 prompt_hint 字段中严格返回以下格式的文案：",
                "【系统全量扫描真理提示】：经底层精准统计，当前文档总计包含 {你得到的数字} 条条款。请直接根据此确切数字回答用户，禁止说库中未明确列出。"
            ]
        )

        # =========================================================
        # 执行 Agent (由于我们不需要像组长生成问题那样做页面流式反馈，
        # 我们只是在这里构建 prompt 字符串，所以不用 stream=True)
        # =========================================================
        try:
            # arun 返回的 RunResponse 会根据 output_schema 自动解析
            response = await agent.arun(input=f"请统计目标文档条款数量，原问题：{user_question}")
            
            # 安全提取模型生成的 prompt_hint
            if hasattr(response, "content") and response.content:
                if hasattr(response.content, "prompt_hint"):
                    # 如果数字大于0，才返回拼接的上下文
                    if getattr(response.content, "count", 0) > 0:
                        return f"\n\n{response.content.prompt_hint}\n\n"
        except Exception as e:
            logging.warning(f"ClauseCounter Agent 执行失败: {e}")
            
        return ""