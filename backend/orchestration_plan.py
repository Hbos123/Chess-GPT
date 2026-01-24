"""
Orchestration Plan Schema and Types
Defines the structured output of the Request Interpreter
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Literal
from enum import Enum
import json
import os
import uuid


class Mode(str, Enum):
    """Chess GPT operational modes"""
    PLAY = "play"
    ANALYZE = "analyze"
    REVIEW = "review"
    TRAINING = "training"
    CHAT = "chat"
    FETCH = "fetch"  # Multi-pass data fetching mode


@dataclass
class InvestigationRequest:
    """A single investigation request from the interpreter"""
    investigation_type: str  # "position" | "move" | "game"
    focus: Optional[str] = None  # What to focus on: "knight", "bishop", "Nf3", "doubled_pawns", etc.
    parameters: Dict[str, Any] = field(default_factory=dict)  # Investigation-specific params (depth, etc.)
    purpose: str = ""  # Why this investigation is needed (for debugging/logging)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "investigation_type": self.investigation_type,
            "focus": self.focus,
            "parameters": self.parameters,
            "purpose": self.purpose
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'InvestigationRequest':
        """Create from dictionary"""
        return cls(
            investigation_type=data.get("investigation_type", "position"),
            focus=data.get("focus"),
            parameters=data.get("parameters", {}),
            purpose=data.get("purpose", "")
        )


@dataclass
class IntentPlan:
    """
    Simplified intent plan from Interpreter layer.
    Contains only intent classification - NO chess reasoning.
    """
    intent: str  # "discuss_position" | "game_review" | "general_chat" | "play_against_ai" | "opening_explorer"
    scope: Optional[str] = None  # "last_game" | "current_position" | "specific_move" | null
    goal: str = ""  # "explain why user lost" | "find best move" | "evaluate move quality" | "explain concept" | "play chess" | "explore opening"
    constraints: Dict[str, str] = field(default_factory=dict)  # {"depth": "standard", "tone": "coach", "verbosity": "medium"}
    investigation_required: bool = False
    investigation_requests: List[InvestigationRequest] = field(default_factory=list)  # NEW: Multiple investigation requests
    investigation_type: Optional[str] = None  # DEPRECATED: Keep for backward compatibility, use investigation_requests instead
    mode: Mode = Mode.CHAT  # For compatibility with existing code
    mode_confidence: float = 0.5
    user_intent_summary: str = ""
    # NEW: Game review support
    needs_game_fetch: bool = False  # True if games need to be fetched from platform
    game_review_params: Optional[Dict[str, Any]] = None  # username, platform, count, etc. for game_review intent
    # NEW: Game selection/listing (non-analytic)
    game_select_params: Optional[Dict[str, Any]] = None  # username, platform, months_back/date window, candidate_fetch_count, etc.
    game_select_requests: Optional[List[Dict[str, Any]]] = None  # list of selection requests for select_games tool
    # NEW: Connected-ideas graph (LLM-extracted). Domain-agnostic relations (prerequisite/enables/blocks/sequence/etc.)
    connected_ideas: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": self.intent,
            "scope": self.scope,
            "goal": self.goal,
            "constraints": self.constraints,
            "investigation_required": self.investigation_required,
            "investigation_requests": [ir.to_dict() for ir in self.investigation_requests],
            "investigation_type": self.investigation_type,  # Keep for backward compatibility
            "mode": self.mode.value,
            "mode_confidence": self.mode_confidence,
            "user_intent_summary": self.user_intent_summary,
            "needs_game_fetch": self.needs_game_fetch,
            "game_review_params": self.game_review_params,
            "game_select_params": self.game_select_params,
            "game_select_requests": self.game_select_requests,
            "connected_ideas": self.connected_ideas
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IntentPlan':
        # Parse investigation_requests (new format)
        investigation_requests = []
        if "investigation_requests" in data and data["investigation_requests"]:
            for ir_data in data["investigation_requests"]:
                # Handle case where LLM returns strings instead of dicts
                if isinstance(ir_data, str):
                    # If it's a string, the model often means a "purpose"/label, not a valid investigation_type.
                    # Normalize: keep the string as purpose and default to position investigation.
                    s = ir_data.strip()
                    canonical = s.lower()
                    if canonical in ("position", "move", "game"):
                        investigation_type = canonical
                        purpose = data.get("goal", "General investigation")
                    else:
                        investigation_type = "position"
                        purpose = s
                    investigation_requests.append(
                        InvestigationRequest(
                            investigation_type=investigation_type,
                        focus=None,
                        parameters={},
                            purpose=purpose or "",
                        )
                    )
                elif isinstance(ir_data, dict):
                    investigation_requests.append(InvestigationRequest.from_dict(ir_data))
                else:
                    print(f"   ⚠️ [CHAIN] [ORCHESTRATION] Invalid investigation_request type: {type(ir_data)}, skipping")
        
        # Backward compatibility: if no investigation_requests but investigation_type exists, create one
        if not investigation_requests and data.get("investigation_type"):
            investigation_requests.append(InvestigationRequest(
                investigation_type=data["investigation_type"],
                focus=None,
                parameters={},
                purpose=data.get("goal", "General investigation")
            ))
        
        # Map old intent types to new ones for backward compatibility
        intent = data.get("intent", "general_chat")
        intent_mapping = {
            "position_analysis": "discuss_position",
            "move_evaluation": "discuss_position",
            "game_analysis": "game_review"
        }
        if intent in intent_mapping:
            intent = intent_mapping[intent]
            print(f"   🔄 Mapped old intent '{data.get('intent')}' to new intent '{intent}'")
        
        return cls(
            intent=intent,
            scope=data.get("scope"),
            goal=data.get("goal", ""),
            constraints=data.get("constraints", {}),
            investigation_required=data.get("investigation_required", False),
            investigation_requests=investigation_requests,
            investigation_type=data.get("investigation_type"),  # Keep for backward compatibility
            mode=Mode(data.get("mode", "chat")),
            mode_confidence=data.get("mode_confidence", 0.5),
            user_intent_summary=data.get("user_intent_summary", ""),
            needs_game_fetch=data.get("needs_game_fetch", False),
            game_review_params=data.get("game_review_params"),
            game_select_params=data.get("game_select_params"),
            game_select_requests=data.get("game_select_requests"),
            connected_ideas=data.get("connected_ideas")
        )


class ResponseStyle(str, Enum):
    """Response formatting style"""
    CONVERSATIONAL = "conversational"  # Natural flowing paragraphs
    STRUCTURED = "structured"          # Headers, sections, tables
    BRIEF = "brief"                    # Short, direct responses


class FrontendCommandType(str, Enum):
    """Types of frontend commands the interpreter can issue"""
    PUSH_MOVE = "push_move"              # Make a move on the board
    SHOW_ANALYSIS = "show_analysis"      # Display analysis panel
    HIGHLIGHT_SQUARES = "highlight_squares"  # Highlight specific squares
    DRAW_ARROWS = "draw_arrows"          # Draw arrows on board
    SET_ORIENTATION = "set_orientation"  # Flip board perspective
    LOAD_FEN = "load_fen"                # Load new position
    LOAD_PGN = "load_pgn"                # Load game from PGN
    SHOW_PV = "show_pv"                  # Display principal variation
    TRIGGER_CONFIDENCE = "trigger_confidence"  # Run confidence analysis
    SHOW_CHARTS = "show_charts"          # Display statistics charts
    START_DRILL = "start_drill"          # Begin training drill
    NAVIGATE_MOVE = "navigate_move"      # Navigate to specific move
    CREATE_TAB = "create_tab"            # Create a new tab
    SWITCH_TAB = "switch_tab"            # Switch to a different tab
    LIST_TABS = "list_tabs"              # List all available tabs
    SHOW_QUICK_ACTIONS = "show_quick_actions"  # Show quick action buttons
    FOCUS_INPUT = "focus_input"         # Focus the input field


@dataclass
class FrontendCommand:
    """A command to be executed by the frontend"""
    type: FrontendCommandType
    payload: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "payload": self.payload
        }


@dataclass
class ToolCall:
    """A planned tool call"""
    name: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    depends_on: Optional[str] = None  # ID of tool this depends on
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "arguments": self.arguments,
            "depends_on": self.depends_on
        }


@dataclass
class FetchRequest:
    """
    Request to fetch games from chess platforms.
    Used in multi-pass interpreter loop when external data is needed.
    """
    platforms: List[str] = field(default_factory=lambda: ["chess.com"])
    count: int = 1
    username: Optional[str] = None  # If None, uses connected account
    time_controls: Optional[List[str]] = None  # ["rapid", "blitz", "bullet"]
    result_filter: Optional[Literal["wins", "losses", "draws", "all"]] = "all"
    date_range: Optional[tuple] = None  # (start_date, end_date)
    opponent: Optional[str] = None  # Filter by specific opponent
    opening: Optional[str] = None  # Filter by opening ECO/name
    months_back: int = 6  # How far back to fetch
    follow_up_instructions: str = ""  # What to do after fetching
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "platforms": self.platforms,
            "count": self.count,
            "username": self.username,
            "time_controls": self.time_controls,
            "result_filter": self.result_filter,
            "date_range": self.date_range,
            "opponent": self.opponent,
            "opening": self.opening,
            "months_back": self.months_back,
            "follow_up_instructions": self.follow_up_instructions
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'FetchRequest':
        return cls(
            platforms=data.get("platforms", ["chess.com"]),
            count=data.get("count", 1),
            username=data.get("username"),
            time_controls=data.get("time_controls"),
            result_filter=data.get("result_filter", "all"),
            date_range=tuple(data["date_range"]) if data.get("date_range") else None,
            opponent=data.get("opponent"),
            opening=data.get("opening"),
            months_back=data.get("months_back", 6),
            follow_up_instructions=data.get("follow_up_instructions", "")
        )


@dataclass
class AnalysisRequest:
    """Request for position/move analysis"""
    fen: str
    move: Optional[str] = None  # If analyzing a specific move
    depth: int = 18
    lines: int = 3
    include_confidence: bool = False
    include_piece_profiles: bool = False  # Generate piece profiles
    include_pv_analysis: bool = False     # Analyze all moves in PV
    include_alternates: bool = False      # Analyze alternate candidate moves
    compare_before_after: bool = False    # Compare piece profiles before/after move
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "fen": self.fen,
            "move": self.move,
            "depth": self.depth,
            "lines": self.lines,
            "include_confidence": self.include_confidence,
            "include_piece_profiles": self.include_piece_profiles,
            "include_pv_analysis": self.include_pv_analysis,
            "include_alternates": self.include_alternates,
            "compare_before_after": self.compare_before_after
        }


@dataclass
class StatusMessage:
    """A status message describing what the system is doing"""
    action: str           # Brief action name: "analyzing", "comparing", "fetching"
    description: str      # Human readable description
    target: Optional[str] = None  # What's being acted on (move, FEN, username)
    phase: str = "planning"  # "interpreting", "planning", "executing", "synthesizing", "complete"
    tool: Optional[str] = None  # Tool being used (if any)
    progress: Optional[float] = None  # 0-1 progress indicator
    timestamp: Optional[float] = None  # Unix timestamp
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "action": self.action,
            "description": self.description,
            "target": self.target,
            "phase": self.phase
        }
        if self.tool:
            result["tool"] = self.tool
        if self.progress is not None:
            result["progress"] = self.progress
        if self.timestamp is not None:
            result["timestamp"] = self.timestamp
        return result
    
    def __str__(self) -> str:
        parts = [f"[{self.phase}]"]
        if self.tool:
            parts.append(f"<{self.tool}>")
        parts.append(self.description)
        if self.target:
            parts.append(f"({self.target})")
        return " ".join(parts)


@dataclass
class MessageComponent:
    """A component of the user's message"""
    component_type: str  # "main_request", "uncertainty", "constraint", "context"
    text: str  # The actual text from the message
    intent: str  # What the user wants for this component
    requires_investigation: bool = False
    investigation_method: Optional[str] = None  # "position_analysis", "move_testing", etc.
    investigation_id: Optional[str] = None  # Unique ID linking to investigation steps
    sub_components: List['MessageComponent'] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "component_type": self.component_type,
            "text": self.text,
            "intent": self.intent,
            "requires_investigation": self.requires_investigation,
            "investigation_method": self.investigation_method,
            "investigation_id": self.investigation_id,
            "sub_components": [sc.to_dict() for sc in self.sub_components]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MessageComponent':
        sub_components = [
            MessageComponent.from_dict(sc) for sc in data.get("sub_components", [])
        ]
        return cls(
            component_type=data["component_type"],
            text=data["text"],
            intent=data["intent"],
            requires_investigation=data.get("requires_investigation", False),
            investigation_method=data.get("investigation_method"),
            investigation_id=data.get("investigation_id"),
            sub_components=sub_components
        )


