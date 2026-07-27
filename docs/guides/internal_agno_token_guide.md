# 内网 Agno 模型 Token 限制对照

本地代码对照文件：

```text
docs/guides/snippets/internal_agno_tools_reference.py
```

内网目标文件是截图中的 `app/utils/tools.py`，目标方法是 `get_agno_model()`。本地项目没有内网的 `app/config` 目录结构和 Agno 依赖，因此对照代码不接入本地运行入口。

## 当前可以确认的值

```text
config.chat[key].max_tokens
  -> 来自 t_model_config.max_tokens
  -> Qwen3.6-27B 为 49152
  -> Qwen3.6-35B-A3B 为 67584
  -> 表示输入与输出合计的总上下文预算
```

Agno `OpenAILike(max_tokens=...)` 中的 `max_tokens` 用于单次最大输出，不能直接传入 `49152/67584`，应限制为：

```python
max_output_tokens = min(requested_output_tokens, 16384)
```

## 不能在模型工厂中直接得到的值

“本次请求已经消耗的输入 token”取决于 Agno 最终构造的系统提示词、历史消息、工具调用结果和用户输入。`get_agno_model()` 只创建模型对象，执行时间早于 Agno 构造最终请求，因此静态的 `config.chat[key]` 通常不能提供本次请求的实际消耗值。

如果内网配置对象确实还有一个已消耗 token 字段，需要继续提供以下证据后再接入：

```text
config.chat[key] 对应类的完整字段定义
t_model_config 对应记录的完整字段名
该消耗值在哪里、何时更新
get_agno_model() 的全部调用结果
```

不要根据字段名称猜测后直接相减，否则多个并发 Agent 请求可能共享同一个过期值。

## 内网修改步骤

1. 删除打印 `config.chat[key].api_key` 的日志。
2. 在 `get_agno_model()` 中读取 `model_config = config.chat[key]`。
3. 读取 `model_config.max_tokens`，只用于记录总上下文和验证数据库配置。
4. 将 `OpenAILike.max_tokens` 限制为 `<=16384`。
5. 搜索全部 `get_agno_model(` 与 `OpenAILike(`，确认没有绕开统一工厂的调用。
6. 单独定位 Agno 最终消息构造位置，再处理 27B 的 32K 输入限制和 35B-A3B 的 50K 输入限制。

## 验证日志

预期日志：

```text
Agno model config: model=Qwen3.6-27B context_tokens=49152 max_output_tokens=16384
Agno model config: model=Qwen3.6-35B-A3B context_tokens=67584 max_output_tokens=16384
```

日志中不得出现 API Key、Authorization、完整用户问题或知识库正文。
