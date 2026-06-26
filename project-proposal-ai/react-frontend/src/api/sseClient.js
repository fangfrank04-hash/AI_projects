/**
 * SSE客户端封装
 * 连接Python FastAPI SSE端点，处理所有AI交互
 */

const SSE_BASE_URL = 'http://localhost:8000';

export class SSEClient {
  constructor() {
    this.eventSource = null;
    this.sessionId = null;
    this.handlers = {};
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 3;
    this.reconnectDelays = [1000, 2000, 4000];
    this.connectionParams = null;
  }

  /**
   * 建立SSE连接
   * @param {Object} params - { projectId, userName, isPM }
   * @param {Object} handlers - 事件处理器
   */
  connect(params, handlers) {
    this.connectionParams = params;
    this.handlers = handlers;
    this.reconnectAttempts = 0;

    // 关闭已有连接，防止 StrictMode 双挂载导致连接泄漏
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }

    const url = `${SSE_BASE_URL}/api/chat/stream?projectId=${encodeURIComponent(params.projectId)}&userName=${encodeURIComponent(params.userName)}&isPM=${params.isPM}`;

    console.log('[SSE] Connecting to:', url);

    this.eventSource = new EventSource(url);

    // 注册事件监听器
    this.eventSource.addEventListener('connected', (e) => {
      const data = JSON.parse(e.data);
      this.sessionId = data.sessionId;
      this.reconnectAttempts = 0;
      console.log('[SSE] Connected, sessionId:', this.sessionId);
      handlers.onConnected?.(data);
    });

    this.eventSource.addEventListener('preview', (e) => {
      handlers.onPreview?.(JSON.parse(e.data));
    });

    this.eventSource.addEventListener('text', (e) => {
      handlers.onText?.(JSON.parse(e.data));
    });

    this.eventSource.addEventListener('update_project', (e) => {
      handlers.onUpdateProject?.(JSON.parse(e.data));
    });

    this.eventSource.addEventListener('update_team', (e) => {
      handlers.onUpdateTeam?.(JSON.parse(e.data));
    });

    this.eventSource.addEventListener('fillback_complete', (e) => {
      handlers.onFillbackComplete?.(JSON.parse(e.data));
    });

    this.eventSource.addEventListener('error', (e) => {
      try {
        handlers.onError?.(JSON.parse(e.data));
      } catch {
        handlers.onError?.({ message: 'SSE连接错误' });
      }
    });

    this.eventSource.addEventListener('ping', (e) => {
      handlers.onPing?.(JSON.parse(e.data));
    });

    this.eventSource.onerror = (err) => {
      console.error('[SSE] Connection error:', err);
      this._scheduleReconnect();
    };

    this.eventSource.onopen = () => {
      console.log('[SSE] Connection opened');
    };
  }

  _scheduleReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('[SSE] Max reconnect attempts reached');
      this.handlers.onError?.({ message: '连接失败，请刷新页面重试' });
      return;
    }

    const delay = this.reconnectDelays[this.reconnectAttempts] || 4000;
    this.reconnectAttempts++;

    console.log(`[SSE] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);

    setTimeout(() => {
      if (this.connectionParams) {
        this.connect(this.connectionParams, this.handlers);
      }
    }, delay);
  }

  /**
   * 发送用户消息
   * @param {string} message - 用户输入的指令
   */
  async sendMessage(message) {
    if (!this.sessionId) {
      console.error('[SSE] No session, cannot send message');
      return { error: '未建立连接' };
    }

    try {
      const response = await fetch(`${SSE_BASE_URL}/api/chat/message`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sessionId: this.sessionId,
          message: message
        }),
      });
      return await response.json();
    } catch (err) {
      console.error('[SSE] Send message failed:', err);
      return { error: err.message };
    }
  }

  /**
   * 发送一键回填指令（携带预览面板的最新数据）
   * @param {Object} draftProjectData - 预览面板的项目数据
   * @param {Array} draftTeamData - 预览面板的团队数据
   */
  async sendFillback(draftProjectData, draftTeamData) {
    if (!this.sessionId) {
      console.error('[SSE] No session, cannot send fillback');
      return { error: '未建立连接' };
    }

    try {
      const response = await fetch(`${SSE_BASE_URL}/api/chat/fillback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sessionId: this.sessionId,
          draftProjectData: draftProjectData,
          draftTeamData: draftTeamData
        }),
      });
      return await response.json();
    } catch (err) {
      console.error('[SSE] Send fillback failed:', err);
      return { error: err.message };
    }
  }

  /**
   * 断开连接
   */
  disconnect() {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
      this.sessionId = null;
      console.log('[SSE] Disconnected');
    }
  }

  /**
   * 检查是否已连接
   */
  isConnected() {
    return this.eventSource !== null && this.sessionId !== null;
  }
}

// 单例实例
export default new SSEClient();