@dataclass
class MessageDecomposition:
    """Structured breakdown of user message into components"""
    original_message: str
    components: List[MessageComponent] = field(default_factory=list)
    main_request: Optional[MessageComponent] = None
    uncertainties: List[MessageComponent] = field(default_factory=list)
    constraints: List[MessageComponent] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_message": self.original_message,
            "components": [c.to_dict() for c in self.components],
            "main_request": self.main_request.to_dict() if self.main_request else None,
            "uncertainties": [u.to_dict() for u in self.uncertainties],
            "constraints": [c.to_dict() for c in self.constraints]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MessageDecomposition':
        components = [MessageComponent.from_dict(c) for c in data.get("components", [])]
        main_request = MessageComponent.from_dict(data["main_request"]) if data.get("main_request") else None
        uncertainties = [MessageComponent.from_dict(u) for u in data.get("uncertainties", [])]
        constraints = [MessageComponent.from_dict(c) for c in data.get("constraints", [])]
        
        return cls(
            original_message=data["original_message"],
            components=components,
            main_request=main_request,
            uncertainties=uncertainties,
            constraints=constraints
        )


@dataclass
class InvestigationStep:
    """A single investigation step"""
    step_id: str  # Unique ID
    step_number: int
    action_type: str  # "analyze", "test_move", "examine_pv", "check_consequence", etc.
    target: Optional[str] = None  # Move to test, piece to examine, etc.
    purpose: str = ""
    addresses_component: Optional[str] = None  # Links to MessageComponent.investigation_id
    depends_on: List[str] = field(default_factory=list)  # Step IDs this depends on
    status: str = "pending"  # "pending", "in_progress", "completed", "failed"
    result: Optional[Dict[str, Any]] = None
    insights: List[str] = field(default_factory=list)
    board_state_before: Optional[str] = None  # FEN before this step
    board_state_after: Optional[str] = None  # FEN after this step
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "step_number": self.step_number,
            "action_type": self.action_type,
            "target": self.target,
            "purpose": self.purpose,
            "addresses_component": self.addresses_component,
            "depends_on": self.depends_on,
            "status": self.status,
            "result": self.result,
            "insights": self.insights,
            "board_state_before": self.board_state_before,
            "board_state_after": self.board_state_after
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'InvestigationStep':
        return cls(
            step_id=data["step_id"],
            step_number=data["step_number"],
            action_type=data["action_type"],
            target=data.get("target"),
            purpose=data.get("purpose", ""),
            addresses_component=data.get("addresses_component"),
            depends_on=data.get("depends_on", []),
            status=data.get("status", "pending"),
            result=data.get("result"),
            insights=data.get("insights", []),
            board_state_before=data.get("board_state_before"),
            board_state_after=data.get("board_state_after")
        )
    
    def mark_completed(self, result: Dict[str, Any] = None, insights: List[str] = None):
        """Mark this step as completed"""
        self.status = "completed"
        if result is not None:
            self.result = result
        if insights:
            self.insights = insights


