"""
Tests for the Multi-Pass Interpreter Loop
"""

import pytest
import asyncio
from typing import Dict, Any

# Import the modules we're testing
import sys
sys.path.insert(0, '..')

from interpreter_budget import (
    ResourceBudget, 
    ResourceUsage, 
    CancellationToken,
    CancellationError,
    BudgetExceededError
)
from interpreter_validator import (
    validate_interpreter_output,
    sanitize_output,
    validate_action_params_strict
)
from data_summarizer import (
    summarize_accumulated,
    summarize_games_data,
    estimate_tokens
)
from interpreter_loop import (
    ActionType,
    InterpreterAction,
    InterpreterState,
    ActionResult,
    PassRecord,
    InterpreterOutput
)


class TestResourceBudget:
    """Tests for ResourceBudget"""
    
    def test_default_budget(self):
        budget = ResourceBudget.default()
        assert budget.max_passes == 5
        assert budget.max_fetches == 3
        assert budget.timeout_seconds == 60.0
    
    def test_generous_budget(self):
        budget = ResourceBudget.generous()
        assert budget.max_passes == 8
        assert budget.max_fetches == 5
    
    def test_minimal_budget(self):
        budget = ResourceBudget.minimal()
        assert budget.max_passes == 2
        assert budget.timeout_seconds == 30.0


class TestResourceUsage:
    """Tests for ResourceUsage"""
    
    def test_initial_usage(self):
        usage = ResourceUsage()
        assert usage.passes == 0
        assert usage.fetches == 0
        assert usage.estimated_cost_usd == 0.0
    
    def test_record_llm_call(self):
        usage = ResourceUsage()
        usage.record_llm_call(1000, 500)
        assert usage.llm_calls == 1
        assert usage.llm_tokens_input == 1000
        assert usage.llm_tokens_output == 500
        assert usage.estimated_cost_usd > 0
    
    def test_can_continue_passes(self):
        budget = ResourceBudget(max_passes=3)
        usage = ResourceUsage()
        
        # Should be able to continue
        can, reason = usage.can_continue(budget)
        assert can == True
        assert reason == ""
        
        # After max passes, should stop
        usage.passes = 3
        can, reason = usage.can_continue(budget)
        assert can == False
        assert reason == "max_passes_reached"
    
    def test_can_fetch(self):
        budget = ResourceBudget(max_fetches=2)
        usage = ResourceUsage()
        
        assert usage.can_fetch(budget) == True
        usage.fetches = 2
        assert usage.can_fetch(budget) == False


class TestCancellationToken:
    """Tests for CancellationToken"""
    
    def test_initial_state(self):
        token = CancellationToken()
        assert token.is_cancelled == False
        assert token.reason is None
    
    def test_cancel(self):
        token = CancellationToken()
        token.cancel("user_request")
        assert token.is_cancelled == True
        assert token.reason == "user_request"
    
    def test_check_raises(self):
        token = CancellationToken()
        token.check()  # Should not raise
        
        token.cancel()
        with pytest.raises(CancellationError):
            token.check()
    
    def test_reset(self):
        token = CancellationToken()
        token.cancel()
        token.reset()
        assert token.is_cancelled == False


class TestInterpreterValidator:
    """Tests for interpreter output validation"""
    
    def test_valid_ready_output(self):
        output = {
            "is_ready": True,
            "final_plan": {
                "mode": "analyze",
                "mode_confidence": 0.9,
                "user_intent_summary": "Analyze position"
            }
        }
        is_valid, errors = validate_interpreter_output(output)
        assert is_valid == True
        assert errors == []
    
    def test_valid_actions_output(self):
        output = {
            "is_ready": False,
            "actions": [
                {
                    "action_type": "fetch",
                    "params": {"platforms": ["chess.com"], "count": 10},
                    "reasoning": "Need user games"
                }
            ],
            "insights": ["User has connected account"]
        }
        is_valid, errors = validate_interpreter_output(output)
        assert is_valid == True
    
    def test_invalid_action_type(self):
        output = {
            "is_ready": False,
            "actions": [
                {
                    "action_type": "invalid_type",
                    "params": {},
                    "reasoning": "Test"
                }
            ]
        }
        is_valid, errors = validate_interpreter_output(output)
        assert is_valid == False
        assert any("invalid action_type" in e for e in errors)
    
    def test_sanitize_output(self):
        # Test with malformed output
        raw = {
            "isReady": True,  # Wrong case
            "finalPlan": {    # Wrong case
                "mode": "analyze"
            }
        }
        sanitized = sanitize_output(raw)
        assert "is_ready" in sanitized
        assert sanitized["is_ready"] == True
        assert "final_plan" in sanitized
    
    def test_sanitize_json_string(self):
        raw = '{"is_ready": false, "actions": []}'
        sanitized = sanitize_output(raw)
        assert sanitized["is_ready"] == False


