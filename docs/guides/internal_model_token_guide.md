# 内网模型 Token 链路、验证与修改指南

## 用途和范围

本指南记录的是内网 IARM 项目中已经通过代码和数据库截图确认的链路，供后续在内网测试环境排查、打印日志和修改使用。

本仓库是参考用的 GitHub RAGFlow 源码；内网项目的实际文件位于 `src/app/...`，应以内网当前分支的代码为准。

## 先分清三个值

| 名称 | 含义 | 当前内网位置 |
| --- | --- | --- |
| `C`，总上下文窗口 | 模型一次请求可容纳的输入和输出总预算 | `t_model_config.max_tokens` |
| `I`，实际输入 token | 系统提示词、用户问题、历史消息、知识库片段、图片等之和 | 每次请求动态计算 |
| `O`，实际允许输出 token | 本次请求模型最多生成多少 token | `t_rag_dialog.llm_setting.max_tokens`，应传给网关 |

原始 RAGFlow 的设计关系是：

```text
I + O <= C
```

官方 RAGFlow 将对应数据库字段说明为 `Max context token num`。它先使输入适配总窗口，再将输出限制为剩余空间。

## 网关限制

组长提供的网关文档说明：

| 模型 | 输入限制 | 输出限制 |
| --- | --- | --- |
| Qwen3.6-27B | `I <= 32K` | `O <= 16K` |
| Qwen3.6-35B-A3B | `I <= 50K` | `O <= 16K` |

补充限制：多模态图片 Base64 最大 5 MB；输入超限返回 `400`；并发超限返回 `429`。

当前业务前提要求在输入达到上限时，仍保留完整 16K 输出，因此总上下文预算已经确定为：

| 模型 | 输入预算 | 输出预算 | `t_model_config.max_tokens` |
| --- | ---: | ---: | ---: |
| Qwen3.6-27B | 32768 | 16384 | 49152 |
| Qwen3.6-35B-A3B | 51200 | 16384 | 67584 |

这里的 `49152/67584` 是输入与输出合计预算，`32768/51200` 才是单独的输入上限。

## 已确认的内网运行链路

### 1. 数据库模型配置进入运行时 `config`

```text
t_model_config
  -> ModelConfig，ORM 表映射
  -> ModelConfigRepository
  -> ModelConfigService.get_models_sync()
  -> TemplateRenderer.to_ns(configs)
  -> ConfigProxy._config_model
  -> config.chat[模型名]
```

相关内网文件和位置：

```text
src/app/core/database/db/model.py
  class ModelConfig，__tablename__ = "t_model_config"

src/app/repositories/model_config_repository.py
  class ModelConfigRepository

src/app/services/model_config_service.py
  class ModelConfigService

src/app/core/config/settings.py
  class ConfigProxy.__getattr__()
  ModelConfigService(session).get_models_sync()
  TemplateRenderer.to_ns(configs)
```

`config` 不是一个简单的 YAML 变量。访问 `config.chat` 时，`ConfigProxy` 会调用 `ModelConfigService.get_models_sync()`，将数据库模型配置合并进运行时配置。

### 2. 普通智能问答选择模型

```text
前端聊天页面
  -> session_api.py 的 completion()
  -> dia_service.chat(..., llmConfig=config)
  -> dialog_service.py 的 get_models()
  -> llmConfig.chat[llm_name]
  -> LLMBundle(..., llm_config=...)
  -> LLM4Tenant
  -> self.max_length = self.llm_config.max_tokens
```

相关内网文件：

```text
src/app/api/chat/session_api.py
src/app/core/rag_document/services/dialog_service.py
src/app/core/rag_document/services/tenant_llm_service.py
```

因此，`t_model_config.max_tokens` 会成为运行时的 `chat_mdl.max_length`。

### 3. 会话输出参数

```text
t_rag_dialog.llm_setting
  -> dialog.llm_setting.model_dump()
  -> gen_conf
  -> chat_model.py
  -> Xinference OpenAI-compatible 请求
```

有关文件：

```text
src/app/core/rag_document/models/models_ext.py
  RagDialog.llm_setting

src/app/core/schemas/base_schema.py
  LLMSetting.max_tokens，当前默认 20480

src/app/core/rag_document/services/dialog_service.py
  gen_conf = dialog.llm_setting.model_dump()
```

当前数据库中已观察到会话 `llm_setting.max_tokens` 有 `20480`、`64000`、`80178`、`90022` 等值，均高于网关要求的 16K。

### 4. 当前输出限制未传给 Xinference

在以下代码中：