@dataclass
class InvestigationPlan:
    """Complete investigation plan with steps"""
    plan_id: str
    question: str
    key_questions: List[str] = field(default_factory=list)
    steps: List[InvestigationStep] = field(default_factory=list)
    completed_steps: List[str] = field(default_factory=list)  # Step IDs
    accumulated_insights: List[str] = field(default_factory=list)
    ready_to_answer: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "question": self.question,
            "key_questions": self.key_questions,
            "steps": [s.to_dict() for s in self.steps],
            "completed_steps": self.completed_steps,
            "accumulated_insights": self.accumulated_insights,
            "ready_to_answer": self.ready_to_answer
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'InvestigationPlan':
        steps = [InvestigationStep.from_dict(s) for s in data.get("steps", [])]
        return cls(
            plan_id=data["plan_id"],
            question=data["question"],
            key_questions=data.get("key_questions", []),
            steps=steps,
            completed_steps=data.get("completed_steps", []),
            accumulated_insights=data.get("accumulated_insights", []),
            ready_to_answer=data.get("ready_to_answer", False)
        )
    
    def get_next_step(self) -> Optional[InvestigationStep]:
        """Get the next pending step that has its dependencies met"""
        for step in self.steps:
            if step.status == "pending":
                # Check if dependencies are met
                if not step.depends_on:
                    return step
                if all(dep_id in self.completed_steps for dep_id in step.depends_on):
                    return step
        return None
    
    def mark_step_completed(self, step_id: str, result: Dict[str, Any] = None, insights: List[str] = None):
        """Mark a step as completed"""
        for step in self.steps:
            if step.step_id == step_id:
                step.mark_completed(result, insights)
                if step_id not in self.completed_steps:
                    self.completed_steps.append(step_id)
                if insights:
                    self.accumulated_insights.extend(insights)
                break


@dataclass
class ResponseGuidelines:
    """Guidelines for how the main LLM should respond"""
    style: ResponseStyle = ResponseStyle.CONVERSATIONAL
    include_sections: List[str] = field(default_factory=list)
    max_length: Literal["short", "medium", "detailed"] = "medium"
    tone: Literal["coaching", "technical", "casual", "encouraging"] = "coaching"
    focus_aspects: List[str] = field(default_factory=list)  # What to emphasize
    direct_answer: bool = False  # Just answer the question, no unsolicited advice
    skip_advice: bool = False    # Skip "tips" and improvement suggestions
    answer_format: Literal["sentence", "list", "paragraph", "flexible"] = "flexible"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "style": self.style.value,
            "include_sections": self.include_sections,
            "max_length": self.max_length,
            "tone": self.tone,
            "focus_aspects": self.focus_aspects,
            "direct_answer": self.direct_answer,
            "skip_advice": self.skip_advice,
            "answer_format": self.answer_format
        }


