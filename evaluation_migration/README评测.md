# RAG 评测系统 - 内网迁移包

> **一句话：在 ragflow 的 RAG 检索后自动计算 Faithfulness / Context Precision / Context Recall / Answer Relevancy 四个指标。**
>
> 参考文章：https://cloud.tencent.com/developer/article/2651859
>
> 生成时间：2026-05-22 | 大小：~120MB | Python：3.12 | 测试：48 passed / 2 skipped

---

## 这个项目是干嘛的

你领导给你那篇文章，讲的是用 RAGAS + LangFuse 搭一套 RAG 质量评测体系。领导让你"写一个接口"，意思是：

> **在 ragflow 每次 RAG 检索完成后，自动算出这次检索质量好不好（有没有幻觉、检索准不准、有没有跑题）。**

这个项目就是干这个的。核心就是**一个 Python 函数**，插在 RAG pipeline 最后一行。


## 领导要的"接口"到底是哪个

```
这个项目里有 4 个"接口"级别的东西，各干各的：

┌──────────────────────────────────────────────────────────┐
│  auto_hook.py  ← ✅ 领导要的就是这个                    │
│  一个 Python 函数 auto_evaluate()                        │
│  插在 RAG 检索后面，自动算四个指标                        │
│  用法：scores = auto_evaluate(question, answer, contexts) │
├──────────────────────────────────────────────────────────┤
│  run_evaluation.py  ← 配套脚本                          │
│  命令行工具，读数据集 → 批量跑 RAG → 出报告               │
│  用法：python run_evaluation.py --dataset xxx.json        │
├──────────────────────────────────────────────────────────┤
│  evaluation_api.py  ← 管理后台（送的）                   │
│  14 个 HTTP 端点，管理评测数据集和查看历史报告             │
│  用法：python evaluation_api.py（启动后浏览器访问）       │
├──────────────────────────────────────────────────────────┤
│  langfuse_integration.py  ← LangFuse 平台集成（送的）     │
│  自动 Tracing、差评入 Dataset、从 LangFuse 拉数据评测     │
│  用法：from evaluation import LangfuseTracer              │
└──────────────────────────────────────────────────────────┘
```


## 目录结构

```
evaluation_migration/
│
├── 入门必看
│   └── README.md                         ← 你正在看的这个
│
├── 核心：领导要的接口
│   └── evaluation/
│       ├── auto_hook.py                  ← ✅ 插在 RAG 后面的 auto_evaluate() 函数
│       ├── base.py                       ← 抽象基类（定义接口规范）
│       ├── prompts.py                    ← 四个指标的 LLM prompt 模板
│       ├── llm_judge_evaluator.py        ← 方案B：手工 LLM-as-Judge（零外部依赖）
│       └── ragas_evaluator.py            ← 方案A：封装 RAGAS 库
│
├── 配套工具
│   ├── evaluation/
│   │   ├── __init__.py                   ← 统一导出入口
│   │   └── langfuse_integration.py       ← LangFuse 集成（Tracing + Dataset + Scores）
│   ├── run_evaluation.py                 ← 独立评测脚本（命令行批量跑）
│   └── api/apps/restful_apis/
│       └── evaluation_api.py             ← HTTP RESTful API（14 个端点）
│
├── 测试
│   └── tests/
│       ├── test_evaluation.py             ← 48 个测试用例
│       └── mock_data/eval_dataset.json    ← 10 条 mock 评测数据
│
├── 依赖
│   ├── offline_packages/                  ← 105 个 Python 3.12 .whl 离线包
│   └── evaluation_deps/
│       ├── requirements.txt               ← 全部依赖清单
│       ├── requirements-ragas.txt         ← 方案A 专属依赖
│       ├── install.bat                    ← Windows 一键安装
│       └── install.sh                     ← Linux/Mac 一键安装
│
└── 文档
    └── docs/
        ├── prd_rag_evaluation_system.md          ← 产品需求文档
        ├── architecture_evaluation_system.md     ← 系统架构设计
        └── eval-system-delivery-2026-05-22.md    ← 交付总结
```


