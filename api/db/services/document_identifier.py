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

import logging
import re
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


class DocumentIdentifier:
    """
    智能文档识别器
    
    用于分析用户问题，识别出针对的是哪个文档，
    从而在检索时只在该文档范围内进行搜索，避免跨文档干扰。
    """
    
    @staticmethod
    async def identify_target_document(
        question: str,
        documents: List[dict],
        chat_mdl
    ) -> Optional[str]:
        """
        识别用户问题针对的目标文档
        
        Args:
            question: 用户问题
            documents: 文档列表，每个文档包含 id, name 等字段
            chat_mdl: LLM 模型实例
            
        Returns:
            目标文档的 ID，如果无法识别则返回 None
        """
        if not documents:
            return None
        
        # 如果只有一个文档，直接返回
        if len(documents) == 1:
            logger.info(f"只有一个文档，直接返回: {documents[0]['id']}")
            return documents[0]["id"]
        
        # 策略 1：先从问题中提取文档名称（快速匹配，不调用 LLM）
        doc_name = DocumentIdentifier.extract_document_name_from_question(question)
        if doc_name:
            logger.info(f"从问题中提取到文档名称: {doc_name}")
            matched_doc_id = DocumentIdentifier.match_document_by_name(documents, doc_name)
            if matched_doc_id:
                logger.info(f"通过名称匹配到文档: {matched_doc_id}")
                return matched_doc_id
            else:
                logger.info(f"未通过名称匹配到文档，将使用 LLM 识别")
        
        # 策略 2：使用 LLM 进行智能识别
        # 构建文档列表描述（只包含名称和 ID，减少 token 消耗）
        doc_descriptions = []
        for i, doc in enumerate(documents):
            doc_name = doc.get("name", "未知文档")
            doc_id = doc.get("id", "")
            # 只取前 50 个字符作为描述，避免 prompt 过长
            doc_descriptions.append(f"{i+1}. {doc_name[:50]} (ID: {doc_id})")
        
        doc_list_text = "\n".join(doc_descriptions)
        
        # 构建提示词（优化版，更精确）
        prompt = f"""你是一个智能文档识别助手。你的任务是根据用户的问题，判断它针对的是知识库中的哪个文档。

## 知识库中的文档列表：
{doc_list_text}

## 用户问题：
{question}

## 识别规则：
1. 仔细分析用户问题中提到的文档名称、关键词或主题
2. 在文档列表中找到最匹配的文档
3. 如果问题明确提到某个文档名称（如"《金融基础设施监督管理办法》"），请选择对应的文档
4. 如果问题没有明确指向某个文档，或者无法确定，请返回 "NONE"
5. 只返回文档的 ID，不要返回其他内容

## 你的回答（只返回文档ID或NONE）：
"""
        
        try:
            # 调用 LLM 进行识别
            response = await chat_mdl.chat(prompt, [])
            logger.info(f"LLM 识别响应: {response}")
            
            # 提取文档 ID
            doc_id = DocumentIdentifier._extract_doc_id(response, documents)
            
            if doc_id:
                logger.info(f"成功识别目标文档: {doc_id}")
            else:
                logger.info(f"无法识别目标文档，将检索所有文档")
            
            return doc_id
            
        except Exception as e:
            logger.error(f"文档识别失败: {e}")
            return None
    
    @staticmethod
    def _extract_doc_id(response: str, documents: List[dict]) -> Optional[str]:
        """
        从 LLM 响应中提取文档 ID
        
        Args:
            response: LLM 的响应文本
            documents: 文档列表
            
        Returns:
            文档 ID，如果未找到则返回 None
        """
        if not response:
            return None
        
        # 清理响应文本
        response = response.strip()
        
        # 如果返回 NONE 或类似表示，说明无法识别
        if response.upper() in ["NONE", "NULL", "N/A", "无法确定", "不确定"]:
            return None
        
        # 尝试直接匹配文档 ID
        for doc in documents:
            doc_id = doc.get("id", "")
            if doc_id and doc_id in response:
                return doc_id
        
        # 尝试从响应中提取 ID（假设 ID 是某种格式的字符串）
        # 匹配常见的 ID 格式：字母数字组合，可能包含连字符或下划线
        id_pattern = r'[a-zA-Z0-9_-]{8,}'
        matches = re.findall(id_pattern, response)
        
        for match in matches:
            for doc in documents:
                if doc.get("id") == match:
                    return match
        
        return None
    
    @staticmethod
    def should_use_document_filter(question: str) -> bool:
        """
        判断是否应该使用文档过滤
        
        如果问题中包含以下关键词，说明用户可能在询问特定文档的信息，
        应该启用文档过滤
        
        Args:
            question: 用户问题
            
        Returns:
            True 表示应该使用文档过滤，False 表示不需要
        """
        # 文档过滤触发关键词
        filter_keywords = [
            "这个文件", "该文件", "此文件", "本文档", "这份文档",
            "文件1", "文件2", "文件3",  # 可以根据实际情况添加
            "《", "》",  # 书名号通常表示文档名称
            "多少条款", "多少条", "多少个", "一共多少",  # 统计类问题
            "第几条", "第几章", "第几节",  # 条款章节类问题
            "完整内容", "全部内容", "所有条款",  # 全局性问题
        ]
        
        question_lower = question.lower()
        for keyword in filter_keywords:
            if keyword.lower() in question_lower:
                return True
        
        return False
    
    @staticmethod
    def extract_document_name_from_question(question: str) -> Optional[str]:
        """
        从问题中提取文档名称（如果有）
        
        Args:
            question: 用户问题
            
        Returns:
            文档名称，如果未找到则返回 None
        """
        # 匹配书名号中的内容
        book_pattern = r'《([^》]+)》'
        matches = re.findall(book_pattern, question)
        if matches:
            return matches[0]
        
        # 匹配引号中的内容
        quote_pattern = r'[""]([^""]+)[""]'
        matches = re.findall(quote_pattern, question)
        if matches:
            return matches[0]
        
        return None
    
    @staticmethod
    def match_document_by_name(documents: List[dict], doc_name: str) -> Optional[str]:
        """
        根据文档名称匹配文档 ID
        
        Args:
            documents: 文档列表
            doc_name: 文档名称
            
        Returns:
            文档 ID，如果未找到则返回 None
        """
        if not doc_name:
            return None
        
        doc_name_lower = doc_name.lower()
        
        # 精确匹配
        for doc in documents:
            name = doc.get("name", "")
            if name.lower() == doc_name_lower:
                return doc.get("id")
        
        # 模糊匹配（包含关系）
        for doc in documents:
            name = doc.get("name", "").lower()
            if doc_name_lower in name or name in doc_name_lower:
                return doc.get("id")
        
        # 去除扩展名后匹配
        doc_name_no_ext = re.sub(r'\.\w+$', '', doc_name_lower)
        for doc in documents:
            name = doc.get("name", "").lower()
            name_no_ext = re.sub(r'\.\w+$', '', name)
            if doc_name_no_ext == name_no_ext:
                return doc.get("id")
        
        return None