@dataclass
class OrchestrationPlan:
    """
    Complete orchestration plan produced by the Request Interpreter.
    Guides the main LLM's response and tool usage.
    """
    
    # Mode detection
    mode: Mode = Mode.CHAT
    mode_confidence: float = 0.8
    
    # Tool orchestration
    tool_sequence: List[ToolCall] = field(default_factory=list)
    parallel_tools: List[str] = field(default_factory=list)
    skip_tools: bool = False  # For simple chat, skip tool calling
    
    # Analysis requirements (pre-execute before main LLM)
    analysis_requests: List[AnalysisRequest] = field(default_factory=list)
    
    # Frontend commands
    frontend_commands: List[FrontendCommand] = field(default_factory=list)
    
    # Response guidelines
    response_guidelines: ResponseGuidelines = field(default_factory=ResponseGuidelines)
    
    # Dynamic system prompt additions
    system_prompt_additions: str = ""
    
    # Status messages (what the system is doing)
    status_messages: List[StatusMessage] = field(default_factory=list)
    
    # Context enrichment
    extracted_data: Dict[str, Any] = field(default_factory=dict)  # Parsed from user message
    
    # Metadata
    user_intent_summary: str = ""  # One-line summary of what user wants
    requires_auth: bool = False
    
    # Self-graded understanding confidence (0.0-1.0)
    # How confident is the interpreter that it understood what the user wants?
    understanding_confidence: float = 1.0
    
    # Clarification handling (when interpreter is uncertain)
    needs_clarification: bool = False
    clarification_question: str = ""  # Question to ask user with example guesses
    
    # Interpreter-driven prompt control (what data to include, how to respond)
    include_context: Dict[str, bool] = field(default_factory=lambda: {
        "board_state": True,
        "pgn": False,  # PGN is too verbose - only include if explicitly needed for game review
        "recent_messages": True,
        "connected_accounts": True,
        "last_move": True,
        "game_metadata": True,
    })
    
    # Which analyses to include (if any)
    relevant_analyses: List[str] = field(default_factory=list)
    # e.g., ["current_position", "last_move", "game_review"]
    
    # Specific data to include (interpreter can pre-filter)
    selected_data: Dict[str, Any] = field(default_factory=dict)
    
    # Detailed response strategy (how to respond)
    response_strategy: str = ""
    # Format: "Context → Goal → Content → Tone → Actions"
    
    # What NOT to mention
    exclude_from_response: List[str] = field(default_factory=list)
    # e.g., ["starting_position", "generic_advice", "board_state"]
    
    # Tool result formatting preferences
    tool_result_format: Dict[str, str] = field(default_factory=dict)
    # e.g., {"fetch_and_review_games": "summary_only"} vs "full_details"
    
    # Investigation planning (NEW)
    message_decomposition: Optional[MessageDecomposition] = None
    investigation_plan: Optional[InvestigationPlan] = None
    investigation_summary: str = ""  # Summary of all investigations
    evidence_links: Dict[str, List[str]] = field(default_factory=dict)  # component_id -> step_ids
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode.value,
            "mode_confidence": self.mode_confidence,
            "tool_sequence": [t.to_dict() for t in self.tool_sequence],
            "parallel_tools": self.parallel_tools,
            "skip_tools": self.skip_tools,
            "analysis_requests": [a.to_dict() for a in self.analysis_requests],
            "frontend_commands": [c.to_dict() for c in self.frontend_commands],
            "response_guidelines": self.response_guidelines.to_dict(),
            "system_prompt_additions": self.system_prompt_additions,
            "status_messages": [s.to_dict() for s in self.status_messages],
            "extracted_data": self.extracted_data,
            "user_intent_summary": self.user_intent_summary,
            "requires_auth": self.requires_auth,
            "understanding_confidence": self.understanding_confidence,
            "needs_clarification": self.needs_clarification,
            "clarification_question": self.clarification_question,
            "include_context": self.include_context,
            "relevant_analyses": self.relevant_analyses,
            "selected_data": self.selected_data,
            "response_strategy": self.response_strategy,
            "exclude_from_response": self.exclude_from_response,
            "tool_result_format": self.tool_result_format,
            "message_decomposition": self.message_decomposition.to_dict() if self.message_decomposition else None,
            "investigation_plan": self.investigation_plan.to_dict() if self.investigation_plan else None,
            "investigation_summary": self.investigation_summary,
            "evidence_links": self.evidence_links
        }
    
    def add_status(self, action: str, description: str, target: str = None, phase: str = "planning"):
        """Helper to add a status message"""
        self.status_messages.append(StatusMessage(
            action=action,
            description=description,
            target=target,
            phase=phase
        ))
    
    def get_status_summary(self) -> str:
        """Get all status messages as a formatted string"""
        return "\n".join([str(s) for s in self.status_messages])
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OrchestrationPlan":
        """Reconstruct plan from dictionary"""
        plan = cls()
        
        if "mode" in data:
            try:
                plan.mode = Mode(data["mode"])
            except ValueError:
                print(f"      ⚠️ Invalid mode '{data['mode']}', defaulting to chat")
                plan.mode = Mode.CHAT
        if "mode_confidence" in data:
            plan.mode_confidence = data["mode_confidence"]
        
        if "tool_sequence" in data:
            plan.tool_sequence = [
                ToolCall(
                    name=t["name"],
                    arguments=t.get("arguments", {}),
                    depends_on=t.get("depends_on")
                )
                for t in data["tool_sequence"]
            ]
        
        if "parallel_tools" in data:
            plan.parallel_tools = data["parallel_tools"]
        
        if "skip_tools" in data:
            plan.skip_tools = data["skip_tools"]
        
        if "analysis_requests" in data:
            plan.analysis_requests = [
                AnalysisRequest(
                    fen=a["fen"],
                    move=a.get("move"),
                    depth=a.get("depth", 18),
                    lines=a.get("lines", 3),
                    include_confidence=a.get("include_confidence", False),
                    include_piece_profiles=a.get("include_piece_profiles", False),
                    include_pv_analysis=a.get("include_pv_analysis", False),
                    include_alternates=a.get("include_alternates", False),
                    compare_before_after=a.get("compare_before_after", False)
                )
                for a in data["analysis_requests"]
            ]
        
        if "status_messages" in data:
            plan.status_messages = [
                StatusMessage(
                    action=s["action"],
                    description=s["description"],
                    target=s.get("target"),
                    phase=s.get("phase", "planning")
                )
                for s in data["status_messages"]
            ]
        
        if "frontend_commands" in data:
            valid_commands = []
            for c in data["frontend_commands"]:
                try:
                    cmd_type = FrontendCommandType(c["type"])
                    valid_commands.append(FrontendCommand(
                        type=cmd_type,
                        payload=c.get("payload", {})
                    ))
                except (ValueError, KeyError) as e:
                    # Skip invalid frontend commands - LLM sometimes hallucinates
                    print(f"      ⚠️ Skipping invalid frontend command: {c.get('type', 'unknown')} - {e}")
            plan.frontend_commands = valid_commands
        
        if "response_guidelines" in data:
            rg = data["response_guidelines"]
            try:
                style = ResponseStyle(rg.get("style", "conversational"))
            except ValueError:
                print(f"      ⚠️ Invalid style '{rg.get('style')}', defaulting to conversational")
                style = ResponseStyle.CONVERSATIONAL
            plan.response_guidelines = ResponseGuidelines(
                style=style,
                include_sections=rg.get("include_sections", []),
                max_length=rg.get("max_length", "medium"),
                tone=rg.get("tone", "coaching"),
                focus_aspects=rg.get("focus_aspects", []),
                direct_answer=rg.get("direct_answer", False),
                skip_advice=rg.get("skip_advice", False),
                answer_format=rg.get("answer_format", "flexible")
            )
        
        if "system_prompt_additions" in data:
            plan.system_prompt_additions = data["system_prompt_additions"]
        
        if "extracted_data" in data:
            plan.extracted_data = data["extracted_data"]
        
        if "user_intent_summary" in data:
            plan.user_intent_summary = data["user_intent_summary"]
        
        if "requires_auth" in data:
            plan.requires_auth = data["requires_auth"]
        
        # Understanding confidence
        if "understanding_confidence" in data:
            plan.understanding_confidence = float(data["understanding_confidence"])
        
        # Clarification handling
        if "needs_clarification" in data:
            plan.needs_clarification = data["needs_clarification"]
        if "clarification_question" in data:
            plan.clarification_question = data["clarification_question"]
        
        # Interpreter-driven prompt control
        if "include_context" in data:
            plan.include_context = data["include_context"]
        if "relevant_analyses" in data:
            plan.relevant_analyses = data["relevant_analyses"]
        if "selected_data" in data:
            plan.selected_data = data["selected_data"]
        if "response_strategy" in data:
            plan.response_strategy = data["response_strategy"]
        if "exclude_from_response" in data:
            plan.exclude_from_response = data["exclude_from_response"]
        if "tool_result_format" in data:
            plan.tool_result_format = data["tool_result_format"]
        
        # Investigation planning fields
        if "message_decomposition" in data and data["message_decomposition"]:
            plan.message_decomposition = MessageDecomposition.from_dict(data["message_decomposition"])
        if "investigation_plan" in data and data["investigation_plan"]:
            plan.investigation_plan = InvestigationPlan.from_dict(data["investigation_plan"])
        if "investigation_summary" in data:
            plan.investigation_summary = data["investigation_summary"]
        if "evidence_links" in data:
            plan.evidence_links = data["evidence_links"]
        
        return plan
    
    def get_evidence_for_component(self, component_id: str) -> List[Dict[str, Any]]:
        """Get all evidence (step results) for a component"""
        evidence = []
        if self.investigation_plan:
            for step in self.investigation_plan.steps:
                if step.addresses_component == component_id and step.status == "completed":
                    evidence.append({
                        "step_id": step.step_id,
                        "action": step.action_type,
                        "result": step.result,
                        "insights": step.insights,
                        "board_state_before": step.board_state_before,
                        "board_state_after": step.board_state_after
                    })
        return evidence


# ============================================================================
# Quick plan builders for common scenarios
# ============================================================================

def build_play_mode_plan(
    engine_move: Optional[str] = None,
    fen: Optional[str] = None,
    user_move: Optional[str] = None
) -> OrchestrationPlan:
    """Build plan for play mode interactions"""
    plan = OrchestrationPlan(
        mode=Mode.PLAY,
        mode_confidence=0.95,
        skip_tools=True,  # Play mode uses cached analysis
        response_guidelines=ResponseGuidelines(
            style=ResponseStyle.CONVERSATIONAL,
            max_length="short",
            tone="coaching",
            focus_aspects=["move_commentary", "position_themes"]
        ),
        system_prompt_additions=(
            "User is in play mode. Comment naturally on moves. "
            "Use tags from context to add concrete details about the position. "
            "Keep responses brief (2-3 sentences) unless position is complex."
        )
    )
    
    # Add status messages
    if user_move:
        plan.add_status("playing", f"User played {user_move}", target=user_move, phase="executing")
    if engine_move:
        plan.add_status("responding", f"Engine responds with {engine_move}", target=engine_move, phase="executing")
    
    if engine_move and fen:
        plan.frontend_commands.append(
            FrontendCommand(
                type=FrontendCommandType.PUSH_MOVE,
                payload={"move": engine_move, "fen": fen}
            )
        )
    
    plan.user_intent_summary = "Playing a game"
    
    return plan