## 🚀 内网部署（Python 3.12）

离线包已全部下载为 Python 3.12 版本（cp312），无需外网。

```bash
# 1. 把整个 evaluation_migration/ 拷到内网机器，解压

# 2. 创建 Python 3.12 虚拟环境
cd evaluation_migration/
python -m venv venv

# 3. 激活虚拟环境
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/Mac

# 4. 安装依赖（仅用本地包，不联网）
pip install --no-index --find-links=./offline_packages/ -r evaluation_deps/requirements.txt

# 5. 验证
python -c "from evaluation import auto_evaluate; print('OK')"
python -m pytest tests/test_evaluation.py -v
```


## 🔥 领导要的用法：在 ragflow 里加评测

### 方案B（推荐，零外部依赖，拷过去就能用）

```python
# ===== ① 项目启动时初始化一次 =====
from evaluation import set_llm_callable

# 把 ragflow 的 LLM 传给评测器
set_llm_callable(LLMBundle(tenant_id, "chat", model_name).chat)


# ===== ② 在 RAG 检索函数里加一行 =====
from evaluation import auto_evaluate

def your_rag_function(question):
    # ... 你们原来的 RAG 检索逻辑 ...
    answer, contexts = do_search_and_generate(question)

    # 🆕 就这一行！自动计算四个指标
    scores = auto_evaluate(
        question=question,
        answer=answer,
        contexts=contexts,
    )

    # scores = {
    #     "faithfulness": 0.85,       # 答案有没有幻觉（0-1，越高越好）
    #     "context_precision": 0.72,   # 检索到的文档有多少真有用（0-1）
    #     "context_recall": None,      # 没给标准答案时为 None
    #     "answer_relevancy": 0.90,    # 有没有答非所问（0-1）
    # }

    return answer, scores
```

### 方案A（需要 OpenAI Key）

```python
from evaluation.auto_hook import auto_evaluate_ragas
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

scores = auto_evaluate_ragas(
    question=question, answer=answer, contexts=contexts,
    llm=llm, embeddings=embeddings,
)
```

### 装饰器写法（更简洁）

```python
from evaluation import with_evaluation

@with_evaluation()
def ask_rag(question):
    answer, contexts = my_search(question)
    return {"answer": answer, "contexts": contexts}

result = ask_rag("什么是RAG？")
print(result["evaluation"])  # 自动带上的四个指标
```


## 独立评测脚本用法

不需要改 ragflow 代码，也能独立跑评测：

```bash
# 最简：读数据集，模拟 RAG，算指标，打印报告
python run_evaluation.py --dataset tests/mock_data/eval_dataset.json

# 输出 JSON 报告
python run_evaluation.py --dataset tests/mock_data/eval_dataset.json --output report.json

# 输出 Markdown 报告
python run_evaluation.py --dataset tests/mock_data/eval_dataset.json --output report.md --format markdown

# 只算部分指标
python run_evaluation.py --dataset tests/mock_data/eval_dataset.json --metrics faithfulness,context_precision

# 只跑前 5 条（调试用）
python run_evaluation.py --dataset tests/mock_data/eval_dataset.json --limit 5 --verbose

# 定时任务（Linux cron，每天早上 8 点自动跑）
# 0 8 * * * cd /path/to/ragflow && python run_evaluation.py --dataset qa_dataset.json --output /var/log/eval_report.json
```


## 四个评测指标

| 指标 | 测什么 | 需要标准答案 |
|------|--------|:---:|
| **faithfulness** | 答案有没有幻觉（是不是从文档里抄的） | ❌ |
| **context_precision** | 检索到的文档有多少是真正有用的，有用的排前面没 | ❌ |
| **context_recall** | 该检索到的信息都检索到了吗 | ✅ |
| **answer_relevancy** | 答案有没有跑题（是不是在回答问题） | ❌ |

