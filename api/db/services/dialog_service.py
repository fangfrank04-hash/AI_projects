#
#  Copyright 2024 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

# ========== 基础Python库导入 ==========
import asyncio           # 异步编程支持
import binascii          # 二进制数据处理（用于语音合成）
import logging           # 日志记录
import re                # 正则表达式（用于文本处理）
import time              # 时间处理
import uuid              # UUID生成（用于唯一标识）
from copy import deepcopy  # 深拷贝（用于复制复杂数据结构）

# 创建日志记录器
logger = logging.getLogger(__name__)

# ========== 标准库扩展导入 ==========
from datetime import datetime      # 日期时间处理
from functools import partial      # 函数部分应用（用于创建偏函数）
from timeit import default_timer as timer  # 高精度计时器

# ========== 第三方库导入 ==========
from langfuse import Langfuse      # Langfuse追踪服务（用于监控LLM调用）
from peewee import fn              # Peewee ORM的函数支持（用于数据库查询）

# ========== 项目内部模块导入 ==========
# 文件服务（处理文件相关操作）
from api.db.services.file_service import FileService

# 常量定义（模型类型、解析器类型、状态枚举）
from common.constants import LLMType, ParserType, StatusEnum

# 数据库模型（数据库连接和对话表模型）
from api.db.db_models import DB, Dialog

# 通用服务（提供基础数据库操作）
from api.db.services.common_service import CommonService

# 文档元数据服务（处理文档元数据）
from api.db.services.doc_metadata_service import DocMetadataService

# 文档识别器（智能识别用户问题中的目标文档）
from api.db.services.document_identifier import DocumentIdentifier

# 知识库服务（获取知识库信息）
from api.db.services.knowledgebase_service import KnowledgebaseService

# Langfuse租户服务（获取租户的Langfuse配置）
from api.db.services.langfuse_service import TenantLangfuseService

# LLM模型服务（封装LLM调用）
from api.db.services.llm_service import LLMBundle

# 元数据过滤工具（根据元数据过滤文档）
from common.metadata_utils import apply_meta_data_filter

# 引用元数据工具（处理文档引用信息）
from api.utils.reference_metadata_utils import (
    enrich_chunks_with_document_metadata,    # 为文本片段添加文档元数据
    resolve_reference_metadata_preferences,  # 解析引用元数据配置
)

# 租户LLM服务（获取租户的LLM配置）
from api.db.services.tenant_llm_service import TenantLLMService

# 租户模型服务（获取模型配置）
from api.db.joint_services.tenant_model_service import (
    get_model_config_by_id,              # 根据ID获取模型配置
    get_model_config_by_type_and_name,   # 根据类型和名称获取模型配置
    get_tenant_default_model_by_type,    # 获取租户默认模型
)

# 时间工具（获取时间戳、格式化日期）
from common.time_utils import current_timestamp, datetime_format

# 文本工具（处理阿拉伯数字）
from common.text_utils import normalize_arabic_digits

# 思维导图提取器（从文本中提取思维导图结构）
from rag.graphrag.general.mind_map_extractor import MindMapExtractor

# 深度研究器（高级RAG功能）
from rag.advanced_rag import DeepResearcher

# 问题标签工具（为问题添加标签特征）
from rag.app.tag import label_question

# 索引名称工具（生成数据库索引名称）
from rag.nlp.search import index_name

# 提示词生成工具
from rag.prompts.generator import (
    chunks_format,           # 格式化引用片段
    citation_prompt,         # 生成引用提示词
    cross_languages,         # 跨语言处理
    full_question,           # 多轮对话问题合并
    kb_prompt,               # 知识库内容格式化
    keyword_extraction,      # 关键词提取
    message_fit_in,          # 消息长度适配（确保不超过token限制）
    PROMPT_JINJA_ENV,        # Jinja2模板环境（用于渲染提示词）
    ASK_SUMMARY,             # 问答摘要模板
)

# Token工具（计算token数量）
from common.token_utils import num_tokens_from_string

# Tavily网络搜索工具（用于联网搜索）
from rag.utils.tavily_conn import Tavily

# 字符串工具（移除多余空格）
from common.string_utils import remove_redundant_spaces

# 全局设置（获取配置信息）
from common import settings

# ====================================
# 辅助函数：处理文档元数据
# ====================================

def _resolve_reference_metadata(request_payload=None, config=None):
    """解析参考元数据配置（用户是否需要显示文档来源）"""
    return resolve_reference_metadata_preferences(request_payload or {}, config)

def _enrich_chunks_with_document_metadata(chunks, metadata_fields=None):
    """为检索到的文本片段添加文档元数据（文档名称、作者等）"""
    enrich_chunks_with_document_metadata(chunks, metadata_fields)

def _chunk_kb_id_for_doc(row_dict, kb_ids, doc_id):
    """为文档选择合适的知识库ID"""
    # 如果只有一个知识库，直接返回它
    if len(kb_ids or []) == 1:
        return kb_ids[0]
    # 否则从数据中获取知识库ID
    return row_dict.get("kb_id") or row_dict.get("kb_id_kwd")


# ====================================
# 辅助函数：处理布尔值和网络搜索配置
# ====================================

def _normalize_internet_flag(value):
    """将各种格式的布尔值统一转换为Python的True/False"""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off", ""}:
            return False
    return None


def _should_use_web_search(prompt_config, internet=None):
    """判断是否应该使用网络搜索（Tavily API）"""
    if not prompt_config.get("tavily_api_key"):
        return False
    normalized = _normalize_internet_flag(internet)
    return normalized is True


def _resolve_reference_metadata(config, request_payload=None):
    """解析参考元数据配置（重载版本）"""
    return resolve_reference_metadata_preferences(request_payload or {}, config)


def _enrich_chunks_with_document_metadata(chunks, metadata_fields=None):
    """为文本片段添加文档元数据（重载版本）"""
    enrich_chunks_with_document_metadata(chunks, metadata_fields)



# ====================================
# 核心类：DialogService（对话服务）
# 负责对话记录的数据库操作和核心聊天逻辑
# ====================================

class DialogService(CommonService):
    # 指定这个服务对应的数据库模型是 Dialog
    model = Dialog

    @classmethod
    def save(cls, **kwargs):
        """保存新对话记录到数据库"""
        sample_obj = cls.model(**kwargs).save(force_insert=True)
        return sample_obj

    @classmethod
    def update_many_by_id(cls, data_list):
        """批量更新多条对话记录"""
        # 使用数据库事务确保原子性（要么全部成功，要么全部失败）
        with DB.atomic():
            for data in data_list:
                # 更新时间戳
                data["update_time"] = current_timestamp()
                data["update_date"] = datetime_format(datetime.now())
                # 根据ID更新记录
                cls.model.update(data).where(cls.model.id == data["id"]).execute()

    @classmethod
    @DB.connection_context()
    def get_list(cls, tenant_id, page_number, items_per_page, orderby, desc, id, name):
        """获取对话列表（分页查询）"""
        # 查询所有对话
        chats = cls.model.select()
        # 如果指定了ID，过滤
        if id:
            chats = chats.where(cls.model.id == id)
        # 如果指定了名称，过滤
        if name:
            chats = chats.where(cls.model.name == name)
        # 只显示指定租户的有效对话
        chats = chats.where((cls.model.tenant_id == tenant_id) & (cls.model.status == StatusEnum.VALID.value))
        # 排序
        if desc:
            chats = chats.order_by(cls.model.getter_by(orderby).desc())
        else:
            chats = chats.order_by(cls.model.getter_by(orderby).asc())
        # 分页
        chats = chats.paginate(page_number, items_per_page)
        # 返回字典列表
        return list(chats.dicts())

    @classmethod
    @DB.connection_context()
    def get_by_tenant_ids(
        cls,
        joined_tenant_ids,
        user_id,
        page_number,
        items_per_page,
        orderby,
        desc,
        keywords,
        id=None,
        name=None,
    ):
        """根据租户ID列表获取对话列表（支持多租户）"""
        from api.db.db_models import User

        # 指定要查询的字段
        fields = [
            cls.model.id,
            cls.model.tenant_id,
            cls.model.name,
            cls.model.description,
            cls.model.language,
            cls.model.llm_id,
            cls.model.llm_setting,
            cls.model.prompt_type,
            cls.model.prompt_config,
            cls.model.similarity_threshold,
            cls.model.vector_similarity_weight,
            cls.model.top_n,
            cls.model.top_k,
            cls.model.do_refer,
            cls.model.rerank_id,
            cls.model.kb_ids,
            cls.model.icon,
            cls.model.status,
            User.nickname,
            User.avatar.alias("tenant_avatar"),
            cls.model.update_time,
            cls.model.create_time,
        ]
        
        # 联合查询：对话表 + 用户表（获取租户昵称和头像）
        dialogs = (
            cls.model.select(*fields)
            .join(User, on=(cls.model.tenant_id == User.id))
            .where(
                # 查询条件：租户ID在列表中 或者 等于用户ID
                (cls.model.tenant_id.in_(joined_tenant_ids) | (cls.model.tenant_id == user_id)) 
                & (cls.model.status == StatusEnum.VALID.value),
            )
        )
        
        # 可选过滤条件
        if id:
            dialogs = dialogs.where(cls.model.id == id)
        if name:
            dialogs = dialogs.where(cls.model.name == name)
        if keywords:
            dialogs = dialogs.where(fn.LOWER(cls.model.name).contains(keywords.lower()))
        
        # 排序
        if desc:
            dialogs = dialogs.order_by(cls.model.getter_by(orderby).desc())
        else:
            dialogs = dialogs.order_by(cls.model.getter_by(orderby).asc())

        # 统计总数
        count = dialogs.count()

        # 分页
        if page_number and items_per_page:
            dialogs = dialogs.paginate(page_number, items_per_page)

        return list(dialogs.dicts()), count

    @classmethod
    @DB.connection_context()
    def get_all_dialogs_by_tenant_id(cls, tenant_id):
        """获取某个租户的所有对话ID（分批获取，避免一次性加载过多）"""
        fields = [cls.model.id]
        dialogs = cls.model.select(*fields).where(cls.model.tenant_id == tenant_id)
        dialogs.order_by(cls.model.create_time.asc())
        
        # 分批获取，每批100条
        offset, limit = 0, 100
        res = []
        while True:
            d_batch = dialogs.offset(offset).limit(limit)
            _temp = list(d_batch.dicts())
            if not _temp:
                break
            res.extend(_temp)
            offset += limit
        return res

    @classmethod
    @DB.connection_context()
    def get_null_tenant_llm_id_row(cls):
        """获取 tenant_llm_id 为空的记录（用于数据迁移）"""
        fields = [cls.model.id, cls.model.tenant_id, cls.model.llm_id]
        objs = cls.model.select(*fields).where(cls.model.tenant_llm_id.is_null())
        return list(objs)

    @classmethod
    @DB.connection_context()
    def get_null_tenant_rerank_id_row(cls):
        """获取 tenant_rerank_id 为空的记录（用于数据迁移）"""
        fields = [cls.model.id, cls.model.tenant_id, cls.model.rerank_id]
        objs = cls.model.select(*fields).where(cls.model.tenant_rerank_id.is_null())
        return list(objs)


# ====================================
# 核心函数：async_chat_solo（简单聊天，不查知识库）
# ====================================

async def async_chat_solo(dialog, messages, stream=True):
    """
    简单聊天函数：不查询知识库，直接调用大模型回答
    
    参数：
        dialog: 对话配置对象（包含模型设置、提示词配置等）
        messages: 消息列表（格式：[{"role": "user", "content": "..."}, ...]）
        stream: 是否流式返回（True=逐字返回，False=一次性返回）
    """
    # 获取模型类型（普通聊天模型还是图片理解模型）
    llm_type = TenantLLMService.llm_id2llm_type(dialog.llm_id)
    
    # 初始化附件变量
    attachments = ""
    image_attachments = []
    image_files = []
    
    # 如果最后一条消息有文件附件
    if "files" in messages[-1]:
        if llm_type == "chat":
            # 普通聊天模型：分离文本和图片附件
            text_attachments, image_attachments = split_file_attachments(messages[-1]["files"])
        else:
            # 图片理解模型：分离文本和原始图片文件
            text_attachments, image_files = split_file_attachments(messages[-1]["files"], raw=True)
        # 拼接所有文本附件
        attachments = "\n\n".join(text_attachments)

    # 获取模型配置（优先级：对话指定 > 租户指定 > 租户默认）
    if dialog.llm_id:
        model_config = get_model_config_by_type_and_name(dialog.tenant_id, LLMType.CHAT, dialog.llm_id)
    elif dialog.tenant_llm_id:
        model_config = get_model_config_by_id(dialog.tenant_llm_id)
    else:
        model_config = get_tenant_default_model_by_type(dialog.tenant_id, LLMType.CHAT)

    # 创建聊天模型实例
    chat_mdl = LLMBundle(dialog.tenant_id, model_config)
    factory = model_config.get("llm_factory", "")  # 模型厂商（如openai、gemini等）

    # 获取提示词配置
    prompt_config = dialog.prompt_config
    
    # 初始化语音合成模型（如果配置了）
    tts_mdl = None
    if prompt_config.get("tts"):
        default_tts_model = get_tenant_default_model_by_type(dialog.tenant_id, LLMType.TTS)
        tts_mdl = LLMBundle(dialog.tenant_id, default_tts_model)
    
    # 清理消息中的特殊标记（移除引用标记），准备发送给模型
    msg = [{"role": m["role"], "content": re.sub(r"##\d+\$\$", "", m["content"])} 
           for m in messages if m["role"] != "system"]
    
    # 如果有附件，添加到最后一条用户消息
    if attachments and msg:
        msg[-1]["content"] += attachments
    
    # 如果有图片附件，转换为多模态格式（适配不同模型）
    if llm_type == "chat" and image_attachments:
        convert_last_user_msg_to_multimodal(msg, image_attachments, factory)

    # 调用模型生成回答
    if stream:
        # 流式调用：逐字返回结果（用户体验更好）
        if llm_type == "chat":
            stream_iter = chat_mdl.async_chat_streamly_delta(
                prompt_config.get("system", ""),  # 系统提示词
                msg,  # 消息历史
                dialog.llm_setting  # 模型参数（temperature等）
            )
        else:
            # 带图片的流式调用
            stream_iter = chat_mdl.async_chat_streamly_delta(
                prompt_config.get("system", ""), 
                msg, 
                dialog.llm_setting, 
                images=image_files
            )
        
        # 处理流式返回的结果
        async for kind, value, state in _stream_with_think_delta(stream_iter):
            if kind == "marker":
                # 处理思考标记（用于显示"正在思考"状态）
                flags = {"start_to_think": True} if value == "<think>" else {"end_to_think": True}
                yield {"answer": "", "reference": {}, "audio_binary": None, "prompt": "", 
                       "created_at": time.time(), "final": False, **flags}
                continue
            # 返回回答片段
            yield {"answer": value, "reference": {}, "audio_binary": tts(tts_mdl, value), 
                   "prompt": "", "created_at": time.time(), "final": False}
    else:
        # 非流式调用：一次性返回完整回答
        if llm_type == "chat":
            answer = await chat_mdl.async_chat(
                prompt_config.get("system", ""), 
                msg, 
                dialog.llm_setting
            )
        else:
            answer = await chat_mdl.async_chat(
                prompt_config.get("system", ""), 
                msg, 
                dialog.llm_setting, 
                images=image_files
            )
        
        # 记录日志
        user_content = msg[-1].get("content", "[content not available]")
        logging.debug("User: {}|Assistant: {}".format(user_content, answer))
        
        # 返回结果
        yield {"answer": answer, "reference": {}, "audio_binary": tts(tts_mdl, answer), 
               "prompt": "", "created_at": time.time()}


