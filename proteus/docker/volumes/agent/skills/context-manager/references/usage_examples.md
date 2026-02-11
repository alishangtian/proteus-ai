# Usage Examples: OpenCode-style Context Management System

## Table of Contents

1. [Basic Integration](#basic-integration)
2. [AI Agent Integration](#ai-agent-integration)
3. [Custom Configuration](#custom-configuration)
4. [Advanced Scenarios](#advanced-scenarios)
5. [Monitoring and Analytics](#monitoring-and-analytics)
6. [Troubleshooting](#troubleshooting)

## Basic Integration

### Example 1: Simple Chat Application

```python
import asyncio
from context_manager import OpenCodeContextManager
from models import Message, MessagePart, MessageType, PartType, TokenCount, ModelLimits

class SimpleChatApp:
    def __init__(self):
        # Initialize context manager with default settings
        self.context_manager = OpenCodeContextManager()
        self.session_id = "chat_session_123"
        
        # Create session with GPT-4 limits
        model_limits = ModelLimits(
            context_limit=128000,
            input_limit=120000,
            output_limit=8000
        )
        
        self.context_manager.create_session(self.session_id, model_limits)
    
    async def chat(self, user_input: str) -> str:
        """Process user input and return response."""
        
        # 1. Create user message
        user_msg = Message(
            id=f"user_{int(time.time())}",
            role=MessageType.USER,
            parts=[
                MessagePart(
                    id=f"part_{int(time.time())}",
                    type=PartType.TEXT,
                    content=user_input,
                    tokens=len(user_input) // 4
                )
            ],
            tokens=TokenCount(input=len(user_input) // 4),
            timestamp=time.time()
        )
        
        # 2. Add message to context (automatically handles compression/pruning)
        result = await self.context_manager.add_message(self.session_id, user_msg)
        
        # 3. Check if compression occurred
        if result.compaction_performed:
            print(f"Context compressed: saved {result.compaction_result.tokens_saved} tokens")
            # You might want to adjust your prompt based on the compression
        
        # 4. Generate response (simplified - in reality you'd call an LLM)
        response = f"Processed: {user_input}"
        
        # 5. Add assistant response to context
        assistant_msg = Message(
            id=f"assistant_{int(time.time())}",
            role=MessageType.ASSISTANT,
            parts=[
                MessagePart(
                    id=f"part_{int(time.time())}_2",
                    type=PartType.TEXT,
                    content=response,
                    tokens=len(response) // 4
                )
            ],
            tokens=TokenCount(output=len(response) // 4),
            timestamp=time.time()
        )
        
        await self.context_manager.add_message(self.session_id, assistant_msg)
        
        return response

# Usage
async def main():
    app = SimpleChatApp()
    
    # Simulate conversation
    messages = [
        "Hello!",
        "Can you help me debug this Python code?",
        "Here's the code: def foo(x): return x + 1",
        "Actually, let me show you the full file...",
        # ... many more messages
    ]
    
    for msg in messages:
        response = await app.chat(msg)
        print(f"User: {msg}")
        print(f"Assistant: {response}")
        print()

asyncio.run(main())
```

### Example 2: Long-running Conversation with Tool Usage

```python
import time
from context_manager import OpenCodeContextManager
from models import Message, MessagePart, MessageType, PartType, TokenCount, ModelLimits

class ToolBasedAssistant:
    def __init__(self):
        # Configure for tool-heavy conversations
        config = {
            "auto_compact": True,
            "auto_prune": True,
            "prune_protect_tokens": 50000,  # Protect more tokens for tool outputs
            "prune_minimum_tokens": 15000,
            "protected_tools": ["code_search", "file_read", "debugger"]
        }
        
        self.context_manager = OpenCodeContextManager(config)
        self.session_id = "tool_session_456"
        
        model_limits = ModelLimits(
            context_limit=128000,
            input_limit=120000,
            output_limit=8000
        )
        
        self.context_manager.create_session(self.session_id, model_limits)
    
    async def execute_tool(self, tool_name: str, tool_input: dict) -> dict:
        """Execute a tool and add result to context."""
        
        # Simulate tool execution
        tool_output = {
            "result": f"Tool {tool_name} executed successfully",
            "data": {"input": tool_input, "processed": True},
            "timestamp": time.time()
        }
        
        # Create tool message
        tool_msg = Message(
            id=f"tool_{int(time.time())}",
            role=MessageType.ASSISTANT,
            parts=[
                MessagePart(
                    id=f"part_{int(time.time())}_tool",
                    type=PartType.TOOL,
                    content={
                        "tool_name": tool_name,
                        "input": tool_input,
                        "output": tool_output,
                        "status": "completed"
                    },
                    tokens=500  # Estimated tokens for tool output
                )
            ],
            tokens=TokenCount(output=500),
            timestamp=time.time()
        )
        
        # Add to context
        result = await self.context_manager.add_message(self.session_id, tool_msg)
        
        # Report any compression/pruning
        if result.compaction_performed:
            print(f"Tool execution triggered compression")
        if result.pruning_performed:
            print(f"Old tool outputs pruned: {result.pruning_result.tokens_pruned} tokens")
        
        return tool_output
    
    async def get_conversation_summary(self) -> str:
        """Get current conversation state summary."""
        session = self.context_manager.get_session(self.session_id)
        
        if not session or not session.messages:
            return "No conversation yet"
        
        # Find latest compression summary
        for msg in reversed(session.messages):
            if msg.role == MessageType.COMPACTION or msg.summary:
                return msg.content
        
        # If no compression yet, get recent messages
        recent = session.messages[-5:] if len(session.messages) >= 5 else session.messages
        return " | ".join([m.content[:50] for m in recent])

# Usage
async def tool_demo():
    assistant = ToolBasedAssistant()
    
    # Simulate tool-heavy conversation
    tools = ["code_search", "file_read", "debugger", "lint_checker"]
    
    for i in range(50):
        tool_name = tools[i % len(tools)]
        result = await assistant.execute_tool(
            tool_name,
            {"query": f"Search query {i}", "params": {"depth": "deep"}}
        )
        
        # Check conversation state periodically
        if i % 10 == 0:
            summary = await assistant.get_conversation_summary()
            print(f"Checkpoint {i}: {summary[:100]}...")
```

## AI Agent Integration

### Example 3: Integration with OpenAI API

```python
import openai
from openai import OpenAI
from context_manager import OpenCodeContextManager
from models import Message, MessagePart, MessageType, PartType, TokenCount, ModelLimits

class OpenAIAgentWithContext:
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)
        
        # Configure context manager for OpenAI models
        config = {
            "auto_compact": True,
            "auto_prune": True,
            "prune_protect_tokens": 40000,
            "prune_minimum_tokens": 20000,
            "protected_tools": ["web_search", "calculator"]  # Common OpenAI tools
        }
        
        self.context_manager = OpenCodeContextManager(config)
        self.current_session_id = None
    
    def create_session(self, session_id: str, model: str = "gpt-4-turbo"):
        """Create a new conversation session."""
        self.current_session_id = session_id
        
        # Set model-specific limits
        model_limits = self._get_model_limits(model)
        self.context_manager.create_session(session_id, model_limits)
        
        return session_id
    
    def _get_model_limits(self, model: str) -> ModelLimits:
        """Get token limits for specific OpenAI models."""
        limits = {
            "gpt-4-turbo": ModelLimits(128000, 120000, 8000),
            "gpt-4": ModelLimits(8192, 8000, 192),
            "gpt-3.5-turbo": ModelLimits(16384, 16000, 384),
            "gpt-4o": ModelLimits(128000, 127000, 1000),
        }
        return limits.get(model, ModelLimits(128000, 120000, 8000))
    
    async def chat_completion(
        self,
        user_message: str,
        system_prompt: str = "You are a helpful assistant.",
        temperature: float = 0.7
    ) -> str:
        """Send message to OpenAI with context management."""
        
        if not self.current_session_id:
            raise ValueError("No active session. Call create_session() first.")
        
        # 1. Add user message to context
        user_msg = self._create_message(user_message, MessageType.USER)
        result = await self.context_manager.add_message(self.current_session_id, user_msg)
        
        # 2. Get conversation context for prompt
        context_messages = await self._prepare_context(system_prompt)
        
        # 3. Call OpenAI API
        response = await self.client.chat.completions.create(
            model="gpt-4-turbo",
            messages=context_messages,
            temperature=temperature,
            max_tokens=4000
        )
        
        assistant_message = response.choices[0].message.content
        
        # 4. Add assistant response to context
        assistant_msg = self._create_message(assistant_message, MessageType.ASSISTANT)
        await self.context_manager.add_message(self.current_session_id, assistant_msg)
        
        # 5. Handle context operations if triggered
        self._handle_context_operations(result)
        
        return assistant_message
    
    async def _prepare_context(self, system_prompt: str) -> list:
        """Prepare messages for OpenAI API from context."""
        session = self.context_manager.get_session(self.current_session_id)
        
        if not session:
            return [{"role": "system", "content": system_prompt}]
        
        messages = [{"role": "system", "content": system_prompt}]
        
        # Convert stored messages to OpenAI format
        for msg in session.messages[-20:]:  # Limit to recent messages
            if msg.role == MessageType.COMPACTION:
                # Include compression summaries as system messages
                messages.append({
                    "role": "system",
                    "content": f"Conversation summary: {msg.content}"
                })
            else:
                messages.append({
                    "role": msg.role.value,
                    "content": msg.content
                })
        
        return messages
    
    def _create_message(self, content: str, role: MessageType) -> Message:
        """Create a message object."""
        return Message(
            id=f"{role}_{int(time.time())}",
            role=role,
            parts=[
                MessagePart(
                    id=f"part_{int(time.time())}",
                    type=PartType.TEXT,
                    content=content,
                    tokens=len(content) // 4
                )
            ],
            tokens=TokenCount(
                input=len(content) // 4 if role == MessageType.USER else 0,
                output=len(content) // 4 if role == MessageType.ASSISTANT else 0
            ),
            timestamp=time.time()
        )
    
    def _handle_context_operations(self, result):
        """Handle and log context operations."""
        if result.compaction_performed:
            compaction = result.compaction_result
            print(f"✅ Compression performed: {compaction.tokens_saved} tokens saved")
            print(f"   Ratio: {compaction.compression_ratio:.2f}")
            
        if result.pruning_performed:
            pruning = result.pruning_result
            print(f"✅ Pruning performed: {pruning.tokens_pruned} tokens pruned")
            print(f"   Protected tools: {pruning.protected_tools_preserved}")

# Usage
async def openai_demo():
    agent = OpenAIAgentWithContext(api_key="your-api-key")
    agent.create_session("openai_session", model="gpt-4-turbo")
    
    # Simulate long conversation
    questions = [
        "Explain quantum computing in simple terms.",
        "Now give me a Python implementation of a quantum algorithm.",
        "What are the practical applications of this algorithm?",
        "How does this compare to classical algorithms?",
        # ... many more questions
    ]
    
    for i, question in enumerate(questions):
        print(f"
Q{i+1}: {question}")
        response = await agent.chat_completion(question)
        print(f"A{i+1}: {response[:100]}...")
        
        # Check session stats periodically
        if i % 5 == 0:
            stats = agent.context_manager.get_session_stats("openai_session")
            if stats:
                print(f"
📊 Session stats: {stats.total_messages} messages, "
                      f"{stats.total_tokens} tokens, {stats.token_usage_percentage:.1f}% used")
```

### Example 4: Integration with Anthropic Claude

```python
import anthropic
from context_manager import OpenCodeContextManager
from models import Message, MessagePart, MessageType, PartType, TokenCount, ModelLimits

class ClaudeAgentWithContext:
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        
        # Claude-specific configuration
        config = {
            "auto_compact": True,
            "auto_prune": True,
            "prune_protect_tokens": 60000,  # Claude has larger context
            "prune_minimum_tokens": 25000,
            "output_token_max": 4000,  # Claude's typical output limit
        }
        
        self.context_manager = OpenCodeContextManager(config)
    
    async def chat_with_claude(
        self,
        session_id: str,
        user_message: str,
        model: str = "claude-3-5-sonnet-20241022"
    ) -> str:
        """Send message to Claude with context management."""
        
        # Create session if it doesn't exist
        if not self.context_manager.get_session(session_id):
            model_limits = self._get_claude_limits(model)
            self.context_manager.create_session(session_id, model_limits)
        
        # Add user message
        user_msg = self._create_message(user_message, MessageType.USER)
        await self.context_manager.add_message(session_id, user_msg)
        
        # Prepare messages for Claude
        messages = await self._prepare_claude_messages(session_id)
        
        # Call Claude API
        response = self.client.messages.create(
            model=model,
            max_tokens=4000,
            messages=messages
        )
        
        assistant_message = response.content[0].text
        
        # Add Claude's response to context
        assistant_msg = self._create_message(assistant_message, MessageType.ASSISTANT)
        await self.context_manager.add_message(session_id, assistant_msg)
        
        return assistant_message
    
    def _get_claude_limits(self, model: str) -> ModelLimits:
        """Get token limits for Claude models."""
        limits = {
            "claude-3-5-sonnet-20241022": ModelLimits(200000, 196000, 4000),
            "claude-3-opus-20240229": ModelLimits(200000, 196000, 4000),
            "claude-3-haiku-20240307": ModelLimits(200000, 196000, 4000),
        }
        return limits.get(model, ModelLimits(200000, 196000, 4000))
```

## Custom Configuration

### Example 5: Domain-Specific Configuration

```python
from context_manager import OpenCodeContextManager
from models import ModelLimits, SessionConfig

class DomainSpecificManager:
    """Context manager configured for specific domains."""
    
    @staticmethod
    def for_code_review():
        """Configuration for code review sessions."""
        config = {
            "auto_compact": True,
            "auto_prune": True,
            "prune_protect_tokens": 50000,  # Preserve more context for reviews
            "prune_minimum_tokens": 25000,
            "protected_tools": ["code_search", "diff_tool", "lint_checker"],
            "enable_caching": True,
            "cache_size": 50
        }
        
        return OpenCodeContextManager(config)
    
    @staticmethod
    def for_research():
        """Configuration for research sessions."""
        config = {
            "auto_compact": True,
            "auto_prune": False,  # Don't prune - research outputs remain relevant
            "prune_protect_tokens": 80000,
            "protected_tools": ["web_search", "citation_lookup", "paper_analyzer"],
            "enable_caching": True,
            "cache_size": 100
        }
        
        return OpenCodeContextManager(config)
    
    @staticmethod
    def for_customer_support():
        """Configuration for customer support sessions."""
        config = {
            "auto_compact": True,
            "auto_prune": True,
            "prune_protect_tokens": 30000,  # More aggressive pruning
            "prune_minimum_tokens": 10000,
            "protected_tools": ["ticket_lookup", "knowledge_base"],
            "background_pruning": True  # Don't block responses
        }
        
        return OpenCodeContextManager(config)

# Usage
async def domain_demo():
    # Code review session
    code_review_mgr = DomainSpecificManager.for_code_review()
    code_session = code_review_mgr.create_session(
        "code_review_1",
        ModelLimits(128000, 120000, 8000)
    )
    
    # Research session
    research_mgr = DomainSpecificManager.for_research()
    research_session = research_mgr.create_session(
        "research_1",
        ModelLimits(200000, 196000, 4000)  # Claude limits for research
    )
    
    # Support session
    support_mgr = DomainSpecificManager.for_customer_support()
    support_session = support_mgr.create_session(
        "support_ticket_123",
        ModelLimits(32000, 30000, 2000)  # Smaller limits for support
    )
```

### Example 6: Dynamic Configuration Based on Usage

```python
from context_manager import OpenCodeContextManager
from models import ModelLimits

class AdaptiveContextManager:
    """Context manager that adapts configuration based on usage patterns."""
    
    def __init__(self):
        self.manager = OpenCodeContextManager()
        self.usage_patterns = {}
    
    def create_adaptive_session(self, session_id: str, initial_purpose: str = "general"):
        """Create session with adaptive configuration."""
        
        # Initial configuration based on purpose
        initial_config = self._get_initial_config(initial_purpose)
        
        model_limits = ModelLimits(128000, 120000, 8000)
        session = self.manager.create_session(session_id, model_limits, initial_config)
        
        # Track usage pattern
        self.usage_patterns[session_id] = {
            "purpose": initial_purpose,
            "message_count": 0,
            "tool_usage": {},
            "compression_count": 0
        }
        
        return session
    
    async def add_message_with_adaptation(self, session_id: str, message):
        """Add message and adapt configuration if needed."""
        
        result = await self.manager.add_message(session_id, message)
        
        # Update usage patterns
        self._update_usage_patterns(session_id, message, result)
        
        # Adapt configuration if patterns change
        self._adapt_configuration(session_id)
        
        return result
    
    def _get_initial_config(self, purpose: str) -> dict:
        """Get initial configuration based on purpose."""
        configs = {
            "debugging": {
                "auto_compact": True,
                "auto_prune": True,
                "prune_protect_tokens": 30000,
                "protected_tools": ["debugger", "stack_trace"]
            },
            "brainstorming": {
                "auto_compact": False,  # Don't compress creative sessions
                "auto_prune": False,
                "prune_protect_tokens": 80000
            },
            "documentation": {
                "auto_compact": True,
                "auto_prune": True,
                "prune_protect_tokens": 40000,
                "protected_tools": ["doc_generator", "template_filler"]
            },
            "general": {
                "auto_compact": True,
                "auto_prune": True,
                "prune_protect_tokens": 40000
            }
        }
        
        return configs.get(purpose, configs["general"])
```

## Advanced Scenarios

### Example 7: Multi-session Management

```python
from context_manager import OpenCodeContextManager
from models import ModelLimits
import asyncio

class MultiSessionManager:
    """Manage multiple conversation sessions."""
    
    def __init__(self, max_sessions: int = 100):
        self.manager = OpenCodeContextManager()
        self.max_sessions = max_sessions
        self.session_metadata = {}  # Track session metadata
    
    async def get_or_create_session(
        self,
        user_id: str,
        conversation_id: str,
        model: str = "gpt-4-turbo"
    ) -> str:
        """Get existing session or create new one."""
        session_id = f"{user_id}_{conversation_id}"
        
        if not self.manager.get_session(session_id):
            # Clean up old sessions if at limit
            await self._cleanup_old_sessions()
            
            # Create new session
            model_limits = self._get_model_limits(model)
            self.manager.create_session(session_id, model_limits)
            
            # Store metadata
            self.session_metadata[session_id] = {
                "user_id": user_id,
                "conversation_id": conversation_id,
                "created_at": time.time(),
                "last_accessed": time.time(),
                "message_count": 0,
                "model": model
            }
        
        # Update last accessed time
        self.session_metadata[session_id]["last_accessed"] = time.time()
        
        return session_id
    
    async def process_message(
        self,
        user_id: str,
        conversation_id: str,
        message: str
    ) -> dict:
        """Process message in appropriate session."""
        
        session_id = await self.get_or_create_session(user_id, conversation_id)
        
        # Add message to session
        # ... (message creation and addition logic)
        
        # Update metadata
        self.session_metadata[session_id]["message_count"] += 1
        
        # Get session stats
        stats = self.manager.get_session_stats(session_id)
        
        return {
            "session_id": session_id,
            "response": "Processed",  # Actual response from LLM
            "stats": {
                "messages": stats.total_messages if stats else 0,
                "tokens": stats.total_tokens if stats else 0,
                "compactions": stats.compaction_count if stats else 0
            }
        }
    
    async def _cleanup_old_sessions(self):
        """Clean up old or inactive sessions."""
        current_time = time.time()
        sessions_to_remove = []
        
        # Check if we're at capacity
        if len(self.manager.sessions) < self.max_sessions:
            return
        
        # Find old sessions (inactive for 24 hours)
        for session_id, metadata in self.session_metadata.items():
            if current_time - metadata["last_accessed"] > 86400:  # 24 hours
                sessions_to_remove.append(session_id)
        
        # Remove sessions
        for session_id in sessions_to_remove[:10]:  # Remove up to 10 at a time
            self.manager.delete_session(session_id)
            del self.session_metadata[session_id]
            
        print(f"Cleaned up {len(sessions_to_remove)} old sessions")
```

### Example 8: Context Export and Import

```python
import json
import pickle
from datetime import datetime
from context_manager import OpenCodeContextManager
from models import Message, MessagePart, MessageType, PartType, TokenCount

class ContextExporter:
    """Export and import conversation context."""
    
    def __init__(self, context_manager: OpenCodeContextManager):
        self.manager = context_manager
    
    def export_session_json(self, session_id: str, include_metadata: bool = True) -> str:
        """Export session to JSON format."""
        session = self.manager.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        export_data = {
            "session_id": session.id,
            "exported_at": datetime.now().isoformat(),
            "message_count": len(session.messages),
            "total_tokens": session.total_tokens,
            "compaction_count": session.compaction_count,
            "model_limits": {
                "context_limit": session.model_limits.context_limit,
                "input_limit": session.model_limits.input_limit,
                "output_limit": session.model_limits.output_limit
            },
            "messages": []
        }
        
        # Export messages
        for msg in session.messages:
            message_data = {
                "id": msg.id,
                "role": msg.role.value,
                "timestamp": msg.timestamp,
                "summary": msg.summary,
                "tokens": {
                    "input": msg.tokens.input,
                    "output": msg.tokens.output,
                    "total": msg.tokens.total
                },
                "content": msg.content[:1000]  # Truncate for JSON
            }
            
            if include_metadata and msg.metadata:
                message_data["metadata"] = msg.metadata
            
            export_data["messages"].append(message_data)
        
        return json.dumps(export_data, indent=2, default=str)
    
    def export_session_compressed(self, session_id: str) -> bytes:
        """Export session using pickle (compressed binary)."""
        session = self.manager.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        export_data = {
            "session": session,
            "exported_at": time.time(),
            "version": "1.0"
        }
        
        return pickle.dumps(export_data)
    
    def import_session(self, session_data: dict) -> str:
        """Import session from exported data."""
        # Create new session ID
        new_session_id = f"imported_{int(time.time())}"
        
        # Recreate session
        if "model_limits" in session_data:
            from models import ModelLimits
            model_limits = ModelLimits(**session_data["model_limits"])
        else:
            model_limits = ModelLimits(128000, 120000, 8000)
        
        # Create session
        self.manager.create_session(new_session_id, model_limits)
        
        # Recreate messages (simplified - in reality would need full recreation)
        print(f"Imported session {new_session_id} with {len(session_data.get('messages', []))} messages")
        
        return new_session_id
```

## Monitoring and Analytics

### Example 9: Real-time Monitoring Dashboard

```python
from context_manager import OpenCodeContextManager
from event_bus import global_event_bus, EventType
import asyncio
import time

class ContextMonitor:
    """Monitor context management operations in real-time."""
    
    def __init__(self, context_manager: OpenCodeContextManager):
        self.manager = context_manager
        self.metrics = {
            "compactions": [],
            "prunings": [],
            "overflows": [],
            "sessions_created": 0,
            "messages_processed": 0
        }
        
        # Subscribe to events
        self._setup_event_handlers()
    
    def _setup_event_handlers(self):
        """Setup event handlers for monitoring."""
        
        async def on_compaction_completed(event):
            self.metrics["compactions"].append({
                "timestamp": event.timestamp,
                "session_id": event.data["session_id"],
                "tokens_saved": event.data.get("tokens_saved", 0),
                "compression_ratio": event.data.get("compression_ratio", 1.0)
            })
            
            # Keep only last 100 compactions
            if len(self.metrics["compactions"]) > 100:
                self.metrics["compactions"] = self.metrics["compactions"][-100:]
        
        async def on_pruning_completed(event):
            self.metrics["prunings"].append({
                "timestamp": event.timestamp,
                "session_id": event.data["session_id"],
                "tokens_pruned": event.data.get("tokens_pruned", 0),
                "parts_pruned": event.data.get("parts_pruned", 0)
            })
        
        async def on_session_created(event):
            self.metrics["sessions_created"] += 1
        
        # Subscribe to events
        global_event_bus.subscribe(on_compaction_completed, [EventType.COMPACTION_COMPLETED])
        global_event_bus.subscribe(on_pruning_completed, [EventType.PRUNING_COMPLETED])
        global_event_bus.subscribe(on_session_created, [EventType.SESSION_CREATED])
    
    def get_metrics_summary(self) -> dict:
        """Get summary of all metrics."""
        now = time.time()
        one_hour_ago = now - 3600
        
        recent_compactions = [
            c for c in self.metrics["compactions"]
            if c["timestamp"] > one_hour_ago
        ]
        
        recent_prunings = [
            p for p in self.metrics["prunings"]
            if p["timestamp"] > one_hour_ago
        ]
        
        total_tokens_saved = sum(c["tokens_saved"] for c in recent_compactions)
        total_tokens_pruned = sum(p["tokens_pruned"] for p in recent_prunings)
        
        return {
            "time_period": "last_hour",
            "compaction_count": len(recent_compactions),
            "pruning_count": len(recent_prunings),
            "total_tokens_saved": total_tokens_saved,
            "total_tokens_pruned": total_tokens_pruned,
            "avg_compression_ratio": (
                sum(c["compression_ratio"] for c in recent_compactions) / 
                len(recent_compactions) if recent_compactions else 0
            ),
            "sessions_created_total": self.metrics["sessions_created"],
            "active_sessions": len(self.manager.sessions)
        }
    
    def print_realtime_dashboard(self, interval: int = 5):
        """Print real-time dashboard at intervals."""
        try:
            while True:
                self._clear_screen()
                print("=" * 80)
                print("CONTEXT MANAGEMENT DASHBOARD")
                print("=" * 80)
                print()
                
                # Overall stats
                stats = self.manager.get_monitoring_stats()
                print("📊 OVERALL STATISTICS")
                print(f"  Active Sessions: {stats['total_sessions']}")
                print(f"  Total Messages: {stats['total_messages']}")
                print(f"  Total Tokens: {stats['total_tokens']:,}")
                print(f"  Total Compactions: {stats['total_compactions']}")
                print(f"  Total Pruned Tokens: {stats['total_pruned_tokens']:,}")
                print()
                
                # Recent metrics
                metrics = self.get_metrics_summary()
                print("⏰ LAST HOUR METRICS")
                print(f"  Compactions: {metrics['compaction_count']}")
                print(f"  Prunings: {metrics['pruning_count']}")
                print(f"  Tokens Saved: {metrics['total_tokens_saved']:,}")
                print(f"  Tokens Pruned: {metrics['total_tokens_pruned']:,}")
                print(f"  Avg Compression Ratio: {metrics['avg_compression_ratio']:.2f}")
                print()
                
                # Active sessions
                print("🎯 ACTIVE SESSIONS")
                for session_id in list(self.manager.sessions.keys())[:5]:  # Show first 5
                    session = self.manager.get_session(session_id)
                    if session:
                        print(f"  {session_id}: {len(session.messages)} msgs, "
                              f"{session.total_tokens:,} tokens, "
                              f"{session.token_usage_percentage:.1f}% used")
                
                if len(self.manager.sessions) > 5:
                    print(f"  ... and {len(self.manager.sessions) - 5} more sessions")
                
                print()
                print(f"Updated: {datetime.now().strftime('%H:%M:%S')}")
                print("=" * 80)
                
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print("
Dashboard stopped.")
    
    def _clear_screen(self):
        """Clear terminal screen."""
        print("[H[J", end="")
```

## Troubleshooting

### Example 10: Debugging Common Issues

```python
from context_manager import OpenCodeContextManager
from models import ModelLimits

class ContextDebugger:
    """Debug tools for context management issues."""
    
    def __init__(self, context_manager: OpenCodeContextManager):
        self.manager = context_manager
    
    def diagnose_session(self, session_id: str) -> dict:
        """Run comprehensive diagnostics on a session."""
        session = self.manager.get_session(session_id)
        if not session:
            return {"error": f"Session {session_id} not found"}
        
        diagnostics = {
            "session_id": session_id,
            "basic_info": {
                "message_count": len(session.messages),
                "total_tokens": session.total_tokens,
                "usable_context": session.model_limits.usable_context,
                "usage_percentage": session.token_usage_percentage,
                "compaction_count": session.compaction_count,
                "pruned_tokens_total": session.pruned_tokens_total
            },
            "config_analysis": self._analyze_config(session.config),
            "message_analysis": self._analyze_messages(session.messages),
            "tool_analysis": self._analyze_tool_usage(session.messages),
            "issues": []
        }
        
        # Check for issues
        if session.total_tokens > session.model_limits.usable_context:
            diagnostics["issues"].append({
                "type": "overflow",
                "severity": "high",
                "message": f"Session overflow: {session.total_tokens} > {session.model_limits.usable_context}",
                "suggestion": "Consider increasing prune_protect_tokens or disabling auto_compact"
            })
        
        if session.compaction_count > 10:
            diagnostics["issues"].append({
                "type": "frequent_compaction",
                "severity": "medium",
                "message": f"High compaction count: {session.compaction_count}",
                "suggestion": "Conversation may be too verbose. Consider shorter responses."
            })
        
        return diagnostics
    
    def _analyze_config(self, config) -> dict:
        """Analyze configuration for potential issues."""
        analysis = {
            "auto_compact": config.auto_compact,
            "auto_prune": config.auto_prune,
            "prune_protect_tokens": config.prune_protect_tokens,
            "prune_minimum_tokens": config.prune_minimum_tokens,
            "protected_tools_count": len(config.protected_tools),
            "notes": []
        }
        
        if config.prune_minimum_tokens > config.prune_protect_tokens:
            analysis["notes"].append(
                "prune_minimum_tokens > prune_protect_tokens: Pruning may never trigger"
            )
        
        if not config.protected_tools:
            analysis["notes"].append(
                "No protected tools: All tool outputs may be pruned"
            )
        
        return analysis
    
    def _analyze_messages(self, messages) -> dict:
        """Analyze message patterns."""
        if not messages:
            return {"empty": True}
        
        message_types = {}
        for msg in messages:
            msg_type = msg.role.value
            message_types[msg_type] = message_types.get(msg_type, 0) + 1
        
        # Calculate average tokens per message
        total_tokens = sum(msg.tokens.total for msg in messages)
        avg_tokens = total_tokens / len(messages) if messages else 0
        
        return {
            "total_messages": len(messages),
            "message_type_distribution": message_types,
            "avg_tokens_per_message": avg_tokens,
            "has_compaction_messages": any(msg.role.value == "compaction" for msg in messages)
        }
    
    def print_diagnostic_report(self, session_id: str):
        """Print formatted diagnostic report."""
        diagnostics = self.diagnose_session(session_id)
        
        print("=" * 80)
        print(f"DIAGNOSTIC REPORT: {session_id}")
        print("=" * 80)
        print()
        
        # Basic Info
        print("📋 BASIC INFORMATION")
        for key, value in diagnostics["basic_info"].items():
            print(f"  {key.replace('_', ' ').title()}: {value}")
        print()
        
        # Configuration
        print("⚙️ CONFIGURATION")
        config = diagnostics["config_analysis"]
        for key, value in config.items():
            if key != "notes":
                print(f"  {key.replace('_', ' ').title()}: {value}")
        
        if config["notes"]:
            print("
  Notes:")
            for note in config["notes"]:
                print(f"    • {note}")
        print()
        
        # Issues
        if diagnostics["issues"]:
            print("🚨 ISSUES DETECTED")
            for issue in diagnostics["issues"]:
                print(f"
  [{issue['severity'].upper()}] {issue['type'].replace('_', ' ').title()}")
                print(f"  Message: {issue['message']}")
                print(f"  Suggestion: {issue['suggestion']}")
            print()
        else:
            print("✅ NO ISSUES DETECTED")
            print()
        
        print("=" * 80)
```

## Performance Optimization Tips

1. **Enable Caching**: For conversations with repeated patterns
2. **Use Background Pruning**: To avoid blocking message processing
3. **Implement Incremental Counting**: For sessions with many messages
4. **Set Appropriate Thresholds**: Based on your specific use case
5. **Monitor and Adjust**: Regularly review metrics and adjust configuration

## Common Patterns

### Pattern 1: Conversation Checkpoints

```python
# Save conversation state at important points
async def create_checkpoint(session_id: str, checkpoint_name: str):
    manager.manual_compact(session_id)
    stats = manager.get_session_stats(session_id)
    print(f"Checkpoint '{checkpoint_name}' created: {stats.total_tokens} tokens")
```

### Pattern 2: Progressive Disclosure

```python
# Start with aggressive compression, become more conservative
config = {
    "prune_protect_tokens": 20000,  # Start aggressive
    # Gradually increase as conversation grows
}
```

### Pattern 3: Session Archiving

```python
# Archive old sessions but keep summaries
async def archive_session(session_id: str):
    # Export summary
    summary = manager.export_session_summary(session_id)
    
    # Save to database or file
    save_to_database(summary)
    
    # Delete from active memory
    manager.delete_session(session_id)
```

## Conclusion

These examples demonstrate the flexibility and power of the OpenCode-style context management system. The key is to:

1. **Understand your use case** and configure accordingly
2. **Monitor performance** and adjust as needed
3. **Leverage events** for real-time insights
4. **Implement proper error handling** and recovery
5. **Regularly review and optimize** your configuration

The system is designed to be adaptable to various scenarios, from simple chat applications to complex AI agent systems with extensive tool usage.
