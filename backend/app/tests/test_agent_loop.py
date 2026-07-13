"""Agent loop mechanics (Stage 3.2) — scripted fake client, no API/DB calls.

call_tool is monkeypatched so these test the LOOP (dispatch, single-message
parallel results, stop-reason handling, iteration cap) — not the tools.
"""
from types import SimpleNamespace

import pytest

from app.agent import loop as loop_mod
from app.schemas.agent import AgentRequest, MealPlanItem, MealPlanResponse


def _tool_use(id, name, inp):
    return SimpleNamespace(type="tool_use", id=id, name=name, input=inp)


def _text(t):
    return SimpleNamespace(type="text", text=t)


def _resp(stop_reason, content):
    return SimpleNamespace(stop_reason=stop_reason, content=content, usage=None)


class FakeMessages:
    def __init__(self, creates, parse_result):
        self._creates = iter(creates)
        self._parse_result = parse_result
        self.create_calls: list[dict] = []
        self.parse_calls: list[dict] = []

    def create(self, **kwargs):
        self.create_calls.append(kwargs)
        return next(self._creates)

    def parse(self, **kwargs):
        self.parse_calls.append(kwargs)
        return SimpleNamespace(parsed_output=self._parse_result)


class FakeClient:
    def __init__(self, creates, parse_result):
        self.messages = FakeMessages(creates, parse_result)


@pytest.fixture(autouse=True)
def stub_tools(monkeypatch):
    calls = []

    def fake_call_tool(session, name, tool_input):
        calls.append((name, tool_input))
        return {"ok": True, "name": name}

    monkeypatch.setattr(loop_mod, "call_tool", fake_call_tool)
    return calls


def _plan():
    return MealPlanResponse(
        recipes=[MealPlanItem(recipe_id=1, title="Tomato Garlic Pasta", why="uses your pantry")],
        summary="A quick pasta.",
    )


def test_dispatch_parallel_results_in_one_message(stub_tools):
    # Turn 1: two tool calls at once -> Turn 2: end_turn.
    creates = [
        _resp("tool_use", [
            _tool_use("t1", "search_recipes", {"pantry": ["pasta"]}),
            _tool_use("t2", "check_allergens", {"recipe_id": 1, "allergens": ["dairy"]}),
        ]),
        _resp("end_turn", [_text("Here's my pick.")]),
    ]
    client = FakeClient(creates, _plan())
    result = loop_mod.run_agent(session=None, request=AgentRequest(pantry=["pasta"]), client=client)

    assert result.plan is not None
    assert result.tool_calls == 2
    assert result.iterations == 2
    assert result.degraded is False
    # Both tools executed.
    assert {c[0] for c in stub_tools} == {"search_recipes", "check_allergens"}
    # ALL tool results returned in ONE user message.
    second_create_messages = client.messages.create_calls[1]["messages"]
    tool_result_msgs = [
        m for m in second_create_messages
        if m["role"] == "user" and isinstance(m["content"], list)
        and all(b.get("type") == "tool_result" for b in m["content"])
    ]
    assert len(tool_result_msgs) == 1
    assert len(tool_result_msgs[0]["content"]) == 2


def test_iteration_cap_degrades():
    # Always asks for a tool -> never ends -> hits the cap.
    always_tool = _resp("tool_use", [_tool_use("t", "search_recipes", {"pantry": ["x"]})])
    creates = [always_tool for _ in range(20)]
    client = FakeClient(creates, _plan())
    result = loop_mod.run_agent(
        session=None, request=AgentRequest(pantry=["x"]), client=client, max_iterations=3
    )
    assert result.degraded is True
    assert result.iterations == 3
    assert result.plan is None


def test_refusal_degrades():
    client = FakeClient([_resp("refusal", [])], _plan())
    result = loop_mod.run_agent(session=None, request=AgentRequest(pantry=["x"]), client=client)
    assert result.degraded is True
    assert result.stop_reason == "refusal"
    assert result.plan is None


def test_no_tools_still_structures():
    # Model answers immediately without tools.
    client = FakeClient([_resp("end_turn", [_text("done")])], _plan())
    result = loop_mod.run_agent(session=None, request=AgentRequest(pantry=["x"]), client=client)
    assert result.degraded is False
    assert result.tool_calls == 0
    assert result.plan.recipes[0].title == "Tomato Garlic Pasta"


def test_tool_error_becomes_is_error_result(monkeypatch):
    def boom(session, name, tool_input):
        raise ValueError("kaboom")

    monkeypatch.setattr(loop_mod, "call_tool", boom)
    creates = [
        _resp("tool_use", [_tool_use("t1", "search_recipes", {"pantry": ["x"]})]),
        _resp("end_turn", [_text("recovered")]),
    ]
    client = FakeClient(creates, _plan())
    result = loop_mod.run_agent(session=None, request=AgentRequest(pantry=["x"]), client=client)
    # Loop survived the tool error and still produced a plan.
    assert result.plan is not None
    # Find the tool_result message (messages list is mutated in place, so scan
    # for it rather than indexing the captured reference).
    all_blocks = [
        b
        for m in client.messages.create_calls[1]["messages"]
        if isinstance(m["content"], list)
        for b in m["content"]
        if isinstance(b, dict) and b.get("type") == "tool_result"
    ]
    assert all_blocks and all_blocks[0]["is_error"] is True
