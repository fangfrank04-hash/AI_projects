import React, { useState, useRef, useEffect } from 'react';
import sseClient from './api/sseClient';
import {
  ChevronRight,
  MessageSquare,
  X,
  Send,
  Bot,
  User,
  Bell,
  Search,
  ChevronDown,
  Loader2,
  CheckCircle,
  Maximize2,
  Minimize2
} from 'lucide-react';

// ============================================
// AI聊天机器人组件
// ============================================

const AIChatbot = ({
  projectData, setProjectData,
  teamData, setTeamData,
  controlData, setControlData,
  scheduleData, setScheduleData,
  resourceData, setResourceData,
  qualityData, setQualityData,
  currentUser, isCurrentUserPM,
  knowledgeRules,
  historyData
}) => {
  const [isOpen, setIsOpen] = useState(true);
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [currentStep, setCurrentStep] = useState(1);

  const [draftProjectData, setDraftProjectData] = useState(null);
  const [draftTeamData, setDraftTeamData] = useState(null);
  const [draftControlData, setDraftControlData] = useState(null);
  const [draftScheduleData, setDraftScheduleData] = useState(null);
  const [draftResourceData, setDraftResourceData] = useState(null);
  const [draftQualityData, setDraftQualityData] = useState(null);

  const [sseConnected, setSseConnected] = useState(false);
  const [sessionId, setSessionId] = useState(null);

  const messagesEndRef = useRef(null);
  const chatboxRef = useRef(null);
  const streamingMsgIdRef = useRef(null);

  const [position, setPosition] = useState({ top: null, left: null });
  const [isDragging, setIsDragging] = useState(false);
  const [isMaximized, setIsMaximized] = useState(false);
  const dragStart = useRef({ offsetX: 0, offsetY: 0 });

  useEffect(() => {
    const handleMouseMove = (e) => {
      if (!isDragging || !chatboxRef.current || isMaximized) return;

      let newLeft = e.clientX - dragStart.current.offsetX;
      let newTop = e.clientY - dragStart.current.offsetY;

      const maxX = window.innerWidth - chatboxRef.current.offsetWidth;
      const maxY = window.innerHeight - chatboxRef.current.offsetHeight;

      newLeft = Math.max(0, Math.min(newLeft, maxX));
      newTop = Math.max(0, Math.min(newTop, maxY));

      setPosition({ top: newTop, left: newLeft });
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    if (isDragging) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
    }
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging, isMaximized]);

  const handleMouseDown = (e) => {
    if (!chatboxRef.current || isMaximized) return;
    setIsDragging(true);
    const rect = chatboxRef.current.getBoundingClientRect();
    dragStart.current = {
      offsetX: e.clientX - rect.left,
      offsetY: e.clientY - rect.top
    };
    if (position.top === null) {
      setPosition({ top: rect.top, left: rect.left });
    }
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    // 切换用户时清空聊天状态
    setMessages([]);
    setIsTyping(false);
    setSseConnected(false);
    setSessionId(null);
    streamingMsgIdRef.current = null;
    setDraftProjectData(null);
    setDraftTeamData(null);
    setDraftControlData(null);
    setDraftScheduleData(null);
    setDraftResourceData(null);
    setDraftQualityData(null);

    sseClient.connect(
      { projectId: projectData.id, userName: currentUser, isPM: isCurrentUserPM },
      {
        onConnected: (data) => {
          setSessionId(data.sessionId);
          setSseConnected(true);
        },
        onPreview: (data) => {
          setDraftProjectData(data.projectData);
          setDraftTeamData(data.teamData);
          // 初始加载时同步到真实表单（后续修改只更新 draft，需点"确认回填"才同步）
          setProjectData(data.projectData);
          setTeamData(data.teamData);
          setMessages(prev => [...prev, {
            id: Date.now(),
            role: 'ai',
            type: 'preview_team',
            text: '📍 【项目基本信息与团队职责确认】\n请确认以下信息，修改后点一键回填同步至主页面表单。'
          }]);
          setIsTyping(false);
        },
        onText: (data) => {
          setIsTyping(false);
          if (streamingMsgIdRef.current) {
            setMessages(prev => prev.map(m =>
              m.id === streamingMsgIdRef.current ? { ...m, text: m.text + data.content } : m
            ));
          } else {
            const newId = Date.now();
            streamingMsgIdRef.current = newId;
            setMessages(prev => [...prev, { id: newId, role: 'ai', text: data.content }]);
          }
        },
        onUpdateProject: (data) => {
          setDraftProjectData(data.projectData);
          setIsTyping(false);
          streamingMsgIdRef.current = null;
        },
        onUpdateTeam: (data) => {
          setDraftTeamData(data.teamData);
          setIsTyping(false);
          streamingMsgIdRef.current = null;
        },
        onFillbackComplete: (data) => {
          setMessages(prev => [...prev, {
            id: Date.now(),
            role: 'ai',
            text: data.message || '🎉 回填成功！项目基本信息与团队数据已同步至左侧表单。'
          }]);
          setIsTyping(false);
          streamingMsgIdRef.current = null;
        },
        onError: (data) => {
          setMessages(prev => [...prev, { id: Date.now(), role: 'ai', text: `❌ 错误：${data.message}` }]);
          setIsTyping(false);
          streamingMsgIdRef.current = null;
        },
      }
    );

    return () => sseClient.disconnect();
  }, [currentUser, isCurrentUserPM, projectData.id]);

  const handleSend = async () => {
    if (!inputValue.trim() || isTyping) return;
    const userText = inputValue;

    streamingMsgIdRef.current = null;
    setMessages(prev => [...prev, { id: Date.now(), role: 'user', text: userText }]);
    setInputValue('');
    setIsTyping(true);

    if (!isCurrentUserPM) {
       setMessages(prev => [...prev, { id: Date.now()+1, role: 'ai', text: `❌ 权限拒绝：抱歉 ${currentUser}，您非项目经理，无权进行编辑。` }]);
       setIsTyping(false);
       return;
    }

    if (!sseClient.isConnected()) {
      setMessages(prev => [...prev, { id: Date.now()+1, role: 'ai', text: '❌ 未连接到AI服务，请刷新页面重试。' }]);
      setIsTyping(false);
      return;
    }

    const result = await sseClient.sendMessage(userText);
    if (result.error) {
      setMessages(prev => [...prev, { id: Date.now()+1, role: 'ai', text: `❌ 发送失败：${result.error}` }]);
      setIsTyping(false);
    }
  };

  if (!isOpen) {
    return (
      <button onClick={() => setIsOpen(true)} className="fixed bottom-6 right-6 bg-blue-600 text-white p-4 rounded-full shadow-lg hover:bg-blue-700 transition-all z-50">
        <MessageSquare size={24} />
      </button>
    );
  }

  return (
    <div
      ref={chatboxRef}
      className={`fixed bg-white border border-red-400 shadow-2xl flex flex-col ${
        isDragging ? 'transition-none' : 'transition-all duration-300'
      } ${
        isMaximized
          ? 'inset-0 z-[60] rounded-none'
          : 'rounded-xl z-50 max-h-[85vh]'
      }`}
      style={
        isMaximized
          ? { width: '100%', height: '100%' }
          : {
              width: '320px',
              top: position.top !== null ? `${position.top}px` : undefined,
              left: position.left !== null ? `${position.left}px` : undefined,
              ...(position.top === null ? { bottom: '24px', right: '24px' } : {})
            }
      }
    >
      <div className={`bg-gradient-to-r from-red-500 to-red-600 text-white p-2 flex justify-between items-center shadow-sm select-none shrink-0 ${isMaximized ? 'cursor-default' : 'cursor-move'}`} onMouseDown={handleMouseDown}>
        <div className="flex items-center space-x-1.5 overflow-hidden">
          <Bot size={16} className="shrink-0" />
          <span className="font-semibold text-xs whitespace-nowrap overflow-hidden text-ellipsis">AI助手 {isMaximized ? '' : '(拖拽)'}</span>
        </div>
        <div className="flex items-center space-x-1 shrink-0">
          <button onClick={(e) => { e.stopPropagation(); setIsMaximized(!isMaximized); }} className="hover:bg-red-700 p-1 rounded">
            {isMaximized ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
          </button>
          <button onClick={(e) => { e.stopPropagation(); setIsOpen(false); }} className="hover:bg-red-700 p-1 rounded">
            <X size={16} />
          </button>
        </div>
      </div>

      <div className={`flex-1 p-3 overflow-y-auto overflow-x-hidden bg-slate-50 flex flex-col space-y-3 ${isMaximized ? '' : 'h-[400px]'}`}>
        {messages.map((msg) => (
          <div key={msg.id} className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'} w-full`}>
            <div className={`max-w-[85%] rounded-2xl p-2.5 text-xs shadow-sm ${msg.role === 'user' ? 'bg-blue-600 text-white rounded-tr-none' : 'bg-white border border-slate-200 text-slate-700 rounded-tl-none whitespace-pre-wrap'}`}>
              {msg.text}
            </div>

            {/* Step 1: 团队与基本信息预览 */}
            {msg.type === 'preview_team' && draftTeamData && draftProjectData && (
              <div className="mt-2 bg-white border border-slate-200 rounded-lg p-3 shadow-md w-full relative flex flex-col">

                {/* 独立区块 1：项目基本信息 */}
                <div className="mb-3 w-full">
                  <div className="flex items-center mb-1.5">
                    <div className="w-1 h-3 bg-blue-600 mr-1.5"></div>
                    <h4 className="font-bold text-[11px] text-slate-800">项目基本信息</h4>
                  </div>
                  <div className="overflow-x-auto w-full pb-1">
                    <table className="w-full min-w-[400px] text-[10px] border-collapse border border-slate-200">
                      <tbody>
                        <tr className="border-b border-slate-200">
                          <th className="p-1 w-[20%] border-r border-slate-200 bg-slate-50 font-medium text-slate-600 text-right pr-1">项目编号</th>
                          <td className="p-0 w-[30%] border-r border-slate-200"><input value={draftProjectData.id} readOnly className="w-full p-1 bg-transparent outline-none text-slate-400 cursor-not-allowed" /></td>
                          <th className="p-1 w-[20%] border-r border-slate-200 bg-slate-50 font-medium text-slate-600 text-right pr-1">产品编号</th>
                          <td className="p-0 w-[30%]"><input value={draftProjectData.productNo} onChange={e => setDraftProjectData({...draftProjectData, productNo: e.target.value})} className="w-full p-1 bg-transparent outline-none focus:bg-blue-50 focus:text-blue-700 transition-colors" disabled={!isCurrentUserPM} /></td>
                        </tr>
                        <tr className="border-b border-slate-200">
                          <th className="p-1 border-r border-slate-200 bg-slate-50 font-medium text-slate-600 text-right pr-1">项目名称</th>
                          <td className="p-0 border-r border-slate-200"><input value={draftProjectData.name} readOnly className="w-full p-1 bg-transparent outline-none text-slate-400 cursor-not-allowed"/></td>
                          <th className="p-1 border-r border-slate-200 bg-slate-50 font-medium text-slate-600 text-right pr-1">产品名称</th>
                          <td className="p-0"><input value={draftProjectData.productName} onChange={e => setDraftProjectData({...draftProjectData, productName: e.target.value})} className="w-full p-1 bg-transparent outline-none focus:bg-blue-50 focus:text-blue-700 transition-colors" disabled={!isCurrentUserPM}/></td>
                        </tr>
                        <tr className="border-b border-slate-200">
                          <th className="p-1 border-r border-slate-200 bg-slate-50 font-medium text-slate-600 text-right pr-1">立项申请部门</th>
                          <td className="p-0 border-r border-slate-200"><input value={draftProjectData.dept} readOnly className="w-full p-1 bg-transparent outline-none text-slate-400 cursor-not-allowed"/></td>
                          <th className="p-1 border-r border-slate-200 bg-slate-50 font-medium text-slate-600 text-right pr-1">需求相关部门</th>
                          <td className="p-0"><input value={draftProjectData.reqDept} readOnly className="w-full p-1 bg-transparent outline-none text-slate-400 cursor-not-allowed"/></td>
                        </tr>
                        <tr className="border-b border-slate-200">
                          <th className="p-1 border-r border-slate-200 bg-slate-50 font-medium text-slate-600 text-right pr-1">基准需求编号</th>
                          <td className="p-0 border-r border-slate-200"><input value={draftProjectData.baseReq} readOnly className="w-full p-1 bg-transparent outline-none text-slate-400 cursor-not-allowed"/></td>
                          <th className="p-1 border-r border-slate-200 bg-slate-50 font-medium text-slate-600 text-right pr-1">变更需求编号</th>
                          <td className="p-0"><input value={draftProjectData.changeReq} readOnly className="w-full p-1 bg-transparent outline-none text-slate-400 cursor-not-allowed"/></td>
                        </tr>
                        <tr>
                          <th className="p-1 border-r border-slate-200 bg-slate-50 font-medium text-slate-600 text-right pr-1">项目控制策略类型</th>
                          <td className="p-0" colSpan={3}><input value={draftProjectData.level} readOnly className="w-full p-1 bg-transparent outline-none text-slate-400 cursor-not-allowed"/></td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* 独立区块 2：项目团队 */}
                <div className="mb-2 w-full">
                  <div className="flex items-center mb-1.5">
                    <div className="w-1 h-3 bg-blue-600 mr-1.5"></div>
                    <h4 className="font-bold text-[11px] text-slate-800">项目团队</h4>
                  </div>
                  <div className="overflow-x-auto w-full pb-1">
                    <table className="w-full min-w-[400px] text-[10px] border-collapse border border-slate-200 text-left">
                      <thead className="bg-slate-50">
                        <tr>
                          <th className="p-1 border border-slate-200 font-normal text-slate-400 text-center w-6"></th>
                          <th className="p-1 border border-slate-200 font-normal text-slate-500 w-[20%]">项目角色</th>
                          <th className="p-1 border border-slate-200 font-normal text-slate-500 w-[20%]">人员</th>
                          <th className="p-1 border border-slate-200 font-normal text-slate-500">职责</th>
                        </tr>
                      </thead>
                      <tbody>
                        {draftTeamData.map((member, idx) => (
                          <tr key={idx} className="border-b border-slate-200">
                            <td className="p-1 border-r border-slate-200 text-center text-slate-400">{idx + 1}</td>
                            <td className="p-0 border-r border-slate-200"><input value={member.role} readOnly className="w-full p-1 bg-transparent outline-none text-slate-400 cursor-not-allowed" /></td>
                            <td className="p-0 border-r border-slate-200"><input value={member.name} readOnly className="w-full p-1 bg-transparent outline-none text-slate-400 cursor-not-allowed" /></td>
                            <td className="p-1">
                              <div className="flex flex-wrap gap-1 text-slate-700">
                                {member.responsibilities.map((resp, rIdx) => (
                                  <label key={rIdx} className={`flex items-center space-x-1 shrink-0 ${isCurrentUserPM ? 'cursor-pointer hover:text-blue-600' : 'opacity-70'}`}>
                                    <input type="checkbox" checked={resp.checked} onChange={e => { if(!isCurrentUserPM)return; const d=[...draftTeamData]; d[idx].responsibilities[rIdx].checked=e.target.checked; setDraftTeamData(d); }} disabled={!isCurrentUserPM} className="accent-blue-600 w-2.5 h-2.5"/>
                                    <span className="text-[9px] leading-tight">{resp.name}</span>
                                  </label>
                                ))}
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                <button
                  onClick={async () => {
                    if(!isCurrentUserPM)return;
                    setTeamData(draftTeamData);
                    setProjectData(draftProjectData);
                    // 将预览面板最新数据传给后端执行持久化
                    if (sseClient.isConnected()) {
                      await sseClient.sendFillback(draftProjectData, draftTeamData);
                    }
                  }}
                  disabled={!isCurrentUserPM}
                  className={`w-full mt-1 text-white py-1.5 rounded text-xs shrink-0 transition-colors ${isCurrentUserPM?'bg-blue-600 hover:bg-blue-700':'bg-slate-300'}`}
                >
                  <CheckCircle size={14} className="inline mr-1" /> 确认并一键回填
                </button>
              </div>
            )}

          </div>
        ))}
        {isTyping && (
          <div className="flex justify-start">
            <div className="bg-white border border-slate-200 rounded-2xl rounded-tl-none p-2.5 text-xs flex items-center space-x-2">
              <Loader2 size={12} className="animate-spin text-blue-500" />
              <span>AI 思考中...</span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="p-2 bg-white border-t border-slate-100 flex items-center space-x-1.5 shrink-0">
        <input type="text" value={inputValue} onChange={e=>setInputValue(e.target.value)} onKeyDown={e=>e.key==='Enter'&&handleSend()}
               placeholder="输入指令..."
               className="flex-1 border border-slate-200 rounded min-w-0 px-2 py-1.5 text-xs focus:outline-none focus:border-red-400"/>
        <button onClick={handleSend} className="bg-red-500 hover:bg-red-600 text-white p-1.5 rounded shrink-0">
          <Send size={14} />
        </button>
      </div>
    </div>
  );
};

// ============================================
// 主页面组件
// ============================================

export default function App() {
  const [currentUser, setCurrentUser] = useState('陈杰');
  const [loading, setLoading] = useState(true);

  // 项目基本信息（与 Java H2 database data.sql 保持一致）
  const [projectData, setProjectData] = useState({
    id: 'PJ-202603-S-068',
    name: '验证主表单01221',
    dept: '信息科技部',
    baseReq: 'BD-2026-0078',
    level: 'S级',
    productNo: '',
    productName: '',
    reqDept: '信息科技部',
    changeReq: '',
    pmName: '陈杰',
    proposalBackground: '',
    proposalScope: ''
  });

  const isCurrentUserPM = currentUser === projectData.pmName;

  // 团队数据（与 Java H2 database data.sql 保持一致）
  const [teamData, setTeamData] = useState([
    { role: '产品经理', name: '张伟', responsibilities: [
      { name: '产品发布', checked: true },
      { name: '业务方案可行性分析', checked: true },
      { name: '需求评审', checked: true }
    ]},
    { role: '项目经理', name: '陈杰', responsibilities: [
      { name: '项目立项', checked: true },
      { name: '进度管理', checked: true },
      { name: '里程碑节点评审', checked: true }
    ]},
    { role: '开发负责人', name: '李明', responsibilities: [
      { name: '技术方案设计', checked: true },
      { name: '编码实现', checked: true },
      { name: '代码评审', checked: true }
    ]},
    { role: '测试负责人', name: '王芳', responsibilities: [
      { name: '测试用例设计', checked: true },
      { name: '功能测试', checked: true },
      { name: '回归测试', checked: true }
    ]},
    { role: '开发工程师', name: '马伟华', responsibilities: [
      { name: '编码实现', checked: true },
      { name: '代码评审', checked: true },
      { name: '技术方案设计', checked: true }
    ]}
  ]);

  // 管控方案数据
  const [controlData, setControlData] = useState([
    { phase: '需求阶段', required: true, result: '执行', reason: '' },
    { phase: '开发阶段', required: true, result: '执行', reason: '' },
    { phase: '测试阶段', required: true, result: '执行', reason: '' },
    { phase: '项目评审', required: false, result: '执行', reason: '' },
    { phase: '结项阶段', required: true, result: '执行', reason: '' }
  ]);

  // 进度计划数据
  const [scheduleData, setScheduleData] = useState([
    { milestone: '需求分析', startDate: '', endDate: '' },
    { milestone: '开发测试', startDate: '', endDate: '' },
    { milestone: '上线发布', startDate: '', endDate: '' }
  ]);

  // 资源计划数据
  const [resourceData, setResourceData] = useState({
    totalWorkload: '',
    totalDuration: '',
    internalWorkload: '',
    personnelOutsourcing: '',
    projectOutsourcing: '',
    personnel: [
      { role: '产品经理', name: '张伟', workload: '' },
      { role: '项目经理', name: '陈杰', workload: '' },
      { role: '开发负责人', name: '李明', workload: '' },
      { role: '测试负责人', name: '王芳', workload: '' },
      { role: '开发工程师', name: '马伟华', workload: '' }
    ]
  });

  // 质量保证计划数据
  const [qualityData, setQualityData] = useState({
    qualityGoals: '1. 缺陷密度控制在0.5个/千行以下\n2. 测试覆盖率达到80%以上\n3. 关键评审通过率100%',
    reviewMechanism: [
      { name: '需求评审', required: true, frequency: '里程碑' },
      { name: '设计评审', required: true, frequency: '里程碑' },
      { name: '代码评审', required: true, frequency: '每周' },
      { name: '测试用例评审', required: true, frequency: '每迭代' }
    ],
    testStrategy: [
      { name: '单元测试', enabled: true },
      { name: '集成测试', enabled: true },
      { name: '系统测试', enabled: true },
      { name: '性能测试', enabled: true },
      { name: '安全测试', enabled: projectData.level === 'S级' },
      { name: 'UAT测试', enabled: true }
    ],
    riskControl: '建立质量风险预警机制，对延期、缺陷激增等情况及时上报',
    metrics: {
      defectDensity: '0.5',
      testCoverage: '80',
      codeReviewRate: '100'
    }
  });

  // 知识库规则
  const [knowledgeRules, setKnowledgeRules] = useState(null);

  // 历史数据
  const [historyData, setHistoryData] = useState(null);

  // 初始化加载数据
  useEffect(() => {
    const loadData = async () => {
      try {
        setKnowledgeRules({ level: projectData.level, phases: ['需求','开发','测试','评审','结项'] });
        setHistoryData({ user: currentUser, recentProjects: [] });
        setLoading(false);
      } catch (e) {
        console.error('加载数据失败:', e);
        setLoading(false);
      }
    };
    loadData();
  }, []);

  if (loading) return <div className="min-h-screen flex items-center justify-center">加载中...</div>;

  return (
    <div className="min-h-screen bg-slate-100 font-sans text-slate-800 flex flex-col">

      {/* 顶部导航栏 */}
      <header className="bg-white border-b h-12 flex items-center justify-between px-4 text-xs overflow-x-auto shrink-0">
        <div className="flex items-center space-x-5 whitespace-nowrap">
          <span className="text-blue-600 font-bold text-sm">管理平台</span>
          <span className="hover:text-blue-600 cursor-pointer">工作台</span>
          <span className="hover:text-blue-600 cursor-pointer">需求管理</span>
          <span className="text-blue-600 border-b-2 border-blue-600 h-12 flex items-center">项目管理</span>
          <span className="hover:text-blue-600 cursor-pointer">测试管理</span>
          <span className="hover:text-blue-600 cursor-pointer">架构总览</span>
          <span className="hover:text-blue-600 cursor-pointer">架构管控</span>
          <span className="hover:text-blue-600 cursor-pointer">架构设计</span>
          <span className="hover:text-blue-600 cursor-pointer">架构资产</span>
          <span className="hover:text-blue-600 cursor-pointer">研发工艺</span>
          <span className="hover:text-blue-600 cursor-pointer">数据标准</span>
          <span className="hover:text-blue-600 cursor-pointer">科技管控</span>
          <span className="hover:text-blue-600 cursor-pointer">帮助</span>
          <span className="hover:text-blue-600 cursor-pointer flex items-center">更多 <ChevronDown size={12} className="ml-0.5" /></span>
        </div>
        <div className="flex items-center space-x-4 ml-4 shrink-0">
          <Search size={16} className="cursor-pointer hover:text-blue-600" />
          <Bell size={16} className="cursor-pointer hover:text-blue-600" />
          <div className="flex items-center bg-slate-50 border px-2 py-1 rounded cursor-pointer hover:border-blue-300">
            <User size={12} className="text-blue-600 mr-1" />
            <select value={currentUser} onChange={e=>setCurrentUser(e.target.value)} className="bg-transparent border-none text-blue-600 text-xs outline-none cursor-pointer">
              <option value="马伟华">马伟华 (成员)</option>
              <option value="陈杰">陈杰 (项目经理)</option>
            </select>
          </div>
        </div>
      </header>

      {/* 面包屑导航 */}
      <div className="bg-white px-4 py-2 border-b text-xs text-slate-500 flex items-center whitespace-nowrap overflow-x-auto shrink-0">
        <span className="cursor-pointer hover:text-blue-600">我的工作台</span> <ChevronRight size={12} className="mx-1"/>
        <span className="cursor-pointer hover:text-blue-600">项目计划与进度管理</span> <ChevronRight size={12} className="mx-1"/>
        <span className="cursor-pointer hover:text-blue-600">项目管理服务台</span> <ChevronRight size={12} className="mx-1"/>
        <span className="cursor-pointer hover:text-blue-600">项目实施管理</span> <ChevronRight size={12} className="mx-1"/>
        <span className="bg-blue-50 text-blue-600 px-2 py-1 rounded flex items-center cursor-pointer border border-blue-100">
          {projectData.name} <X size={12} className="ml-1 hover:text-red-500" />
        </span>
      </div>

      {/* 项目内 Tab 导航 */}
      <div className="bg-white border-b px-4 flex space-x-6 text-sm pt-3 shrink-0 overflow-x-auto">
        <div className="pb-2 text-slate-500 hover:text-blue-600 cursor-pointer whitespace-nowrap">验证主表单01221</div>
        <div className="pb-2 text-slate-500 hover:text-blue-600 cursor-pointer whitespace-nowrap">项目信息</div>
        <div className="pb-2 text-slate-500 hover:text-blue-600 cursor-pointer whitespace-nowrap">项目需求管理</div>
        <div className="pb-2 text-blue-600 border-b-2 border-blue-600 font-medium cursor-pointer whitespace-nowrap">项目方案</div>
        <div className="pb-2 text-slate-500 hover:text-blue-600 cursor-pointer whitespace-nowrap">项目计划与任务管理</div>
        <div className="pb-2 text-slate-500 hover:text-blue-600 cursor-pointer whitespace-nowrap">问题风险管理</div>
        <div className="pb-2 text-slate-500 hover:text-blue-600 cursor-pointer whitespace-nowrap">项目周报</div>
        <div className="pb-2 text-slate-500 hover:text-blue-600 cursor-pointer whitespace-nowrap">项目质量管理</div>
        <div className="pb-2 text-slate-500 hover:text-blue-600 cursor-pointer whitespace-nowrap">项目团队</div>
        <div className="pb-2 text-slate-500 hover:text-blue-600 cursor-pointer whitespace-nowrap">项目管控流程</div>
        <div className="pb-2 text-slate-500 hover:text-blue-600 cursor-pointer whitespace-nowrap">项目过程文档</div>
        <div className="pb-2 text-slate-500 hover:text-blue-600 cursor-pointer whitespace-nowrap">项目工作量管理</div>
        <div className="pb-2 text-slate-500 hover:text-blue-600 cursor-pointer whitespace-nowrap">项目测试管理</div>
      </div>

      {/* 主内容 */}
      <main className="flex-1 p-4 md:p-6 overflow-y-auto">
        <div className="bg-white border rounded shadow-sm p-6 relative">

          {/* 水印 */}
          <div className="absolute inset-0 pointer-events-none flex items-center justify-center opacity-[0.03] overflow-hidden">
             <div className="transform -rotate-45 text-4xl font-bold tracking-widest whitespace-nowrap flex flex-col space-y-32">
                <span>{currentUser} 产品管理部 2026-03-26</span>
             </div>
          </div>

          {/* 标题栏 */}
          <div className="flex justify-between items-center mb-6 border-b pb-4 relative z-10">
            <div className="flex items-center space-x-3">
              <h1 className="text-xl font-bold">项目方案书</h1>
              <span className="bg-green-100 text-green-700 px-2 py-0.5 rounded text-xs">待确认</span>
              <button className="bg-blue-500 text-white px-3 py-1 rounded text-xs hover:bg-blue-600">项目方案书确认</button>
            </div>
            <button className="text-blue-600 border border-blue-600 px-3 py-1 rounded text-xs hover:bg-blue-50">操作日志</button>
          </div>

          {/* 项目基本信息 */}
          <section className="mb-8 relative z-10">
            <div className="flex items-center mb-3">
              <div className="w-1 h-4 bg-blue-600 mr-2"></div>
              <h2 className="font-bold text-sm">项目基本信息</h2>
            </div>
            <table className="w-full text-xs border-collapse border border-slate-200">
              <tbody>
                <tr>
                  <th className="bg-slate-50 p-2.5 w-1/6 border text-slate-500 text-right">项目编号</th>
                  <td className="p-2.5 w-2/6 border">{projectData.id}</td>
                  <th className="bg-slate-50 p-2.5 w-1/6 border text-slate-500 text-right">产品编号</th>
                  <td className="p-2.5 w-2/6 border">{projectData.productNo}</td>
                </tr>
                <tr>
                  <th className="bg-slate-50 p-2.5 border text-slate-500 text-right">项目名称</th>
                  <td className="p-2.5 border">{projectData.name}</td>
                  <th className="bg-slate-50 p-2.5 border text-slate-500 text-right">产品名称</th>
                  <td className="p-2.5 border">{projectData.productName}</td>
                </tr>
                <tr>
                  <th className="bg-slate-50 p-2.5 border text-slate-500 text-right">立项申请部门</th>
                  <td className="p-2.5 border">{projectData.dept}</td>
                  <th className="bg-slate-50 p-2.5 border text-slate-500 text-right">需求相关部门</th>
                  <td className="p-2.5 border">{projectData.reqDept}</td>
                </tr>
                <tr>
                  <th className="bg-slate-50 p-2.5 border text-slate-500 text-right">基准需求编号</th>
                  <td className="p-2.5 border">{projectData.baseReq}</td>
                  <th className="bg-slate-50 p-2.5 border text-slate-500 text-right">变更需求编号</th>
                  <td className="p-2.5 border">{projectData.changeReq}</td>
                </tr>
                <tr>
                  <th className="bg-slate-50 p-2.5 border text-slate-500 text-right">项目控制策略类型</th>
                  <td className="p-2.5 border" colSpan={3}>{projectData.level}</td>
                </tr>
              </tbody>
            </table>
          </section>

          {/* 项目团队 */}
          <section className="mb-8 relative z-10">
            <div className="flex items-center mb-3">
              <div className="w-1 h-4 bg-blue-600 mr-2"></div>
              <h2 className="font-bold text-sm text-slate-700">项目团队</h2>
            </div>
            <table className="w-full text-xs border-collapse border border-slate-200">
              <thead className="bg-slate-50"><tr><th className="p-2.5 border w-12 text-slate-500"></th><th className="p-2.5 border w-1/4 text-slate-500 text-left font-normal">项目角色</th><th className="p-2.5 border w-1/4 text-slate-500 text-left font-normal">人员</th><th className="p-2.5 border w-2/4 text-slate-500 text-left font-normal">职责</th></tr></thead>
              <tbody>
                {teamData.map((m, i) => (
                  <tr key={i}>
                    <td className="p-2.5 border text-center text-slate-400">{i+1}</td>
                    <td className="p-2.5 border text-slate-700">{m.role}</td>
                    <td className="p-2.5 border text-slate-700">{m.name}</td>
                    <td className="p-2.5 border">
                      <div className="flex flex-wrap gap-x-4 gap-y-2 text-slate-600">
                        {m.responsibilities.map(r=>(
                          <label key={r.name} className="flex items-center space-x-1">
                            <input type="checkbox" checked={r.checked} readOnly className="accent-blue-600"/>
                            <span>{r.name}</span>
                          </label>
                        ))}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          {/* 管控方案 */}
          <section className="mb-8 relative z-10">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center">
                <div className="w-1 h-4 bg-blue-600 mr-2"></div>
                <h2 className="font-bold text-sm text-slate-700">管控方案</h2>
              </div>
            </div>

            <div className="text-xs text-slate-600 mb-2">
              使用的项目研发流程：研发流程 - 增量 - 不同方案确认管控要求 - 不同检查项 {"{1.6}"}
            </div>

            <div className="flex space-x-6 border-b text-xs mb-4 text-slate-500 overflow-x-auto">
               <div className="pb-1 border-b-2 border-blue-600 text-blue-600 font-medium whitespace-nowrap">阶段/活动</div>
               <div className="pb-1 cursor-pointer hover:text-blue-600 whitespace-nowrap">交付物</div>
               <div className="pb-1 cursor-pointer hover:text-blue-600 whitespace-nowrap">工艺方法</div>
               <div className="pb-1 cursor-pointer hover:text-blue-600 whitespace-nowrap">质量管控</div>
               <div className="pb-1 cursor-pointer hover:text-blue-600 whitespace-nowrap">架构管控</div>
               <div className="pb-1 cursor-pointer hover:text-blue-600 whitespace-nowrap">标准管控</div>
               <div className="pb-1 cursor-pointer hover:text-blue-600 whitespace-nowrap">安全管控</div>
            </div>

            <table className="w-full text-xs border-collapse border border-slate-200">
              <thead className="bg-slate-50">
                <tr>
                  <th className="p-2.5 border text-slate-500 text-left font-normal w-1/4">阶段/活动</th>
                  <th className="p-2.5 border text-slate-500 text-left font-normal w-1/4">剪裁标准说明</th>
                  <th className="p-2.5 border text-slate-500 text-left font-normal w-1/4">剪裁结果</th>
                  <th className="p-2.5 border text-slate-500 text-left font-normal w-1/4">剪裁结果说明</th>
                </tr>
              </thead>
              <tbody>
                {controlData.map((item, i) => (
                  <tr key={i}>
                    <td className="p-2.5 border text-slate-700 flex items-center">
                      <ChevronRight size={14} className="inline mr-1 text-slate-400"/>
                      <span className="text-yellow-500 mr-1">📁</span>
                      {item.phase}
                    </td>
                    <td className="p-2.5 border"></td>
                    <td className={`p-2.5 border ${item.result==='裁剪'?'text-slate-400':'text-slate-800'}`}>{item.result}</td>
                    <td className="p-2.5 border text-slate-400">{item.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          {/* 项目进度计划 */}
          <section className="mb-8 relative z-10">
            <div className="flex items-center mb-3">
              <div className="w-1 h-4 bg-blue-600 mr-2"></div>
              <h2 className="font-bold text-sm">项目进度计划</h2>
            </div>
            <table className="w-full text-xs border-collapse border border-slate-200">
              <thead className="bg-slate-50"><tr><th className="p-2.5 border">里程碑名称</th><th className="p-2.5 border">计划开始时间</th><th className="p-2.5 border">计划结束时间</th></tr></thead>
              <tbody>
                {scheduleData.map((item, i) => (
                  <tr key={i}>
                    <td className="p-2.5 border">{item.milestone}</td>
                    <td className="p-2.5 border">{item.startDate || '-'}</td>
                    <td className="p-2.5 border">{item.endDate || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          {/* 项目资源计划 */}
          <section className="mb-8 relative z-10">
            <div className="flex items-center mb-3">
              <div className="w-1 h-4 bg-blue-600 mr-2"></div>
              <h2 className="font-bold text-sm">项目资源计划</h2>
            </div>
            <div className="grid grid-cols-5 gap-4 mb-4 text-xs">
              <div className="bg-slate-50 border p-3 rounded">总工作量(人天): <span className="font-bold text-blue-600">{resourceData.totalWorkload || '-'}</span></div>
              <div className="bg-slate-50 border p-3 rounded">总工期(天): <span className="font-bold text-blue-600">{resourceData.totalDuration || '-'}</span></div>
              <div className="bg-slate-50 border p-3 rounded">自有人员工作量: <span className="font-bold text-blue-600">{resourceData.internalWorkload || '-'}</span></div>
              <div className="bg-slate-50 border p-3 rounded">人员外包工作量: <span className="font-bold text-blue-600">{resourceData.personnelOutsourcing || '-'}</span></div>
              <div className="bg-slate-50 border p-3 rounded">项目外包工作量: <span className="font-bold text-blue-600">{resourceData.projectOutsourcing || '-'}</span></div>
            </div>
            <table className="w-full text-xs border-collapse border border-slate-200">
              <thead className="bg-slate-50"><tr><th className="p-2.5 border">项目角色</th><th className="p-2.5 border">人员</th><th className="p-2.5 border">投入工作量</th></tr></thead>
              <tbody>
                {resourceData.personnel?.map((p, i) => (
                  <tr key={i}><td className="p-2.5 border">{p.role}</td><td className="p-2.5 border">{p.name}</td><td className="p-2.5 border">{p.workload || '-'}</td></tr>
                ))}
              </tbody>
            </table>
          </section>

          {/* 质量保证计划 */}
          <section className="pb-20 relative z-10">
            <div className="flex items-center mb-3">
              <div className="w-1 h-4 bg-blue-600 mr-2"></div>
              <h2 className="font-bold text-sm">质量保证计划</h2>
            </div>

            <div className="mb-4">
              <h3 className="text-xs font-semibold text-slate-600 mb-2">质量目标</h3>
              <div className="bg-slate-50 border p-3 rounded text-xs whitespace-pre-line">{qualityData.qualityGoals}</div>
            </div>

            <div className="mb-4">
              <h3 className="text-xs font-semibold text-slate-600 mb-2">评审机制</h3>
              <table className="w-full text-xs border-collapse border border-slate-200">
                <thead className="bg-slate-50"><tr><th className="p-2.5 border">评审类型</th><th className="p-2.5 border">是否必需</th><th className="p-2.5 border">频率</th></tr></thead>
                <tbody>
                  {qualityData.reviewMechanism?.map((item, i) => (
                    <tr key={i}>
                      <td className="p-2.5 border">{item.name}</td>
                      <td className="p-2.5 border">{item.required ? '✓' : '-'}</td>
                      <td className="p-2.5 border">{item.frequency}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="mb-4">
              <h3 className="text-xs font-semibold text-slate-600 mb-2">测试策略</h3>
              <div className="flex flex-wrap gap-2">
                {qualityData.testStrategy?.filter(t=>t.enabled).map(t => (
                  <span key={t.name} className="bg-blue-50 text-blue-700 px-2 py-1 rounded text-xs border border-blue-200">{t.name}</span>
                ))}
              </div>
            </div>

            <div className="mb-4">
              <h3 className="text-xs font-semibold text-slate-600 mb-2">质量指标</h3>
              <div className="grid grid-cols-3 gap-4 text-xs">
                <div className="bg-slate-50 border p-3 rounded">缺陷密度: <span className="font-bold text-blue-600">{qualityData.metrics?.defectDensity}</span> 个/千行</div>
                <div className="bg-slate-50 border p-3 rounded">测试覆盖率: <span className="font-bold text-blue-600">{qualityData.metrics?.testCoverage}</span>%</div>
                <div className="bg-slate-50 border p-3 rounded">代码评审率: <span className="font-bold text-blue-600">{qualityData.metrics?.codeReviewRate}</span>%</div>
              </div>
            </div>

            <div>
              <h3 className="text-xs font-semibold text-slate-600 mb-2">风险管控措施</h3>
              <div className="bg-slate-50 border p-3 rounded text-xs">{qualityData.riskControl}</div>
            </div>
          </section>

        </div>
      </main>

      {/* AI聊天机器人 */}
      <AIChatbot
        projectData={projectData} setProjectData={setProjectData}
        teamData={teamData} setTeamData={setTeamData}
        controlData={controlData} setControlData={setControlData}
        scheduleData={scheduleData} setScheduleData={setScheduleData}
        resourceData={resourceData} setResourceData={setResourceData}
        qualityData={qualityData} setQualityData={setQualityData}
        currentUser={currentUser} isCurrentUserPM={isCurrentUserPM}
        knowledgeRules={knowledgeRules}
        historyData={historyData}
      />
    </div>
  );
}