def build_analyze_plan(
    fen: str,
    move: Optional[str] = None,
    depth: int = 18,
    include_piece_profiles: bool = True,
    include_alternates: bool = False,
    compare_before_after: bool = False
) -> OrchestrationPlan:
    """Build plan for position/move analysis"""
    plan = OrchestrationPlan(
        mode=Mode.ANALYZE,
        mode_confidence=0.95,
        response_guidelines=ResponseGuidelines(
            style=ResponseStyle.STRUCTURED,
            include_sections=["eval", "candidates", "themes", "plan"],
            max_length="detailed",
            tone="technical"
        )
    )
    
    # Add status message
    if move:
        plan.add_status("analyzing", f"Evaluating move quality", target=move, phase="planning")
        if compare_before_after:
            plan.add_status("comparing", "Comparing piece profiles before and after move", target=move, phase="planning")
    else:
        plan.add_status("analyzing", "Analyzing position", target=fen[:30], phase="planning")
    
    # Pre-analysis requests (legacy) can bypass the D2/D16 tree-first path.
    # Default: skip analysis_requests and rely on tool calls (analyze_position/analyze_move),
    # which are rebased to D2/D16 in backend/main.py.
    enable_precompute = os.getenv("ENABLE_LEGACY_PRECOMPUTE_ANALYSIS_REQUESTS", "false").lower().strip() in ("1", "true", "yes", "on")
    if enable_precompute:
        plan.analysis_requests.append(
            AnalysisRequest(
                fen=fen,
                move=move,
                depth=depth,
                include_piece_profiles=include_piece_profiles,
                include_alternates=include_alternates,
                compare_before_after=compare_before_after if move else False,
            )
        )
    
    # Add frontend command to show analysis
    plan.frontend_commands.append(
        FrontendCommand(
            type=FrontendCommandType.SHOW_ANALYSIS,
            payload={"fen": fen}
        )
    )
    
    if move:
        plan.tool_sequence.append(
            ToolCall(name="analyze_move", arguments={"fen": fen, "move_san": move})
        )
        plan.system_prompt_additions = (
            f"Rate the move {move} with a quality label (excellent/good/inaccuracy/mistake/blunder) and CP loss. "
            "Provide a concise justification. Format your response without extra line breaks - keep the quality rating and move name on the same line. "
            "At the end of your response, append a comma-separated list of relevant tag names in brackets, like (tag.diagonal.open.a1h8,tag.center.control,tag.threat.attack). "
            "Only include tags that are mentioned or relevant to your explanation. Use verbatim tag names from the analysis data."
        )
        if compare_before_after:
            plan.system_prompt_additions += " Compare the raw analysis before and after the move to explain impact."
    else:
        plan.tool_sequence.append(
            ToolCall(name="analyze_position", arguments={"fen": fen, "depth": depth})
        )
        plan.system_prompt_additions = "Provide comprehensive position analysis with eval, candidates, and strategic plan."
    
    plan.user_intent_summary = f"Analyze {'move ' + move if move else 'position'}"
    
    return plan


def build_review_plan(
    username: Optional[str] = None,
    platform: Optional[str] = None,
    pgn: Optional[str] = None
) -> OrchestrationPlan:
    """Build plan for game/profile review"""
    plan = OrchestrationPlan(
        mode=Mode.REVIEW,
        mode_confidence=0.95,
        response_guidelines=ResponseGuidelines(
            style=ResponseStyle.STRUCTURED,
            include_sections=["verdict", "justification", "recommendations"],
            max_length="detailed",
            tone="coaching"
        )
    )
    
    if pgn:
        # Single game review
        plan.add_status("reviewing", "Analyzing game with Stockfish", phase="planning")
        plan.tool_sequence.append(
            ToolCall(name="review_full_game", arguments={"pgn": pgn})
        )
        plan.system_prompt_additions = "Provide game review with key moments, accuracy, and improvement areas."
        plan.user_intent_summary = "Review the loaded game"
    elif username:
        # Profile review
        plan.add_status("fetching", f"Fetching games from {platform or 'platform'}", target=username, phase="planning")
        plan.add_status("analyzing", "Running Stockfish analysis on games", phase="planning")
        plan.add_status("aggregating", "Computing statistics and patterns", phase="planning")
        
        args = {"username": username}
        if platform:
            args["platform"] = platform
        plan.tool_sequence.append(
            ToolCall(name="fetch_and_review_games", arguments=args)
        )
        plan.frontend_commands.append(
            FrontendCommand(
                type=FrontendCommandType.SHOW_CHARTS,
                payload={"type": "accuracy"}
            )
        )
        plan.system_prompt_additions = "Provide comprehensive profile analysis with patterns, weaknesses, and actionable advice."
        plan.user_intent_summary = f"Review {username}'s profile on {platform or 'their platform'}"
    
    if username:
        plan.extracted_data["username"] = username
    if platform:
        plan.extracted_data["platform"] = platform
    
    return plan


def build_training_plan(
    training_query: str,
    username: Optional[str] = None
) -> OrchestrationPlan:
    """Build plan for training/drill generation"""
    plan = OrchestrationPlan(
        mode=Mode.TRAINING,
        mode_confidence=0.90,
        requires_auth=True,
        response_guidelines=ResponseGuidelines(
            style=ResponseStyle.STRUCTURED,
            include_sections=["focus_areas", "drills_preview", "motivation"],
            max_length="medium",
            tone="encouraging"
        )
    )
    
    # Add status messages
    plan.add_status("planning", f"Creating training plan for: {training_query}", phase="planning")
    plan.add_status("mining", "Finding relevant positions from your games", phase="planning")
    plan.add_status("generating", "Building personalized drills", phase="planning")
    
    args = {"training_query": training_query}
    if username:
        args["username"] = username
    
    plan.tool_sequence.append(
        ToolCall(name="generate_training_session", arguments=args)
    )
    
    plan.system_prompt_additions = (
        f"User wants training on: {training_query}. "
        "Explain what drills were created and why, preview a few examples, motivate practice."
    )
    
    plan.extracted_data["training_query"] = training_query
    plan.user_intent_summary = f"Training on {training_query}"
    
    return plan


