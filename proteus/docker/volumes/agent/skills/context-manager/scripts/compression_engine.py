"""
Compression Engine for OpenCode-style context management.

Implements intelligent conversation summarization (compaction) to
preserve critical context while reducing token usage.
"""

import time
import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from models import SessionState, Message, MessageType, PartType, CompactionResult


@dataclass
class CompressionStrategy:
    """Strategy for compression based on conversation type."""

    name: str
    focus_points: List[str]
    compression_ratio: float  # Target ratio (0-1)
    preserve_tools: List[str]

    @staticmethod
    def for_conversation_type(convo_type: str) -> "CompressionStrategy":
        """Get compression strategy for conversation type."""
        strategies = {
            "debugging": CompressionStrategy(
                name="debugging",
                focus_points=["error_messages", "fixes", "root_cause", "stack_traces"],
                compression_ratio=0.3,
                preserve_tools=["code_search", "file_read", "debug_tool"],
            ),
            "code_review": CompressionStrategy(
                name="code_review",
                focus_points=["file_changes", "comments", "decisions", "suggestions"],
                compression_ratio=0.4,
                preserve_tools=["code_search", "diff_tool", "lint_tool"],
            ),
            "research": CompressionStrategy(
                name="research",
                focus_points=["findings", "citations", "conclusions", "sources"],
                compression_ratio=0.5,
                preserve_tools=["web_search", "citation_lookup", "data_analysis"],
            ),
            "brainstorming": CompressionStrategy(
                name="brainstorming",
                focus_points=["ideas", "decisions", "action_items", "constraints"],
                compression_ratio=0.6,
                preserve_tools=["mind_map", "whiteboard"],
            ),
            "default": CompressionStrategy(
                name="default",
                focus_points=[
                    "key_decisions",
                    "current_state",
                    "next_steps",
                    "important_context",
                ],
                compression_ratio=0.5,
                preserve_tools=["skill", "code_search"],
            ),
        }
        return strategies.get(convo_type, strategies["default"])