# ====================================
# 核心函数：get_models（获取各种AI模型）
# ====================================

def get_models(dialog):
    """
    获取对话需要的所有模型：
    
    返回值：
        kbs: 知识库列表
        embd_mdl: 嵌入模型（用于文本向量化）
        rerank_mdl: 重排序模型（用于优化检索结果顺序）
        chat_mdl: 聊天模型（用于生成回答）
        tts_mdl: 语音合成模型（用于生成语音）
    """
    # 初始化所有模型为 None
    embd_mdl, chat_mdl, rerank_mdl, tts_mdl = None, None, None, None
    
    # 获取知识库信息
    kbs = KnowledgebaseService.get_by_ids(dialog.kb_ids)
    # 获取所有知识库使用的嵌入模型ID（去重）
    embedding_list = list(set([kb.embd_id for kb in kbs]))
    
    # 检查：所有知识库必须使用相同的嵌入模型
    if len(embedding_list) > 1:
        raise Exception("**ERROR**: Knowledge bases use different embedding models.")

    # 创建嵌入模型实例（如果有知识库）
    if embedding_list:
        embd_owner_tenant_id = kbs[0].tenant_id
        embd_model_config = get_model_config_by_type_and_name(
            embd_owner_tenant_id, LLMType.EMBEDDING, embedding_list[0]
        )
        embd_mdl = LLMBundle(embd_owner_tenant_id, embd_model_config)
        if not embd_mdl:
            raise LookupError("Embedding model(%s) not found" % embedding_list[0])

    # 获取聊天模型配置（优先级：对话指定 > 租户指定 > 租户默认）
    if dialog.llm_id:
        chat_model_config = get_model_config_by_type_and_name(
            dialog.tenant_id, LLMType.CHAT, dialog.llm_id
        )
    elif dialog.tenant_llm_id:
        chat_model_config = get_model_config_by_id(dialog.tenant_llm_id)
    else:
        chat_model_config = get_tenant_default_model_by_type(dialog.tenant_id, LLMType.CHAT)

    # 创建聊天模型实例
    chat_mdl = LLMBundle(dialog.tenant_id, chat_model_config)

    # 创建重排序模型实例（如果配置了）
    if dialog.rerank_id:
        rerank_model_config = get_model_config_by_type_and_name(
            dialog.tenant_id, LLMType.RERANK, dialog.rerank_id
        )
        rerank_mdl = LLMBundle(dialog.tenant_id, rerank_model_config)

    # 创建TTS模型实例（如果配置了）
    if dialog.prompt_config.get("tts"):
        default_tts_model_config = get_tenant_default_model_by_type(dialog.tenant_id, LLMType.TTS)
        tts_mdl = LLMBundle(dialog.tenant_id, default_tts_model_config)
    
    return kbs, embd_mdl, rerank_mdl, chat_mdl, tts_mdl


# ====================================
# 辅助函数：文件附件处理
# ====================================

def split_file_attachments(files: list[dict] | None, raw: bool = False) -> tuple[list[str], list[str] | list[dict]]:
    """
    分离文件附件中的文本和图片
    
    参数：
        files: 文件列表
        raw: 是否返回原始格式
    
    返回：
        text_attachments: 文本附件列表
        image_attachments: 图片附件列表
    """
    if not files:
        return [], []

    text_attachments = []
    if raw:
        # 原始模式：获取文件内容和图片
        file_contents, image_files = FileService.get_files(files, raw=True)
        for content in file_contents:
            if not isinstance(content, str):
                content = str(content)
            text_attachments.append(content)
        return text_attachments, image_files

    # 非原始模式：分离文本和图片
    image_attachments = []
    for content in FileService.get_files(files, raw=False):
        if not isinstance(content, str):
            content = str(content)
        # 检查是否为Data URI格式的图片
        if content.strip().startswith("data:"):
            image_attachments.append(content.strip())
            continue
        text_attachments.append(content)
    return text_attachments, image_attachments


# 正则表达式：匹配Data URI格式（data:mime;base64,内容）
_DATA_URI_RE = re.compile(r"^data:(?P<mime>[^;]+);base64,(?P<b64>[A-Za-z0-9+/=\s]+)$")


def _parse_data_uri_or_b64(s: str, default_mime: str = "image/png") -> tuple[str, str]:
    """
    解析Data URI或纯Base64字符串
    
    参数：
        s: 输入字符串（Data URI或Base64）
        default_mime: 默认MIME类型
    
    返回：
        (mime类型, Base64内容)
    """
    s = (s or "").strip()
    match = _DATA_URI_RE.match(s)
    if match:
        # 如果是Data URI格式，提取MIME和Base64
        mime = match.group("mime").strip()
        b64 = match.group("b64").strip()
        return mime, b64
    # 否则返回默认MIME和原始字符串
    return default_mime, s