def build_direct_question_plan(
    question_type: str,
    fen: Optional[str] = None,
    focus: str = None
) -> OrchestrationPlan:
    """Build plan for direct questions that need concise answers"""
    plan = OrchestrationPlan(
        mode=Mode.ANALYZE if fen else Mode.CHAT,
        mode_confidence=0.90,
        skip_tools=not fen,  # Use tools only if we have a position
        response_guidelines=ResponseGuidelines(
            style=ResponseStyle.BRIEF,
            max_length="short",
            tone="casual",
            direct_answer=True,
            skip_advice=True,
            answer_format="sentence"
        )
    )
    
    # Status message
    plan.add_status("answering", f"Finding {focus or 'answer'}", phase="executing")
    
    # If position-specific question, add analysis request
    if fen:
        plan.analysis_requests.append(
            AnalysisRequest(
                fen=fen,
                depth=12,  # Lighter analysis for quick questions
                include_piece_profiles=True  # Need profiles for piece questions
            )
        )
    
    # Set system prompt based on question type
    if question_type == "most_active":
        plan.system_prompt_additions = (
            "User asks which piece is most active. "
            "Answer directly: name the piece, its square, and briefly why (1-2 sentences max). "
            "Do NOT add general advice or improvement tips."
        )
    elif question_type == "weakest_piece":
        plan.system_prompt_additions = (
            "User asks which piece is weakest/least active. "
            "Answer directly: name the piece, its square, and briefly why (1-2 sentences max). "
            "Do NOT add general advice."
        )
    elif question_type == "best_square":
        plan.system_prompt_additions = (
            "User asks about best squares for a piece. "
            "Answer directly: name the square(s) and briefly why. "
            "Do NOT add general advice."
        )
    elif question_type == "threat":
        plan.system_prompt_additions = (
            "User asks about threats. "
            "Answer directly: describe the threat(s) concisely. "
            "If no immediate threats, say so briefly."
        )
    elif question_type == "plan":
        plan.system_prompt_additions = (
            "User asks what the plan is. "
            "Answer directly: state the main strategic idea in 1-2 sentences. "
            "No lengthy explanations."
        )
        plan.response_guidelines.answer_format = "paragraph"
    elif question_type == "weaknesses":
        plan.system_prompt_additions = (
            "User asks about weaknesses in the position. "
            "Answer directly: name the key weakness(es) concisely. "
            "No improvement tips."
        )
    elif question_type == "tactics":
        plan.system_prompt_additions = (
            "User asks if there's a tactic. "
            "Answer directly: yes/no and briefly what it is, or 'No immediate tactics visible.' "
            "Keep it short."
        )
    elif question_type == "mate":
        plan.system_prompt_additions = (
            "User asks about checkmate possibilities. "
            "Answer directly: yes/no and the key line if there is one. "
            "If no mate, say so briefly."
        )
    elif question_type == "opening_name":
        plan.system_prompt_additions = (
            "User asks what opening this is. "
            "Answer directly: name the opening and variation if known. "
            "One sentence is enough."
        )
    elif question_type == "pawn_structure":
        plan.system_prompt_additions = (
            "User asks about pawn structure. "
            "Answer directly: describe the key features (isolated, doubled, chains, etc.) concisely. "
            "No tips."
        )
    elif question_type == "trade":
        plan.system_prompt_additions = (
            "User asks about whether to trade. "
            "Answer directly: yes/no and briefly why. "
            "One or two sentences max."
        )
    elif question_type == "king_safety":
        plan.system_prompt_additions = (
            "User asks about king safety. "
            "Answer directly: safe/unsafe and briefly why. "
            "No lengthy explanations."
        )
    elif question_type == "outcome":
        plan.system_prompt_additions = (
            "User asks about the position outcome (winning/drawn). "
            "Answer directly: winning/drawn/unclear and briefly why. "
            "No tips."
        )
    elif question_type == "explain_mistake":
        plan.system_prompt_additions = (
            "User asks why a move was bad. "
            "Answer directly: explain the concrete problem with the move. "
            "No general advice."
        )
        plan.response_guidelines.answer_format = "paragraph"
    elif question_type == "evaluation":
        plan.system_prompt_additions = (
            "User asks who is better or wants the evaluation. "
            "Answer directly: state who has the advantage and briefly why. "
            "One or two sentences."
        )
    elif question_type == "checks":
        plan.system_prompt_additions = (
            "User asks about check possibilities. "
            "Answer directly: name any available checks and if they're useful."
        )
    elif question_type == "position_type":
        plan.system_prompt_additions = (
            "User asks about position character (complicated/quiet/etc). "
            "Answer directly: describe the position type briefly."
        )
    elif question_type == "development":
        plan.system_prompt_additions = (
            "User asks about development. "
            "Answer directly: state if well/poorly developed and which pieces if any."
        )
    elif question_type == "candidates":
        plan.system_prompt_additions = (
            "User asks for candidate moves. "
            "Answer directly: list 2-3 main candidate moves briefly."
        )
        plan.response_guidelines.answer_format = "list"
    elif question_type == "center_type":
        plan.system_prompt_additions = (
            "User asks if center is open or closed. "
            "Answer directly: open/closed/semi-open and briefly why."
        )
    elif question_type == "space":
        plan.system_prompt_additions = (
            "User asks about space control. "
            "Answer directly: who has more space and briefly why."
        )
    elif question_type == "castling":
        plan.system_prompt_additions = (
            "User asks about castling. "
            "Answer directly: can/cannot castle, which side if both, and briefly if safe."
        )
    elif question_type == "what_if":
        plan.system_prompt_additions = (
            "User asks what happens after a move. "
            "Answer directly: describe the main consequence in 1-2 sentences."
        )
    elif question_type == "piece_assessment":
        plan.system_prompt_additions = (
            "User asks if a specific piece is good/bad/active. "
            "Answer directly: good/bad/active and briefly why."
        )
    elif question_type == "trap":
        plan.system_prompt_additions = (
            "User asks if they can trap a piece. "
            "Answer directly: yes/no and how if yes."
        )
    elif question_type == "key_move":
        plan.system_prompt_additions = (
            "User asks for the critical/key move. "
            "Answer directly: name the move and briefly why it's key."
        )
    elif question_type == "explain_engine":
        plan.system_prompt_additions = (
            "User asks why the engine recommends something. "
            "Answer directly: explain the main point of the engine's suggestion."
        )
        plan.response_guidelines.answer_format = "paragraph"
    elif question_type == "pawn_push":
        plan.system_prompt_additions = (
            "User asks about pushing pawns. "
            "Answer directly: yes/no and briefly why."
        )
    elif question_type == "next_move":
        plan.system_prompt_additions = (
            "User asks which piece to move. "
            "Answer directly: name the piece/move and briefly why."
        )
    elif question_type == "sacrifice":
        plan.system_prompt_additions = (
            "User asks about sacrifice possibilities. "
            "Answer directly: yes/no, what sacrifice, and if it works."
        )
    elif question_type == "move_necessity":
        plan.system_prompt_additions = (
            "User asks if a move is necessary. "
            "Answer directly: necessary/not necessary and briefly why."
        )
    elif question_type == "move_viability":
        plan.system_prompt_additions = (
            "User asks if a move is playable. "
            "Answer directly: playable/not playable and briefly why."
        )
    elif question_type == "engine_line":
        plan.system_prompt_additions = (
            "User asks for the engine/computer line. "
            "Answer directly: state the main line from analysis."
        )
    elif question_type == "compensation":
        plan.system_prompt_additions = (
            "User asks about compensation for material. "
            "Answer directly: sufficient/insufficient and what the compensation is."
        )
    elif question_type == "theory":
        plan.system_prompt_additions = (
            "User asks if position is theoretical/typical. "
            "Answer directly: yes/no and name the structure/opening if known."
        )
    elif question_type == "holdability":
        plan.system_prompt_additions = (
            "User asks if position can be held/equalized. "
            "Answer directly: holdable/not holdable and briefly why."
        )
    elif question_type == "fortress":
        plan.system_prompt_additions = (
            "User asks if this is a fortress. "
            "Answer directly: yes/no and what makes it so."
        )
    elif question_type == "imbalances":
        plan.system_prompt_additions = (
            "User asks about imbalances. "
            "Answer directly: list the key imbalances briefly."
        )
        plan.response_guidelines.answer_format = "list"
    elif question_type == "initiative":
        plan.system_prompt_additions = (
            "User asks about initiative/counterplay. "
            "Answer directly: who has it and briefly why."
        )
    elif question_type == "recapture":
        plan.system_prompt_additions = (
            "User asks how to recapture. "
            "Answer directly: which way and briefly why."
        )
    elif question_type == "file_importance":
        plan.system_prompt_additions = (
            "User asks about file/rank importance. "
            "Answer directly: important/not important and briefly why."
        )
    elif question_type == "gambit":
        plan.system_prompt_additions = (
            "User asks whether to accept a gambit. "
            "Answer directly: accept/decline and briefly why."
        )
    elif question_type == "piece_comparison":
        plan.system_prompt_additions = (
            "User asks which piece is better. "
            "Answer directly: which one and briefly why."
        )
    elif question_type == "position_change":
        plan.system_prompt_additions = (
            "User asks if position improved/worsened. "
            "Answer directly: better/worse and briefly why."
        )
    elif question_type == "pawn_assessment":
        plan.system_prompt_additions = (
            "User asks about a specific pawn. "
            "Answer directly: weak/strong and briefly why."
        )
    elif question_type == "blockade":
        plan.system_prompt_additions = (
            "User asks about blockading. "
            "Answer directly: yes/no and which piece should blockade."
        )
    elif question_type == "theory_end":
        plan.system_prompt_additions = (
            "User asks where theory ends. "
            "Answer directly: state when/where theory typically ends here."
        )
    elif question_type == "activation":
        plan.system_prompt_additions = (
            "User asks about activating a piece. "
            "Answer directly: yes/no and briefly how/why."
        )
    elif question_type == "piece_safety":
        plan.system_prompt_additions = (
            "User asks if a piece is safe/exposed. "
            "Answer directly: safe/exposed and briefly why."
        )
    elif question_type == "move_consideration":
        plan.system_prompt_additions = (
            "User asks if a move is worth considering. "
            "Answer directly: yes/no and briefly why."
        )
    elif question_type == "move_mistake":
        plan.system_prompt_additions = (
            "User asks if a move would be a mistake. "
            "Answer directly: yes/no and briefly why."
        )
    elif question_type == "capture_choice":
        plan.system_prompt_additions = (
            "User asks about the best way to capture. "
            "Answer directly: which capture and briefly why."
        )
    elif question_type == "weak_squares":
        plan.system_prompt_additions = (
            "User asks about weak squares. "
            "Answer directly: name the weak squares if any."
        )
    elif question_type == "equality":
        plan.system_prompt_additions = (
            "User asks if position is equal. "
            "Answer directly: equal/not equal and briefly why."
        )
    elif question_type == "side_evaluation":
        plan.system_prompt_additions = (
            "User asks which side is better. "
            "Answer directly: state which side and how much."
        )
    elif question_type == "position_assessment":
        plan.system_prompt_additions = (
            "User asks how good/bad their position is. "
            "Answer directly: rate the position briefly."
        )
    elif question_type == "variation":
        plan.system_prompt_additions = (
            "User asks about the variation/line. "
            "Answer directly: name the variation if known."
        )
    elif question_type == "book_status":
        plan.system_prompt_additions = (
            "User asks if still in book/theory. "
            "Answer directly: in book/out of book."
        )
    elif question_type == "conversion":
        plan.system_prompt_additions = (
            "User asks about converting the advantage. "
            "Answer directly: convertible/difficult and briefly how."
        )
    elif question_type == "strategy_choice":
        plan.system_prompt_additions = (
            "User asks about strategic approach. "
            "Answer directly: which approach and briefly why."
        )
    elif question_type == "timing":
        plan.system_prompt_additions = (
            "User asks about timing for action. "
            "Answer directly: right time/not yet and briefly why."
        )
    elif question_type == "square_quality":
        plan.system_prompt_additions = (
            "User asks about a square's quality. "
            "Answer directly: strong/weak/outpost and briefly why."
        )
    elif question_type == "square_vulnerability":
        plan.system_prompt_additions = (
            "User asks if a square is vulnerable. "
            "Answer directly: vulnerable/safe and briefly why."
        )
    elif question_type == "passed_pawn":
        plan.system_prompt_additions = (
            "User asks about creating a passed pawn. "
            "Answer directly: yes/no and briefly how."
        )
    elif question_type == "pawn_majority":
        plan.system_prompt_additions = (
            "User asks about pawn majority. "
            "Answer directly: useful/not useful and briefly why."
        )
    elif question_type == "pawn_extension":
        plan.system_prompt_additions = (
            "User asks if pawns are overextended. "
            "Answer directly: yes/no and briefly why."
        )
    elif question_type == "move_committal":
        plan.system_prompt_additions = (
            "User asks if a move is committal. "
            "Answer directly: committal/flexible and briefly why."
        )
    elif question_type == "pawn_safety":
        plan.system_prompt_additions = (
            "User asks about safe pawn advances. "
            "Answer directly: safe/risky and briefly why."
        )
    elif question_type == "king_placement":
        plan.system_prompt_additions = (
            "User asks about king placement. "
            "Answer directly: where the king should be and briefly why."
        )
    elif question_type == "engine_top":
        plan.system_prompt_additions = (
            "User asks if this is the engine's top move. "
            "Answer directly: yes/no and what the top move is."
        )
    elif question_type == "alternatives":
        plan.system_prompt_additions = (
            "User asks about alternatives. "
            "Answer directly: name 1-2 alternatives briefly."
        )
    elif question_type == "opponent_chances":
        plan.system_prompt_additions = (
            "User asks about opponent's chances. "
            "Answer directly: can/cannot save and briefly why."
        )
    elif question_type == "opponent_assessment":
        plan.system_prompt_additions = (
            "User asks about opponent's situation. "
            "Answer directly: in trouble/fine and briefly why."
        )
    elif question_type == "tempo":
        plan.system_prompt_additions = (
            "User asks about tempo. "
            "Answer directly: gains/loses tempo and briefly why."
        )
    elif question_type == "zugzwang":
        plan.system_prompt_additions = (
            "User asks about zugzwang. "
            "Answer directly: yes/no zugzwang and briefly explain."
        )
    elif question_type == "critical_moment":
        plan.system_prompt_additions = (
            "User asks if this is a critical position. "
            "Answer directly: critical/not critical and briefly why."
        )
    elif question_type == "key_factors":
        plan.system_prompt_additions = (
            "User asks about key factors. "
            "Answer directly: list 2-3 key factors."
        )
        plan.response_guidelines.answer_format = "list"
    elif question_type == "time_factor":
        plan.system_prompt_additions = (
            "User asks if time is a factor. "
            "Answer directly: yes/no and briefly why."
        )
    # ============================================================
    # GENERAL FLEXIBLE HANDLERS
    # ============================================================
    elif question_type == "general_any":
        plan.system_prompt_additions = (
            "User asks 'any X?' about the position. "
            "Answer directly: yes/no and name them if yes."
        )
    elif question_type == "piece_problem":
        plan.system_prompt_additions = (
            "User asks if a piece is trapped/stuck/bad. "
            "Answer directly: yes/no and briefly why."
        )
    elif question_type == "can_i_action":
        plan.system_prompt_additions = (
            "User asks if they can do something. "
            "Answer directly: yes/no and briefly how."
        )
    elif question_type == "should_i_action":
        plan.system_prompt_additions = (
            "User asks if they should do something. "
            "Answer directly: yes/no and briefly why."
        )
    elif question_type == "feature_importance":
        plan.system_prompt_additions = (
            "User asks if something is important/useful. "
            "Answer directly: yes/no and briefly why."
        )
    elif question_type == "tactical_resource":
        plan.system_prompt_additions = (
            "User asks about tactical resources. "
            "Answer directly: yes/no and what it is."
        )
    elif question_type == "move_quality":
        plan.system_prompt_additions = (
            "User asks about a move's quality. "
            "Answer directly: good/bad/best and briefly why."
        )
    elif question_type == "color_complex":
        plan.system_prompt_additions = (
            "User asks about color complex/weak squares. "
            "Answer directly: weak/strong and briefly why."
        )
    elif question_type == "improvement":
        plan.system_prompt_additions = (
            "User asks about improving something. "
            "Answer directly: yes/no and briefly how."
        )
    elif question_type == "sufficiency":
        plan.system_prompt_additions = (
            "User asks if something is 'enough'. "
            "Answer directly: yes/no and briefly why."
        )
    elif question_type == "specific_move":
        plan.system_prompt_additions = (
            "User asks if a specific move is correct. "
            "Answer directly: yes/no and briefly why."
        )
    elif question_type == "position_pressure":
        plan.system_prompt_additions = (
            "User asks about pressure/tension. "
            "Answer directly: yes/no and where."
        )
    elif question_type == "necessity":
        plan.system_prompt_additions = (
            "User asks if they need to do something. "
            "Answer directly: yes/no and briefly why."
        )
    elif question_type == "forcing":
        plan.system_prompt_additions = (
            "User asks if something is forced/forcing. "
            "Answer directly: yes/no and briefly why."
        )
    elif question_type == "accessibility":
        plan.system_prompt_additions = (
            "User asks if something is accessible/contestable. "
            "Answer directly: yes/no and briefly how."
        )
    elif question_type == "defensive_resource":
        plan.system_prompt_additions = (
            "User asks about defensive resources. "
            "Answer directly: yes/no and what they are."
        )
    elif question_type == "play_style":
        plan.system_prompt_additions = (
            "User asks about how to play (style). "
            "Answer directly: yes/no and briefly why."
        )
    elif question_type == "imminent_move":
        plan.system_prompt_additions = (
            "User asks if a move is coming/imminent. "
            "Answer directly: yes/no and briefly explain."
        )
    elif question_type == "move_threat":
        plan.system_prompt_additions = (
            "User asks if a specific move is a threat. "
            "Answer directly: yes/no and briefly why."
        )
    else:
        plan.system_prompt_additions = (
            "Answer the user's question directly and concisely. "
            "Do NOT add unsolicited advice, tips, or improvement suggestions. "
            "Just answer what was asked."
        )
    
    plan.user_intent_summary = f"Direct question: {focus or question_type}"
    
    return plan


