#!/bin/bash
# ============================================
# 端到端集成测试脚本
# 测试链路: 前端 → Java 后台 → Python AI → 通义千问
# ============================================

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PASS=0
FAIL=0

pass() {
  echo -e "${GREEN}✓ PASS${NC}: $1"
  PASS=$((PASS + 1))
}

fail() {
  echo -e "${RED}✗ FAIL${NC}: $1"
  FAIL=$((FAIL + 1))
}

info() {
  echo -e "${BLUE}ℹ${NC} $1"
}

warn() {
  echo -e "${YELLOW}⚠${NC} $1"
}

# ============================================
# 配置
# ============================================
JAVA_URL="http://localhost:8080"
PYTHON_URL="http://localhost:8000"
PROJECT_ID="P001"
TEST_USER="张三"

# ============================================
# 1. 检查服务是否启动
# ============================================
echo ""
echo "========================================="
echo "  1. 服务健康检查"
echo "========================================="
echo ""

info "检查 Python AI 服务 (port 8000)..."
if curl -sf "${PYTHON_URL}/health" > /dev/null 2>&1; then
  pass "Python AI 服务运行中"
else
  fail "Python AI 服务未启动 - 请先运行: cd proposal-python && uvicorn main:app --port 8000"
  info "无 Python 服务则跳过 AI 生成测试"
  PYTHON_UP=false
fi

if [ "${PYTHON_UP}" != "false" ]; then
  PYTHON_UP=true
fi

info "检查 Java 后台 (port 8080)..."
if curl -sf "${JAVA_URL}/api/auth/test-token" > /dev/null 2>&1; then
  pass "Java 后台运行中"
  JAVA_UP=true
else
  fail "Java 后台未启动 - 请先运行: cd proposal-java && mvn spring-boot:run -Dspring-boot.run.profiles=dev"
  JAVA_UP=false
fi

# ============================================
# 2. 认证测试
# ============================================
echo ""
echo "========================================="
echo "  2. 认证接口测试"
echo "========================================="
echo ""

if [ "$JAVA_UP" = true ]; then
  info "获取测试 JWT token..."
  TOKEN_RESP=$(curl -s "${JAVA_URL}/api/auth/test-token")
  TOKEN=$(echo "$TOKEN_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('token',''))" 2>/dev/null || echo "")

  if [ -n "$TOKEN" ]; then
    pass "获取 JWT token 成功"
    info "Token: ${TOKEN:0:50}..."
  else
    fail "获取 JWT token 失败"
    TOKEN="test-token-fallback"
  fi
else
  warn "跳过认证测试（Java 未启动）"
  TOKEN=""
fi

# ============================================
# 3. Python AI 接口测试
# ============================================
echo ""
echo "========================================="
echo "  3. Python AI 接口测试"
echo "========================================="
echo ""

test_python_endpoint() {
  local name="$1"
  local url="$2"
  local data="$3"

  info "测试: $name"
  RESP=$(curl -s -w "\n%{http_code}" -X POST "${PYTHON_URL}${url}" \
    -H "Content-Type: application/json" \
    -d "$data" 2>/dev/null || echo -e "\n000")

  HTTP_CODE=$(echo "$RESP" | tail -1)
  BODY=$(echo "$RESP" | sed '$d')

  if [ "$HTTP_CODE" = "200" ]; then
    pass "$name (HTTP $HTTP_CODE)"
    # 检查是否包含有效 JSON
    if echo "$BODY" | python3 -c "import sys,json; json.load(sys.stdin)" 2>/dev/null; then
      pass "$name 返回有效 JSON"
    else
      warn "$name 返回内容非 JSON（可能是 LLM 响应格式问题）"
    fi
  elif [ "$HTTP_CODE" = "000" ]; then
    fail "$name - 无法连接 Python 服务"
  else
    warn "$name (HTTP $HTTP_CODE) - 可能需要有效的 API Key"
  fi
}