def _normalize_text_from_content(content) -> str:
    """
    将各种格式的内容转换为标准化文本
    
    参数：
        content: 内容（可能是字符串、列表、字典等）
    
    返回：
        标准化后的文本字符串
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = []
        for blk in content:
            if isinstance(blk, dict):
                # 处理文本类型的块
                if blk.get("type") in {"text", "input_text"}:
                    txt = blk.get("text")
                    if txt:
                        texts.append(str(txt))
                # 处理包含text字段的字典
                elif "text" in blk and isinstance(blk.get("text"), (str, int, float)):
                    texts.append(str(blk["text"]))
        return "\n".join(texts).strip()
    # 默认转换为字符串
    return str(content)


def convert_last_user_msg_to_multimodal(msg: list[dict], image_data_uris: list[str], factory: str) -> None:
    """
    将用户消息转换为多模态格式（支持图片）
    
    参数：
        msg: 消息列表
        image_data_uris: 图片Data URI列表
        factory: LLM服务商（gemini/anthropic/openai等）
    
    返回：
        None（直接修改msg列表）
    """
    if not msg or not image_data_uris:
        return

    # 标准化服务商名称
    factory_norm = (factory or "").strip().lower()

    # 从后往前查找用户消息
    for idx in range(len(msg) - 1, -1, -1):
        if msg[idx].get("role") != "user":
            continue

        original_content = msg[idx].get("content", "")
        text = _normalize_text_from_content(original_content)

        # Gemini格式
        if factory_norm == "gemini":
            parts = []
            if text:
                parts.append({"text": text})
            for image in image_data_uris:
                mime, b64 = _parse_data_uri_or_b64(str(image), default_mime="image/png")
                parts.append({"inline_data": {"mime_type": mime, "data": b64}})
            msg[idx]["content"] = parts
            return

        # Anthropic格式
        if factory_norm == "anthropic":
            blocks = []
            if text:
                blocks.append({"type": "text", "text": text})
            for image in image_data_uris:
                mime, b64 = _parse_data_uri_or_b64(str(image), default_mime="image/png")
                blocks.append(
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": mime, "data": b64},
                    }
                )
            msg[idx]["content"] = blocks
            return

        # 默认格式（OpenAI风格）
        multimodal_content = []
        if isinstance(original_content, list):
            multimodal_content = deepcopy(original_content)
        else:
            text_content = "" if original_content is None else str(original_content)
            if text_content:
                multimodal_content.append({"type": "text", "text": text_content})

        for data_uri in image_data_uris:
            image_url = data_uri
            if not isinstance(image_url, str):
                image_url = str(image_url)
            if not image_url.startswith("data:"):
                image_url = f"data:image/png;base64,{image_url}"
            multimodal_content.append({"type": "image_url", "image_url": {"url": image_url}})

        msg[idx]["content"] = multimodal_content
        return


# ========== 引用格式修复相关常量 ==========

# 错误的引用格式模式列表（需要修复）
BAD_CITATION_PATTERNS = [
    re.compile(r"\(\s*ID\s*[: ]*\s*(\d+)\s*\)"),  # 匹配格式：(ID: 12)
    re.compile(r"\[\s*ID\s*[: ]*\s*(\d+)\s*\]"),  # 匹配格式：[ID: 12]
    re.compile(r"【\s*ID\s*[: ]*\s*(\d+)\s*】"),  # 匹配格式：【ID: 12】
    re.compile(r"ref\s*(\d+)", flags=re.IGNORECASE),  # 匹配格式：ref12、REF 12
]

# 引用标记模式（用于提取引用索引）
# 支持阿拉伯数字和阿拉伯文数字（\u0660-\u0669是阿拉伯-印度数字，\u06F0-\u06F9是波斯数字）
CITATION_MARKER_PATTERN = re.compile(r"\[(?:ID:)?([0-9\u0660-\u0669\u06F0-\u06F9]+)\]")


def repair_bad_citation_formats(answer: str, kbinfos: dict, idx: set):
    """
    修复回答中的错误引用格式
    
    参数：
        answer: 模型生成的回答
        kbinfos: 检索结果（包含chunks信息）
        idx: 引用索引集合（用于记录哪些chunk被引用）
    
    返回：
        修复后的回答和引用索引集合
    """
    max_index = len(kbinfos["chunks"])
    normalized_answer = normalize_arabic_digits(answer) or ""

    def safe_add(i):
        if 0 <= i < max_index:
            idx.add(i)
            return True
        return False

    def find_and_replace(pattern, group_index=1, repl=lambda digits: f"ID:{digits}"):
        nonlocal answer
        nonlocal normalized_answer

        matches = list(pattern.finditer(normalized_answer))
        if not matches:
            return

        parts = []
        last_idx = 0
        for match in matches:
            parts.append(answer[last_idx : match.start()])
            try:
                i = int(match.group(group_index))
            except Exception:
                parts.append(answer[match.start() : match.end()])
                last_idx = match.end()
                continue

            if safe_add(i):
                digit_start, digit_end = match.span(group_index)
                digits_original = answer[digit_start:digit_end]
                parts.append(f"[{repl(digits_original)}]")
            else:
                parts.append(answer[match.start() : match.end()])
            last_idx = match.end()

        parts.append(answer[last_idx:])
        answer = "".join(parts)
        normalized_answer = normalize_arabic_digits(answer) or ""

    for pattern in BAD_CITATION_PATTERNS:
        find_and_replace(pattern)

    return answer, idx


# ====================================
# 核心函数：async_chat（完整RAG聊天流程）
# 这是最重要的函数，实现了完整的检索增强生成流程
# ====================================

async def async_chat(dialog, messages, stream=True, **kwargs):
    """
    完整的RAG聊天函数：查询知识库并生成回答
    
    参数：
        dialog: 对话配置对象（包含知识库ID、模型设置、提示词配置等）
        messages: 消息列表（格式：[{"role": "user", "content": "..."}, ...]）
        stream: 是否流式返回（True=逐字返回，False=一次性返回）
        **kwargs: 额外参数（如internet=是否使用网络搜索，doc_ids=指定文档ID等）
    
    返回：
        生成器，产生回答片段或完整回答
    """
    logging.debug("Begin async_chat")
    
    # 断言：最后一条消息必须是用户消息
    assert messages[-1]["role"] == "user", "The last content of this conversation is not from user."
    
    # 判断是否使用网络搜索（Tavily）
    use_web_search = _should_use_web_search(dialog.prompt_config, kwargs.get("internet"))
    logging.debug("web_search kb=%s tavily=%s internet=%r enabled=%s", 
                  bool(dialog.kb_ids), 
                  bool(dialog.prompt_config.get("tavily_api_key")), 
                  kwargs.get("internet"), 
                  use_web_search)
    
    # 如果没有知识库且不使用网络搜索，直接调用简单聊天（不查知识库）
    if not dialog.kb_ids and not use_web_search:
        async for ans in async_chat_solo(dialog, messages, stream):
            yield ans
        return

    # ========== 步骤1：初始化和模型准备 ==========
    chat_start_ts = timer()  # 记录开始时间
    
    # 获取模型类型（普通聊天还是图片理解）
    llm_type = TenantLLMService.llm_id2llm_type(dialog.llm_id)
    if llm_type == "image2text":
        llm_model_config = TenantLLMService.get_model_config(dialog.tenant_id, LLMType.IMAGE2TEXT, dialog.llm_id)
    else:
        llm_model_config = TenantLLMService.get_model_config(dialog.tenant_id, LLMType.CHAT, dialog.llm_id)

    factory = llm_model_config.get("llm_factory", "")  # 模型厂商（openai/gemini等）
    max_tokens = llm_model_config.get("max_tokens", 8192)  # 模型最大token限制

    check_llm_ts = timer()

    # ========== 步骤2：初始化Langfuse追踪（可选） ==========
    langfuse_tracer = None
    trace_context = {}
    langfuse_keys = TenantLangfuseService.filter_by_tenant(tenant_id=dialog.tenant_id)
    if langfuse_keys:
        langfuse = Langfuse(
            public_key=langfuse_keys.public_key, 
            secret_key=langfuse_keys.secret_key, 
            host=langfuse_keys.host
        )
        try:
            if langfuse.auth_check():
                langfuse_tracer = langfuse
                trace_id = langfuse_tracer.create_trace_id()
                trace_context = {"trace_id": trace_id}
        except Exception:
            # 如果连接失败，跳过追踪
            pass

    check_langfuse_tracer_ts = timer()
    
    # ========== 步骤3：获取所有需要的模型 ==========
    kbs, embd_mdl, rerank_mdl, chat_mdl, tts_mdl = get_models(dialog)
    
    # 如果有工具调用会话，绑定工具到聊天模型
    toolcall_session, tools = kwargs.get("toolcall_session"), kwargs.get("tools")
    if toolcall_session and tools:
        chat_mdl.bind_tools(toolcall_session, tools)
    
    bind_models_ts = timer()

    # ========== 步骤4：准备问题和附件 ==========
    retriever = settings.retriever  # 获取检索器实例
    questions = [m["content"] for m in messages if m["role"] == "user"][-3:]  # 取最近3条用户问题
    
    attachments = None  # 用户指定的文档ID列表
    
    # 从kwargs获取文档ID（API参数方式）
    if "doc_ids" in kwargs:
        attachments = [doc_id for doc_id in kwargs["doc_ids"].split(",") if doc_id]
    
    attachments_ = ""  # 文件附件内容
    image_attachments = []  # 图片附件（用于多模态）
    image_files = []  # 原始图片文件
    
    # 从消息中获取文档ID（前端传参方式）
    if "doc_ids" in messages[-1]:
        attachments = [doc_id for doc_id in messages[-1]["doc_ids"] if doc_id]
    
    # 处理文件附件
    if "files" in messages[-1]:
        if llm_type == "chat":
            text_attachments, image_attachments = split_file_attachments(messages[-1]["files"])
        else:
            text_attachments, image_files = split_file_attachments(messages[-1]["files"], raw=True)
        attachments_ = "\n\n".join(text_attachments)

    # ========== 步骤5：获取提示词配置和字段映射 ==========
    prompt_config = dialog.prompt_config  # 获取对话的提示词配置
    include_reference_metadata, metadata_fields = _resolve_reference_metadata(prompt_config, request_payload=kwargs)
    
    # 获取知识库的字段映射（用于SQL检索）
    field_map = KnowledgebaseService.get_field_map(dialog.kb_ids)
    logging.debug(f"field_map retrieved: {field_map}")
    
    # ========== 步骤6：尝试SQL检索（如果字段映射可用） ==========
    # 如果知识库有结构化字段映射，可以尝试用SQL查询
    if field_map:
        logging.debug("Use SQL to retrieval:{}".format(questions[-1]))
        ans = await use_sql(
            questions[-1], 
            field_map, 
            dialog.tenant_id, 
            chat_mdl, 
            prompt_config.get("quote", True), 
            dialog.kb_ids
        )
        # 对于聚合查询（COUNT, SUM等），chunks可能为空但答案仍然有效
        if ans and (ans.get("reference", {}).get("chunks") or ans.get("answer")):
            # 添加文档元数据
            if include_reference_metadata and ans.get("reference", {}).get("chunks"):
                if len(dialog.kb_ids) != 1 and any(not c.get("kb_id") for c in ans["reference"]["chunks"]):
                    logging.warning(
                        "Skipping some _enrich_chunks_with_document_metadata results because "
                        "dialog.kb_ids has %d entries and use_sql returned chunks without kb_id.",
                        len(dialog.kb_ids),
                    )
                _enrich_chunks_with_document_metadata(ans["reference"]["chunks"], metadata_fields)
            yield ans  # 返回SQL查询结果
            return
        else:
            logging.debug("SQL failed or returned no results, falling back to vector search")

    # ========== 步骤7：处理提示词参数 ==========
    param_keys = [p["key"] for p in prompt_config.get("parameters", [])]
    
    # 自动修复：如果有知识库但提示词中缺少 knowledge 参数
    if dialog.kb_ids and "knowledge" not in param_keys and "{knowledge}" in prompt_config.get("system", ""):
        logging.warning("prompt_config['parameters'] is missing 'knowledge' entry despite kb_ids being set; auto-fixing.")
        prompt_config.setdefault("parameters", []).append({"key": "knowledge", "optional": False})
        param_keys.append("knowledge")
    logging.debug(f"attachments={attachments}, param_keys={param_keys}, embd_mdl={embd_mdl}")

    # 检查必须的参数是否都提供了
    for p in prompt_config.get("parameters", []):
        if p["key"] == "knowledge":
            continue  # knowledge是特殊参数，稍后填充
        if p["key"] not in kwargs and not p["optional"]:
            raise KeyError("Miss parameter: " + p["key"])
        if p["key"] not in kwargs:
            # 如果可选参数没提供，用空格替换
            prompt_config["system"] = prompt_config["system"].replace("{%s}" % p["key"], " ")

    # ========== 步骤8：问题预处理 ==========
    # 多轮对话优化：将历史对话合并为完整问题
    if len(questions) > 1 and prompt_config.get("refine_multiturn"):
        questions = [await full_question(dialog.tenant_id, dialog.llm_id, messages)]
    else:
        questions = questions[-1:]  # 只保留最后一个问题

    # 跨语言处理：将问题翻译成指定语言
    if prompt_config.get("cross_languages"):
        questions = [await cross_languages(dialog.tenant_id, dialog.llm_id, questions[0], prompt_config["cross_languages"])]

    # 元数据过滤：根据配置的元数据过滤文档
    if dialog.meta_data_filter:
        attachments = await apply_meta_data_filter(
            dialog.meta_data_filter,
            None,
            questions[-1],
            chat_mdl,
            attachments,
            kb_ids=dialog.kb_ids,
            metas_loader=lambda: DocMetadataService.get_flatted_meta_by_kbs(dialog.kb_ids),
        )

    # 关键词提取：增强问题检索效果
    if prompt_config.get("keyword", False):
        questions[-1] = questions[-1] + "," + await keyword_extraction(chat_mdl, questions[-1])
    
    refine_question_ts = timer()

    # ========== 步骤9：向量检索（核心步骤） ==========
    thought = ""
    kbinfos = {"total": 0, "chunks": [], "doc_aggs": []}  # 检索结果
    knowledges = []  # 格式化后的知识库内容

    if "knowledge" in param_keys:
        logging.debug("Proceeding with retrieval")
        tenant_ids = list(set([kb.tenant_id for kb in kbs]))  # 获取租户ID列表
        
        # 方式A：深度推理模式（DeepResearcher）
        if prompt_config.get("reasoning", False) or kwargs.get("reasoning"):
            reasoner = DeepResearcher(
                chat_mdl,
                prompt_config,
                partial(
                    retriever.retrieval,
                    embd_mdl=embd_mdl,
                    tenant_ids=tenant_ids,
                    kb_ids=dialog.kb_ids,
                    page=1,
                    page_size=dialog.top_n,
                    similarity_threshold=0.2,
                    vector_similarity_weight=0.3,
                    doc_ids=attachments,
                ),
                internet_enabled=use_web_search,
            )
            queue = asyncio.Queue()

            async def callback(msg: str):
                nonlocal queue
                await queue.put(msg + "<br/>")

            await callback("<START_DEEP_RESEARCH>")
            task = asyncio.create_task(reasoner.research(kbinfos, questions[-1], questions[-1], callback=callback))
            
            # 处理深度推理的进度消息
            while True:
                msg = await queue.get()
                if msg.find("<START_DEEP_RESEARCH>") == 0:
                    yield {"answer": "<retrieving>", "reference": {}, "audio_binary": None, "final": False}
                elif msg.find("<END_DEEP_RESEARCH>") == 0:
                    yield {"answer": "</retrieving>", "reference": {}, "audio_binary": None, "final": False}
                    break
                else:
                    yield {"answer": msg, "reference": {}, "audio_binary": None, "final": False}

            await task

        # 方式B：普通向量检索
        else:
            if embd_mdl:
                # ========== 智能文档识别 ==========
                # 如果用户没有指定文档，但问题可能针对特定文档，尝试自动识别
                target_doc_ids = attachments
                if not target_doc_ids and DocumentIdentifier.should_use_document_filter(questions[-1]):
                    try:
                        # 获取知识库中的所有文档列表
                        from api.db.services.document_service import DocumentService
                        docs_list, _ = DocumentService.get_list(
                            kb_id=dialog.kb_ids[0] if len(dialog.kb_ids) == 1 else None,
                            page_number=1,
                            items_per_page=1000,  # 获取所有文档
                            orderby="create_time",
                            desc=True,
                            keywords=None
                        )
                        
                        # 调用文档识别器，让LLM根据问题匹配文档名称
                        identified_doc_id = await DocumentIdentifier.identify_target_document(
                            question=questions[-1],
                            documents=docs_list,
                            chat_mdl=chat_mdl
                        )
                        
                        if identified_doc_id:
                            target_doc_ids = [identified_doc_id]
                            logging.info(f"智能文档识别成功，将只检索文档: {identified_doc_id}")
                        else:
                            logging.info("智能文档识别未找到目标文档，将检索所有文档")
                    except Exception as e:
                        logging.warning(f"智能文档识别失败: {e}，将检索所有文档")
                
                # ========== 执行向量检索 ==========
                kbinfos = await retriever.retrieval(
                    " ".join(questions),        # 查询文本
                    embd_mdl,                   # 嵌入模型
                    tenant_ids,                 # 租户ID列表
                    dialog.kb_ids,              # 知识库ID列表
                    1,                          # 页码
                    dialog.top_n,               # 每页大小
                    dialog.similarity_threshold, # 相似度阈值
                    dialog.vector_similarity_weight,  # 向量相似度权重
                    doc_ids=target_doc_ids,     # 目标文档ID（可选）
                    top=dialog.top_k,           # 返回前top_k个结果
                    aggs=True,                  # 是否返回文档聚合信息
                    rerank_mdl=rerank_mdl,      # 重排序模型（可选）
                    rank_feature=label_question(" ".join(questions), kbs),  # 问题标签特征
                )
                
                # TOC增强：根据目录结构优化检索结果
                if prompt_config.get("toc_enhance"):
                    cks = await retriever.retrieval_by_toc(" ".join(questions), kbinfos["chunks"], tenant_ids, chat_mdl, dialog.top_n)
                    if cks:
                        kbinfos["chunks"] = cks
                
                # 获取子切块（处理文档层级结构）
                kbinfos["chunks"] = retriever.retrieval_by_children(kbinfos["chunks"], tenant_ids)
            
            # 网络搜索增强
            if use_web_search:
                tav = Tavily(prompt_config["tavily_api_key"])
                tav_res = tav.retrieve_chunks(" ".join(questions))
                kbinfos["chunks"].extend(tav_res["chunks"])
                kbinfos["doc_aggs"].extend(tav_res["doc_aggs"])
            
            # 知识图谱检索（可选）
            if prompt_config.get("use_kg"):
                default_chat_model = get_tenant_default_model_by_type(dialog.tenant_id, LLMType.CHAT)
                ck = await settings.kg_retriever.retrieval(
                    " ".join(questions), 
                    tenant_ids, 
                    dialog.kb_ids, 
                    embd_mdl, 
                    LLMBundle(dialog.tenant_id, default_chat_model)
                )
                if ck["content_with_weight"]:
                    kbinfos["chunks"].insert(0, ck)  # 知识图谱结果放在最前面

    # 为检索到的切块添加文档元数据
    if include_reference_metadata:
        logging.debug(
            "reference_metadata enrichment enabled for async_chat: chunk_count=%d metadata_fields=%s",
            len(kbinfos.get("chunks", [])),
            metadata_fields,
        )
        _enrich_chunks_with_document_metadata(kbinfos.get("chunks", []), metadata_fields)

    # ========== 步骤10：格式化知识库内容为prompt格式 ==========
    # kb_prompt函数将检索到的chunks转换为适合LLM输入的格式
    knowledges = kb_prompt(kbinfos, max_tokens)
    logging.debug("{}->{}".format(" ".join(questions), "\n->".join(knowledges)))

    retrieval_ts = timer()
    
    # 如果没有找到知识且配置了空响应，返回预设内容
    if not knowledges and prompt_config.get("empty_response"):
        empty_res = prompt_config["empty_response"]
        yield {"answer": empty_res, "reference": kbinfos, "prompt": "\n\n### Query:\n%s" % " ".join(questions), 
               "audio_binary": tts(tts_mdl, empty_res), "final": True}
        return

    # ========== 步骤11：构建最终Prompt ==========
    # 将知识库内容添加到kwargs，用于格式化系统提示词
    kwargs["knowledge"] = "\n------\n" + "\n\n------\n\n".join(knowledges)
    gen_conf = dialog.llm_setting  # 模型生成配置

    # 构建消息列表
    # 第一条是系统消息，包含格式化后的系统提示词和附件
    msg = [{"role": "system", "content": prompt_config["system"].format(**kwargs) + attachments_}]
    
    # 引用提示词（用于让模型生成带引用标记的回答）
    prompt4citation = ""
    if knowledges and (prompt_config.get("quote", True) and kwargs.get("quote", True)):
        prompt4citation = citation_prompt()
    
    # 添加用户和助手的历史消息（移除系统消息和引用标记）
    msg.extend([{"role": m["role"], "content": re.sub(r"##\d+\$\$", "", m["content"])} 
                for m in messages if m["role"] != "system"])
    
    # 确保消息总数不超过模型的token限制
    used_token_count, msg = message_fit_in(msg, int(max_tokens * 0.95))
    
    # 如果有图片附件，转换为多模态格式
    if llm_type == "chat" and image_attachments:
        convert_last_user_msg_to_multimodal(msg, image_attachments, factory)
    
    assert len(msg) >= 2, f"message_fit_in has bug: {msg}"
    prompt = msg[0]["content"]  # 提取系统提示词（用于日志和追踪）

    # 调整生成token数限制
    if "max_tokens" in gen_conf:
        gen_conf["max_tokens"] = min(gen_conf["max_tokens"], max_tokens - used_token_count)

    # ========== 步骤12：定义回答后处理函数 ==========
    def decorate_answer(answer):
        """
        后处理回答：添加引用、统计token使用、记录日志等
        """
        # nonlocal声明：使用外部函数的变量
        nonlocal embd_mdl, prompt_config, knowledges, kwargs, kbinfos, prompt, retrieval_ts, questions, langfuse_tracer, used_token_count

        refs = []  # 引用信息
        
        # 分离思考内容和实际回答（如果有的话）
        ans = answer.split("</think>")
        think = ""
        if len(ans) == 2:
            think = ans[0] + "</think>"
            answer = ans[1]

        # 如果需要添加引用
        if knowledges and (prompt_config.get("quote", True) and kwargs.get("quote", True)):
            idx = set([])  # 引用的chunk索引集合
            normalized_answer = normalize_arabic_digits(answer) or ""
            
            # 如果模型没有生成引用标记，自动插入
            if embd_mdl and not CITATION_MARKER_PATTERN.search(normalized_answer):
                answer, idx = retriever.insert_citations(
                    answer,
                    [ck["content_ltks"] for ck in kbinfos["chunks"]],
                    [ck["vector"] for ck in kbinfos["chunks"]],
                    embd_mdl,
                    tkweight=1 - dialog.vector_similarity_weight,
                    vtweight=dialog.vector_similarity_weight,
                )
            else:
                # 解析模型生成的引用标记
                for match in CITATION_MARKER_PATTERN.finditer(normalized_answer):
                    i = int(match.group(1))
                    if i < len(kbinfos["chunks"]):
                        idx.add(i)

            # 修复不规范的引用格式
            answer, idx = repair_bad_citation_formats(answer, kbinfos, idx)

            # 根据引用的chunk获取对应的文档ID
            idx = set([kbinfos["chunks"][int(i)]["doc_id"] for i in idx])
            recall_docs = [d for d in kbinfos["doc_aggs"] if d["doc_id"] in idx]
            if not recall_docs:
                recall_docs = kbinfos["doc_aggs"]
            kbinfos["doc_aggs"] = recall_docs

            # 复制引用信息，移除向量数据（节省空间）
            refs = deepcopy(kbinfos)
            for c in refs["chunks"]:
                if c.get("vector"):
                    del c["vector"]

        # 处理API Key错误
        if answer.lower().find("invalid key") >= 0 or answer.lower().find("invalid api") >= 0:
            answer += " Please set LLM API-Key in 'User Setting -> Model providers -> API-Key'"
        
        finish_chat_ts = timer()

        # ========== 计算各阶段耗时 ==========
        total_time_cost = (finish_chat_ts - chat_start_ts) * 1000
        check_llm_time_cost = (check_llm_ts - chat_start_ts) * 1000
        check_langfuse_tracer_cost = (check_langfuse_tracer_ts - check_llm_ts) * 1000
        bind_embedding_time_cost = (bind_models_ts - check_langfuse_tracer_ts) * 1000
        refine_question_time_cost = (refine_question_ts - bind_models_ts) * 1000
        retrieval_time_cost = (retrieval_ts - refine_question_ts) * 1000
        generate_result_time_cost = (finish_chat_ts - retrieval_ts) * 1000

        # 计算输入和输出 token
        input_tokens = used_token_count
        output_tokens = num_tokens_from_string(think + answer)
        total_tokens = input_tokens + output_tokens

        # 构建完整的prompt日志（包含性能统计）
        tk_num = output_tokens
        prompt += "\n\n### Query:\n%s" % " ".join(questions)
        prompt = (
            f"{prompt}\n\n"
            "## Time elapsed:\n"
            f"  - Total: {total_time_cost:.1f}ms\n"
            f"  - Check LLM: {check_llm_time_cost:.1f}ms\n"
            f"  - Check Langfuse tracer: {check_langfuse_tracer_cost:.1f}ms\n"
            f"  - Bind models: {bind_embedding_time_cost:.1f}ms\n"
            f"  - Query refinement(LLM): {refine_question_time_cost:.1f}ms\n"
            f"  - Retrieval: {retrieval_time_cost:.1f}ms\n"
            f"  - Generate answer: {generate_result_time_cost:.1f}ms\n\n"
            "## Token usage:\n"
            f"  - Input tokens: {input_tokens}\n"
            f"  - Output tokens: {output_tokens}\n"
            f"  - Total tokens: {total_tokens}\n"
            f"  - Token speed: {int(output_tokens / (generate_result_time_cost / 1000.0))}/s"
        )

        # 更新Langfuse追踪（如果启用）
        if langfuse_tracer and "langfuse_generation" in locals():
            langfuse_output = "\n" + re.sub(r"^.*?(### Query:.*)", r"\1", prompt, flags=re.DOTALL)
            langfuse_output = {"time_elapsed:": re.sub(r"\n", "  \n", langfuse_output), "created_at": time.time()}
            langfuse_generation.update(output=langfuse_output)
            langfuse_generation.end()

        # 返回最终结果
        return {"answer": think + answer, "reference": refs, "prompt": re.sub(r"\n", "  \n", prompt), 
                "created_at": time.time(), "token_usage": {"input_tokens": input_tokens, 
                                                          "output_tokens": output_tokens, 
                                                          "total_tokens": total_tokens}}

    # ========== 步骤13：启动Langfuse追踪（如果启用） ==========
    if langfuse_tracer:
        langfuse_generation = langfuse_tracer.start_generation(
            trace_context=trace_context, 
            name="chat", 
            model=llm_model_config["llm_name"], 
            input={"prompt": prompt, "prompt4citation": prompt4citation, "messages": msg}
        )

    # ========== 步骤14：调用LLM生成回答 ==========
    if stream:
        # 流式调用（逐字返回，用户体验更好）
        if llm_type == "chat":
            stream_iter = chat_mdl.async_chat_streamly_delta(prompt + prompt4citation, msg[1:], gen_conf)
        else:
            stream_iter = chat_mdl.async_chat_streamly_delta(prompt + prompt4citation, msg[1:], gen_conf, images=image_files)
        
        last_state = None
        async for kind, value, state in _stream_with_think_delta(stream_iter):
            last_state = state
            if kind == "marker":
                # 处理思考标记
                flags = {"start_to_think": True} if value == "<think>" else {"end_to_think": True}
                yield {"answer": "", "reference": {}, "audio_binary": None, "final": False, **flags}
                continue
            # 返回回答片段
            yield {"answer": value, "reference": {}, "audio_binary": tts(tts_mdl, value), "final": False}
        
        # 流式结束后，处理完整回答
        full_answer = last_state.full_text if last_state else ""
        if full_answer:
            final = decorate_answer(_extract_visible_answer(thought + full_answer))
            final["final"] = True
            final["audio_binary"] = None
            yield final
    else:
        # 非流式调用（一次性返回完整回答）
        if llm_type == "chat":
            answer = await chat_mdl.async_chat(prompt + prompt4citation, msg[1:], gen_conf)
        else:
            answer = await chat_mdl.async_chat(prompt + prompt4citation, msg[1:], gen_conf, images=image_files)
        
        user_content = msg[-1].get("content", "[content not available]")
        logging.debug("User: {}|Assistant: {}".format(user_content, answer))
        
        # 后处理回答
        res = decorate_answer(answer)
        res["audio_binary"] = tts(tts_mdl, answer)
        yield res

    return


# ====================================
# 核心函数：use_sql（SQL检索）
# 将自然语言问题转换为SQL查询并执行
# ====================================

async def use_sql(question, field_map, tenant_id, chat_mdl, quota=True, kb_ids=None):
    """
    将自然语言问题转换为SQL查询并执行
    
    工作流程：
    1. 检测文档引擎类型（Infinity/OceanBase/Elasticsearch）
    2. 让LLM生成对应的SQL语句
    3. 注入经过验证的kb_id过滤器（防止SQL注入）
    4. 执行查询
    5. 返回格式化结果和引用
    
    参数：
        question: 用户的自然语言问题
        field_map: 文档索引的字段映射（字段名->类型）
        tenant_id: 租户ID，用于确定目标表/索引名
        chat_mdl: LLM模型实例，用于生成SQL
        quota: 是否启用token配额检查（默认True）
        kb_ids: 知识库ID列表，限制查询范围
    
    返回：
        dict: {"answer": 格式化回答, "reference": 引用信息, "prompt": 使用的提示词}
        None: 如果SQL生成或执行失败
    """
    logging.debug(f"use_sql: Question: {question}")

    # ========== 步骤1：确定使用的文档引擎 ==========
    if settings.DOC_ENGINE_INFINITY:
        doc_engine = "infinity"
    elif settings.DOC_ENGINE_OCEANBASE:
        doc_engine = "oceanbase"
    else:
        doc_engine = "es"  # Elasticsearch

    # ========== SQL注入防护：UUID验证函数 ==========
    def _assert_valid_uuid(value: str, label: str = "id") -> None:
        """验证值是否为有效的UUID格式（防止SQL注入）"""
        try:
            uuid.UUID(str(value))
        except (ValueError, AttributeError, TypeError):
            logger.warning("SQL injection guard rejected invalid %s value (length=%d)", label, len(str(value)))
            raise ValueError(f"Invalid {label} format: {value!r}")

    # ========== 步骤2：构建表名 ==========
    # Elasticsearch: ragflow_{tenant_id} (kb_id在WHERE子句中)
    # Infinity: ragflow_{tenant_id}_{kb_id} (每个知识库有自己的表)
    base_table = index_name(tenant_id)
    if doc_engine == "infinity" and kb_ids and len(kb_ids) == 1:
        # Infinity: 将kb_id附加到表名（先验证）
        _assert_valid_uuid(kb_ids[0], "kb_id")
        table_name = f"{base_table}_{kb_ids[0]}"
        logging.debug(f"use_sql: Using Infinity table name: {table_name}")
    else:
        # Elasticsearch/OpenSearch: 使用基础索引名
        table_name = base_table
        logging.debug(f"use_sql: Using ES/OS table name: {table_name}")

    # 文档名字段名（不同引擎不同）
    expected_doc_name_column = "docnm" if doc_engine == "infinity" else "docnm_kwd"

    # ========== 辅助函数：检查是否有引用所需的列 ==========
    def has_source_columns(columns):
        """检查结果集是否包含构建引用所需的列（doc_id, docnm/docnm_kwd）"""
        normalized_names = {str(col.get("name", "")).lower() for col in columns}
        return "doc_id" in normalized_names and bool({"docnm_kwd", "docnm"} & normalized_names)

    # ========== 辅助函数：判断是否为聚合查询 ==========
    def is_aggregate_sql(sql_text):
        """判断SQL是否包含聚合函数（COUNT, SUM, AVG, MAX, MIN, DISTINCT）"""
        return bool(re.search(r"(count|sum|avg|max|min|distinct)\s*\(", (sql_text or "").lower()))

    # ========== 辅助函数：清理LLM生成的SQL ==========
    def normalize_sql(sql):
        """清理LLM生成的SQL，移除多余标记"""
        logging.debug(f"use_sql: Raw SQL from LLM: {repr(sql[:500])}")
        # 移除思考块（</think>...）
        sql = re.sub(r"</think>\n.*?\n\s*", "", sql, flags=re.DOTALL)
        sql = re.sub(r"思考\n.*?\n", "", sql, flags=re.DOTALL)
        # 移除markdown代码块（```sql ... ```）
        sql = re.sub(r"```(?:sql)?\s*", "", sql, flags=re.IGNORECASE)
        sql = re.sub(r"```\s*$", "", sql, flags=re.IGNORECASE)
        # 移除末尾分号（某些引擎不喜欢）
        return sql.rstrip().rstrip(";").strip()

    # ========== 辅助函数：添加知识库过滤条件 ==========
    def add_kb_filter(sql):
        """为ES/OceanBase引擎添加经过验证的kb_id WHERE过滤器"""
        # Infinity已经在表名中包含了知识库信息，不需要额外过滤
        if doc_engine == "infinity" or not kb_ids:
            return sql

        # 验证所有kb_ids都是UUID格式（防止SQL注入）
        for kid in kb_ids:
            _assert_valid_uuid(kid, "kb_id")

        # 构建过滤条件：单个知识库或多个知识库用OR连接
        if len(kb_ids) == 1:
            kb_filter = f"kb_id = '{kb_ids[0]}'"
        else:
            kb_filter = "(" + " OR ".join([f"kb_id = '{kid}'" for kid in kb_ids]) + ")"

        # 将过滤条件添加到SQL中
        if "where " not in sql.lower():
            o = sql.lower().split("order by")
            if len(o) > 1:
                sql = o[0] + f" WHERE {kb_filter}  order by " + o[1]
            else:
                sql += f" WHERE {kb_filter}"
        elif "kb_id =" not in sql.lower() and "kb_id=" not in sql.lower():
            sql = re.sub(r"\bwhere\b ", f"where {kb_filter} and ", sql, flags=re.IGNORECASE)
        return sql

    # ========== 辅助函数：判断是否为行数统计问题 ==========
    def is_row_count_question(q: str) -> bool:
        """判断问题是否询问数据集/表格的总行数"""
        q = (q or "").lower()
        if not re.search(r"\bhow many rows\b|\bnumber of rows\b|\brow count\b", q):
            return False
        return bool(re.search(r"\bdataset\b|\btable\b|\bspreadsheet\b|\bexcel\b", q))

    # ========== 步骤3：构建针对特定引擎的SQL提示词 ==========
    if doc_engine == "infinity":
        # Infinity使用JSON字段存储数据，需要特殊处理
        json_field_names = list(field_map.keys())
        row_count_override = f"SELECT COUNT(*) AS rows FROM {table_name}" if is_row_count_question(question) else None
        
        sys_prompt = """You are a Database Administrator. Write SQL for a table with JSON 'chunk_data' column.