```text
src/app/core/rag_document/common/llm/chat_model.py
  Base._clean_conf()
```

存在：

```python
if "max_tokens" in gen_conf:
    del gen_conf["max_tokens"]
```

而 `XinferenceChat` 只继承 `Base`，没有自己的 `_clean_conf()` 覆盖。因此当前链路是：

```text
llm_setting.max_tokens
  -> gen_conf
  -> 被 Base._clean_conf() 删除
  -> 最终 Xinference 请求没有该输出上限
```

`total_tokens` 不是配置，也不会限制模型。它只是模型回复后对实际用量的统计。

## 当前风险

1. 当前会话输出设置大于 16K，但适配层删除了设置，项目无法显式控制网关输出。
2. 如果直接恢复传递旧会话的值，可能把 `90022` 等非法输出上限发给网关。
3. 只把 `t_model_config.max_tokens` 改成 `49152/67584` 还不够。原代码用 `max_tokens * 0.95` 裁剪输入，会分别允许约 46694/64204 token，超过网关的 32K/50K 输入上限。
4. 截图中的普通 `chat()` 分支曾将 `kb_ids` 设为空并转到 `chat_solo()`。该分支是否先裁剪长输入，需要在当前代码中单独验证。

## 修改方案

所有改动先在测试环境完成。不要先批量修改旧会话。

### A. 修改总上下文窗口 C

改动位置：

```text
优先使用前端模型管理页面保存
  -> POST /model/update
  -> ModelConfigService.update_model()
  -> t_model_config.max_tokens
```

不要先直接执行 SQL。通过页面/API 更新会走服务层，并清理 `model_config` Redis 缓存键。

数据库修改与验证 SQL：

```sql
SELECT id, name, type, factory, max_tokens, extra
FROM t_model_config
WHERE name IN ('Qwen3.6-27B', 'Qwen3.6-35B-A3B');

UPDATE t_model_config
SET max_tokens = CASE name
    WHEN 'Qwen3.6-27B' THEN 49152
    WHEN 'Qwen3.6-35B-A3B' THEN 67584
END
WHERE name IN ('Qwen3.6-27B', 'Qwen3.6-35B-A3B');
```

通过页面/API 修改会清理缓存。若直接执行 SQL，修改后应重启后端服务或清除 Redis 的 `model_config` 缓存键；只刷新浏览器不够。

### B. 单独限制两个模型的输入长度

在 `dialog_service.py` 中，不能继续对这两个模型使用：

```python
used_token_count, msg = message_fit_in(msg, int(max_tokens * 0.95))
```

应按实际模型限制输入，并让其他模型保留原有逻辑：

```python
llm_id = dialog.llm_id or ""
if "Qwen3.6-27B" in llm_id:
    input_token_limit = 32768
elif "Qwen3.6-35B-A3B" in llm_id:
    input_token_limit = 51200
else:
    input_token_limit = int(max_tokens * 0.95)

used_token_count, msg = message_fit_in(msg, input_token_limit)
```

输出同时受会话设置、16K 网关上限和总上下文剩余空间约束：

```python
gen_conf["max_tokens"] = min(
    gen_conf["max_tokens"],
    16384,
    max_tokens - used_token_count,
)
```

### C. 修改新会话的默认输出上限

验收完整 16K 输出能力时，新测试会话应设置 `max_tokens=16384`。如果后续出于性能策略希望默认生成更短，可再将新会话默认值设为 `14000`，但运行时硬上限仍保持 `16384`。

文件一：

```text
src/app/core/schemas/base_schema.py
class LLMSetting
```

将：

```python
max_tokens: Annotated[int | None, Field(default=20480)]
```

改为：

```python
max_tokens: Annotated[int | None, Field(default=16384)]
```

文件二：

```text
src/app/core/rag_document/models/models_ext.py
class RagDialog
```

将 `llm_setting` 的数据库默认 JSON 中的 `max_tokens` 改为相同值 `16384`，避免代码默认值与数据库默认值不一致。

这一步只影响后续创建的会话，不能使输出控制立刻生效。

### D. 让 Xinference 输出上限真正生效

先确认网关接收的字段名，二选一：

```text
max_tokens
max_completion_tokens
```

确认后，在下列类中增加专用处理，不要直接修改所有厂商共用的 `Base._clean_conf()`：

```text
src/app/core/rag_document/common/llm/chat_model.py
class XinferenceChat(Base)
```

如果网关确认接收 `max_tokens`，可在 `XinferenceChat` 类中加入：

