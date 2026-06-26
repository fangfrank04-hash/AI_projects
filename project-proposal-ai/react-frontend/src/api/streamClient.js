/**
 * streamClient.js — 模式3：fetch + ReadableStream
 * 每次对话是一条独立的 POST 请求，响应体是 SSE 格式的流。
 * 不需要预建连接、不需要 sessionId、不需要心跳。
 */

const API_BASE = 'http://localhost:8000';

export class StreamClient {
  constructor() {
    this.abortController = null;
  }

  /**
   * 发送消息并流式接收回复
   * @param {Object} params - { projectId, userName, isPM, message }
   * @param {Object} handlers - 事件处理器，key 为 onXxx（如 onText, onUpdateProject）
   * @returns {Promise<{aborted: boolean}>}
   */
  async chat(params, handlers) {
    // 取消上一次未完成的请求（用户快速连续发送时）
    if (this.abortController) {
      this.abortController.abort();
    }
    this.abortController = new AbortController();

    try {
      const response = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params),
        signal: this.abortController.signal,
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        handlers.onError?.({ message: err.message || `请求失败 (${response.status})` });
        return { aborted: false };
      }

      // 关键：从响应体中逐块读取
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // SSE 格式解析：按行切分，遇到空行视为一个事件结束
        const parts = buffer.split('\n\n');
        buffer = parts.pop() || '';  // 最后一段可能不完整，留到下轮拼接

        for (const part of parts) {
          if (!part.trim()) continue;
          const parsed = this._parseSSE(part);
          if (parsed) {
            this._dispatch(parsed.event, parsed.data, handlers);
          }
        }
      }
    } catch (err) {
      if (err.name !== 'AbortError') {
        console.error('[streamClient] fetch error:', err);
        handlers.onError?.({ message: err.message || '网络错误' });
      }
      return { aborted: err.name === 'AbortError' };
    }
  }

  /**
   * 一键回填（独立 POST，不走流式）
   */
  async fillback(projectId, userName, isPM, draftProjectData, draftTeamData) {
    try {
      const response = await fetch(`${API_BASE}/api/chat/fillback-v3`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          projectId,
          userName,
          isPM,
          draftProjectData,
          draftTeamData,
        }),
      });
      return await response.json();
    } catch (err) {
      return { status: 'error', message: err.message };
    }
  }

  /** 取消进行中的请求 */
  cancel() {
    if (this.abortController) {
      this.abortController.abort();
      this.abortController = null;
    }
  }

  // ---------- 内部方法 ----------

  /**
   * 解析单个 SSE 事件块
   * 输入: "event: text\ndata: {\"content\":\"你好\"}"
   * 输出: { event: "text", data: { content: "你好" } }
   */
  _parseSSE(block) {
    let event = '';
    let dataStr = '';
    for (const line of block.split('\n')) {
      const trimmed = line.trim();
      if (trimmed.startsWith('event:')) {
        event = trimmed.slice(6).trim();
      } else if (trimmed.startsWith('data:')) {
        dataStr = trimmed.slice(5).trim();
      }
    }
    if (!event || !dataStr) return null;

    try {
      return { event, data: JSON.parse(dataStr) };
    } catch {
      return { event, data: { raw: dataStr } };
    }
  }

  /**
   * 把 event 名映射到 handlers
   * event="text" → handlers.onText(data)
   * event="update_project" → handlers.onUpdateProject(data)
   */
  _dispatch(event, data, handlers) {
    // event 名转驼峰: "update_project" → "onUpdateProject"
    const handlerKey = 'on' + event
      .split('_')
      .map(w => w.charAt(0).toUpperCase() + w.slice(1))
      .join('');
    handlers[handlerKey]?.(data);
  }
}

// 单例
export default new StreamClient();