JSON Extraction: json_extract_string(chunk_data, '$.FieldName')
Numeric Cast: CAST(json_extract_string(chunk_data, '$.FieldName') AS INTEGER/FLOAT)
NULL Check: json_extract_isnull(chunk_data, '$.FieldName') == false

RULES:
1. Use EXACT field names (case-sensitive) from the list below
2. For SELECT: include doc_id, docnm, and json_extract_string() for requested fields
3. For COUNT: use COUNT(*) or COUNT(DISTINCT json_extract_string(...))
4. Add AS alias for extracted field names
5. DO NOT select 'content' field
6. Only add NULL check (json_extract_isnull() == false) in WHERE clause when:
   - Question asks to "show me" or "display" specific columns
   - Question mentions "not null" or "excluding null"
   - Add NULL check for count specific column
   - DO NOT add NULL check for COUNT(*) queries (COUNT(*) counts all rows including nulls)
7. Output ONLY the SQL, no explanations"""
        
        user_prompt = """Table: {}
Fields (EXACT case): {}
{}
Question: {}
Write SQL using json_extract_string() with exact field names. Include doc_id, docnm for data queries. Only SQL.""".format(
            table_name, ", ".join(json_field_names), "\n".join([f"  - {field}" for field in json_field_names]), question
        )
    elif doc_engine == "oceanbase":
        # OceanBase也使用JSON字段存储数据
        json_field_names = list(field_map.keys())
        row_count_override = f"SELECT COUNT(*) AS rows FROM {table_name}" if is_row_count_question(question) else None
        sys_prompt = """You are a Database Administrator. Write SQL for a table with JSON 'chunk_data' column.