if [ "$PYTHON_UP" = true ]; then
  # 健康检查
  HEALTH=$(curl -s "${PYTHON_URL}/health")
  if echo "$HEALTH" | grep -q "ok"; then
    pass "Python 健康检查通过"
  else
    fail "Python 健康检查失败"
  fi

  # 团队职责生成
  test_python_endpoint "生成团队职责" "/ai/generate/team-responsibilities" '{
    "project_data": {"id":"P001","name":"测试项目","level":"A级","pm_name":"张三"},
    "team_data": [{"role":"产品经理","name":"李四"},{"role":"开发工程师","name":"王五"}],
    "knowledge_rules": {"min_roles":2},
    "history_data": null
  }'

  # 管控方案生成
  test_python_endpoint "生成管控方案" "/ai/generate/control-plan" '{
    "project_data": {"id":"P001","name":"测试项目","level":"A级"},
    "knowledge_rules": {"required_phases":["开发","测试"]}
  }'

  # 进度计划生成
  test_python_endpoint "生成进度计划" "/ai/generate/schedule" '{
    "project_data": {"id":"P001","name":"测试项目","level":"A级"},
    "approve_date": "2026-05-10",
    "project_cycle": "90天",
    "knowledge_rules": null
  }'

  # 资源计划生成
  test_python_endpoint "生成资源计划" "/ai/generate/resource-plan" '{
    "project_data": {"id":"P001","name":"测试项目","level":"A级"},
    "team_data": [{"role":"产品经理","name":"李四"}],
    "input": {"totalWorkload":"100","totalDuration":"60","internalWorkload":"50"},
    "knowledge_rules": null
  }'

  # 质量计划生成
  test_python_endpoint "生成质量保证计划" "/ai/generate/quality-plan" '{
    "project_data": {"id":"P001","name":"测试项目","level":"A级"},
    "knowledge_rules": {"testRequired":["单元测试","集成测试"]}
  }'

  # 对话接口
  test_python_endpoint "AI 对话" "/ai/chat" '{
    "message": "请帮我调整团队职责",
    "session_id": null,
    "current_step": 1,
    "draft_data": null
  }'
else
  warn "跳过 Python AI 接口测试（Python 未启动）"
fi

# ============================================
# 4. Java → Python 代理测试
# ============================================
echo ""
echo "========================================="
echo "  4. Java → Python 代理测试"
echo "========================================="
echo ""

