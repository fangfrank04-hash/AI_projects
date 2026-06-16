# -*- coding: utf-8 -*-
"""
方案B（LLMJudgeEvaluator）所用的 LLM Prompt 模板

参考 RAGAS 论文的 prompt 设计，四个指标各有一套 prompt。
所有 prompt 期望 LLM 返回结构化输出（JSON），便于程序解析。
"""

# ============================================================================
# 1. Faithfulness（忠实度）— 两阶段
# ============================================================================

FAITHFULNESS_STATEMENT_EXTRACTION_PROMPT = """\
Your task is to extract all atomic factual claims from the given answer.

Rules:
1. Break the answer down into the smallest independent factual statements.
2. Each statement must be a complete, self-contained sentence.
3. Do NOT add any information not present in the answer.
4. Output ONLY a JSON array of strings, nothing else.

Answer:
{answer}

Output format (JSON array):
["claim 1", "claim 2", "claim 3"]
"""

FAITHFULNESS_VERDICT_PROMPT = """\
Your task is to judge whether a claim is supported by the given context documents.

Claim: {claim}

Context documents:
{contexts}

Instructions:
1. Determine if the claim can be directly inferred from the context documents.
2. Output ONLY a JSON object with a single key "verdict" set to 1 (supported) or 0 (not supported).
3. A claim is "supported" if the context documents explicitly state or logically imply it.
4. If the context documents are irrelevant or insufficient, output 0.

Output format:
{{"verdict": 1}}  or  {{"verdict": 0}}
"""

# ============================================================================
# 2. Context Precision（上下文精确度）— 逐文档判定 + 位置加权
# ============================================================================

CONTEXT_PRECISION_JUDGE_PROMPT = """\
Your task is to judge whether a retrieved document is relevant to the given question.

Question: {question}

Retrieved document:
{document}

Instructions:
1. Judge if this document contains information that helps answer the question.
2. Output ONLY a JSON object with a single key "relevant" set to 1 (relevant) or 0 (not relevant).
3. A document is "relevant" if it contains facts, data, or reasoning that could contribute to answering the question.

Output format:
{{"relevant": 1}}  or  {{"relevant": 0}}
"""

# ============================================================================
# 3. Context Recall（上下文召回率）— ground_truth 拆句 + 归因
# ============================================================================

CONTEXT_RECALL_SENTENCE_SPLIT_PROMPT = """\
Your task is to split the following reference answer into independent factual sentences.
Each sentence should contain exactly ONE piece of information.

Reference answer:
{ground_truth}

Output ONLY a JSON array of sentences, nothing else.

Example output:
["sentence 1", "sentence 2", "sentence 3"]
"""

CONTEXT_RECALL_ATTRIBUTION_PROMPT = """\
Your task is to determine whether a sentence from the reference answer can be attributed to (found in) the retrieved context documents.

Sentence to verify: {sentence}

Retrieved context documents:
{contexts}

Instructions:
1. Determine if the sentence's information can be found in ANY of the context documents.
2. Output ONLY a JSON object with a single key "attributed" set to 1 (found) or 0 (not found).
3. Exact wording is NOT required — the meaning must be substantively present.

Output format:
{{"attributed": 1}}  or  {{"attributed": 0}}
"""

# ============================================================================
# 4. Answer Relevancy（答案相关性）— 反向生成问题 + 语义相似度
# ============================================================================

ANSWER_RELEVANCY_REVERSE_QUESTION_PROMPT = """\
Your task is to generate {n} questions that could be answered by the given answer.

Answer: {answer}

Instructions:
1. Generate exactly {n} different questions that this answer would be a good response to.
2. Each question should be concise and natural.
3. Output ONLY a JSON array of strings, nothing else.

Output format:
["question 1", "question 2", "question 3"]
"""