JSON Extraction: json_extract_string(chunk_data, '$.FieldName')
Numeric Cast: CAST(json_extract_string(chunk_data, '$.FieldName') AS INTEGER/FLOAT)
NULL Check: json_extract_isnull(chunk_data, '$.FieldName') == false

RULES:
1. Use EXACT field names (case-sensitive) from the list below
2. For SELECT: include doc_id, docnm_kwd, and json_extract_string() for requested fields
3. For COUNT: use COUNT(*) or COUNT(DISTINCT json_extract_string(...))
4. Add AS alias for extracted field names
5. DO NOT select 'content' field
6. Only add NULL check (json_extract_isnull() == false) in WHERE clause when:
   - Question asks to "show me" or "display" specific columns
   - Question mentions "not null" or "excluding null"
   - Add NULL check for count specific column
   - DO NOT add NULL check for COUNT(*) queries (COUNT(*) counts all rows including nulls)
7. Output ONLY the SQL, no explanations"""
        user_prompt = """Table: {}
Fields (EXACT case): {}
{}
Question: {}
Write SQL using json_extract_string() with exact field names. Include doc_id, docnm_kwd for data queries. Only SQL.""".format(
            table_name, ", ".join(json_field_names), "\n".join([f"  - {field}" for field in json_field_names]), question
        )
    else:
        # Elasticsearch/OpenSearch:直接访问字段
        row_count_override = None
        sys_prompt = """You are a Database Administrator. Write SQL queries.

RULES:
1. Use EXACT field names from the schema below (e.g., product_tks, not product)
2. Quote field names starting with digit: "123_field"
3. Add IS NOT NULL in WHERE clause when:
   - Question asks to "show me" or "display" specific columns
4. Include doc_id/docnm in non-aggregate statement
5. Output ONLY the SQL, no explanations"""
        user_prompt = """Table: {}
Available fields:
{}
Question: {}
Write SQL using exact field names above. Include doc_id, docnm_kwd for data queries. Only SQL.""".format(table_name, "\n".join([f"  - {k} ({v})" for k, v in field_map.items()]), question)

    # ========== 步骤4：执行SQL查询（带重试机制） ==========
    tried_times = 0

    async def get_table(custom_user_prompt=None):
        """执行SQL查询的内部函数"""
        nonlocal sys_prompt, user_prompt, question, tried_times, row_count_override
        
        # 如果是行数统计问题且没有自定义prompt，使用预定义的SQL
        if row_count_override and custom_user_prompt is None:
            sql = row_count_override
        else:
            # 让LLM生成SQL
            prompt = custom_user_prompt if custom_user_prompt is not None else user_prompt
            sql = await chat_mdl.async_chat(sys_prompt, [{"role": "user", "content": prompt}], {"temperature": 0.06})
        
        # 清理和处理SQL
        sql = normalize_sql(sql)
        sql = add_kb_filter(sql)

        logging.debug(f"{question} get SQL(refined): {sql}")
        tried_times += 1
        logging.debug(f"use_sql: Executing SQL retrieval (attempt {tried_times})")
        
        # 执行SQL检索
        tbl = settings.retriever.sql_retrieval(sql, format="json")
        if tbl is None:
            logging.debug("use_sql: SQL retrieval returned None")
            return None, sql
        logging.debug(f"use_sql: SQL retrieval completed, got {len(tbl.get('rows', []))} rows")
        return tbl, sql

    async def repair_table_for_missing_source_columns(previous_sql):
        """修复缺少引用列的SQL（添加doc_id和docnm_kwd/docnm）"""
        if doc_engine in ("infinity", "oceanbase"):
            json_field_names = list(field_map.keys())
            repair_prompt = """Table name: {};
JSON fields available in 'chunk_data' column (use exact names):
{}

Question: {}
Previous SQL:
{}

The previous SQL result is missing required source columns for citations.
Rewrite SQL to keep the same query intent and include doc_id and {} in the SELECT list.
For extracted JSON fields, use json_extract_string(chunk_data, '$.field_name').
Return ONLY SQL.""".format(table_name, "\n".join([f"  - {field}" for field in json_field_names]), question, previous_sql, expected_doc_name_column)
        else:
            repair_prompt = """Table name: {}
Available fields:
{}

Question: {}
Previous SQL:
{}

The previous SQL result is missing required source columns for citations.
Rewrite SQL to keep the same query intent and include doc_id and docnm_kwd in the SELECT list.
Return ONLY SQL.""".format(table_name, "\n".join([f"  - {k} ({v})" for k, v in field_map.items()]), question, previous_sql)
        return await get_table(custom_user_prompt=repair_prompt)

    try:
        tbl, sql = await get_table()
        logging.debug(f"use_sql: Initial SQL execution SUCCESS. SQL: {sql}")
        logging.debug(f"use_sql: Retrieved {len(tbl.get('rows', []))} rows, columns: {[c['name'] for c in tbl.get('columns', [])]}")
    except Exception as e:
        logging.warning(f"use_sql: Initial SQL execution FAILED with error: {e}")
        # Build retry prompt with error information
        if doc_engine in ("infinity", "oceanbase"):
            # Build Infinity error retry prompt
            json_field_names = list(field_map.keys())
            user_prompt = """
Table name: {};
JSON fields available in 'chunk_data' column (use these exact names in json_extract_string):
{}

Question: {}
Please write the SQL using json_extract_string(chunk_data, '$.field_name') with the field names from the list above. Only SQL, no explanations.


The SQL error you provided last time is as follows:
{}