- 没有标准答案时，自动跳过 context_recall（返回 None）
- 所有指标值域 0.0 ~ 1.0


## 每个文件什么用

| 文件 | 谁用 | 什么时候用 |
|------|------|-----------|
| `evaluation/auto_hook.py` | RAG pipeline | 每次检索后自动调 |
| `evaluation/base.py` | 开发者 | 定义评测器接口规范 |
| `evaluation/prompts.py` | 开发者 | 改 prompt 调优评测精度 |
| `evaluation/llm_judge_evaluator.py` | 开发者 | 方案B 核心（手工 LLM 评测） |
| `evaluation/ragas_evaluator.py` | 开发者 | 方案A 核心（RAGAS 库） |
| `evaluation/langfuse_integration.py` | 运维/开发者 | 接入 LangFuse 平台 |
| `run_evaluation.py` | 任何人 | 命令行批量评测出报告 |
| `evaluation_api.py` | 前端/curl | HTTP 管理评测数据 |
| `eval_dataset.json` | 测试 | 10 条样例评测题 |


## 测试脚本测了什么（48 个用例）

| 测试类 | 数量 | 测试内容 |
|--------|:--:|---------|
| `TestBaseEvaluator` | 6 | 基类：聚合计算、指标筛选、参数校验 |
| `TestLLMJudgeEvaluator` | 17 | 方案B：四个指标计算、JSON 容错解析、边界条件（空值、无 ground_truth） |
| `TestRagasEvaluator` | 2 | 方案A：单条+批量评测（需 OpenAI Key，默认跳过） |
| `TestEvaluationAPI` | 12 | HTTP API：数据集 CRUD、用例增删导入、Run 创建查询、完整工作流 |
| `TestAutoHook` | 11 | **领导要的接口**：`auto_evaluate()` 基础调用、`with_evaluation()` 装饰器、结果落盘、LLM 异常容错、真实 RAG pipeline 模拟 |

运行测试：

```bash
# 全量
python -m pytest tests/test_evaluation.py -v

# 只看领导要的接口
python -m pytest tests/test_evaluation.py -v -k "AutoHook"

# 只看方案B
python -m pytest tests/test_evaluation.py -v -k "LLMJudge"

# 只看 HTTP API
python -m pytest tests/test_evaluation.py -v -k "API"
```


## 内网部署步骤

### 方式一：离线包安装（推荐）

```bash
cd evaluation_migration/
python -m venv venv
venv\Scripts\activate
pip install --no-index --find-links=./offline_packages/ -r evaluation_deps/requirements.txt
python -c "from evaluation import auto_evaluate; print('OK')"
```

### 方式二：方案B 零安装

方案B 不依赖 ragas/langfuse 等第三方库，只需 Python 3.12 + numpy/scikit-learn。直接把 `evaluation/` 目录拷过去就能 import。numpy/scikit-learn 离线包也在 `offline_packages/` 里。


## 常见问题

**Q: 我只想要方案B，不想要 ragas/langfuse，怎么精简？**
A: 只拷贝 `evaluation/auto_hook.py`、`base.py`、`prompts.py`、`llm_judge_evaluator.py`、`__init__.py` 五个文件就够了。方案B 零外部依赖。

**Q: 评测一次要多久？**
A: 方案B 每条用例约 6-12 次 LLM 调用（取决于算几个指标）。用 mock LLM 验证时约 1-2 秒/条。

**Q: 内网没有 OpenAI 能用吗？**
A: 方案B 不需要 OpenAI，只要你有任意 LLM（内网的 ragflow 模型就行）。方案A 需要 OpenAI API。

**Q: auto_evaluate 报 "未初始化" 错？**
A: 需要先调用 `set_llm_callable()`，把你们的 LLM 传进去。参考上面的"领导要的用法"。
