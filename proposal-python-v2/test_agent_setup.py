"""
Unit tests for agent_setup.py — focusing on the _push_structured_data_by_intent fix
and regression verification of unchanged code paths.
"""
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

# ============================================================
# Fixtures & Helpers
# ============================================================

def _make_tool_response(text_content: str):
    """Create a mock ToolResponse with text content (matches agentscope pattern)."""
    mock = MagicMock()
    mock.content = [{"type": "text", "text": text_content}]
    return mock


def _success_response(data: dict | list) -> str:
    """Build a JSON string representing a successful MCP response."""
    return json.dumps({"success": True, "data": data}, ensure_ascii=False)


def _fail_response(msg: str = "something went wrong") -> str:
    """Build a JSON string representing a failed MCP response."""
    return json.dumps({"success": False, "message": msg}, ensure_ascii=False)


@pytest.fixture
def agent():
    """Create a minimally-initialized ProjectAssistantAgent for unit testing."""
    from agent_setup import ProjectAssistantAgent

    queue = asyncio.Queue()
    agent = ProjectAssistantAgent(
        project_id="TEST-001",
        user_name="tester",
        is_pm=True,
        queue=queue,
    )
    # Inject mock MCP client so we don't need a real server
    agent._mcp_client = AsyncMock()
    agent._mcp_get_team = AsyncMock()
    agent._mcp_update_project = AsyncMock()
    agent._mcp_add_member = AsyncMock()
    agent._mcp_update_duty = AsyncMock()
    return agent


@pytest.fixture
def agent_non_pm():
    """Same as agent but non-PM user."""
    from agent_setup import ProjectAssistantAgent

    queue = asyncio.Queue()
    agent = ProjectAssistantAgent(
        project_id="TEST-001",
        user_name="viewer",
        is_pm=False,
        queue=queue,
    )
    agent._mcp_client = AsyncMock()
    agent._mcp_get_team = AsyncMock()
    agent._mcp_update_project = AsyncMock()
    agent._mcp_add_member = AsyncMock()
    agent._mcp_update_duty = AsyncMock()
    return agent


# ============================================================
# _push_structured_data_by_intent — NEW METHOD
# ============================================================

