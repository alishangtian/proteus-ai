"""
Adaptive Compression Strategies for OpenCode-style context management.

Provides context-aware compression strategies based on conversation type,
user behavior, and system requirements.
"""

import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum
from models import Message, MessageType, PartType

class ConversationType(str, Enum):
    """Types of conversations for adaptive strategies."""
    DEBUGGING = "debugging"
    CODE_REVIEW = "code_review"
    RESEARCH = "research"
    BRAINSTORMING = "brainstorming"
    TECHNICAL_DESIGN = "technical_design"
    CREATIVE_WRITING = "creative_writing"
    CUSTOMER_SUPPORT = "customer_support"
    DEFAULT = "default"

@dataclass
class CompressionProfile:
    """Compression profile for a specific conversation type."""
    name: str
    description: str
    target_compression_ratio: float  # 0-1, lower = more aggressive
    preserve_tools: List[str]
    focus_keywords: List[str]
    min_context_preserved: int = 1000  # Minimum tokens to preserve
    max_summary_length: int = 4000     # Maximum summary tokens
    
    @property
    def is_aggressive(self) -> bool:
        """Whether this is an aggressive compression profile."""
        return self.target_compression_ratio < 0.4
    
    @property
    def is_conservative(self) -> bool:
        """Whether this is a conservative compression profile."""
        return self.target_compression_ratio > 0.6

