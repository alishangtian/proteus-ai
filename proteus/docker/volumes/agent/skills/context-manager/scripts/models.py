"""
Data models for OpenCode-style context management system.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Union
from enum import Enum
import time

class MessageType(str, Enum):
    """Type of message in conversation."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    COMPACTION = "compaction"  # Special type for compression summaries

class PartType(str, Enum):
    """Type of message part."""
    TEXT = "text"
    TOOL = "tool"
    FILE = "file"
    SNAPSHOT = "snapshot"
    REASONING = "reasoning"
    COMPACTION = "compaction"

@dataclass
class TokenCount:
    """Token counts for a message or operation."""
    input: int = 0            # Input tokens
    output: int = 0           # Output tokens
    reasoning: int = 0        # Reasoning tokens (for models with reasoning)
    cache_read: int = 0       # Cache read tokens
    cache_write: int = 0      # Cache write tokens
    
    @property
    def total(self) -> int:
        """Total tokens across all categories."""
        return self.input + self.output + self.reasoning + self.cache_read + self.cache_write
    
    def __add__(self, other: 'TokenCount') -> 'TokenCount':
        """Add two TokenCount objects."""
        return TokenCount(
            input=self.input + other.input,
            output=self.output + other.output,
            reasoning=self.reasoning + other.reasoning,
            cache_read=self.cache_read + other.cache_read,
            cache_write=self.cache_write + other.cache_write
        )

@dataclass
class MessagePart:
    """A single part of a message."""
    id: str
    type: PartType
    content: Any
    tokens: int = 0
    metadata: Optional[Dict[str, Any]] = None
    compacted: bool = False  # Whether this part has been compressed/compacted

@dataclass
class Message:
    """A complete message in the conversation."""
    id: str
    role: MessageType
    parts: List[MessagePart]
    tokens: TokenCount
    timestamp: float
    parent_id: Optional[str] = None
    summary: bool = False  # Whether this is a summary/compaction message
    metadata: Optional[Dict[str, Any]] = None
    
    @property
    def content(self) -> str:
        """Extract text content from message parts."""
        content_parts = []
        for part in self.parts:
            if part.type == PartType.TEXT:
                content_parts.append(str(part.content))
            elif part.type == PartType.TOOL:
                tool_name = part.content.get("tool_name", "unknown") if isinstance(part.content, dict) else "tool"
                content_parts.append(f"[Tool: {tool_name}]")
        return " ".join(content_parts)

@dataclass
class ModelLimits:
    """Limits for a specific LLM model."""
    context_limit: int      # Total context limit (e.g., 128000 for GPT-4)
    input_limit: int        # Input token limit
    output_limit: int       # Output token limit
    
    @property
    def usable_context(self) -> int:
        """
        Usable context after reserving space for output.
        
        Formula: context_limit - min(output_limit, 32000)
        Based on OpenCode's OUTPUT_TOKEN_MAX constant.
        """
        reserved_output = min(self.output_limit, 32000)  # Max output to reserve
        return self.context_limit - reserved_output

@dataclass  
class SessionConfig:
    """Configuration for session behavior."""
    auto_compact: bool = True          # Enable automatic compression
    auto_prune: bool = True            # Enable automatic pruning
    prune_protect_tokens: int = 40000  # Protect recent tokens from pruning
    prune_minimum_tokens: int = 20000  # Minimum tokens to trigger pruning
    output_token_max: int = 32000      # Maximum output tokens to reserve
    protected_tools: List[str] = field(default_factory=lambda: ["skill", "code_search", "file_read"])
    enable_caching: bool = True        # Enable compression result caching
    cache_size: int = 100              # LRU cache size
    background_pruning: bool = True    # Perform pruning in background
    incremental_counting: bool = True  # Use incremental token counting
    
    def __post_init__(self):
        """Validate configuration."""
        if self.prune_protect_tokens < 0:
            raise ValueError("prune_protect_tokens must be non-negative")
        if self.prune_minimum_tokens < 0:
            raise ValueError("prune_minimum_tokens must be non-negative")
        if self.output_token_max < 0:
            raise ValueError("output_token_max must be non-negative")

@dataclass
class SessionState:
    """State of a conversation session."""
    id: str
    messages: List[Message]
    config: SessionConfig
    model_limits: ModelLimits
    total_tokens: int = 0
    last_compaction_time: Optional[float] = None
    last_pruning_time: Optional[float] = None
    compaction_count: int = 0
    pruned_tokens_total: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def token_usage_percentage(self) -> float:
        """Percentage of usable context being used."""
        if self.model_limits.usable_context <= 0:
            return 0.0
        return (self.total_tokens / self.model_limits.usable_context) * 100
    
    @property
    def is_over_limit(self) -> bool:
        """Check if session exceeds usable context limit."""
        if not self.config.auto_compact:
            return False
        return self.total_tokens > self.model_limits.usable_context

@dataclass
class CompactionResult:
    """Result of a compression operation."""
    session_id: str
    message_id: str
    summary: str
    tokens_before: int
    tokens_after: int
    original_messages_count: int
    timestamp: float = field(default_factory=time.time)
    
    @property
    def compression_ratio(self) -> float:
        """Compression ratio (0-1, where 1 = no compression)."""
        if self.tokens_before == 0:
            return 1.0
        return self.tokens_after / self.tokens_before
    
    @property
    def tokens_saved(self) -> int:
        """Tokens saved by compression."""
        return self.tokens_before - self.tokens_after

@dataclass
class PruningResult:
    """Result of a pruning operation."""
    session_id: str
    pruned_parts: List[str]  # IDs of pruned parts
    tokens_pruned: int
    protected_tools_preserved: List[str]
    timestamp: float = field(default_factory=time.time)

@dataclass
class OperationResult:
    """Result of adding a message to context."""
    message_added: bool
    compaction_performed: bool = False
    compaction_result: Optional[CompactionResult] = None
    pruning_performed: bool = False
    pruning_result: Optional[PruningResult] = None
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

@dataclass
class SessionStats:
    """Statistics for a session."""
    session_id: str
    total_messages: int
    total_tokens: int
    token_usage_percentage: float
    compaction_count: int
    pruned_tokens_total: int
    average_compression_ratio: float
    last_activity_time: float
    message_type_distribution: Dict[MessageType, int]
    
    @classmethod
    def from_session(cls, session: SessionState) -> 'SessionStats':
        """Create stats from a session."""
        # Calculate message type distribution
        distribution = {}
        for msg in session.messages:
            distribution[msg.role] = distribution.get(msg.role, 0) + 1
        
        # Calculate average compression ratio (simplified)
        avg_ratio = 0.7  # Placeholder - would need tracking of compression ratios
        
        return cls(
            session_id=session.id,
            total_messages=len(session.messages),
            total_tokens=session.total_tokens,
            token_usage_percentage=session.token_usage_percentage,
            compaction_count=session.compaction_count,
            pruned_tokens_total=session.pruned_tokens_total,
            average_compression_ratio=avg_ratio,
            last_activity_time=time.time(),
            message_type_distribution=distribution
        )