class TestPushStructuredDataByIntent:
    """Tests for the new _push_structured_data_by_intent method (lines 443-464)."""

    @pytest.mark.asyncio
    async def test_project_info_branch_pushes_projectData(self, agent):
        """Intent 'project_info' → calls get_project_info → pushes projectData."""
        project_data = {"productCode": "P001", "productName": "Test Product"}
        mock_get = AsyncMock(return_value=_make_tool_response(_success_response(project_data)))
        agent._mcp_client.get_callable_function = AsyncMock(return_value=mock_get)

        await agent._push_structured_data_by_intent("project_info")

        # Verify MCP call
        agent._mcp_client.get_callable_function.assert_called_once_with("get_project_info")
        mock_get.assert_called_once_with(project_id="TEST-001")

        # Verify draft cache updated
        assert agent.draft_project == project_data

        # Verify event pushed
        event = agent.queue.get_nowait()
        assert event["data"]["type"] == "data"
        assert "projectData" in event["data"]["content"]
        assert event["data"]["content"]["projectData"] == project_data

    @pytest.mark.asyncio
    async def test_team_management_branch_pushes_teamData(self, agent):
        """Intent 'team_management' → uses cached _mcp_get_team → pushes teamData."""
        team_data = [
            {"name": "Alice", "role": "PM"},
            {"name": "Bob", "role": "Dev"},
        ]
        agent._mcp_get_team.return_value = _make_tool_response(_success_response(team_data))

        await agent._push_structured_data_by_intent("team_management")

        # Verify cached function used
        agent._mcp_get_team.assert_called_once_with(project_id="TEST-001")

        # Verify draft cache updated
        assert agent.draft_team == team_data

        # Verify event pushed
        event = agent.queue.get_nowait()
        assert event["data"]["type"] == "data"
        assert "teamData" in event["data"]["content"]
        assert event["data"]["content"]["teamData"] == team_data

    @pytest.mark.asyncio
    async def test_project_info_mcp_failure_does_not_push(self, agent):
        """When get_project_info returns success=False, no event is pushed."""
        mock_get = AsyncMock(return_value=_make_tool_response(_fail_response("error")))
        agent._mcp_client.get_callable_function = AsyncMock(return_value=mock_get)

        await agent._push_structured_data_by_intent("project_info")

        # No event pushed (queue should be empty)
        assert agent.queue.empty()
        # draft_project should NOT be updated
        assert agent.draft_project is None

    @pytest.mark.asyncio
    async def test_team_management_mcp_failure_does_not_push(self, agent):
        """When get_team_members_list returns success=False, no event is pushed."""
        agent._mcp_get_team.return_value = _make_tool_response(_fail_response("error"))

        await agent._push_structured_data_by_intent("team_management")

        assert agent.queue.empty()
        assert agent.draft_team is None

    @pytest.mark.asyncio
    async def test_project_info_no_data_key_does_not_push(self, agent):
        """Response with success=True but no 'data' key → no push."""
        mock_get = AsyncMock(return_value=_make_tool_response(
            json.dumps({"success": True, "message": "ok"})))
        agent._mcp_client.get_callable_function = AsyncMock(return_value=mock_get)

        await agent._push_structured_data_by_intent("project_info")

        assert agent.queue.empty()

    @pytest.mark.asyncio
    async def test_team_management_no_data_key_does_not_push(self, agent):
        """Response with success=True but no 'data' key → no push."""
        agent._mcp_get_team.return_value = _make_tool_response(
            json.dumps({"success": True, "message": "ok"}))

        await agent._push_structured_data_by_intent("team_management")

        assert agent.queue.empty()

    @pytest.mark.asyncio
    async def test_mcp_exception_is_caught_and_does_not_crash(self, agent):
        """MCP call raises exception → caught, logged, no crash."""
        agent._mcp_client.get_callable_function = AsyncMock(
            side_effect=ConnectionError("MCP server unreachable"))

        # Should NOT raise
        await agent._push_structured_data_by_intent("project_info")

        # Queue should be empty
        assert agent.queue.empty()

    @pytest.mark.asyncio
    async def test_team_mcp_exception_is_caught_and_does_not_crash(self, agent):
        """Cached _mcp_get_team raises exception → caught, no crash."""
        agent._mcp_get_team.side_effect = RuntimeError("unexpected")

        # Should NOT raise
        await agent._push_structured_data_by_intent("team_management")

        assert agent.queue.empty()

    @pytest.mark.asyncio
    async def test_unknown_intent_does_nothing(self, agent):
        """Intent not matching project_info or team_management → no-op."""
        await agent._push_structured_data_by_intent("chat")
        assert agent.queue.empty()

        await agent._push_structured_data_by_intent("fillback")
        assert agent.queue.empty()

        await agent._push_structured_data_by_intent("")
        assert agent.queue.empty()

    @pytest.mark.asyncio
    async def test_project_info_parses_nested_json_string(self, agent):
        """_parse_result handles double-encoded JSON gracefully."""
        project_data = {"productCode": "P002"}
        # MCP returns JSON string; _parse_result parses it
        mock_get = AsyncMock(return_value=_make_tool_response(_success_response(project_data)))
        agent._mcp_client.get_callable_function = AsyncMock(return_value=mock_get)

        await agent._push_structured_data_by_intent("project_info")

        event = agent.queue.get_nowait()
        assert event["data"]["content"]["projectData"] == project_data


# ============================================================
# _parse_result — static method
# ============================================================

class TestParseResult:
    """Tests for _parse_result static method (lines 403-417)."""

    def test_valid_json_string(self, agent):
        result = agent._parse_result('{"success": true, "data": {"key": "val"}}')
        assert result == {"success": True, "data": {"key": "val"}}

    def test_empty_string(self, agent):
        result = agent._parse_result("")
        assert result == {"success": False, "message": "空数据"}

    def test_none_input(self, agent):
        result = agent._parse_result(None)
        assert result == {"success": False, "message": "空数据"}

    def test_already_dict(self, agent):
        d = {"success": True, "data": [1, 2, 3]}
        result = agent._parse_result(d)
        assert result is d  # returns the same object

    def test_single_quoted_json_fallback(self, agent):
        """Single-quote JSON with Python bool keywords won't parse — falls to error path.
        This is a known limitation; the method does not handle Python literal syntax."""
        result = agent._parse_result("{'success': True, 'data': [1,2]}")
        # Python True is not valid JSON; the replace("'", '"') trick can't fix that.
        assert result["success"] is False
        assert "数据格式异常" in result["message"]

    def test_bad_json_returns_failure(self, agent):
        result = agent._parse_result("not json at all{{{")
        assert result["success"] is False
        assert "数据格式异常" in result["message"]

    def test_empty_dict_default(self, agent):
        """An object that isn't str/dict → returns {}."""
        result = agent._parse_result(42)
        assert result == {}


# ============================================================
# _extract_text_from_response — static method
# ============================================================