class TestDataSummarizer:
    """Tests for data summarization"""
    
    def test_summarize_empty(self):
        summary = summarize_accumulated({})
        assert "No data" in summary
    
    def test_summarize_games(self):
        data = {
            "fetch_1_abc": {
                "games": [
                    {"white": "player1", "black": "player2", "result": "1-0"},
                    {"white": "player2", "black": "player1", "result": "0-1"}
                ]
            }
        }
        summary = summarize_accumulated(data)
        assert "Fetched Games" in summary
        assert "2" in summary  # Total games
    
    def test_estimate_tokens(self):
        text = "Hello world"
        tokens = estimate_tokens(text)
        assert tokens > 0
        assert tokens < len(text)  # Should be less than char count


class TestInterpreterAction:
    """Tests for InterpreterAction"""
    
    def test_action_id(self):
        action = InterpreterAction(
            action_type=ActionType.FETCH,
            params={"platforms": ["chess.com"]},
            reasoning="Get games"
        )
        assert len(action.id) == 8  # MD5 hash truncated
    
    def test_action_to_dict(self):
        action = InterpreterAction(
            action_type=ActionType.ANALYZE,
            params={"fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"},
            reasoning="Analyze position"
        )
        d = action.to_dict()
        assert d["action_type"] == "analyze"
        assert "fen" in d["params"]
    
    def test_action_from_dict(self):
        data = {
            "action_type": "search",
            "params": {"query": "Magnus Carlsen"},
            "reasoning": "Find info"
        }
        action = InterpreterAction.from_dict(data)
        assert action.action_type == ActionType.SEARCH
        assert action.params["query"] == "Magnus Carlsen"


class TestInterpreterState:
    """Tests for InterpreterState"""
    
    def test_create_state(self):
        state = InterpreterState.create(
            message="Test message",
            context={"fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"}
        )
        assert state.original_message == "Test message"
        assert len(state.context_hash) > 0
    
    def test_add_pass(self):
        state = InterpreterState.create("Test", {})
        
        actions = [InterpreterAction(
            action_type=ActionType.FETCH,
            params={},
            reasoning="Test"
        )]
        results = {actions[0].id: ActionResult(
            action_id=actions[0].id,
            success=True,
            data={"games": []}
        )}
        
        state.add_pass(actions, results, ["Insight 1"], 100)
        
        assert len(state.passes) == 1
        assert "Insight 1" in state.insights
    
    def test_context_staleness(self):
        state = InterpreterState.create(
            "Test",
            {"fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"}
        )
        
        # Same context should not be stale
        assert state.check_context_staleness({
            "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"
        }) == False
        
        # Different FEN should be stale
        assert state.check_context_staleness({
            "fen": "different_fen"
        }) == True


class TestInterpreterOutput:
    """Tests for InterpreterOutput"""
    
    def test_ready_output(self):
        plan = {"mode": "analyze"}
        output = InterpreterOutput.ready(plan)
        assert output.is_ready == True
        assert output.final_plan == plan
    
    def test_needs_actions_output(self):
        actions = [InterpreterAction(
            action_type=ActionType.FETCH,
            params={},
            reasoning="Test"
        )]
        output = InterpreterOutput.needs_actions(actions, ["insight"])
        assert output.is_ready == False
        assert len(output.actions) == 1
        assert "insight" in output.insights


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v"])