```python
def _clean_conf(self, gen_conf):
    raw_conf = dict(gen_conf or {})
    requested = raw_conf.get("max_tokens", 14000)

    try:
        requested = int(requested)
    except (TypeError, ValueError):
        requested = 14000

    cleaned_conf = super()._clean_conf(raw_conf)
    cleaned_conf["max_tokens"] = min(max(requested, 1), 16384)

    logger.info(
        "Xinference generation config: model=%s config=%s",
        self.model_name,
        cleaned_conf,
    )
    return cleaned_conf
```

如果网关确认接收 `max_completion_tokens`，将上面唯一的一行改为：

```python
cleaned_conf["max_completion_tokens"] = min(max(requested, 1), 16384)
```

不要同时发送两个字段。

### E. 将本地估算 token 写入 `reference`

当前第三方平台的流式总 token 在 `LLMBundle.chat_streamly()` 中被截住，而且底层值混合了网关总数与分片估算，不能直接作为三个字段使用。第一版在 `dialog_service.py` 的 `decorate_answer()` 中使用同一套本地估算口径：

```python
tk_num = num_tokens_from_string(think + answer)

refs["token_usage"] = {
    "input_tokens": used_token_count,
    "output_tokens": tk_num,
    "total_tokens": used_token_count + tk_num,
    "count_source": "local_estimate",
}
```

`input_tokens` 来自 `message_fit_in()`，`output_tokens` 包含处理后的思考内容与答案。它们适合排查和展示，不应用于第三方计费对账。若以后要求网关真实值，需要单独贯通 `prompt_tokens/completion_tokens/total_tokens` 的流式 usage 链路。

## 如何确认网关字段

在测试环境使用测试 API Key 发一个很小的输出请求。不要在日志、截图或聊天中暴露真实 Key。

PowerShell 示例，先测试 `max_tokens`：

```powershell
curl.exe -sS -X POST "http://<gateway-host>/v1/chat/completions" `
  -H "Content-Type: application/json" `
  -H "Authorization: Bearer <test-api-key>" `
  -d "{\"model\":\"Qwen3.6-27B\",\"messages\":[{\"role\":\"user\",\"content\":\"请连续输出一段很长的中文内容。\"}],\"max_tokens\":64,\"stream\":false}"
```

判断方法：

```text
HTTP 200 且回复明显受 64 token 限制，或 finish_reason=length：字段有效。
未知字段/400：改测 max_completion_tokens。
HTTP 200 但输出明显不受限：查看网关日志或向网关维护方确认。
```

## 打印验证

临时日志只记录模型名、总窗口和生成参数，绝不记录 API Key、Authorization、完整问题或知识库内容。

### 验证数据库总窗口是否进入运行时

在 `LLM4Tenant.__init__()` 中，紧跟：

```python
self.max_length = self.llm_config.max_tokens
```

增加：

```python
logger.info(
    "LLM context window: model=%s max_length=%s",
    self.llm_name,
    self.max_length,
)
```

### 验证最终输出参数

使用上面的 `XinferenceChat._clean_conf()` 日志。预期日志示例：

```text
Xinference generation config: model=Qwen3.6-27B max_tokens=16384
```

## 推荐测试顺序

1. 备份并查询 `t_model_config` 当前值。
2. 将 27B/35B-A3B 的总上下文分别更新为 `49152/67584`，并让后端缓存失效。
3. 在 `dialog_service.py` 将两个模型的输入分别限制为 `32768/51200`。
4. 修正 `XinferenceChat._clean_conf()`，确认读取的是复数键 `max_tokens`，并将最终值限制到 `<=16384`。
5. 新建临时测试会话，将 `llm_setting.max_tokens` 设置为 `16384`。
6. 在 `reference.token_usage` 中写入本地估算的输入、输出、总 token 和 `count_source`。
7. 重启后验证运行时 `max_length`、输入限制、最终输出参数和数据库/API 中的 `reference`。
8. 最后才处理历史会话中大于 16K 的 `llm_setting.max_tokens`。

## 变更后的验收条件

```text
数据库模型配置能够在日志中显示为运行时 max_length。
Qwen3.6-27B 的 max_length=49152，输入限制=32768。
Qwen3.6-35B-A3B 的 max_length=67584，输入限制=51200。
最终 Xinference 请求含有且只含一个输出上限字段。
最终输出上限 <= 16384。
测试会话输出上限为 16384。
长输入按已确认的总上下文窗口和网关输入上限处理。
reference.token_usage 包含 input_tokens、output_tokens、total_tokens、count_source。
API Key 和用户问题不进入新增日志。
```