class TestExtractTextFromResponse:
    """Tests for _extract_text_from_response (lines 391-401)."""

    def test_none_response(self, agent):
        assert agent._extract_text_from_response(None) == ""

    def test_string_response(self, agent):
        assert agent._extract_text_from_response("hello") == "hello"

    def test_object_with_text_block(self, agent):
        resp = MagicMock()
        resp.content = [{"type": "text", "text": "hello world"}]
        assert agent._extract_text_from_response(resp) == "hello world"

    def test_object_without_text_block(self, agent):
        resp = MagicMock()
        resp.content = [{"type": "image", "url": "http://..."}]
        assert agent._extract_text_from_response(resp) == ""

    def test_object_empty_content(self, agent):
        resp = MagicMock()
        resp.content = []
        assert agent._extract_text_from_response(resp) == ""

    def test_object_no_content_attr(self, agent):
        resp = MagicMock(spec=[])  # no 'content' attribute
        assert agent._extract_text_from_response(resp) == ""


# ============================================================
# _route — intent classification
# ============================================================

class TestRoute:
    """Tests for the _route method keyword matching (lines 254-295)."""

    @pytest.mark.asyncio
    async def test_fillback_keyword(self, agent):
        assert await agent._route("回填数据") == "fillback"
        assert await agent._route("保存到表单") == "fillback"
        assert await agent._route("提交修改") == "fillback"
        assert await agent._route("持久化数据") == "fillback"

    @pytest.mark.asyncio
    async def test_chat_keyword(self, agent):
        assert await agent._route("你好") == "chat"
        assert await agent._route("谢谢") == "chat"
        assert await agent._route("你是谁") == "chat"
        assert await agent._route("介绍一下") == "chat"
        assert await agent._route("帮助") == "chat"
        assert await agent._route("能做什么") == "chat"

    @pytest.mark.asyncio
    async def test_project_info_message_fallback(self, agent):
        """Messages with project keywords route to project_info (text fallback)."""
        # These trigger the text fallback after structured_model call fails
        # (because router is not initialized in test — the structured_model
        #  call will raise an exception and fall through to text parsing)
        result = await agent._route("查看项目信息")
        # structured_model will fail (no real LLM), text fallback activates
        assert result in ("project_info", "chat")  # chat if keyword didn't match the fallback list exactly


# ============================================================
# handle_message — regression tests
# ============================================================

class TestHandleMessage:
    """Tests for handle_message method (lines 300-345)."""

    @pytest.mark.asyncio
    async def test_fillback_message_bypasses_route(self, agent):
        """__FILLBACK__ message should trigger _handle_fillback directly."""
        with patch.object(agent, '_handle_fillback', new_callable=AsyncMock) as mock_fb:
            await agent.handle_message("__FILLBACK__")
            mock_fb.assert_called_once()

    @pytest.mark.asyncio
    async def test_closed_agent_returns_error(self, agent):
        """When agent is closed, an error event is pushed."""
        agent._closed = True
        await agent.handle_message("hello")
        event = agent.queue.get_nowait()
        assert event["data"]["type"] == "error"
        assert "关闭" in event["data"]["content"]

    @pytest.mark.asyncio
    async def test_error_in_handler_pushes_error_event(self, agent):
        """When handle_message raises, error event is pushed (not propagated)."""
        with patch.object(agent, '_route', side_effect=RuntimeError("boom")):
            await agent.handle_message("hello")
            event = agent.queue.get_nowait()
            assert event["data"]["type"] == "error"
            assert "boom" in event["data"]["content"]

    @pytest.mark.asyncio
    async def test_chat_intent_pushes_greeting_and_done(self, agent):
        """chat intent → friendly reply + done event (no structured data push)."""
        with patch.object(agent, '_route', return_value="chat"):
            await agent.handle_message("hello")
            events = []
            while not agent.queue.empty():
                events.append(agent.queue.get_nowait())

            assert len(events) == 2
            assert events[0]["data"]["type"] == "content"
            assert events[1]["data"]["type"] == "done"

    @pytest.mark.asyncio
    async def test_project_info_intent_calls_push_structured(self, agent):
        """project_info intent → pushes structured data after content."""
        from agentscope.message import Msg
        with patch.object(agent, '_route', return_value="project_info"):
            with patch.object(agent, '_push_structured_data_by_intent', new_callable=AsyncMock) as mock_push:
                # Need a mock project_agent
                agent._project_agent = AsyncMock()
                mock_response = MagicMock()
                mock_response.content = [{"type": "text", "text": "项目信息如下"}]
                agent._project_agent.return_value = mock_response

                await agent.handle_message("查看项目信息")

                # Verify push_structured_data_by_intent was called with correct intent
                mock_push.assert_called_once_with("project_info")

    @pytest.mark.asyncio
    async def test_team_management_intent_calls_push_structured(self, agent):
        """team_management intent → pushes structured data after content."""
        with patch.object(agent, '_route', return_value="team_management"):
            with patch.object(agent, '_push_structured_data_by_intent', new_callable=AsyncMock) as mock_push:
                agent._team_agent = AsyncMock()
                mock_response = MagicMock()
                mock_response.content = [{"type": "text", "text": "团队成员如下"}]
                agent._team_agent.return_value = mock_response

                await agent.handle_message("查看团队")

                mock_push.assert_called_once_with("team_management")

    @pytest.mark.asyncio
    async def test_handle_message_lock_exception_handling_intact(self, agent):
        """Verify the try/except inside async with self._lock still works."""
        # Simulate an error AFTER intent routing but during agent call
        with patch.object(agent, '_route', return_value="project_info"):
            agent._project_agent = AsyncMock(side_effect=ValueError("agent crash"))
            with patch.object(agent, '_push_structured_data_by_intent', new_callable=AsyncMock) as mock_push:
                await agent.handle_message("查看项目信息")

                # Error should be caught, error event pushed
                event = agent.queue.get_nowait()
                assert event["data"]["type"] == "error"
                assert "agent crash" in event["data"]["content"]
                # push_structured should NOT be called (crash happened before it)
                mock_push.assert_not_called()