def build_chat_plan(simple: bool = True, topic: str = None) -> OrchestrationPlan:
    """Build plan for general chat/questions"""
    plan = OrchestrationPlan(
        mode=Mode.CHAT,
        mode_confidence=0.85,
        skip_tools=simple,
        response_guidelines=ResponseGuidelines(
            style=ResponseStyle.CONVERSATIONAL,
            max_length="medium",
            tone="casual"
        )
    )
    
    if simple:
        plan.add_status("responding", "Answering question directly", phase="executing")
        plan.system_prompt_additions = "Answer conversationally. No tools needed for this question."
    else:
        plan.add_status("thinking", "Processing complex question", phase="planning")
    
    plan.user_intent_summary = topic or "General chess question"
    
    return plan


def build_compare_moves_plan(
    fen: str,
    move1: str,
    move2: str,
    depth: int = 18
) -> OrchestrationPlan:
    """Build plan to compare two alternate moves side by side"""
    plan = OrchestrationPlan(
        mode=Mode.ANALYZE,
        mode_confidence=0.95,
        response_guidelines=ResponseGuidelines(
            style=ResponseStyle.STRUCTURED,
            include_sections=["comparison", "eval_diff", "strategic_diff", "recommendation"],
            max_length="detailed",
            tone="technical"
        )
    )
    
    # Status messages
    plan.add_status("analyzing", f"Analyzing {move1}", target=move1, phase="executing")
    plan.add_status("profiling", f"Building piece profiles after {move1}", phase="executing")
    plan.add_status("analyzing", f"Analyzing {move2}", target=move2, phase="executing")
    plan.add_status("profiling", f"Building piece profiles after {move2}", phase="executing")
    plan.add_status("comparing", f"Comparing {move1} vs {move2}", phase="executing")
    
    # Analysis request for move1 - with piece profiles and PV
    plan.analysis_requests.append(
        AnalysisRequest(
            fen=fen,
            move=move1,
            depth=depth,
            include_piece_profiles=True,
            include_pv_analysis=True,
            include_alternates=False,
            compare_before_after=True
        )
    )
    
    # Analysis request for move2 - with piece profiles and PV
    plan.analysis_requests.append(
        AnalysisRequest(
            fen=fen,
            move=move2,
            depth=depth,
            include_piece_profiles=True,
            include_pv_analysis=True,
            include_alternates=False,
            compare_before_after=True
        )
    )
    
    plan.system_prompt_additions = (
        f"Comparing {move1} vs {move2}. For each move describe: "
        "1) Eval and ranking, 2) What each move accomplishes strategically, "
        "3) How piece profiles change after each move (activity, roles, threats), "
        "4) Which move is better and why. "
        "Use the raw analysis data to explain concrete differences."
    )
    
    plan.user_intent_summary = f"Compare {move1} vs {move2}"
    plan.extracted_data["move1"] = move1
    plan.extracted_data["move2"] = move2
    plan.extracted_data["fen"] = fen
    
    return plan