class AdaptiveCompression:
    """Adaptive compression strategy selector."""
    
    # Predefined compression profiles
    PROFILES: Dict[ConversationType, CompressionProfile] = {
        ConversationType.DEBUGGING: CompressionProfile(
            name="Debugging",
            description="Aggressive compression for debugging sessions. Focus on errors and fixes.",
            target_compression_ratio=0.3,
            preserve_tools=["code_search", "debug_tool", "stack_trace_analyzer"],
            focus_keywords=["error", "exception", "bug", "fix", "debug", "crash", "traceback"]
        ),
        ConversationType.CODE_REVIEW: CompressionProfile(
            name="Code Review",
            description="Balanced compression for code reviews. Preserve file changes and decisions.",
            target_compression_ratio=0.5,
            preserve_tools=["code_search", "diff_tool", "lint_tool", "security_scanner"],
            focus_keywords=["review", "comment", "suggestion", "improve", "refactor", "best practice"]
        ),
        ConversationType.RESEARCH: CompressionProfile(
            name="Research",
            description="Conservative compression for research. Preserve citations and findings.",
            target_compression_ratio=0.7,
            preserve_tools=["web_search", "citation_lookup", "data_analysis", "paper_reader"],
            focus_keywords=["research", "study", "analysis", "finding", "citation", "source", "paper"]
        ),
        ConversationType.BRAINSTORMING: CompressionProfile(
            name="Brainstorming",
            description="Moderate compression for brainstorming. Preserve ideas and decisions.",
            target_compression_ratio=0.6,
            preserve_tools=["mind_map", "whiteboard", "idea_generator"],
            focus_keywords=["idea", "brainstorm", "design", "plan", "strategy", "concept"]
        ),
        ConversationType.TECHNICAL_DESIGN: CompressionProfile(
            name="Technical Design",
            description="Conservative compression for technical design. Preserve specifications and decisions.",
            target_compression_ratio=0.8,
            preserve_tools=["arch_diagram", "spec_writer", "api_designer"],
            focus_keywords=["design", "spec", "requirement", "architecture", "component", "interface"]
        ),
        ConversationType.CREATIVE_WRITING: CompressionProfile(
            name="Creative Writing",
            description="Minimal compression for creative writing. Preserve narrative flow.",
            target_compression_ratio=0.9,
            preserve_tools=["thesaurus", "style_checker", "plot_generator"],
            focus_keywords=["story", "character", "plot", "scene", "dialogue", "description"]
        ),
        ConversationType.CUSTOMER_SUPPORT: CompressionProfile(
            name="Customer Support",
            description="Aggressive compression for support tickets. Focus on issues and solutions.",
            target_compression_ratio=0.4,
            preserve_tools=["ticket_system", "knowledge_base", "escalation_check"],
            focus_keywords=["issue", "problem", "solution", "workaround", "escalate", "resolve"]
        ),
        ConversationType.DEFAULT: CompressionProfile(
            name="Default",
            description="General purpose compression for mixed conversations.",
            target_compression_ratio=0.5,
            preserve_tools=["skill", "code_search", "file_read"],
            focus_keywords=["key", "important", "decision", "next", "action"]
        )
    }
    
    def __init__(self):
        self.conversation_history: Dict[str, List[ConversationType]] = {}
        self.profile_effectiveness: Dict[ConversationType, float] = {}
        self.learning_rate = 0.1  # How quickly to adapt
    
    def detect_conversation_type(self, messages: List[Message]) -> ConversationType:
        """
        Detect the type of conversation from message content.
        
        Uses keyword matching and conversation patterns.
        """
        if not messages:
            return ConversationType.DEFAULT
        
        # Combine recent message content for analysis
        recent_messages = messages[-5:] if len(messages) >= 5 else messages
        content = " ".join([msg.content.lower() for msg in recent_messages])
        
        # Check for tool usage patterns
        tool_usage = self._analyze_tool_usage(messages[-10:] if len(messages) >= 10 else messages)
        
        # Score each conversation type
        scores: Dict[ConversationType, float] = {}
        
        for conv_type, profile in self.PROFILES.items():
            if conv_type == ConversationType.DEFAULT:
                continue
            
            # Keyword matching score
            keyword_score = 0
            for keyword in profile.focus_keywords:
                if keyword in content:
                    keyword_score += 1
            
            # Tool usage score
            tool_score = 0
            for tool in profile.preserve_tools:
                if tool in tool_usage:
                    tool_score += tool_usage[tool]
            
            # Message pattern score
            pattern_score = self._analyze_message_patterns(messages, conv_type)
            
            # Combine scores (weighted)
            total_score = (
                keyword_score * 0.4 +
                tool_score * 0.3 +
                pattern_score * 0.3
            )
            
            scores[conv_type] = total_score
        
        # Find best matching type
        if scores:
            best_type = max(scores.items(), key=lambda x: x[1])[0]
            best_score = scores[best_type]
            
            # Only return if score is above threshold
            if best_score > 1.0:  # At least 2 strong signals
                return best_type
        
        return ConversationType.DEFAULT
    
    def get_compression_profile(
        self,
        conversation_type: ConversationType,
        urgency: float = 0.5,
        importance: float = 0.5
    ) -> CompressionProfile:
        """
        Get compression profile with adaptive adjustments.
        
        Args:
            conversation_type: Detected conversation type
            urgency: How urgent compression is (0-1)
            importance: How important context preservation is (0-1)
        """
        base_profile = self.PROFILES.get(conversation_type, self.PROFILES[ConversationType.DEFAULT])
        
        # Adjust compression ratio based on urgency and importance
        adjusted_ratio = self._adjust_compression_ratio(
            base_profile.target_compression_ratio,
            urgency,
            importance
        )
        
        # Create adjusted profile
        adjusted_profile = CompressionProfile(
            name=f"{base_profile.name} (Adjusted)",
            description=base_profile.description,
            target_compression_ratio=adjusted_ratio,
            preserve_tools=base_profile.preserve_tools.copy(),
            focus_keywords=base_profile.focus_keywords.copy(),
            min_context_preserved=base_profile.min_context_preserved,
            max_summary_length=base_profile.max_summary_length
        )
        
        return adjusted_profile
    
    def record_effectiveness(
        self,
        conversation_type: ConversationType,
        compression_ratio: float,
        user_satisfaction: Optional[float] = None
    ):
        """
        Record effectiveness of compression for learning.
        
        Args:
            conversation_type: Type of conversation
            compression_ratio: Actual compression ratio achieved
            user_satisfaction: Optional satisfaction score (0-1)
        """
        if conversation_type not in self.profile_effectiveness:
            self.profile_effectiveness[conversation_type] = 0.5  # Default
        
        current = self.profile_effectiveness[conversation_type]
        
        # Calculate effectiveness score
        if user_satisfaction is not None:
            # Use user satisfaction if available
            effectiveness = user_satisfaction
        else:
            # Estimate based on compression ratio
            target = self.PROFILES[conversation_type].target_compression_ratio
            ratio_diff = abs(compression_ratio - target)
            effectiveness = 1.0 - min(ratio_diff, 1.0)
        
        # Update with learning rate
        new_effectiveness = current * (1 - self.learning_rate) + effectiveness * self.learning_rate
        self.profile_effectiveness[conversation_type] = new_effectiveness
        
        print(f"[AdaptiveCompression] Updated effectiveness for {conversation_type}: "
              f"{current:.2f} -> {new_effectiveness:.2f}")
    
    def get_recommended_profiles(self, session_id: str) -> List[CompressionProfile]:
        """Get recommended compression profiles for a session."""
        if session_id in self.conversation_history:
            history = self.conversation_history[session_id]
            
            # Count occurrences of each type
            type_counts: Dict[ConversationType, int] = {}
            for conv_type in history:
                type_counts[conv_type] = type_counts.get(conv_type, 0) + 1
            
            # Get profiles for frequent types
            profiles = []
            for conv_type, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
                if count >= 2:  # At least 2 occurrences
                    profiles.append(self.PROFILES[conv_type])
            
            if profiles:
                return profiles
        
        # Default to general profiles
        return [
            self.PROFILES[ConversationType.DEFAULT],
            self.PROFILES[ConversationType.CODE_REVIEW],
            self.PROFILES[ConversationType.DEBUGGING]
        ]
    
    def _analyze_tool_usage(self, messages: List[Message]) -> Dict[str, int]:
        """Analyze tool usage patterns in messages."""
        tool_counts: Dict[str, int] = {}
        
        for msg in messages:
            for part in msg.parts:
                if part.type == PartType.TOOL:
                    tool_name = self._extract_tool_name(part)
                    if tool_name:
                        tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1
        
        return tool_counts
    
    def _analyze_message_patterns(self, messages: List[Message], conv_type: ConversationType) -> float:
        """Analyze message patterns for conversation type."""
        if len(messages) < 3:
            return 0.0
        
        score = 0.0
        
        # Check for patterns specific to conversation type
        if conv_type == ConversationType.DEBUGGING:
            # Debugging often has: error -> analysis -> fix -> test pattern
            error_keywords = ["error", "exception", "failed", "crash"]
            fix_keywords = ["fixed", "solved", "resolved", "patched"]
            
            has_error = any(kw in msg.content.lower() for msg in messages for kw in error_keywords)
            has_fix = any(kw in msg.content.lower() for msg in messages for kw in fix_keywords)
            
            if has_error and has_fix:
                score += 1.0
        
        elif conv_type == ConversationType.CODE_REVIEW:
            # Code review often has: file mention -> comment -> suggestion pattern
            file_mentions = sum(1 for msg in messages if any(ext in msg.content.lower() 
                                                          for ext in [".js", ".py", ".java", ".cpp"]))
            comment_words = ["should", "could", "consider", "suggest", "recommend"]
            has_comments = any(kw in msg.content.lower() for msg in messages for kw in comment_words)
            
            if file_mentions >= 2 and has_comments:
                score += 1.0
        
        elif conv_type == ConversationType.RESEARCH:
            # Research often has: question -> search -> analysis -> conclusion
            question_marks = sum(msg.content.count("?") for msg in messages)
            citation_indicators = ["according to", "source:", "reference", "study shows"]
            has_citations = any(kw in msg.content.lower() for msg in messages for kw in citation_indicators)
            
            if question_marks >= 2 and has_citations:
                score += 1.0
        
        return score
    
    def _extract_tool_name(self, part) -> Optional[str]:
        """Extract tool name from message part."""
        if isinstance(part.content, dict):
            return part.content.get("tool_name")
        return None
    
    def _adjust_compression_ratio(
        self,
        base_ratio: float,
        urgency: float,
        importance: float
    ) -> float:
        """
        Adjust compression ratio based on urgency and importance.
        
        Args:
            base_ratio: Base compression ratio from profile
            urgency: How urgent compression is (0-1, higher = more urgent)
            importance: How important context preservation is (0-1, higher = more important)
        """
        # Urgency pushes for more compression (lower ratio)
        urgency_adjustment = -0.3 * urgency  # Up to 30% more compression
        
        # Importance pushes for less compression (higher ratio)
        importance_adjustment = 0.2 * importance  # Up to 20% less compression
        
        # Combine adjustments
        adjusted = base_ratio + urgency_adjustment + importance_adjustment
        
        # Clamp to valid range
        return max(0.1, min(0.95, adjusted))
    
    def analyze_conversation_flow(self, messages: List[Message]) -> Dict[str, Any]:
        """Analyze conversation flow for compression insights."""
        if len(messages) < 5:
            return {"complexity": "low", "topics": 1, "turn_frequency": 0}
        
        # Estimate number of topics
        topics = self._estimate_topic_count(messages)
        
        # Calculate turn frequency (messages per estimated minute)
        time_span = messages[-1].timestamp - messages[0].timestamp
        minutes = max(1, time_span / 60)
        turn_frequency = len(messages) / minutes
        
        # Determine complexity
        if topics <= 2 and turn_frequency < 5:
            complexity = "low"
        elif topics <= 4 and turn_frequency < 10:
            complexity = "medium"
        else:
            complexity = "high"
        
        return {
            "complexity": complexity,
            "topics": topics,
            "turn_frequency": turn_frequency,
            "time_span_minutes": minutes,
            "total_messages": len(messages)
        }
    
    def _estimate_topic_count(self, messages: List[Message]) -> int:
        """Estimate number of topics in conversation."""
        # Simple implementation: count unique file mentions and major topic shifts
        file_extensions = [".js", ".py", ".java", ".cpp", ".md", ".txt", ".json", ".yaml", ".yml"]
        
        topics = set()
        
        for msg in messages:
            content_lower = msg.content.lower()
            
            # Check for file mentions
            for ext in file_extensions:
                if ext in content_lower:
                    topics.add(f"file_{ext}")
            
            # Check for major topic keywords
            topic_keywords = {
                "debug": ["error", "bug", "fix", "debug"],
                "design": ["design", "architecture", "component", "interface"],
                "review": ["review", "comment", "feedback", "suggest"],
                "research": ["research", "study", "analysis", "find"],
                "plan": ["plan", "strategy", "roadmap", "timeline"]
            }
            
            for topic_name, keywords in topic_keywords.items():
                if any(kw in content_lower for kw in keywords):
                    topics.add(topic_name)
        
        return max(1, len(topics))