# ============================================================
# _on_write_success — unchanged, regression verification
# ============================================================

class TestOnWriteSuccess:
    """Tests for _on_write_success callback (lines 350-363) — verify unchanged."""

    @pytest.mark.asyncio
    async def test_projectData_success_updates_draft_and_pushes(self, agent):
        tool_resp = _make_tool_response(_success_response({"productCode": "P003"}))
        await agent._on_write_success(tool_resp, "update_project", "projectData")

        # draft updated
        assert agent.draft_project == {"productCode": "P003"}

        # Event pushed (asyncio.create_task, so wait a tick)
        await asyncio.sleep(0)
        event = agent.queue.get_nowait()
        assert event["data"]["type"] == "data"
        assert "projectData" in event["data"]["content"]

    @pytest.mark.asyncio
    async def test_teamData_success_updates_draft_and_pushes(self, agent):
        team = [{"name": "Charlie", "role": "QA"}]
        tool_resp = _make_tool_response(_success_response(team))
        await agent._on_write_success(tool_resp, "update_team", "teamData")

        assert agent.draft_team == team
        await asyncio.sleep(0)
        event = agent.queue.get_nowait()
        assert event["data"]["content"]["teamData"] == team

    @pytest.mark.asyncio
    async def test_failed_write_does_not_push(self, agent):
        tool_resp = _make_tool_response(_fail_response("permission denied"))
        await agent._on_write_success(tool_resp, "update_project", "projectData")

        await asyncio.sleep(0.05)
        assert agent.queue.empty()
        assert agent.draft_project is None

    @pytest.mark.asyncio
    async def test_teamData_with_nested_content_key(self, agent):
        """When team data comes wrapped in {'content': [...]}, unwrap correctly."""
        team = [{"name": "Dave"}]
        data = {"content": team}
        tool_resp = _make_tool_response(json.dumps({"success": True, "data": data}))
        await agent._on_write_success(tool_resp, "update_team", "teamData")

        # draft_team should be unwrapped to the list
        assert agent.draft_team == team


# ============================================================
# _auto_push_tool_data — preserved but no longer called, verify unchanged
# ============================================================

class TestAutoPushToolData:
    """_auto_push_tool_data (lines 365-389) — preserved, not called from handle_message."""

    @pytest.mark.asyncio
    async def test_project_info_pushes_projectData(self, agent):
        response = MagicMock()
        response.content = [
            {"type": "tool_result", "content": _success_response({"productCode": "P004"})}
        ]

        await agent._auto_push_tool_data(response, intent="project_info")

        assert agent.draft_project == {"productCode": "P004"}
        event = agent.queue.get_nowait()
        assert event["data"]["content"]["projectData"] == {"productCode": "P004"}

    @pytest.mark.asyncio
    async def test_team_management_pushes_teamData(self, agent):
        response = MagicMock()
        response.content = [
            {"type": "tool_result", "content": _success_response([{"name": "Eve"}])}
        ]

        await agent._auto_push_tool_data(response, intent="team_management")

        assert agent.draft_team == [{"name": "Eve"}]
        event = agent.queue.get_nowait()
        assert event["data"]["content"]["teamData"] == [{"name": "Eve"}]

    @pytest.mark.asyncio
    async def test_no_tool_result_blocks_does_nothing(self, agent):
        response = MagicMock()
        response.content = [{"type": "text", "text": "no tool results here"}]

        await agent._auto_push_tool_data(response, intent="project_info")
        assert agent.queue.empty()

    @pytest.mark.asyncio
    async def test_response_without_content_attr_does_nothing(self, agent):
        response = MagicMock(spec=[])  # no 'content'
        await agent._auto_push_tool_data(response, intent="project_info")
        assert agent.queue.empty()


