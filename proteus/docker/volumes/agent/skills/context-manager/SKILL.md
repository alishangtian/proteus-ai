---
name: context-manager
description: OpenCode-style intelligent context management system for AI agents with
  automatic compression and pruning. Use when building or working with long-running
  AI conversations, managing context windows for LLM interactions, implementing conversation
  history optimization, or dealing with token limit constraints in AI systems. Provides
  architecture patterns, Python implementations, and best practices for context overflow
  handling, intelligent summarization, and selective memory retention.
version: 1.0.0
---
# Context Manager: OpenCode-style Intelligent Context Management System

## Overview

This skill provides a comprehensive implementation of OpenCode's sophisticated context management architecture, designed for AI agents dealing with long conversations and limited context windows. It implements intelligent compression (summarization) and pruning (selective forgetting) strategies to optimize token usage while preserving critical conversation context.

Based on the production-proven architecture from [anomalyco/opencode](https://github.com/anomalyco/opencode), this system enables AI agents to handle extended dialogues without losing important information or exceeding model token limits.

## Core Capabilities

### 1. Context Overflow Detection
- **Token tracking**: Real-time monitoring of input/output/cache tokens
- **Smart thresholds**: Calculates usable context considering output reservation
- **Model-aware limits**: Respects specific model constraints (GPT-4, Claude, etc.)

### 2. Intelligent Compression (Compaction)
- **Agent-based summarization**: Uses specialized AI agent to generate conversation summaries
- **Context preservation**: Retains critical information (files, decisions, next steps)
- **Automatic triggering**: Activates when conversation exceeds available context

### 3. Selective Pruning
- **Tool output management**: Clears old tool outputs while preserving recent ones
- **Protected tools**: Excludes critical tools (e.g., "skill", "code_search") from pruning
- **Configurable thresholds**: 40k tokens protected, 20k minimum pruning threshold

### 4. Layered Architecture
- **Async context isolation**: Uses AsyncLocalStorage for thread-safe context management
- **Session management**: Hierarchical context (Instance → Session → Message)
- **Event-driven updates**: Pub/Sub system for state changes

## Architecture

For detailed architecture documentation, see [ARCHITECTURE.md](references/architecture.md).

### Key Components

#### Context Manager (`context_manager.py`)
Main orchestrator that coordinates compression and pruning operations.

```python
from context_manager import OpenCodeContextManager

# Initialize with custom configuration
config = {
    "auto_compact": True,
    "auto_prune": True,
    "prune_protect_tokens": 40000,
    "prune_minimum_tokens": 20000,
}
manager = OpenCodeContextManager(config)
```

#### Compression Engine (`compression_engine.py`)
Generates intelligent summaries of conversation history.

#### Pruning Engine (`pruning_engine.py`)
Selectively removes old tool outputs to free up tokens.

#### Data Models (`models.py`)
Type-safe data structures for messages, sessions, and tokens.

## Quick Start

### Installation

The context manager is implemented as a pure Python library with no external dependencies (beyond standard libraries).

```python
# Import the complete system
from scripts.context_manager import OpenCodeContextManager
from scripts.models import SessionConfig, ModelLimits, Message, MessageType
```

### Basic Usage

```python
import asyncio
from datetime import datetime

async def basic_demo():
    # 1. Initialize context manager
    config = {
        "auto_compact": True,
        "auto_prune": True,
        "prune_protect_tokens": 40000,
        "prune_minimum_tokens": 20000,
    }
    
    manager = OpenCodeContextManager(config)
    
    # 2. Create a session (simulating GPT-4 128k context)
    model_limits = ModelLimits(
        context_limit=128000,
        input_limit=120000,
        output_limit=8000
    )
    
    session = manager.create_session("session_123", model_limits)
    
    # 3. Add messages (automatically triggers compression/pruning)
    message = Message(
        id="msg_1",
        role=MessageType.USER,
        content="Please help me debug this Python function...",
        tokens=150
    )
    
    operations = await manager.add_message("session_123", message)
    
    if operations.get("compacted"):
        print("Compaction performed to manage context window")
    if operations.get("pruned_tokens", 0) > 0:
        print(f"Pruned {operations['pruned_tokens']} tokens")
    
    return operations

# Run the demo
asyncio.run(basic_demo())
```

## Workflows

### Workflow 1: Managing Long Conversations

When dealing with extended AI conversations (code reviews, debugging sessions, research assistance):

1. **Initialize** with appropriate model limits
2. **Add messages** normally - the system handles overflow automatically
3. **Monitor operations** to understand when compression/pruning occurs
4. **Review summaries** generated during compaction for context preservation

### Workflow 2: Custom Compression Strategies

For specialized use cases requiring custom compression logic:

1. **Extend CompressionEngine** to implement domain-specific summarization
2. **Configure protected tools** to preserve critical tool outputs
3. **Adjust thresholds** based on conversation patterns
4. **Implement custom triggers** for compression events

### Workflow 3: Integration with Existing Systems

To integrate with existing AI agent frameworks:

1. **Wrap message handling** to intercept add_message calls
2. **Implement storage adapters** for different backends (SQLite, Redis, etc.)
3. **Add event listeners** for compression/pruning events
4. **Extend data models** to include application-specific metadata

## Configuration Options

### Core Settings

```python
config = {
    # Automatic compression when context overflows
    "auto_compact": True,
    
    # Automatic pruning of old tool outputs
    "auto_prune": True,
    
    # Number of recent tokens to protect from pruning
    "prune_protect_tokens": 40000,
    
    # Minimum tokens to prune (avoids frequent small operations)
    "prune_minimum_tokens": 20000,
    
    # Maximum output tokens to reserve
    "output_token_max": 32000,
    
    # Tools whose outputs should never be pruned
    "protected_tools": ["skill", "code_search", "file_read"],
    
    # Compression agent configuration
    "compaction_agent": {
        "model": "gpt-4-turbo",
        "temperature": 0.3,
        "max_tokens": 4000
    }
}
```

### Model-Specific Configuration

Different LLMs have different context window characteristics:

```python
# GPT-4 Turbo (128k)
gpt4_limits = ModelLimits(
    context_limit=128000,
    input_limit=120000,
    output_limit=8000
)

# Claude 3.5 Sonnet (200k)
claude_limits = ModelLimits(
    context_limit=200000,
    input_limit=196000,
    output_limit=4000
)

# GPT-4o (128k)
gpt4o_limits = ModelLimits(
    context_limit=128000,
    input_limit=127000,
    output_limit=1000
)
```

## Advanced Features

### Event-Driven Architecture

The system uses an event bus for loose coupling:

```python
from scripts.event_bus import EventBus

# Subscribe to compression events
event_bus = EventBus()

@event_bus.subscribe("session.compacted")
def on_compaction(event):
    print(f"Session {event.session_id} was compacted")
    print(f"Summary: {event.summary[:100]}...")

@event_bus.subscribe("tool.pruned")
def on_pruning(event):
    print(f"Pruned tool {event.tool_name}, saved {event.tokens_saved} tokens")
```

### Adaptive Compression Strategies

Intelligent compression based on conversation type:

```python
from scripts.adaptive_compression import AdaptiveCompression

adaptive = AdaptiveCompression()

# Detect conversation type automatically
convo_type = adaptive.detect_conversation_type(messages)

# Apply type-specific compression strategy
if convo_type == "debugging":
    # Focus on error messages and fixes
    strategy = adaptive.STRATEGIES["debugging"]
elif convo_type == "code_review":
    # Focus on file changes and decisions
    strategy = adaptive.STRATEGIES["code_review"]
```

### Performance Optimization

```python
# Enable caching for compression results
config["enable_caching"] = True
config["cache_size"] = 100  # LRU cache entries

# Background pruning to avoid blocking
config["background_pruning"] = True
config["pruning_batch_size"] = 10

# Incremental token counting
config["incremental_counting"] = True
```

## API Reference

For complete API documentation, see [API_REFERENCE.md](references/api_reference.md).

### Core Classes

- **`OpenCodeContextManager`**: Main orchestrator class
- **`CompressionEngine`**: Handles conversation summarization
- **`PruningEngine`**: Manages selective tool output removal
- **`SessionState`**: Represents a conversation session
- **`Message`**: Individual message with token tracking

### Key Methods

- **`add_message()`**: Add message with automatic overflow handling
- **`compact_conversation()`**: Manually trigger compression
- **`prune_session()`**: Manually trigger pruning
- **`get_session_stats()`**: Get token usage and compression history
- **`export_summary()`**: Export compression summaries for review

## Usage Examples

For detailed examples and scenarios, see [USAGE_EXAMPLES.md](references/usage_examples.md).

### Example 1: Code Review Session

Managing a multi-file code review with extensive discussion:

```python
async def code_review_example():
    manager = OpenCodeContextManager()
    
    # Simulate code review conversation
    for i in range(50):
        msg = create_code_review_message(i)
        operations = await manager.add_message("review_123", msg)
        
        if operations.get("compacted"):
            print(f"Checkpoint created at message {i}")
    
    # Export final summary
    summary = manager.export_summary("review_123")
    print(f"Final summary: {summary}")
```

### Example 2: Research Assistant

Handling research queries with extensive citations and references:

```python
async def research_assistant_example():
    config = {
        "protected_tools": ["web_search", "citation_lookup", "data_analysis"],
        "prune_protect_tokens": 60000  # Protect more tokens for research
    }
    
    manager = OpenCodeContextManager(config)
    
    # Research conversations preserve tool outputs longer
    # due to their ongoing relevance
```

## Best Practices

### When to Use Compression vs Pruning

| Scenario | Recommended Strategy | Rationale |
|----------|---------------------|-----------|
| **Code debugging** | Aggressive pruning, light compression | Tool outputs become irrelevant quickly |
| **Research analysis** | Light pruning, heavy compression | Citations and references remain relevant |
| **Creative writing** | Balanced approach | Preserve narrative flow while managing length |
| **Technical design** | Focus on compression | Important decisions must be retained |

### Configuration Guidelines

1. **Start with defaults**: The default configuration works for most use cases
2. **Monitor operations**: Adjust thresholds based on actual compression/pruning frequency
3. **Protect critical tools**: Identify tools whose outputs should never be pruned
4. **Consider conversation type**: Adjust strategies based on domain (debugging, research, etc.)

### Performance Considerations

- **Token counting**: Use incremental counting for large sessions
- **Cache compression results**: Similar conversations can reuse summaries
- **Background operations**: Non-blocking pruning for better responsiveness
- **Storage optimization**: Compress stored messages when not in active use

## Integration Patterns

### With AI Agent Frameworks

```python
class AIAgentWithContextManager:
    def __init__(self):
        self.context_manager = OpenCodeContextManager()
        self.llm_client = OpenAIClient()
    
    async def chat(self, message: str):
        # 1. Add user message to context
        user_msg = Message(role="user", content=message)
        await self.context_manager.add_message(self.session_id, user_msg)
        
        # 2. Check for recent compression
        recent_compactions = self.context_manager.get_recent_compactions()
        if recent_compactions:
            # Include summary in prompt
            prompt = self.build_prompt_with_summary()
        else:
            prompt = self.build_normal_prompt()
        
        # 3. Generate response
        response = await self.llm_client.complete(prompt)
        
        # 4. Add assistant response to context
        assistant_msg = Message(role="assistant", content=response)
        await self.context_manager.add_message(self.session_id, assistant_msg)
        
        return response
```

### With Vector Databases

Combine with vector search for enhanced context retrieval:

```python
class HybridContextManager:
    def __init__(self):
        self.context_manager = OpenCodeContextManager()
        self.vector_db = VectorDatabase()
    
    async def get_relevant_context(self, query: str):
        # 1. Get recent messages from context manager
        recent = self.context_manager.get_recent_messages(limit=20)
        
        # 2. Search vector DB for similar historical context
        similar = await self.vector_db.search(query, limit=5)
        
        # 3. Combine with intelligent compression
        if len(recent) + len(similar) > self.max_context:
            compressed = await self.context_manager.compress_context(recent)
            return compressed + similar
        else:
            return recent + similar
```

## Troubleshooting

### Common Issues

1. **Over-compression**: If too much context is lost, increase `prune_protect_tokens` or reduce `auto_compact` frequency
2. **Under-compression**: If context overflows frequently, decrease thresholds or enable more aggressive pruning
3. **Performance issues**: For large sessions, enable background operations and caching
4. **Memory growth**: Implement session expiration or archiving for very long-running sessions

### Monitoring and Metrics

```python
# Get detailed session statistics
stats = manager.get_session_stats("session_123")
print(f"Total messages: {stats.total_messages}")
print(f"Total tokens: {stats.total_tokens}")
print(f"Compactions: {stats.compaction_count}")
print(f"Tokens pruned: {stats.tokens_pruned}")
print(f"Compression ratio: {stats.compression_ratio:.2f}")

# Monitor over time
history = manager.get_compaction_history("session_123")
for event in history:
    print(f"{event.timestamp}: {event.tokens_before} → {event.tokens_after}")
```

## Resources

### Included Scripts

- `context_manager.py` - Main orchestrator class
- `compression_engine.py` - Intelligent summarization engine
- `pruning_engine.py` - Selective tool output management
- `models.py` - Data structures and type definitions
- `event_bus.py` - Event-driven communication system
- `adaptive_compression.py` - Context-aware compression strategies
- `demo.py` - Complete demonstration script

### References

- [ARCHITECTURE.md](references/architecture.md) - Detailed system architecture
- [API_REFERENCE.md](references/api_reference.md) - Complete API documentation
- [USAGE_EXAMPLES.md](references/usage_examples.md) - Practical examples and scenarios

### External Resources

- [OpenCode GitHub](https://github.com/anomalyco/opencode) - Original inspiration
- [Model Context Protocol](https://spec.modelcontextprotocol.io/) - Related context management standard
- [LLM Context Window Research](https://arxiv.org/abs/2307.03172) - Academic background

---

## License

This skill is provided under the MIT License. See the LICENSE.txt file for details.

## Contributing

When extending this skill:

1. **Test new compression strategies** with diverse conversation types
2. **Benchmark performance** with different model limits
3. **Validate token counting accuracy** against actual LLM tokenizers
4. **Document configuration options** thoroughly

Report issues or suggest improvements through the standard skill contribution process.