class CompressionEngine:
    """Engine for compressing conversation history."""

    def __init__(self):
        self.summary_cache: Dict[str, str] = {}  # Cache for similar conversations
        self.strategy_cache: Dict[str, CompressionStrategy] = {}

    async def compact_conversation(
        self,
        session: SessionState,
        context_messages: Optional[List[Message]] = None,
        auto: bool = True,
    ) -> CompactionResult:
        """
        Compress conversation history into a summary.

        Based on OpenCode's compaction implementation.

        Args:
            session: Session to compact
            context_messages: Specific messages to include in context (defaults to recent)
            auto: Whether this is automatic compaction (vs manual)
        """
        print(f"[Compression] Starting compaction for session {session.id}")

        # Select messages for context if not provided
        if context_messages is None:
            context_messages = self._select_context_messages(session.messages)

        # Detect conversation type for strategy selection
        convo_type = self._detect_conversation_type(context_messages)
        strategy = self._get_compression_strategy(convo_type)

        # Check cache for similar conversations
        cache_key = self._generate_cache_key(context_messages)
        cached_summary = self.summary_cache.get(cache_key)

        if cached_summary and session.config.enable_caching:
            print(f"[Compression] Using cached summary for {cache_key}")
            summary = cached_summary
        else:
            # Generate new summary
            prompt = self._build_compaction_prompt(context_messages, strategy)
            summary = await self._generate_summary(prompt, strategy)

            # Cache the result
            if session.config.enable_caching:
                self.summary_cache[cache_key] = summary
                # Manage cache size (LRU)
                if len(self.summary_cache) > session.config.cache_size:
                    oldest_key = next(iter(self.summary_cache))
                    del self.summary_cache[oldest_key]

        # Calculate token savings
        tokens_before = sum(msg.tokens.total for msg in context_messages)
        tokens_after = self._estimate_summary_tokens(summary)

        # Create compaction result
        result = CompactionResult(
            session_id=session.id,
            message_id=f"compaction_{int(time.time())}",
            summary=summary,
            tokens_before=tokens_before,
            tokens_after=tokens_after,
            original_messages_count=len(context_messages),
        )

        print(
            f"[Compression] Created compaction with {result.compression_ratio:.2f} ratio, "
            f"saved {result.tokens_saved} tokens"
        )

        return result

    def _select_context_messages(self, messages: List[Message]) -> List[Message]:
        """
        Select messages to include in compression context.

        Strategy:
        1. Always include last 5 messages
        2. Include messages with important tool calls
        3. Include messages that appear to be decision points
        4. Exclude already compacted summary messages
        """
        if len(messages) <= 5:
            return messages

        selected = []

        # Always include recent messages
        selected.extend(messages[-5:])

        # Look for important tool calls in older messages
        important_tools = {"code_search", "file_read", "web_search", "debug_tool"}

        for msg in messages[:-5]:  # Exclude already selected recent messages
            if msg.summary:  # Skip summary messages
                continue

            # Check for important tools
            for part in msg.parts:
                if part.type == PartType.TOOL:
                    tool_info = self._extract_tool_info(part)
                    if tool_info.get("name") in important_tools:
                        if msg not in selected:
                            selected.append(msg)
                        break

            # Check for decision indicators
            if self._is_decision_message(msg):
                if msg not in selected:
                    selected.append(msg)

        # Sort by timestamp
        selected.sort(key=lambda m: m.timestamp)

        return selected

    def _detect_conversation_type(self, messages: List[Message]) -> str:
        """
        Detect the type of conversation for strategy selection.

        Simple keyword-based detection.
        """
        if not messages:
            return "default"

        # Combine recent message content
        content = " ".join([msg.content.lower() for msg in messages[-3:]])

        # Keyword detection
        debug_keywords = ["error", "bug", "fix", "debug", "crash", "exception"]
        review_keywords = ["review", "feedback", "comment", "suggestion", "improve"]
        research_keywords = ["research", "study", "analysis", "findings", "citation"]
        brainstorm_keywords = ["idea", "brainstorm", "design", "plan", "strategy"]

        if any(keyword in content for keyword in debug_keywords):
            return "debugging"
        elif any(keyword in content for keyword in review_keywords):
            return "code_review"
        elif any(keyword in content for keyword in research_keywords):
            return "research"
        elif any(keyword in content for keyword in brainstorm_keywords):
            return "brainstorming"

        return "default"

    def _get_compression_strategy(self, convo_type: str) -> CompressionStrategy:
        """Get or create compression strategy."""
        if convo_type not in self.strategy_cache:
            self.strategy_cache[convo_type] = CompressionStrategy.for_conversation_type(
                convo_type
            )
        return self.strategy_cache[convo_type]

    def _build_compaction_prompt(
        self, messages: List[Message], strategy: CompressionStrategy
    ) -> str:
        """Build prompt for summarization."""
        prompt = f"""Provide a comprehensive summary of our conversation focusing on:

What we've accomplished:
- Key changes, code written, problems solved
- Important decisions and why they were made

Current state:
- What files we're working on
- Current issues or blockers
- Recent tool outputs or findings

Next steps:
- What needs to be done next
- Priority order of tasks
- Dependencies or prerequisites

Important context to preserve:
- Critical decisions and their rationale
- Constraints or requirements
- Assumptions being made

Focus particularly on: {', '.join(strategy.focus_points)}

Conversation history:
"""

        # Add message excerpts
        for i, msg in enumerate(messages):
            role_display = msg.role.value.upper()

            # Extract key content (simplified)
            content_preview = (
                msg.content[:200] + "..." if len(msg.content) > 200 else msg.content
            )

            prompt += f"\n--- Message {i+1} ({role_display}) ---\n"
            prompt += f"{content_preview}\n"

            # Include tool information
            tool_parts = [p for p in msg.parts if p.type == PartType.TOOL]
            if tool_parts:
                prompt += "Tools used: "
                tool_names = []
                for part in tool_parts:
                    tool_info = self._extract_tool_info(part)
                    tool_names.append(tool_info.get("name", "unknown"))
                prompt += ", ".join(tool_names) + "\n"

        prompt += "\nPlease provide a detailed but concise summary that preserves all critical context:"

        return prompt

    def _extract_tool_info(self, part) -> Dict[str, Any]:
        """Extract tool information from message part."""
        if isinstance(part.content, dict):
            return {
                "name": part.content.get("tool_name", "unknown"),
                "status": part.content.get("status", "unknown"),
                "output": part.content.get("output", ""),
            }
        return {"name": "unknown", "status": "unknown", "output": ""}

    def _is_decision_message(self, msg: Message) -> bool:
        """Check if message appears to contain a decision."""
        decision_indicators = [
            "decision",
            "decided",
            "choose",
            "selected",
            "agreed",
            "will use",
            "going with",
            "settled on",
            "concluded",
        ]

        content_lower = msg.content.lower()
        return any(indicator in content_lower for indicator in decision_indicators)

    def _generate_cache_key(self, messages: List[Message]) -> str:
        """Generate cache key based on message content."""
        if not messages:
            return "empty"

        # Use IDs of recent messages and their types
        recent_ids = [msg.id for msg in messages[-3:]]
        recent_types = [msg.role.value for msg in messages[-3:]]

        # Include tool presence
        tool_count = 0
        for msg in messages[-3:]:
            for part in msg.parts:
                if part.type == PartType.TOOL:
                    tool_count += 1

        return f"{'_'.join(recent_ids)}_{'_'.join(recent_types)}_{tool_count}"

    def _estimate_summary_tokens(self, summary: str) -> int:
        """Estimate tokens in summary text."""
        # Rough estimate: 1 token ≈ 4 characters
        return max(100, len(summary) // 4)

    def adaptive_compact(
        self, session: SessionState, target_tokens: int, min_preservation: float = 0.3
    ) -> CompactionResult:
        """
        Adaptive compression to reach target token count.

        Args:
            session: Session to compact
            target_tokens: Desired maximum tokens after compression
            min_preservation: Minimum fraction of context to preserve (0-1)
        """
        current_tokens = session.total_tokens

        if current_tokens <= target_tokens:
            # No compression needed
            return CompactionResult(
                session_id=session.id,
                message_id="no_compaction",
                summary="No compression needed",
                tokens_before=current_tokens,
                tokens_after=current_tokens,
                original_messages_count=0,
            )

        # Calculate required compression ratio
        required_ratio = target_tokens / current_tokens

        # Adjust strategy based on required ratio
        if required_ratio < 0.3:
            strategy_name = "aggressive"
        elif required_ratio < 0.6:
            strategy_name = "balanced"
        else:
            strategy_name = "conservative"

        # For now, use default strategy
        # In real implementation, adjust strategy based on required_ratio
        return asyncio.run(self.compact_conversation(session))