# ============================================================
# Integration-style: handle_message → push_structured full chain
# ============================================================

class TestHandleMessageIntegration:
    """End-to-end tests for the handle_message → _push_structured_data_by_intent chain."""

    @pytest.mark.asyncio
    async def test_project_info_full_chain(self, agent):
        """Full chain: route → project_agent → push content + structured data."""
        from agentscope.message import Msg

        agent._project_agent = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = [{"type": "text", "text": "项目信息：编号P005"}]
        agent._project_agent.return_value = mock_response

        project_data = {"productCode": "P005", "productName": "My Project"}
        mock_get = AsyncMock(return_value=_make_tool_response(_success_response(project_data)))
        agent._mcp_client.get_callable_function = AsyncMock(return_value=mock_get)

        with patch.object(agent, '_route', return_value="project_info"):
            await agent.handle_message("查看项目信息")

        events = []
        while not agent.queue.empty():
            events.append(agent.queue.get_nowait())

        # Expected events: content, data, done
        assert len(events) == 3
        assert events[0]["data"]["type"] == "content"
        assert "编号P005" in events[0]["data"]["content"]
        assert events[1]["data"]["type"] == "data"
        assert events[1]["data"]["content"]["projectData"] == project_data
        assert events[2]["data"]["type"] == "done"

    @pytest.mark.asyncio
    async def test_team_management_full_chain(self, agent):
        """Full chain: route → team_agent → push content + structured data."""
        agent._team_agent = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = [{"type": "text", "text": "团队成员：3人"}]
        agent._team_agent.return_value = mock_response

        team_data = [{"name": "Alice"}, {"name": "Bob"}, {"name": "Charlie"}]
        agent._mcp_get_team.return_value = _make_tool_response(_success_response(team_data))

        with patch.object(agent, '_route', return_value="team_management"):
            await agent.handle_message("查看团队")

        events = []
        while not agent.queue.empty():
            events.append(agent.queue.get_nowait())

        assert len(events) == 3
        assert events[0]["data"]["type"] == "content"
        assert events[1]["data"]["type"] == "data"
        assert events[1]["data"]["content"]["teamData"] == team_data
        assert events[2]["data"]["type"] == "done"

    @pytest.mark.asyncio
    async def test_structured_push_failure_does_not_block_done_event(self, agent):
        """If _push_structured_data_by_intent raises, it should not block the flow."""
        agent._project_agent = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = [{"type": "text", "text": "ok"}]
        agent._project_agent.return_value = mock_response

        # Cause push_structured to fail (not caught by its own try/except — say, a
        # truly unexpected error pattern). But our implementation has try/except
        # inside _push_structured_data_by_intent, so the outer handler won't see it.
        agent._mcp_client.get_callable_function = AsyncMock(
            side_effect=ConnectionError("down"))

        with patch.object(agent, '_route', return_value="project_info"):
            await agent.handle_message("查看项目信息")

        events = []
        while not agent.queue.empty():
            events.append(agent.queue.get_nowait())

        # content + done still pushed (data push was suppressed by exception handler)
        assert events[0]["data"]["type"] == "content"
        assert events[-1]["data"]["type"] == "done"


# ============================================================
# Regression: _on_write_success callback is completely unchanged
# ============================================================

class TestOnWriteSuccessUnchanged:
    """Confirm _on_write_success was NOT modified by the fix."""

    def test_on_write_success_source_lines_match_expected(self):
        """Sanity check: the method body matches the expected preserved version."""
        import inspect
        from agent_setup import ProjectAssistantAgent

        source = inspect.getsource(ProjectAssistantAgent._on_write_success)

        # Key patterns that must exist (unchanged)
        assert "self._extract_text_from_response(tool_response)" in source
        assert "parsed = self._parse_result(text)" in source
        assert 'data_key == "projectData"' in source
        assert "self.draft_project = data" in source
        assert "self.draft_team = data" in source
        assert 'asyncio.create_task(self._push_event' in source
        # Key: does NOT call _push_structured_data_by_intent
        assert "_push_structured_data_by_intent" not in source
