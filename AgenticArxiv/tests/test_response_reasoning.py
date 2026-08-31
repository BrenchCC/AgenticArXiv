import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.base_agent import ResponseParseError
from agents.agent_engine import ReActAgent


def _make_response(content: str, reasoning_content: str = "") -> dict:
    """Build a minimal chat completion response for parser tests.

    Args:
        content: Final answer content returned by the provider.
        reasoning_content: Separate reasoning text returned by the provider.

    Returns:
        A minimal OpenAI-compatible response dictionary.
    """
    return {"choices": [{"message": {"content": content, "reasoning_content": reasoning_content}}]}


def test_parse_response_uses_reasoning_content_when_thought_is_missing():
    """Use provider reasoning when content contains only an Action."""
    agent = object.__new__(ReActAgent)
    response = _make_response(
        'Action: {"name":"get_recently_submitted_cs_papers","args":{"aspect":"AI","days":7,"max_results":5}}',
        "需要检索最近七天的 cs.AI 论文，并限制为五篇。",
    )

    thought, action = agent.parse_response(response)

    assert thought == "需要检索最近七天的 cs.AI 论文，并限制为五篇。"
    assert action == {
        "name": "get_recently_submitted_cs_papers",
        "args": {
            "aspect": "AI",
            "days": 7,
            "max_results": 5,
        },
    }


def test_parse_response_prefers_explicit_thought():
    """Keep the formatted Thought when both response fields contain reasoning."""
    agent = object.__new__(ReActAgent)
    response = _make_response(
        "Thought: 任务已完成\nAction: FINISH",
        "服务端独立返回的推理内容",
    )

    thought, action = agent.parse_response(response)

    assert thought == "任务已完成"
    assert action is None


def test_parse_response_keeps_fallback_without_reasoning_content():
    """Keep the existing fallback for providers without reasoning output."""
    agent = object.__new__(ReActAgent)
    response = _make_response(
        'Action: {"name":"get_recently_submitted_cs_papers","args":{}}'
    )

    thought, action = agent.parse_response(response)

    assert thought == "未提供思考过程"
    assert action == {
        "name": "get_recently_submitted_cs_papers",
        "args": {},
    }


def test_parse_response_rejects_empty_content_instead_of_finishing():
    """Do not treat an empty model response as successful completion."""
    agent = object.__new__(ReActAgent)
    response = _make_response("", "模型仍在判断下一步操作。")

    try:
        agent.parse_response(response)
    except ResponseParseError as error:
        assert str(error) == "模型返回了空内容"
        assert error.thought == "模型仍在判断下一步操作。"
    else:
        raise AssertionError("Empty content must raise ResponseParseError")


def test_parse_response_rejects_missing_action_instead_of_finishing():
    """Do not treat a response without Action as successful completion."""
    agent = object.__new__(ReActAgent)
    response = _make_response("Thought: 还需要调用翻译工具")

    try:
        agent.parse_response(response)
    except ResponseParseError as error:
        assert str(error) == "响应中缺少 Action"
        assert error.thought == "还需要调用翻译工具"
    else:
        raise AssertionError("Missing Action must raise ResponseParseError")