def build_pv_analysis_plan(
    fen: str,
    pv_moves: List[str],
    depth: int = 18
) -> OrchestrationPlan:
    """Build plan to analyze a PV sequence qualitatively"""
    plan = OrchestrationPlan(
        mode=Mode.ANALYZE,
        mode_confidence=0.95,
        response_guidelines=ResponseGuidelines(
            style=ResponseStyle.STRUCTURED,
            include_sections=["sequence_overview", "move_by_move", "final_position", "key_transformations"],
            max_length="detailed",
            tone="technical"
        )
    )
    
    # Status messages
    plan.add_status("analyzing", f"Analyzing {len(pv_moves)}-move sequence", phase="executing")
    for i, move in enumerate(pv_moves[:5]):  # Cap at 5 for status
        plan.add_status("profiling", f"Building profile after move {i+1}: {move}", target=move, phase="executing")
    plan.add_status("tracking", "Tracking piece profile transformations through PV", phase="executing")
    
    # Analyze starting position
    plan.analysis_requests.append(
        AnalysisRequest(
            fen=fen,
            depth=depth,
            include_piece_profiles=True,
            include_pv_analysis=True
        )
    )
    
    # Mark that we want PV trajectory analysis
    plan.extracted_data["analyze_pv_trajectory"] = True
    plan.extracted_data["pv_moves"] = pv_moves
    plan.extracted_data["fen"] = fen
    
    plan.system_prompt_additions = (
        f"Analyzing PV sequence: {' '.join(pv_moves[:7])}{'...' if len(pv_moves) > 7 else ''}. "
        "Describe how the position transforms through this sequence: "
        "1) Overall strategic goal of the sequence, "
        "2) Key piece profile changes at each step, "
        "3) How piece activity/roles evolve, "
        "4) What makes this the best continuation. "
        "Track pieces through the PV to explain WHY this sequence is strong."
    )
    
    plan.user_intent_summary = f"Analyze PV sequence ({len(pv_moves)} moves)"
    
    return plan


def build_move_impact_plan(
    fen_before: str,
    move: str,
    fen_after: str,
    depth: int = 18
) -> OrchestrationPlan:
    """Build plan for detailed move impact analysis with before/after comparison"""
    plan = OrchestrationPlan(
        mode=Mode.ANALYZE,
        mode_confidence=0.95,
        response_guidelines=ResponseGuidelines(
            style=ResponseStyle.STRUCTURED,
            include_sections=["quality", "impact", "piece_changes", "alternatives"],
            max_length="detailed",
            tone="technical"
        )
    )
    
    # Status messages for the analysis pipeline
    plan.add_status("analyzing", "Calculating move quality", target=move, phase="executing")
    plan.add_status("profiling", "Building piece profiles before move", target="before", phase="executing")
    plan.add_status("profiling", "Building piece profiles after move", target="after", phase="executing")
    plan.add_status("comparing", "Comparing piece profile changes", phase="executing")
    plan.add_status("evaluating", "Analyzing alternate candidate moves", phase="executing")
    
    # Analysis request with all options enabled
    plan.analysis_requests.append(
        AnalysisRequest(
            fen=fen_before,
            move=move,
            depth=depth,
            include_piece_profiles=True,
            include_pv_analysis=True,
            include_alternates=True,
            compare_before_after=True
        )
    )
    
    # Also analyze position after move
    plan.analysis_requests.append(
        AnalysisRequest(
            fen=fen_after,
            depth=depth,
            include_piece_profiles=True
        )
    )
    
    plan.tool_sequence.append(
        ToolCall(name="analyze_move", arguments={"fen": fen_before, "move_san": move, "depth": depth})
    )
    
    plan.system_prompt_additions = (
        f"Rate the move {move} with a quality label (excellent/good/inaccuracy/mistake/blunder) and CP loss. "
        "Provide a concise justification based on the before/after analysis. Format your response without extra line breaks - keep the quality rating and move name on the same line. "
        "At the end of your response, append a comma-separated list of relevant tag names in brackets, like (tag.diagonal.open.a1h8,tag.center.control,tag.threat.attack). "
        "Only include tags that are mentioned or relevant to your explanation. Use verbatim tag names from the analysis data."
    )
    
    plan.frontend_commands.append(
        FrontendCommand(
            type=FrontendCommandType.SHOW_ANALYSIS,
            payload={"fen": fen_after, "highlight_move": move}
        )
    )
    
    plan.user_intent_summary = f"Full impact analysis of {move}"
    plan.extracted_data["move"] = move
    plan.extracted_data["fen_before"] = fen_before
    plan.extracted_data["fen_after"] = fen_after
    
    return plan