Please correct the error and write SQL again using json_extract_string(chunk_data, '$.field_name') syntax with the correct field names. Only SQL, no explanations.
""".format(table_name, "\n".join([f"  - {field}" for field in json_field_names]), question, e)
        else:
            # Build ES/OS error retry prompt
            user_prompt = """
        Table name: {};
        Table of database fields are as follows (use the field names directly in SQL):
        {}

        Question are as follows:
        {}
        Please write the SQL using the exact field names above, only SQL, without any other explanations or text.


        The SQL error you provided last time is as follows:
        {}

        Please correct the error and write SQL again using the exact field names above, only SQL, without any other explanations or text.
        """.format(table_name, "\n".join([f"{k} ({v})" for k, v in field_map.items()]), question, e)
        try:
            tbl, sql = await get_table()
            logging.debug(f"use_sql: Retry SQL execution SUCCESS. SQL: {sql}")
            logging.debug(f"use_sql: Retrieved {len(tbl.get('rows', []))} rows on retry")
        except Exception:
            logging.error("use_sql: Retry SQL execution also FAILED, returning None")
            return

    if len(tbl["rows"]) == 0:
        logging.warning(f"use_sql: No rows returned from SQL query, returning None. SQL: {sql}")
        return None

    if not is_aggregate_sql(sql) and not has_source_columns(tbl.get("columns", [])):
        logging.warning(f"use_sql: Non-aggregate SQL missing required source columns; retrying once. SQL: {sql}")
        try:
            repaired_tbl, repaired_sql = await repair_table_for_missing_source_columns(sql)
            if repaired_tbl and len(repaired_tbl.get("rows", [])) > 0 and has_source_columns(repaired_tbl.get("columns", [])):
                tbl, sql = repaired_tbl, repaired_sql
                logging.info(f"use_sql: Source-column SQL repair succeeded. SQL: {sql}")
            else:
                logging.warning(f"use_sql: Source-column SQL repair did not provide required columns. Repaired SQL: {repaired_sql}")
        except Exception as e:
            logging.warning(f"use_sql: Source-column SQL repair failed, returning best-effort answer. Error: {e}")

    logging.debug(f"use_sql: Proceeding with {len(tbl['rows'])} rows to build answer")

    docid_idx = set([ii for ii, c in enumerate(tbl["columns"]) if c["name"].lower() == "doc_id"])
    doc_name_idx = set([ii for ii, c in enumerate(tbl["columns"]) if c["name"].lower() in ["docnm_kwd", "docnm"]])
    kb_id_idx = set([ii for ii, c in enumerate(tbl["columns"]) if c["name"].lower() in ["kb_id", "kb_id_kwd"]])

    logging.debug(f"use_sql: All columns: {[(i, c['name']) for i, c in enumerate(tbl['columns'])]}")
    logging.debug(f"use_sql: docid_idx={docid_idx}, doc_name_idx={doc_name_idx}, kb_id_idx={kb_id_idx}")

    column_idx = [ii for ii in range(len(tbl["columns"])) if ii not in (docid_idx | doc_name_idx | kb_id_idx)]

    logging.debug(f"use_sql: column_idx={column_idx}")
    logging.debug(f"use_sql: field_map={field_map}")

    # ========== 步骤5：构建结果（格式化表格和引用） ==========
    
    # 辅助函数：将列名映射为显示名称
    def map_column_name(col_name):
        """将SQL列名映射为用户友好的显示名称"""
        if col_name.lower() == "count(star)":
            return "COUNT(*)"

        # 首先尝试从表达式中提取AS别名（如 json_extract_string(...) AS alias）
        as_match = re.search(r"\s+AS\s+([^\s,)]+)", col_name, re.IGNORECASE)
        if as_match:
            alias = as_match.group(1).strip("\"'")
            # 使用别名查找显示名称
            if alias in field_map:
                display = field_map[alias]
                return re.sub(r"(/.*|（[^（）]+）)", "", display)
            # 如果别名不在field_map中，尝试不区分大小写匹配
            for field_key, display_value in field_map.items():
                if field_key.lower() == alias.lower():
                    return re.sub(r"(/.*|（[^（）]+）)", "", display_value)
            # 如果没找到映射，返回别名本身
            return alias

        # 尝试直接映射（对于简单列名）
        if col_name in field_map:
            display = field_map[col_name]
            return re.sub(r"(/.*|（[^（）]+）)", "", display)

        # 尝试不区分大小写匹配
        col_lower = col_name.lower()
        for field_key, display_value in field_map.items():
            if field_key.lower() == col_lower:
                return re.sub(r"(/.*|（[^（）]+）)", "", display_value)

        # 对于聚合表达式或复杂表达式，尝试替换字段名
        result = col_name
        for field_name, display_name in field_map.items():
            result = result.replace(field_name, display_name)

        # 清理后缀模式
        result = re.sub(r"(/.*|（[^（）]+）)", "", result)
        return result

    # ========== 构建Markdown表格格式的回答 ==========
    # 列标题行
    columns = "|" + "|".join([map_column_name(tbl["columns"][i]["name"]) for i in column_idx]) + ("|Source|" if docid_idx and doc_name_idx else "|")

    # 分隔线行
    line = "|" + "|".join(["------" for _ in range(len(column_idx))]) + ("|------|" if docid_idx and docid_idx else "")

    # 构建数据行
    rows = []
    for row_idx, r in enumerate(tbl["rows"]):
        # 创建行字典，处理SQL列顺序可能不同的情况
        row_dict = {tbl["columns"][i]["name"]: r[i] for i in range(len(tbl["columns"])) if i < len(r)}
        if row_idx == 0:
            logging.debug(f"use_sql: First row data: {row_dict}")
        row_values = []
        for col_idx in column_idx:
            col_name = tbl["columns"][col_idx]["name"]
            value = row_dict.get(col_name, " ")
            row_values.append(remove_redundant_spaces(str(value)).replace("None", " "))
        # 如果有引用信息，添加Source列
        if docid_idx and doc_name_idx:
            row_values.append(f" ##{row_idx}$$")
        row_str = "|" + "|".join(row_values) + "|"
        if re.sub(r"[ |]+", "", row_str):
            rows.append(row_str)
    
    # 合并行（quota参数在这里没有实际区别）
    rows = "\n".join(rows)
    # 清理时间戳格式
    rows = re.sub(r"T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+Z)?\|", "|", rows)

    # ========== 处理缺少doc_id或docnm_kwd的情况 ==========
    if not docid_idx or not doc_name_idx:
        logging.warning(f"use_sql: SQL missing required doc_id or docnm_kwd field. docid_idx={docid_idx}, doc_name_idx={doc_name_idx}. SQL: {sql}")
        
        # 对于聚合查询（COUNT, SUM等），单独获取doc_id用于引用
        if is_aggregate_sql(sql):
            # 保持原始表格格式作为回答
            answer = "\n".join([columns, line, rows])

            # 从原始SQL中提取WHERE子句，用于获取源文档
            where_match = re.search(r"\bwhere\b(.+?)(?:\bgroup by\b|\border by\b|\blimit\b|$)", sql, re.IGNORECASE)
            if where_match:
                where_clause = where_match.group(1).strip()
                # 构建获取源字段的查询
                chunks_kb_column = ", kb_id" if not (kb_ids and len(kb_ids) == 1) else ""
                chunks_sql = f"select doc_id, {expected_doc_name_column}{chunks_kb_column} from {table_name} where {where_clause}"
                # 添加LIMIT避免获取过多数据
                if "limit" not in chunks_sql.lower():
                    chunks_sql += " limit 20"
                logging.debug(f"use_sql: Fetching chunks with SQL: {chunks_sql}")
                try:
                    chunks_tbl = settings.retriever.sql_retrieval(chunks_sql, format="json")
                    if chunks_tbl.get("rows") and len(chunks_tbl["rows"]) > 0:
                        # 构建引用信息
                        chunks_did_idx = next((i for i, c in enumerate(chunks_tbl["columns"]) if c["name"].lower() == "doc_id"), None)
                        chunks_dn_idx = next((i for i, c in enumerate(chunks_tbl["columns"]) if c["name"].lower() in ["docnm_kwd", "docnm"]), None)
                        chunks_kb_idx = next((i for i, c in enumerate(chunks_tbl["columns"]) if c["name"].lower() in ["kb_id", "kb_id_kwd"]), None)
                        if chunks_did_idx is not None and chunks_dn_idx is not None:
                            chunks = []
                            for r in chunks_tbl["rows"]:
                                chunk = {"doc_id": r[chunks_did_idx], "docnm_kwd": r[chunks_dn_idx]}
                                row_dict = {chunks_tbl["columns"][i]["name"]: r[i] for i in range(len(chunks_tbl["columns"])) if i < len(r)}
                                kb_id = _chunk_kb_id_for_doc(row_dict, kb_ids, chunk["doc_id"])
                                if kb_id:
                                    chunk["kb_id"] = kb_id
                                elif chunks_kb_idx is not None:
                                    chunk["kb_id"] = r[chunks_kb_idx]
                                chunks.append(chunk)
                            # 构建文档聚合信息
                            doc_aggs = {}
                            for r in chunks_tbl["rows"]:
                                doc_id = r[chunks_did_idx]
                                doc_name = r[chunks_dn_idx]
                                if doc_id not in doc_aggs:
                                    doc_aggs[doc_id] = {"doc_name": doc_name, "count": 0}
                                doc_aggs[doc_id]["count"] += 1
                            doc_aggs_list = [{"doc_id": did, "doc_name": d["doc_name"], "count": d["count"]} for did, d in doc_aggs.items()]
                            logging.debug(f"use_sql: Returning aggregate answer with {len(chunks)} chunks from {len(doc_aggs)} documents")
                            return {"answer": answer, "reference": {"chunks": chunks, "doc_aggs": doc_aggs_list}, "prompt": sys_prompt}
                except Exception as e:
                    logging.warning(f"use_sql: Failed to fetch chunks: {e}")
            # 降级：返回没有引用的回答
            return {"answer": answer, "reference": {"chunks": [], "doc_aggs": []}, "prompt": sys_prompt}
        # 其他情况返回表格格式
        return {"answer": "\n".join([columns, line, rows]), "reference": {"chunks": [], "doc_aggs": []}, "prompt": sys_prompt}

    # ========== 构建完整结果 ==========
    docid_idx = list(docid_idx)[0]
    doc_name_idx = list(doc_name_idx)[0]
    
    # 统计每个文档出现的次数
    doc_aggs = {}
    for r in tbl["rows"]:
        if r[docid_idx] not in doc_aggs:
            doc_aggs[r[docid_idx]] = {"doc_name": r[doc_name_idx], "count": 0}
        doc_aggs[r[docid_idx]]["count"] += 1

    # 构建最终结果
    result = {
        "answer": "\n".join([columns, line, rows]),
        "reference": {
            "chunks": [
                {
                    key: value
                    for key, value in {
                        "doc_id": r[docid_idx],
                        "docnm_kwd": r[doc_name_idx],
                        "kb_id": _chunk_kb_id_for_doc(
                            {tbl["columns"][i]["name"]: r[i] for i in range(len(tbl["columns"])) if i < len(r)},
                            kb_ids,
                            r[docid_idx],
                        ),
                    }.items()
                    if value
                }
                for r in tbl["rows"]
            ],
            "doc_aggs": [{"doc_id": did, "doc_name": d["doc_name"], "count": d["count"]} for did, d in doc_aggs.items()],
        },
        "prompt": sys_prompt,
    }
    logging.debug(f"use_sql: Returning answer with {len(result['reference']['chunks'])} chunks from {len(doc_aggs)} documents")
    return result


# ====================================
# 辅助函数：文本清理（用于语音合成）
# ====================================

def clean_tts_text(text: str) -> str:
    """清理文本，使其适合语音合成（TTS）"""
    if not text:
        return ""

    # 处理UTF-8编码问题
    text = text.encode("utf-8", "ignore").decode("utf-8", "ignore")

    # 移除控制字符（除了换行符）
    text = re.sub(r"[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]", "", text)

    # 移除表情符号
    emoji_pattern = re.compile(
        "[\U0001f600-\U0001f64f\U0001f300-\U0001f5ff\U0001f680-\U0001f6ff\U0001f1e0-\U0001f1ff\U00002700-\U000027bf\U0001f900-\U0001f9ff\U0001fa70-\U0001faff\U0001fad0-\U0001faff]+", 
        flags=re.UNICODE
    )
    text = emoji_pattern.sub("", text)

    # 合并连续空格
    text = re.sub(r"\s+", " ", text).strip()

    # 限制长度（避免TTS服务报错）
    MAX_LEN = 500
    if len(text) > MAX_LEN:
        text = text[:MAX_LEN]

    return text


# ====================================
# 辅助函数：语音合成
# ====================================

def tts(tts_mdl, text):
    """调用语音合成模型，将文本转换为语音"""
    if not tts_mdl or not text:
        return None
    
    # 清理文本
    text = clean_tts_text(text)
    if not text:
        return None
    
    # 调用TTS模型生成语音
    bin = b""
    try:
        for chunk in tts_mdl.tts(text):
            bin += chunk
    except Exception as e:
        logging.error(f"TTS failed: {e}, text={text!r}")
        return None
    
    # 将二进制语音数据转换为十六进制字符串
    return binascii.hexlify(bin).decode("utf-8")


# ====================================
# 辅助类：流式思考状态管理
# ====================================

class _ThinkStreamState:
    """管理流式输出中的思考标记状态"""
    def __init__(self) -> None:
        self.full_text = ""           # 完整的文本
        self.last_idx = 0             # 上次处理到的位置
        self.endswith_think = False   # 是否以</think>结尾
        self.last_full = ""           # 上次的完整文本
        self.last_model_full = ""     # 上次模型返回的完整文本
        self.in_think = False         # 是否在思考块中
        self.buffer = ""              # 缓冲区


# ====================================
# 辅助函数：提取可见回答
# ====================================

def _extract_visible_answer(text: str) -> str:
    """从文本中提取可见的回答部分（移除或保留思考标记）"""
    text = text or ""
    if "</think>" not in text:
        return re.sub(r"</?think>", "", text)

    # 分离思考部分和回答部分
    thought, answer = text.rsplit("</think>", 1)
    thought = re.sub(r"</?think>", "", thought).strip()
    answer = re.sub(r"</?think>", "", answer)
    
    if not thought:
        return answer
    return f"<think>{thought}</think>{answer}"


# ====================================
# 辅助函数：获取思考增量
# ====================================

def _next_think_delta(state: _ThinkStreamState) -> str:
    """计算流式输出中的增量部分（处理思考标记）"""
    full_text = state.full_text
    if full_text == state.last_full:
        return ""
    
    state.last_full = full_text
    delta_ans = full_text[state.last_idx :]

    # 处理思考开始标记
    if delta_ans.find("<think>") == 0:
        state.last_idx += len("<think>")
        return "<think>"
    
    # 处理思考标记之前的内容
    if delta_ans.find("<think>") > 0:
        delta_text = full_text[state.last_idx : state.last_idx + delta_ans.find("<think>")]
        state.last_idx += delta_ans.find("<think>")
        return delta_text
    
    # 处理思考结束标记
    if delta_ans.endswith("</think>"):
        state.endswith_think = True
    elif state.endswith_think:
        state.endswith_think = False
        return "</think>"

    # 更新位置
    state.last_idx = len(full_text)
    if full_text.endswith("</think>"):
        state.last_idx -= len("</think>")
    
    return re.sub(r"(<think>|</think>)", "", delta_ans)


# ====================================
# 辅助函数：流式输出处理（带思考标记）
# ====================================

async def _stream_with_think_delta(stream_iter, min_tokens: int = 16):
    """
    处理流式输出，将思考标记与文本分开返回
    
    参数：
        stream_iter: 流式迭代器（模型返回的token流）
        min_tokens: 最小token数（累积到足够token才返回）
    
    返回：
        生成器，产生("text", 文本内容, 状态)或("marker", "<think>", 状态)
    """
    state = _ThinkStreamState()
    
    async for chunk in stream_iter:
        if not chunk:
            continue
        
        # 处理增量（流式返回可能包含重复内容）
        if chunk.startswith(state.last_model_full):
            new_part = chunk[len(state.last_model_full) :]
            state.last_model_full = chunk
        else:
            new_part = chunk
            state.last_model_full += chunk
        
        if not new_part:
            continue
        
        # 更新完整文本
        state.full_text += new_part
        
        # 计算增量
        delta = _next_think_delta(state)
        if not delta:
            continue
        
        # 处理思考标记
        if delta in ("<think>", "</think>"):
            # 过滤重复标记
            if delta == "<think>" and state.in_think:
                continue
            if delta == "</think>" and not state.in_think:
                continue
            
            # 先返回缓冲区中的文本
            if state.buffer:
                yield ("text", state.buffer, state)
                state.buffer = ""
            
            state.in_think = delta == "<think>"
            yield ("marker", delta, state)
            continue
        
        # 累积文本到缓冲区
        state.buffer += delta
        
        # 达到最小token数才返回
        if num_tokens_from_string(state.buffer) < min_tokens:
            continue
        
        yield ("text", state.buffer, state)
        state.buffer = ""

    # 处理剩余内容
    if state.buffer:
        yield ("text", state.buffer, state)
        state.buffer = ""
    if state.endswith_think:
        yield ("marker", "</think>", state)


# ====================================
# 核心方法：chat（RAG对话主流程 - 由内网 async_ask 改写而来）
# ====================================

    async def chat(self, dialog, messages, stream=True, **kwargs):
        kb_ids = kwargs.get("kb_ids") or dialog.kb_ids
        request = kwargs.get("request")
        kb_permission = kwargs.get("kb_permission")
        doc_ids = kwargs.get("doc_ids")
        system_prompt = kwargs.get("system_prompt")
        is_generate_questions = kwargs.get("is_generate_questions", False)
        questions_generate = []
        generate_questions_task = None

        if kb_ids and request is not None and kb_permission is not None:
            try:
                kb_ids = kb_permission.resolve_kb_ids_sync(request, kb_ids)
            except BusinessException as exc:
                if str(exc) == "当前 API Key 无权访问请求中的知识库":
                    raise
                kb_ids = []

        # TODO: 当前仅基于 API Key tenant 裁剪知识库，不切换 dialog.tenant_id，后续统一评估模型选择、提示词与租户
        if not kb_ids:
            logger.info("未携带kb，转为solo")
            for ans in self.chat_solo(dialog, messages, kwargs.get("llmConfig"), system_prompt, stream):
                yield ans
            return

        chat_start_ts = timer()
        _prev = chat_start_ts

        check_llm_ts = timer()
        langfuse_tracer = None
        check_langfuse_tracer_ts = timer()
        kbs, embd_mdl, rerank_mdl, chat_mdl, tts_mdl = self.get_models(dialog, kwargs.get("llmConfig"),
                                                                       kwargs.get("embdMdl"), rerank_mdl)
        max_tokens = chat_mdl.max_length or 8192
        toolcall_session, tools = kwargs.get("toolcall_session"), kwargs.get("tools")
        if toolcall_session and tools:
            chat_mdl.bind_tools(toolcall_session, tools)

        bind_models_ts = timer()

        es_store = ESConnection()
        retriever = Search.Dealer(es_store)
        recent_questions = [m['content'] for m in messages if m['role'] == 'user'][-3:]
        labeled_injection = recent_questions[-1] if len(recent_questions) >= 1 else ""
        recent_questions = [m['content'] for m in messages if m['role'] == "user"][-3:]
        latest_question = recent_questions[-1] if recent_questions else ""
        attachments = doc_ids
        if "doc_ids" in messages[-1]:
            attachments = messages[-1]["doc_ids"]

        prompt_config = dialog.prompt_config.model_dump()
        field_map = self.kb_repo.get_field_map(self.session, kb_ids)
        if field_map and latest_question:
            ans = self.use_sql(latest_question, field_map, dialog.tenant_id, chat_mdl, prompt_config.get("quote", True), kb_ids)
            if ans:
                yield ans
                # return None

        for p in prompt_config["parameters"]:
            if p["key"] == "knowledge":
                continue
            if p['key'] not in kwargs and not p["optional"]:
                raise KeyError(f"Miss parameter: {p['key']}")
            if p["key"] not in kwargs:
                prompt_config["system"] = prompt_config["system"].replace("{%" + p['key'], "")

        has_knowledge_parameter = "knowledge" in [
            p['key'] for p in prompt_config["parameters"]
        ]
        has_prompt_query_rewrite = "query_rewrite" in dialog.prompt_config.model_fields
        query_rewrite_config = prompt_config.get("query_rewrite", {}) or {}
        if not has_prompt_query_rewrite:
            query_rewrite_config = {"enabled": False}
        rewrite_options = QueryRewriteOptions.from_config(query_rewrite_config)
        rewrite_enabled = rewrite_options.enabled and has_knowledge_parameter

        questions = recent_questions
        original_question = latest_question
        rewrite_result = None

        if rewrite_enabled:
            rewrite_result = self.query_rewrite_service.rewrite(
                messages,
                original_question,
                chat_mdl,
                rewrite_options,
                questions
            )
            questions = [rewrite_result.standalone_question] or original_question
            retrieval_queries = rewrite_result.retrieval_queries()
        else:
            if len(questions) > 1 and prompt_config.get("refine_multiturn"):
                questions = [full_question(dialog.tenant_id, dialog.llm_id, messages, chat_mdl=chat_mdl)]
            else:
                questions = questions[-1:]
            retrieval_queries = []

        if prompt_config.get("cross_languages"):
            questions = [
                cross_languages(dialog.tenant_id, dialog.llm_id, questions[0], prompt_config["cross_languages"], chat_mdl=chat_mdl)
            ]

        if prompt_config.get("keyword", False):
            questions[-1] += keyword_extraction(chat_mdl, questions[-1])

        if not retrieval_queries:
            retrieval_queries = [" ".join(questions)] if questions else []

        logger.info(
            "msg: 查询重写结果 original=%s standalone=%r queries=%s rewrite_enabled=%s",
            args=(original_question, questions[-1] if questions else "", retrieval_queries, rewrite_enabled),
        )

        if dialog.meta_data_filter:
            metas = self.doc_repo.get_meta_by_kbs_mo(self.session, kb_ids)
            if dialog.meta_data_filter.get("method") == "auto":
                filters = gen_meta_filter(chat_mdl, metas, questions[-1])
                attachments.extend(self.k_repo.meta_filter(metas, [filters]))
                if not attachments:
                    attachments = None
        elif dialog.meta_data_filter.get("method") == "manual":
            attachments.extend(self.k_repo.meta_filter(metas, dialog.meta_data_filter["manual"]))
            if not attachments:
                attachments = None

        refine_question_ts = timer()
        _t = timer(); logger.info(f"[⏱ 段耗时] 前置汇总(准备检索): {(_t - _prev)*1000:.0f} ms"); _prev = _t

        thought = ""
        kbinfos = {"total": 0, "chunks": [], "doc_aggs": []}
        knowledges = []

        if attachments is not None and has_knowledge_parameter:
           
            # TODO: 当前业务约束下单请求 KB 只允许属于同一 tenant，后续统一检索链路时可将此处收敛为单 tenant 请求。
            tenant_ids = list(set([kb.tenant_id for kb in kbs]))
            knowledges = []
            if prompt_config.get("reasoning", False):
                _t = timer(); logger.info(f"[⏱ 段耗时] 深度推理模式(DeepResearcher): {(_t - _prev)*1000:.0f} ms"); _prev = _t
                reasoner = DeepResearcher(
                    chat_mdl,
                    prompt_config,
                    partial(
                        retriever.retrieval,
                        embd_mdl=embd_mdl,
                        tenant_ids=tenant_ids,
                        kb_ids=kb_ids,
                        top_n=1,
                        page_size=dialog.top_n,
                        similarity_threshold=0.2,
                        vector_similarity_weight=0.3,
                        doc_ids=attachments,
                    )
                )
                for think in reasoner.thinking(kbinfos, "".join(questions)):
                    if isinstance(think, str):
                        thought = think
                        knowledges = [t for t in think.split("\n") if t]
                    elif stream:
                        yield think
            else:
                if embd_mdl:
                    if rewrite_enabled:

                        def run_retrieval(query: str):  # @ huangjianghui XCKF-IB0559 2026-06-16
                            return retriever.retrieval(
                                query,
                                embd_mdl,
                                tenant_ids,
                                kb_ids,
                                page=1,
                                page_size=dialog.top_n,
                                similarity_threshold=dialog.similarity_threshold,
                                vector_similarity_weight=dialog.vector_similarity_weight,
                                doc_ids=attachments,
                                top=dialog.top_k,
                                aggis=False,
                                rerank_mdl=rerank_mdl,
                                rank_feature=label_question(query, kbs)
                            )
                        kbinfos = multi_query_retrieval(
                            run_retrieval,
                            retrieval_queries,
                            dialog.top_n,
                            fallback_query=original_question,
                        )
                        _t = timer(); logger.info(f"[⏱ 段耗时] 多路向量检索: {(_t - _prev)*1000:.0f} ms"); _prev = _t
                        logger.info(
                            msg="查询重写融合后的 chunk_ids=%s",
                            args=[ck.get("chunk_id") for ck in kbinfos.get("chunks", [])],
                        )
                    else:
                        kbinfos = retriever.retrieval(
                            "".join(questions),
                            embd_mdl,
                            tenant_ids,
                            kb_ids,
                            page=1,
                            page_size=dialog.top_n,
                            similarity_threshold=dialog.similarity_threshold,
                            vector_similarity_weight=dialog.vector_similarity_weight,
                            doc_ids=attachments,
                            top=dialog.top_k,
                            aggis=False,
                            rerank_mdl=rerank_mdl,
                            rank_feature=label_question("".join(questions), kbs)
                        )
                    _t = timer(); logger.info(f"[⏱ 段耗时] 单路向量检索: {(_t - _prev)*1000:.0f} ms"); _prev = _t
        else:
            logger.info(f"[⏱ 段耗时] ⚠️ 跳过检索！attachments={attachments}, has_knowledge_parameter={has_knowledge_parameter}")

        if prompt_config.get("toc_enhance"):
            cks = retriever.retrieval_by_toc("".join(questions), kbinfos["chunks"], tenant_ids, chat_mdl,
                                             dialog.top_n)
            if cks:
                kbinfos["chunks"] = cks

        if prompt_config.get("tavily_api_key"):
            tav = Tavily(prompt_config["tavily_api_key"])
            tav_res = tav.retrieve_chunks("".join(questions))
            kbinfos["chunks"].extend(tav_res["chunks"])
            kbinfos["doc_aggs"].extend(tav_res["doc_aggs"])

        if prompt_config.get("use_kg"):
            ck = settings.kg_retriever.retrievallm("".join(questions), tenant_ids, kb_ids, embd_mdl,
                                                   LLMType.CHAT)

            if ck["content_with_weight"]:
                kbinfos["chunks"].insert(0, ck)

        knowledges = kg_prompt(kbinfos, max_tokens)

        if not kbinfos["doc_aggs"]:
            chunks = kbinfos["chunks"]

            def _filed_count(data, *fileds):
                def make_key(item):
                    return tuple(item[filed] for filed in fileds)
                return Counter(make_key(item) for item in data)

            doc_aggs = []
            _count = _filed_count(chunks, ["docnm_kwd", "doc_id", "file_id"])
            for (docnm_kwd, doc_id, file_id), cnt in _count.items():
                doc_aggs.append({"doc_name": docnm_kwd, "doc_id": doc_id, "file_id": file_id, "count": cnt})
            kbinfos["doc_aggs"] = doc_aggs

        retrieval_ts = timer()

        if not knowledges and prompt_config.get("empty_response"):
            empty_res = prompt_config["empty_response"]
            yield {"answer": empty_res, "reference": kbinfos, "prompt": "\n\n#### Query:\n%s" % "".join(questions),
                   "audio_binary": self.tts(tts_mdl, empty_res) if tts_mdl else ""}
            return

        kwargs["knowledge"] = "\n-------\n" + "\n\n-------\n".join(knowledges)
        gen_conf = dialog.llm_setting.model_dump()
        msg = [{"role": "system", "content": prompt_config["system"].format(**kwargs)}]
        prompt4citation = ""
        if knowledges and (prompt_config.get("quote", True)) and kwargs.get("quote", True):
            prompt4citation = citation_prompt()

        msg.extend([{"role": m["role"], "content": re.sub(r"<\d{4}>\s*", "", m["content"])} for m in messages if
                    m["role"] != "system"])

        llm_id = dialog.llm_id or ""
        # ① 输入上限：网关按【字符】限制，用“中英混合÷2.5”换算成 token 交给 message_fit_in。
        #    min(..., max_tokens) 防止数据库 max_tokens 配太小时，③的输出额度算成负数
        if "Qwen3.6-27B" in llm_id:
            input_token_limit = min(13107, max_tokens)   # 32768 字符 ÷ 2.5
            input_char_limit = 32768
        elif "Qwen3.6-35B-A3B" in llm_id:
            input_token_limit = min(20480, max_tokens)   # 51200 字符 ÷ 2.5
            input_char_limit = 51200
        else:
            input_token_limit = int(max_tokens * 0.95)
            input_char_limit = None

        used_token_count, msg = message_fit_in(msg, input_token_limit)
        assert len(msg) >= 2, f"message_fit_in has bug: {msg}"

        # ② 字符兜底：token 只是估算，网关真正卡的是 len() 字符数。留 8% 余量做最终保险，
        #    优先裁 system（知识库最长），拦住“token没超但字符超”的英文/混合内容
        if input_char_limit:
            safe_char_limit = int(input_char_limit * 0.92)
            if sum(len(m["content"]) for m in msg) > safe_char_limit:
                others = sum(len(m["content"]) for m in msg[1:])
                msg[0]["content"] = msg[0]["content"][: max(0, safe_char_limit - others)]
                used_token_count = sum(num_tokens_from_string(m["content"]) for m in msg)

        prompt = msg[0]["content"]

        # ③ 输出上限：16384 字符 ÷ 2.5 = 6554 token；再受会话配置和“总窗口−输入”约束
        if "max_tokens" in gen_conf:
            gen_conf["max_tokens"] = min(
                gen_conf["max_tokens"],
                6554,
                max_tokens - used_token_count,
            )

        logger.info(
            "Token limits: model=%s context=%s input_limit=%s input_used=%s output_limit=%s",
            llm_id,
            max_tokens,
            input_token_limit,
            used_token_count,
            gen_conf.get("max_tokens"),
        )

        if is_generate_questions and knowledges:
            # 相关问题生成task
            from app.core.job.tasks.simple_task import generate_questions
            generate_questions_task = await generate_questions.kid(msg[1:][0]["content"], ",".join(knowledges))

        def decorate_answer(answer, questions_generate=[]):
            nonlocal embd_mdl, prompt_config, knowledges, kwargs, kbinfos, prompt, retrieval_ts, questions, langfuse_tracer, is_generate_questions

            refs = []
            ans = answer.split("</think")
            think = ""
            if len(ans) == 2:
                think = ans[0] + "</think"
                answer = ans[1]

            if knowledges and (prompt_config.get("quote", True)) and kwargs.get("quote", True):
                idx = set([])
                if embd_mdl and not re.search(r"\[\d{1,4}(-\d{1,4}){0,3}\]", answer):
                    if len(kbinfos["chunks"]) == 0 or prompt_config.get("empty_response") not in answer:
                        answer, idx = retriever.insert_citations(
                            answer,
                            [ck["content_ltks"] for ck in kbinfos["chunks"]],
                            [ck["vector"] for ck in kbinfos["chunks"]],
                            embd_mdl,
                            # tkweight=1 - dialog.vector_similarity_weight,
                            # vtweight=dialog.vector_similarity_weight,
                        )
                else:
                    for match in re.finditer(r"\[(\d{1,4}(-\d{1,4}){0,3})\]", answer):
                        i = int(match.group(1))
                        if i < len(kbinfos["chunks"]):
                            idx.add(i)

                answer, idx = self.repair_bad_citation_formats(answer, kbinfos, idx)
                idx = set([kbinfos["chunks"][int(i)]["doc_id"] for i in idx])
                recall_docs = [d for d in kbinfos["doc_aggs"] if d["doc_id"] in idx]
                if not recall_docs:
                    recall_docs = kbinfos["doc_aggs"]
                kbinfos["doc_aggs"] = recall_docs

            if not kbinfos["doc_aggs"]:
                _chunks = kbinfos["chunks"]

                def _filed_count(data, *fileds):
                    def make_key(item):
                        return tuple(item[filed] for filed in fileds)
                    return Counter(make_key(item) for item in data)

                doc_aggs = []
                _count = _filed_count(_chunks, ["docnm_kwd", "doc_id", "file_id"])
                for (docnm_kwd, doc_id, file_id), cnt in _count.items():
                    doc_aggs.append({"doc_name": docnm_kwd, "doc_id": doc_id, "file_id": file_id, "count": cnt})
                kbinfos["doc_aggs"] = doc_aggs

            refs = deepcopy(kbinfos)
            for c in refs["chunks"]:
                if c.get("vector"):
                    del c["vector"]

            if answer.lower().find("invalid key") >= 0 or answer.lower().find("invalid api") >= 0:
                answer += "\nPlease set LLM API-Key in 'User Setting -> Model providers -> API-Key'"

            finish_chat_ts = timer()

            total_time_cost = (finish_chat_ts - chat_start_ts) * 1000
            check_llm_time_cost = (check_llm_ts - chat_start_ts) * 1000
            check_langfuse_tracer_cost = (check_langfuse_tracer_ts - check_llm_ts) * 1000
            bind_embedding_time_cost = (bind_models_ts - check_langfuse_tracer_ts) * 1000
            refine_question_time_cost = (refine_question_ts - bind_models_ts) * 1000
            retrieval_time_cost = (retrieval_ts - refine_question_ts) * 1000
            generate_result_time_cost = (finish_chat_ts - retrieval_ts) * 1000

            tk_num = num_tokens_from_string(think + answer)
            prompt = "\n\n#### Query:\n%s" % "".join(questions)
            prompt += (
                f"\n{prompt}\n\n"
                #f"### Time elapsed:\n"
                f" - Total: {total_time_cost:.1f}ms\n"
                f" - Check LLM: {check_llm_time_cost:.1f}ms\n"
                f" - Check Langfuse tracer: {check_langfuse_tracer_cost:.1f}ms\n"
                f" - Bind models: {bind_embedding_time_cost:.1f}ms\n"
                f" - Query refinement(LLM): {refine_question_time_cost:.1f}ms\n"
                f" - Retrieval: {retrieval_time_cost:.1f}ms\n"
                f" - Generate answer: {generate_result_time_cost:.1f}ms\n"
                "### Token usage:\n"
                f" - Generated tokens(approximately): {tk_num}\n"
                f" - Token speed: {int(tk_num / (generate_result_time_cost / 1000))}/s"
            )

            # Add a condition check to call the end method only if langfuse_tracer exists
            if langfuse_tracer and "langfuse_generation" in locals():
                langfuse_output = "\n" + re.sub(r"\s+", " ### Query: ", prompt, flags=re.DOTALL)
                langfuse_output = {"time_elapsed": re.sub(pattern="\n", repl=" ", string=langfuse_output), "created_at": time.time()}
                langfuse_generation.update(output=langfuse_output)
                langfuse_generation.end()
            refs["prompt"] = prompt
            refs["cost_time"] = f"Retrieval:{retrieval_time_cost:.1f}ms"
            refs["token_usage"] = {
                "input_tokens": used_token_count,
                "output_tokens": tk_num,
                "total_tokens": used_token_count + tk_num,
                "count_source": "local_estimate",
            }
            logger.info(
                "Token usage estimate: input=%s output=%s total=%s",
                used_token_count,
                tk_num,
                used_token_count + tk_num,
            )
            final_result = {
                "answer": think + answer,
                "reference": refs,
                "prompt": re.sub(pattern=r'\n', repl=" ", string=prompt),
                "created_at": time.time(),
                "generate_questions": questions_generate if knowledges else []
            }
            # TODO: 传给结果审批通过，再新传优秩，poetry add lancedb datasets ragas
            # if prompt_config.get("evaluation_enabled", False):
            #     from app.core.rag.evaluation.eval_wrapper import eval_answer
            #     final_result = eval_answer(final_result, question=" ".join(questions))

            logger.info(final_result)
            return final_result

        if langfuse_tracer:
            langfuse_generation = langfuse_tracer.start_generation(
                trace_context=trace_context, name='chat', model=llm_model_config["llm_name"],
                input={"prompt": prompt4citation, "messages": msg}
            )

        if stream:
            from app.agents.analysis_long_doc import LongDocAnalysisAgent
            last_ans = ""
            answer = ""
            # 判断是否需要文档特殊处理专家
            expert_config = prompt_config.get('expert')
            expert = kwargs.get("is_expert", expert_config.get('enabled') if expert_config else False)
            user_input = questions[-1] if questions else ''
            log_doc_expert = LongDocAnalysisExpert()

            # 意图识别
            _prev = timer()
            # irr = log_doc_expert.intent_recognition(user_input)
            irt = ''     # 意图识别思考
            irr = ''     # 意图识别结果

            for chunk in log_doc_expert.intent_recognition(user_input):
                if chunk['type'] == 'reasoning':
                    irt += chunk['content']
                elif chunk['type'] == 'answer':
                    irt += chunk['content']
                    irr += chunk['content']
                yield {"answer": f"<think{irt}</think", "reference": {}, "audio_binary": ''}
            logger.info(f"意图识别耗时: {irr}")
            _t = timer()
            logger.info(f"意图识别777: {(_t - _prev) * 1000:.1f}ms")
            _prev = _t
            # 判断是否设置历史轮数
            history_len_config = prompt_config.get("history_len")
            history_len_obj = history_len_config if history_len_config else {}
            history_len_enabled = history_len_obj.get("enabled", False)
            history_len_value = int(history_len_obj.get("len", 1))
            history_value = (history_len_value -1) * 2 +1
            irr_listt = ["长文档摘要要总结", "条统计"]
            if expert and irr in irr_listt:
                logger.info('expert mode enabled, using log_doc_expert')

                doc_ids = [item['doc_id'] for item in kbinfos["doc_aggs"]]
                tenant_id, = dialog.tenant_id,
                kb_msg = messages

                expert_prompt = await log_doc_expert.process(user_input, doc_ids, tenant_id, intent=irr)

                try:
                    for ans in chat_mdl.chat_streamly(expert_prompt, msg[1:], gen_conf):
                        if thought:
                            # 深度思考
                            ans = re.sub(pattern=r'</?think>', repl="", string=ans)
                            ans = re.sub(pattern=r'^.*?<think', repl="", string=ans, flags=re.DOTALL)
                        else:
                            ### 兼容qwen3-8b mac 非标准think，此模型在content内容包含<think/></think标签而非reasoning_content
                            if ans.startswith("<think") and not ans.endswith("</think") and ans.find("</think") == -1:
                                ans = ans + "</\think>"
                            ### 兼容qwen3-8b mac 非标准think
                        answer += ans
                        delta_ans = ans[len(last_ans):]
                        if num_tokens_from_string(delta_ans) < 16:
                            continue
                        last_ans = answer
                        yield {"answer": thought + answer, "reference": {},
                               "audio_binary": self.tts(tts_mdl, delta_ans)}
                        delta_ans = answer[len(last_ans):]
                        if delta_ans:
                            yield {"answer": thought + answer, "reference": {}, "audio_binary": self.tts(tts_mdl, delta_ans)}
                        if is_generate_questions and knowledges and generate_questions_task:
                            # 相关问题生成任务结果获取
                            questions_generate_res = await generate_questions_task.wait_result()
                            if questions_generate_res.is_err:
                                raise questions_generate_res.error
                            if questions_generate_res and hasattr(questions_generate_res, "return_value"):
                                questions_generate = questions_generate_res.return_value
                        print(f"result------answer>>>{questions_generate}")
                        yield decorate_answer(thought + answer, questions_generate)
                except Exception as e:
                    logger.error(f'log_doc_expert failed: {e}, falling back to normal logic')
            else:
                for ans in chat_mdl.chat_streamly(prompt + prompt4citation, msg[1:][-history_value:] if history_len_enabled else msg[1:], gen_conf):
                    _t = timer()
                    logger.info(f"正常流程777: {(_t - _prev) * 1000:.1f}ms")
                    if thought:
                        # 深度思考
                        ans = re.sub(pattern=r'</?think>', repl="", string=ans)
                        ans = re.sub(pattern=r'^.*?<think', repl="", string=ans, flags=re.DOTALL)
                    else:
                        ### 兼容qwen3-8b mac 非标准think，此模型在content内容包含<think/></think标签而非reasoning_content
                        if ans.startswith("<think") and not ans.endswith("</think") and ans.find("</think") == -1:
                            ans = ans + "</\think>"
                        ### 兼容qwen3-8b mac 非标准think
                    answer += ans
                    delta_ans = ans[len(last_ans):]
                    if num_tokens_from_string(delta_ans) < 16:
                        continue
                    last_ans = answer
                    yield {"answer": thought + answer, "reference": {},
                           "audio_binary": self.tts(tts_mdl, delta_ans)}
                    delta_ans = answer[len(last_ans):]
                    if delta_ans:
                        yield {"answer": thought + answer, "reference": {}, "audio_binary": self.tts(tts_mdl, delta_ans)}
                    if is_generate_questions and knowledges and generate_questions_task:
                        # 相关问题生成任务结果获取
                        questions_generate_res = await generate_questions_task.wait_result()
                        if questions_generate_res.is_err:
                            raise questions_generate_res.error
                        if questions_generate_res and hasattr(questions_generate_res, "return_value"):
                            questions_generate = questions_generate_res.return_value
                    yield decorate_answer(thought + answer, questions_generate)

        else:
            answer = chat_mdl.chat(prompt + prompt4citation, msg[1:], gen_conf)
            user_content = msg[-1].get("content", "[content not available]")
            logging.debug("User: {}\nAssistant: {}".format(user_content, answer))
            res = decorate_answer(answer)
            res["audio_binary"] = self.tts(tts_mdl, answer)
            yield res

        return


async def async_ask(question, kb_ids, tenant_id, chat_llm_name=None, search_config={}, search_id=None):
    doc_ids = search_config.get("doc_ids", [])
    rerank_mdl = None
    kb_ids = search_config.get("kb_ids", kb_ids)
    chat_llm_name = search_config.get("chat_id", chat_llm_name)
    rerank_id = search_config.get("rerank_id", "")
    meta_data_filter = search_config.get("meta_data_filter")
    include_reference_metadata, metadata_fields = _resolve_reference_metadata(search_config)

    kbs = KnowledgebaseService.get_by_ids(kb_ids)
    if not kbs:
        if not kb_ids:
            error = "**ERROR**: No KB selected"
        else:
            error = "**ERROR**: The selected KB is not valid"
        yield {"answer": error, "reference": {}, "final": True}
        return

    embedding_list = list(set([kb.embd_id for kb in kbs]))

    is_knowledge_graph = all([kb.parser_id == ParserType.KG for kb in kbs])
    retriever = settings.retriever if not is_knowledge_graph else settings.kg_retriever
    embd_owner_tenant_id = kbs[0].tenant_id
    embd_model_config = get_model_config_from_provider_instance(embd_owner_tenant_id, LLMType.EMBEDDING, embedding_list[0])
    embd_mdl = LLMBundle(embd_owner_tenant_id, embd_model_config)
    chat_model_config = get_model_config_from_provider_instance(tenant_id, LLMType.CHAT, chat_llm_name)
    chat_mdl = LLMBundle(tenant_id, chat_model_config)
    if rerank_id:
        rerank_model_config = get_model_config_from_provider_instance(tenant_id, LLMType.RERANK, rerank_id)
        rerank_mdl = LLMBundle(tenant_id, rerank_model_config)
    max_tokens = chat_mdl.max_length
    tenant_ids = list(set([kb.tenant_id for kb in kbs]))

    if meta_data_filter:
        doc_ids = await apply_meta_data_filter(
            meta_data_filter,
            None,
            question,
            chat_mdl,
            doc_ids,
            kb_ids=kb_ids,
            metas_loader=lambda: DocMetadataService.get_flatted_meta_by_kbs(kb_ids),
        )

    vector_similarity_weight = search_config.get("vector_similarity_weight", 0.3)
    try:
        full_text_weight = 1 - vector_similarity_weight
    except TypeError:
        full_text_weight = None
    logger.debug(
        "Search async_ask retrieval weight: search_id=%s tenant_id=%s kb_count=%s "
        "vector_similarity_weight=%s full_text_weight=%s",
        search_id,
        tenant_id,
        len(kb_ids),
        vector_similarity_weight,
        full_text_weight,
    )

    kbinfos = await retriever.retrieval(
        question=question,
        embd_mdl=embd_mdl,
        tenant_ids=tenant_ids,
        kb_ids=kb_ids,
        page=1,
        page_size=12,
        similarity_threshold=search_config.get("similarity_threshold", 0.1),
        vector_similarity_weight=vector_similarity_weight,
        top=search_config.get("top_k", 1024),
        doc_ids=doc_ids,
        aggs=True,
        rerank_mdl=rerank_mdl,
        rank_feature=label_question(question, kbs),
        trace_id=search_id,
    )
    if include_reference_metadata:
        logging.debug(
            "reference_metadata enrichment enabled for async_ask: chunk_count=%d metadata_fields=%s",
            len(kbinfos.get("chunks", [])),
            metadata_fields,
        )
        _enrich_chunks_with_document_metadata(kbinfos.get("chunks", []), metadata_fields)

    knowledges = kb_prompt(kbinfos, max_tokens)
    sys_prompt = PROMPT_JINJA_ENV.from_string(ASK_SUMMARY).render(knowledge="\n".join(knowledges))

    msg = [{"role": "user", "content": question}]

    async def decorate_answer(answer):
        nonlocal knowledges, kbinfos, sys_prompt
        # Main retrieval no longer ships chunk vectors back from ES. Pull
        # them on demand for the chunks we are about to cite.
        await _hydrate_chunk_vectors(retriever, kbinfos.get("chunks", []), tenant_ids, kb_ids)
        answer, idx = retriever.insert_citations(answer, [ck["content_ltks"] for ck in kbinfos["chunks"]], [ck["vector"] for ck in kbinfos["chunks"]], embd_mdl, tkweight=0.7, vtweight=0.3)
        idx = set([kbinfos["chunks"][int(i)]["doc_id"] for i in idx])
        recall_docs = [d for d in kbinfos["doc_aggs"] if d["doc_id"] in idx]
        if not recall_docs:
            recall_docs = kbinfos["doc_aggs"]
        kbinfos["doc_aggs"] = recall_docs
        refs = deepcopy(kbinfos)
        for c in refs["chunks"]:
            if c.get("vector"):
                del c["vector"]

        if answer.lower().find("invalid key") >= 0 or answer.lower().find("invalid api") >= 0:
            answer += " Please set LLM API-Key in 'User Setting -> Model Providers -> API-Key'"
        refs["chunks"] = chunks_format(refs)
        return {"answer": answer, "reference": refs}

    stream_iter = chat_mdl.async_chat_streamly_delta(sys_prompt, msg, {"temperature": 0.1})
    last_state = None
    async for kind, value, state in _stream_with_think_delta(stream_iter):
        last_state = state
        if kind == "marker":
            flags = {"start_to_think": True} if value == "<think>" else {"end_to_think": True}
            yield {"answer": "", "reference": {}, "final": False, **flags}
            continue
        yield {"answer": value, "reference": {}, "final": False}
    full_answer = last_state.full_text if last_state else ""
    final = await decorate_answer(_extract_visible_answer(full_answer))
    final["final"] = True
    final["answer"] = ""
    yield final


# ====================================
# 核心函数：gen_mindmap（生成思维导图）
# ====================================

async def gen_mindmap(question, kb_ids, tenant_id, search_config={}):
    """
    生成思维导图（从知识库中提取知识结构）
    
    参数：
        question: 用户问题
        kb_ids: 知识库ID列表
        tenant_id: 租户ID
        search_config: 搜索配置
    
    返回：
        思维导图结构
    """
    # 提取配置参数
    meta_data_filter = search_config.get("meta_data_filter", {})
    doc_ids = search_config.get("doc_ids", [])
    rerank_id = search_config.get("rerank_id", "")
    rerank_mdl = None
    
    # 获取知识库信息
    kbs = KnowledgebaseService.get_by_ids(kb_ids)
    if not kbs:
        return {"error": "No KB selected"}
    
    tenant_embedding_list = list(set([kb.tenant_embd_id for kb in kbs]))
    tenant_ids = list(set([kb.tenant_id for kb in kbs]))
    
    # 获取嵌入模型配置
    if tenant_embedding_list[0]:
        embd_model_config = get_model_config_by_id(tenant_embedding_list[0])
        embd_owner_tenant_id = kbs[0].tenant_id
    else:
        embd_owner_tenant_id = kbs[0].tenant_id
        embd_model_config = get_model_config_by_type_and_name(embd_owner_tenant_id, LLMType.EMBEDDING, kbs[0].embd_id)
    
    embd_mdl = LLMBundle(embd_owner_tenant_id, embd_model_config)
    
    # 获取聊天模型配置
    chat_id = search_config.get("chat_id", "")
    if chat_id:
        chat_model_config = get_model_config_by_type_and_name(tenant_id, LLMType.CHAT, chat_id)
    else:
        chat_model_config = get_tenant_default_model_by_type(tenant_id, LLMType.CHAT)
    chat_mdl = LLMBundle(tenant_id, chat_model_config)
    
    # 获取重排序模型（如果配置了）
    if rerank_id:
        rerank_model_config = get_model_config_by_type_and_name(tenant_id, LLMType.RERANK, rerank_id)
        rerank_mdl = LLMBundle(tenant_id, rerank_model_config)

    # 应用元数据过滤
    if meta_data_filter:
        doc_ids = await apply_meta_data_filter(
            meta_data_filter,
            None,
            question,
            chat_mdl,
            doc_ids,
            kb_ids=kb_ids,
            metas_loader=lambda: DocMetadataService.get_flatted_meta_by_kbs(kb_ids),
        )

    # 执行检索
    ranks = await settings.retriever.retrieval(
        question=question,
        embd_mdl=embd_mdl,
        tenant_ids=tenant_ids,
        kb_ids=kb_ids,
        page=1,
        page_size=12,
        similarity_threshold=search_config.get("similarity_threshold", 0.2),
        vector_similarity_weight=search_config.get("vector_similarity_weight", 0.3),
        top=search_config.get("top_k", 1024),
        doc_ids=doc_ids,
        aggs=False,
        rerank_mdl=rerank_mdl,
        rank_feature=label_question(question, kbs),
    )
    
    # 使用MindMapExtractor提取思维导图
    mindmap = MindMapExtractor(chat_mdl)
    mind_map = await mindmap([c["content_with_weight"] for c in ranks["chunks"]])
    return mind_map.output