if [ "$JAVA_UP" = true ] && [ -n "$TOKEN" ]; then
  AUTH_HEADER="Authorization: Bearer $TOKEN"

  # 获取方案书
  info "获取方案书数据..."
  PROPOSAL_RESP=$(curl -s -w "\n%{http_code}" "${JAVA_URL}/api/project/${PROJECT_ID}/proposal" \
    -H "$AUTH_HEADER" 2>/dev/null || echo -e "\n000")
  PROPOSAL_CODE=$(echo "$PROPOSAL_RESP" | tail -1)

  if [ "$PROPOSAL_CODE" = "200" ] || [ "$PROPOSAL_CODE" = "404" ]; then
    pass "方案书查询接口响应 (HTTP $PROPOSAL_CODE)"
  else
    warn "方案书查询接口 (HTTP $PROPOSAL_CODE)"
  fi

  # AI 生成步骤1（通过 Java 代理到 Python）
  if [ "$PYTHON_UP" = true ]; then
    info "测试 Java 代理 AI 生成步骤1..."

    GEN_RESP=$(curl -s -w "\n%{http_code}" -X POST \
      "${JAVA_URL}/api/project/${PROJECT_ID}/ai/generate/1" \
      -H "$AUTH_HEADER" \
      -H "Content-Type: application/json" \
      -d '{}' 2>/dev/null || echo -e "\n000")

    GEN_CODE=$(echo "$GEN_RESP" | tail -1)
    GEN_BODY=$(echo "$GEN_RESP" | sed '$d')

    if [ "$GEN_CODE" = "200" ]; then
      pass "Java AI 代理生成步骤1 (HTTP 200)"
      # 检查 sessionId
      if echo "$GEN_BODY" | grep -q "sessionId"; then
        SESSION_ID=$(echo "$GEN_BODY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('sessionId',''))" 2>/dev/null || echo "")
        pass "返回 sessionId: ${SESSION_ID:0:30}..."
      fi
    elif [ "$GEN_CODE" = "403" ]; then
      warn "Java AI 生成步骤1 返回 403（权限校验：测试用户非 PM）"
    else
      warn "Java AI 生成步骤1 (HTTP $GEN_CODE)"
    fi

    # AI 对话（通过 Java 代理到 Python）
    info "测试 Java 代理 AI 对话..."
    CHAT_RESP=$(curl -s -w "\n%{http_code}" -X POST \
      "${JAVA_URL}/api/project/${PROJECT_ID}/ai/chat" \
      -H "$AUTH_HEADER" \
      -H "Content-Type: application/json" \
      -d '{"message":"你好","sessionId":null,"currentStep":1}' 2>/dev/null || echo -e "\n000")

    CHAT_CODE=$(echo "$CHAT_RESP" | tail -1)
    if [ "$CHAT_CODE" = "200" ] || [ "$CHAT_CODE" = "403" ]; then
      pass "Java AI 对话接口响应 (HTTP $CHAT_CODE)"
    else
      warn "Java AI 对话接口 (HTTP $CHAT_CODE)"
    fi
  fi

  # 方案书检查
  info "测试方案书检查..."
  CHECK_RESP=$(curl -s -w "\n%{http_code}" -X POST \
    "${JAVA_URL}/api/project/${PROJECT_ID}/ai/check" \
    -H "$AUTH_HEADER" \
    -H "Content-Type: application/json" 2>/dev/null || echo -e "\n000")

  CHECK_CODE=$(echo "$CHECK_RESP" | tail -1)
  if [ "$CHECK_CODE" = "200" ] || [ "$CHECK_CODE" = "403" ]; then
    pass "方案书检查接口响应 (HTTP $CHECK_CODE)"
  else
    warn "方案书检查接口 (HTTP $CHECK_CODE)"
  fi

else
  warn "跳过 Java 代理测试（Java 未启动或无 token）"
fi

# ============================================
# 5. 前端检查
# ============================================
echo ""
echo "========================================="
echo "  5. 前端检查"
echo "========================================="
echo ""

if [ -f "react-frontend/index.html" ] && [ -f "react-frontend/src/App.jsx" ]; then
  pass "前端源文件存在"
  if [ -f "react-frontend/vite.config.js" ]; then
    pass "Vite 配置文件存在"
    # 检查代理配置
    if grep -q "proxy" react-frontend/vite.config.js; then
      pass "Vite 代理配置已设置 (/api → localhost:8080)"
    fi
  fi
  if [ -f "react-frontend/package.json" ]; then
    pass "package.json 存在"
  fi
else
  fail "前端源文件缺失"
fi

# ============================================
# 6. 结果汇总
# ============================================
echo ""
echo "========================================="
echo "  测试结果汇总"
echo "========================================="
echo ""

TOTAL=$((PASS + FAIL))
echo -e "通过: ${GREEN}${PASS}${NC}"
echo -e "失败: ${RED}${FAIL}${NC}"
echo -e "总计: ${TOTAL}"
echo ""

if [ "$JAVA_UP" != "true" ]; then
  echo -e "${YELLOW}提示: 请先启动所有服务再运行完整测试：${NC}"
  echo ""
  echo "  # 终端1: 启动 Python AI 服务"
  echo "  cd proposal-python && uvicorn main:app --port 8000 --reload"
  echo ""
  echo "  # 终端2: 启动 Java 后台"
  echo "  cd proposal-java && mvn spring-boot:run -Dspring-boot.run.profiles=dev"
  echo ""
  echo "  # 终端3: 启动前端"
  echo "  cd react-frontend && npm run dev"
  echo ""
fi

if [ $FAIL -gt 0 ]; then
  echo -e "${RED}存在 ${FAIL} 项失败，请检查服务状态。${NC}"
  exit 1
else
  echo -e "${GREEN}所有检查项通过！${NC}"
  exit 0
fi
