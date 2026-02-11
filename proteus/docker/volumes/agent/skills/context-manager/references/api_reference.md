# API Reference: OpenCode-style Context Management System

## Overview

This document provides complete API documentation for the context management system. All classes, methods, and configuration options are documented here.

## Table of Contents

1. [OpenCodeContextManager](#opencodecontextmanager)
2. [Data Models](#data-models)
3. [CompressionEngine](#compressionengine)
4. [PruningEngine](#pruningengine)
5. [Event System](#event-system)
6. [AdaptiveCompression](#adaptivecompression)
7. [Configuration](#configuration)
8. [Usage Examples](#usage-examples)

## OpenCodeContextManager

Main orchestrator class for context management operations.

### Class Definition

```python
class OpenCodeContextManager:
    """Main orchestrator for context management operations."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the context manager.
        
        Args:
            config: Optional configuration dictionary. If None, defaults are used.
        """
```

### Methods

#### `create_session()`

```python
def create_session(
    self,
    session_id: str,
    model_limits: Optional[ModelLimits] = None,
    config: Optional[SessionConfig] = None
) -> SessionState:
    """
    Create a new conversation session.
    
    Args:
        session_id: Unique identifier for the session
        model_limits: Model token limits (defaults to GPT-4 128k)
        config: Session-specific configuration (defaults to manager config)
    
    Returns:
        New session state
    
    Raises:
        ValueError: If session_id already exists
    """
```

#### `add_message()`

```python
async def add_message(
    self,
    session_id: str,
    message: Message,
    trigger_operations: bool = True
) -> OperationResult:
    """
    Add a message to a session, optionally triggering compression/pruning.
    
    Args:
        session_id: Session identifier
        message: Message to add
        trigger_operations: Whether to automatically trigger compression/pruning
    
    Returns:
        Operation result with details of any operations performed
    
    Raises:
        ValueError: If session_id not found
    """
```

#### `manual_compact()`

```python
async def manual_compact(self, session_id: str) -> CompactionResult:
    """
    Manually trigger compression for a session.
    
    Args:
        session_id: Session identifier
    
    Returns:
        Result of compression operation
    
    Raises:
        ValueError: If session_id not found
    """
```

#### `manual_prune()`

```python
def manual_prune(self, session_id: str) -> PruningResult:
    """
    Manually trigger pruning for a session.
    
    Args:
        session_id: Session identifier
    
    Returns:
        Result of pruning operation
    
    Raises:
        ValueError: If session_id not found
    """
```

#### `get_session()`

```python
def get_session(self, session_id: str) -> Optional[SessionState]:
    """
    Get session by ID.
    
    Args:
        session_id: Session identifier
    
    Returns:
        Session state or None if not found
    """
```

#### `get_session_stats()`

```python
def get_session_stats(self, session_id: str) -> Optional[SessionStats]:
    """
    Get statistics for a session.
    
    Args:
        session_id: Session identifier
    
    Returns:
        Session statistics or None if session not found
    """
```

#### `list_sessions()`

```python
def list_sessions(self) -> List[str]:
    """
    List all session IDs.
    
    Returns:
        List of session identifiers
    """
```

#### `delete_session()`

```python
def delete_session(self, session_id: str) -> bool:
    """
    Delete a session.
    
    Args:
        session_id: Session identifier
    
    Returns:
        True if session was deleted, False if not found
    """
```

#### `export_session_summary()`

```python
def export_session_summary(self, session_id: str) -> Dict[str, Any]:
    """
    Export comprehensive session summary.
    
    Args:
        session_id: Session identifier
    
    Returns:
        Dictionary with session summary data
    
    Raises:
        ValueError: If session_id not found
    """
```

#### `get_monitoring_stats()`

```python
def get_monitoring_stats(self) -> Dict[str, Any]:
    """
    Get overall monitoring statistics.
    
    Returns:
        Dictionary with system-wide statistics
    """
```

## Data Models

### SessionState

```python
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
    
    @property
    def is_over_limit(self) -> bool:
        """Check if session exceeds usable context limit."""
```

### Message

```python
@dataclass
class Message:
    """A complete message in the conversation."""
    
    id: str
    role: MessageType          # user, assistant, system, compaction
    parts: List[MessagePart]   # Text, tool, file, reasoning parts
    tokens: TokenCount         # Token breakdown
    timestamp: float
    parent_id: Optional[str] = None
    summary: bool = False      # Whether this is a summary message
    metadata: Optional[Dict[str, Any]] = None
    
    @property
    def content(self) -> str:
        """Extract text content from message parts."""
```

### MessagePart

```python
@dataclass
class MessagePart:
    """A single part of a message."""
    
    id: str
    type: PartType            # text, tool, file, snapshot, reasoning, compaction
    content: Any
    tokens: int = 0
    metadata: Optional[Dict[str, Any]] = None
    compacted: bool = False   # Whether this part has been compressed/compacted
```

### TokenCount

```python
@dataclass
class TokenCount:
    """Token counts for a message or operation."""
    
    input: int = 0            # Input tokens
    output: int = 0           # Output tokens
    reasoning: int = 0        # Reasoning tokens
    cache_read: int = 0       # Cache read tokens
    cache_write: int = 0      # Cache write tokens
    
    @property
    def total(self) -> int:
        """Total tokens across all categories."""
    
    def __add__(self, other: 'TokenCount') -> 'TokenCount':
        """Add two TokenCount objects."""
```

### ModelLimits

```python
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
        """
```

### SessionConfig

```python
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
```

### OperationResult

```python
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
```

### CompactionResult

```python
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
    
    @property
    def tokens_saved(self) -> int:
        """Tokens saved by compression."""
```

### PruningResult

```python
@dataclass
class PruningResult:
    """Result of a pruning operation."""
    
    session_id: str
    pruned_parts: List[str]  # IDs of pruned parts
    tokens_pruned: int
    protected_tools_preserved: List[str]
    timestamp: float = field(default_factory=time.time)
```

### SessionStats

```python
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
```

## CompressionEngine

### Class Definition

```python
class CompressionEngine:
    """Engine for compressing conversation history."""
```

### Methods

#### `compact_conversation()`

```python
async def compact_conversation(
    self,
    session: SessionState,
    context_messages: Optional[List[Message]] = None,
    auto: bool = True
) -> CompactionResult:
    """
    Compress conversation history into a summary.
    
    Args:
        session: Session to compact
        context_messages: Specific messages to include in context
        auto: Whether this is automatic compaction (vs manual)
    
    Returns:
        Result of compression operation
    """
```

#### `adaptive_compact()`

```python
def adaptive_compact(
    self,
    session: SessionState,
    target_tokens: int,
    min_preservation: float = 0.3
) -> CompactionResult:
    """
    Adaptive compression to reach target token count.
    
    Args:
        session: Session to compact
        target_tokens: Desired maximum tokens after compression
        min_preservation: Minimum fraction of context to preserve (0-1)
    
    Returns:
        Result of compression operation
    """
```

## PruningEngine

### Class Definition

```python
class PruningEngine:
    """Engine for pruning old tool outputs."""
```

### Methods

#### `prune_old_tool_outputs()`

```python
def prune_old_tool_outputs(self, session: SessionState) -> PruningResult:
    """
    Prune old tool outputs from session.
    
    Algorithm based on OpenCode's implementation:
    1. Scan messages from newest to oldest
    2. Skip first 2 conversation turns
    3. Stop at first summary message or already compacted tool
    4. Accumulate tokens, protect recent tokens
    5. Prune beyond protection threshold
    6. Only prune if minimum tokens can be saved
    
    Args:
        session: Session to prune
    
    Returns:
        Result of pruning operation
    """
```

#### `smart_prune()`

```python
def smart_prune(self, session: SessionState, focus_tokens: int = 30000) -> PruningResult:
    """
    Smarter pruning that considers conversation structure.
    
    Args:
        session: Session to prune
        focus_tokens: Target tokens to keep in focused context
    
    Returns:
        Result of pruning operation
    """
```

#### `calculate_potential_savings()`

```python
def calculate_potential_savings(self, session: SessionState) -> int:
    """
    Calculate potential token savings without actually pruning.
    
    Args:
        session: Session to analyze
    
    Returns:
        Estimated tokens that could be saved by pruning
    """
```

## Event System

### EventBus

```python
class EventBus:
    """Simple event bus for pub/sub communication."""
    
    def subscribe(
        self,
        callback: Callable[[Event], Any],
        event_types: Optional[List[EventType]] = None,
        filter_func: Optional[Callable[[Event], bool]] = None,
        transform_func: Optional[Callable[[Event], Any]] = None
    ) -> EventHandler:
        """
        Subscribe to events.
        
        Args:
            callback: Function to call when event occurs
            event_types: List of event types to subscribe to
            filter_func: Additional filter function
            transform_func: Function to transform event
        
        Returns:
            EventHandler object
        """
    
    async def publish(
        self,
        event_type: EventType,
        data: Dict[str, Any],
        source: str = "system"
    ) -> List[Any]:
        """
        Publish an event to all subscribers.
        
        Args:
            event_type: Type of event
            data: Event data
            source: Source of the event
        
        Returns:
            List of results from handlers
        """
```

### ContextEventBus

```python
class ContextEventBus(EventBus):
    """Specialized event bus for context management events."""
    
    async def publish_session_created(self, session_id: str, config: Dict[str, Any]):
        """Publish session created event."""
    
    async def publish_session_updated(self, session_id: str, changes: Dict[str, Any]):
        """Publish session updated event."""
    
    async def publish_compaction_started(self, session_id: str, trigger: str = "auto"):
        """Publish compaction started event."""
    
    async def publish_compaction_completed(
        self,
        session_id: str,
        tokens_saved: int,
        compression_ratio: float,
        summary_preview: str
    ):
        """Publish compaction completed event."""
    
    async def publish_pruning_completed(
        self,
        session_id: str,
        tokens_pruned: int,
        parts_pruned: int,
        protected_tools: List[str]
    ):
        """Publish pruning completed event."""
    
    async def publish_context_overflow(
        self,
        session_id: str,
        current_tokens: int,
        limit: int,
        operations_performed: List[str]
    ):
        """Publish context overflow event."""
```

### Event Types

```python
class EventType(str, Enum):
    """Types of events in the system."""
    
    # Session events
    SESSION_CREATED = "session.created"
    SESSION_UPDATED = "session.updated"
    SESSION_DELETED = "session.deleted"
    
    # Compression events
    COMPACTION_STARTED = "compaction.started"
    COMPACTION_COMPLETED = "compaction.completed"
    COMPACTION_FAILED = "compaction.failed"
    
    # Pruning events
    PRUNING_STARTED = "pruning.started"
    PRUNING_COMPLETED = "pruning.completed"
    PRUNING_FAILED = "pruning.failed"
    
    # Context events
    CONTEXT_OVERFLOW = "context.overflow"
    CONTEXT_CLEARED = "context.cleared"
    
    # Monitoring events
    STATS_UPDATED = "stats.updated"
    WARNING_ISSUED = "warning.issued"
    ERROR_OCCURRED = "error.occurred"
```

## AdaptiveCompression

### Class Definition

```python
class AdaptiveCompression:
    """Adaptive compression strategy selector."""
```

### Methods

#### `detect_conversation_type()`

```python
def detect_conversation_type(self, messages: List[Message]) -> ConversationType:
    """
    Detect the type of conversation from message content.
    
    Args:
        messages: Conversation messages to analyze
    
    Returns:
        Detected conversation type
    """
```

#### `get_compression_profile()`

```python
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
    
    Returns:
        Adjusted compression profile
    """
```

#### `record_effectiveness()`

```python
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
```

## Configuration

### Default Configuration

```python
DEFAULT_CONFIG = {
    "auto_compact": True,
    "auto_prune": True,
    "prune_protect_tokens": 40000,
    "prune_minimum_tokens": 20000,
    "output_token_max": 32000,
    "protected_tools": ["skill", "code_search", "file_read"],
    "enable_caching": True,
    "cache_size": 100,
    "background_pruning": True,
    "incremental_counting": True
}
```

### Model-Specific Configurations

#### GPT-4 (128k)

```python
GPT4_LIMITS = ModelLimits(
    context_limit=128000,
    input_limit=120000,
    output_limit=8000
)
```

#### Claude 3.5 Sonnet (200k)

```python
CLAUDE_LIMITS = ModelLimits(
    context_limit=200000,
    input_limit=196000,
    output_limit=4000
)
```

#### GPT-4o (128k)

```python
GPT4O_LIMITS = ModelLimits(
    context_limit=128000,
    input_limit=127000,
    output_limit=1000
)
```

### Conversation Type Profiles

```python
PROFILES = {
    ConversationType.DEBUGGING: CompressionProfile(
        name="Debugging",
        description="Aggressive compression for debugging sessions.",
        target_compression_ratio=0.3,
        preserve_tools=["code_search", "debug_tool"],
        focus_keywords=["error", "bug", "fix", "debug"]
    ),
    ConversationType.CODE_REVIEW: CompressionProfile(
        name="Code Review",
        description="Balanced compression for code reviews.",
        target_compression_ratio=0.5,
        preserve_tools=["code_search", "diff_tool"],
        focus_keywords=["review", "comment", "suggestion"]
    ),
    # ... additional profiles
}
```

## Usage Examples

### Basic Usage

```python
from context_manager import OpenCodeContextManager
from models import ModelLimits

# Initialize manager
manager = OpenCodeContextManager()

# Create session
model_limits = ModelLimits(
    context_limit=128000,
    input_limit=120000,
    output_limit=8000
)
session = manager.create_session("my_session", model_limits)

# Add messages (automatic compression/pruning)
result = await manager.add_message("my_session", message)
if result.compaction_performed:
    print(f"Compression saved {result.compaction_result.tokens_saved} tokens")
```

### Custom Configuration

```python
config = {
    "auto_compact": True,
    "auto_prune": True,
    "prune_protect_tokens": 50000,
    "prune_minimum_tokens": 25000,
    "protected_tools": ["skill", "my_custom_tool"],
    "enable_caching": True,
    "cache_size": 200
}

manager = OpenCodeContextManager(config)
```

### Event Handling

```python
from event_bus import global_event_bus, EventType

async def on_compaction(event):
    print(f"Compression completed: {event.data['tokens_saved']} tokens saved")

# Subscribe to events
global_event_bus.subscribe(on_compaction, [EventType.COMPACTION_COMPLETED])
```

### Manual Operations

```python
# Manual compression
compaction_result = await manager.manual_compact("my_session")
print(f"Manual compression: {compaction_result.compression_ratio:.2f} ratio")

# Manual pruning
pruning_result = manager.manual_prune("my_session")
print(f"Manual pruning: {pruning_result.tokens_pruned} tokens pruned")
```

### Session Monitoring

```python
# Get session statistics
stats = manager.get_session_stats("my_session")
if stats:
    print(f"Messages: {stats.total_messages}")
    print(f"Tokens: {stats.total_tokens}")
    print(f"Usage: {stats.token_usage_percentage:.1f}%")

# Export session summary
summary = manager.export_session_summary("my_session")
print(f"Session created at: {summary['created_at']}")
```

## Error Handling

### Common Exceptions

1. **ValueError**: Invalid arguments or session not found
2. **TypeError**: Incorrect data types
3. **RuntimeError**: System errors during operations

### Error Recovery

```python
try:
    result = await manager.add_message("nonexistent_session", message)
except ValueError as e:
    print(f"Session error: {e}")
    # Create new session or handle error
except Exception as e:
    print(f"Unexpected error: {e}")
    # Log error and retry or fail gracefully
```

## Performance Tips

1. **Use Incremental Counting**: Enable for large sessions
2. **Enable Caching**: For repeated conversation patterns
3. **Background Pruning**: For better responsiveness
4. **Session Limits**: Prevent memory growth with timeouts
5. **Batch Operations**: Group messages when possible

## Testing

### Unit Tests

```python
def test_overflow_detection():
    manager = OpenCodeContextManager()
    session = manager.create_session("test", ModelLimits(10000, 9000, 1000))
    
    # Add messages until overflow
    # Assert compression/pruning triggered
```

### Integration Tests

```python
async def test_end_to_end():
    manager = OpenCodeContextManager()
    
    # Simulate conversation
    # Verify final state and statistics
```

## Migration and Compatibility

### Version 1.0 to 2.0

- Added adaptive compression strategies
- Enhanced event system
- Improved monitoring capabilities
- Backward compatible API

### Data Migration

Sessions and messages are stored in memory by default. For persistence, implement custom storage adapters.
