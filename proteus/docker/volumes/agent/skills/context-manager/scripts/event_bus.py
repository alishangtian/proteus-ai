"""
Event Bus for OpenCode-style context management.

Provides pub/sub functionality for loose coupling between components.
"""

import asyncio
import time
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

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

@dataclass
class Event:
    """Event data structure."""
    type: EventType
    data: Dict[str, Any]
    timestamp: float
    source: str
    
    def __str__(self) -> str:
        return f"{self.type} from {self.source} at {time.strftime('%H:%M:%S', time.localtime(self.timestamp))}"

class EventHandler:
    """Handler for events with filtering and transformation."""
    
    def __init__(
        self,
        callback: Callable[[Event], Any],
        event_types: Optional[List[EventType]] = None,
        filter_func: Optional[Callable[[Event], bool]] = None,
        transform_func: Optional[Callable[[Event], Any]] = None
    ):
        self.callback = callback
        self.event_types = event_types
        self.filter_func = filter_func
        self.transform_func = transform_func
        self.call_count = 0
        self.last_called = 0.0
    
    def should_handle(self, event: Event) -> bool:
        """Check if this handler should handle the event."""
        if self.event_types and event.type not in self.event_types:
            return False
        
        if self.filter_func and not self.filter_func(event):
            return False
        
        return True
    
    async def handle(self, event: Event) -> Any:
        """Handle the event."""
        self.call_count += 1
        self.last_called = time.time()
        
        # Transform event if needed
        if self.transform_func:
            event_data = self.transform_func(event)
        else:
            event_data = event
        
        # Call handler
        try:
            result = self.callback(event_data)
            if asyncio.iscoroutine(result):
                result = await result
            return result
        except Exception as e:
            print(f"Error in event handler for {event.type}: {e}")
            raise

class EventBus:
    """Simple event bus for pub/sub communication."""
    
    def __init__(self):
        self.handlers: Dict[EventType, List[EventHandler]] = {}
        self.event_history: List[Event] = []
        self.max_history = 1000
        self._lock = asyncio.Lock()
    
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
            event_types: List of event types to subscribe to (None = all)
            filter_func: Additional filter function
            transform_func: Function to transform event before passing to callback
        
        Returns:
            EventHandler object that can be used to unsubscribe
        """
        handler = EventHandler(callback, event_types, filter_func, transform_func)
        
        if event_types:
            for event_type in event_types:
                if event_type not in self.handlers:
                    self.handlers[event_type] = []
                self.handlers[event_type].append(handler)
        else:
            # Subscribe to all event types
            for event_type in EventType:
                if event_type not in self.handlers:
                    self.handlers[event_type] = []
                self.handlers[event_type].append(handler)
        
        print(f"[EventBus] New subscription for events: {event_types or 'ALL'}")
        return handler
    
    def unsubscribe(self, handler: EventHandler) -> bool:
        """Unsubscribe a handler."""
        removed = False
        
        for event_type, handlers in self.handlers.items():
            if handler in handlers:
                handlers.remove(handler)
                removed = True
        
        if removed:
            print(f"[EventBus] Handler unsubscribed")
        
        return removed
    
    async def publish(self, event_type: EventType, data: Dict[str, Any], source: str = "system") -> List[Any]:
        """
        Publish an event to all subscribers.
        
        Args:
            event_type: Type of event
            data: Event data
            source: Source of the event
        
        Returns:
            List of results from handlers
        """
        async with self._lock:
            event = Event(
                type=event_type,
                data=data,
                timestamp=time.time(),
                source=source
            )
            
            # Add to history
            self.event_history.append(event)
            if len(self.event_history) > self.max_history:
                self.event_history = self.event_history[-self.max_history:]
            
            # Get handlers for this event type
            handlers = self.handlers.get(event_type, [])
            
            # Also get handlers subscribed to all events
            all_handlers = self.handlers.get(None, []) if None in self.handlers else []
            
            all_handlers_to_call = handlers + all_handlers
            
            if not all_handlers_to_call:
                print(f"[EventBus] No handlers for event: {event_type}")
                return []
            
            print(f"[EventBus] Publishing {event_type} to {len(all_handlers_to_call)} handlers")
            
            # Call handlers
            results = []
            for handler in all_handlers_to_call:
                if handler.should_handle(event):
                    try:
                        result = await handler.handle(event)
                        results.append(result)
                    except Exception as e:
                        print(f"[EventBus] Error in handler for {event_type}: {e}")
            
            return results
    
    def get_event_history(
        self,
        event_type: Optional[EventType] = None,
        since: Optional[float] = None,
        limit: int = 100
    ) -> List[Event]:
        """Get event history with optional filtering."""
        filtered = self.event_history
        
        if event_type:
            filtered = [e for e in filtered if e.type == event_type]
        
        if since:
            filtered = [e for e in filtered if e.timestamp >= since]
        
        return filtered[-limit:] if limit else filtered
    
    def get_handler_stats(self) -> Dict[str, Any]:
        """Get statistics about handlers."""
        stats = {
            "total_handlers": 0,
            "events_with_handlers": 0,
            "handler_call_counts": {},
            "most_active_handlers": []
        }
        
        for event_type, handlers in self.handlers.items():
            if handlers:
                stats["events_with_handlers"] += 1
                stats["total_handlers"] += len(handlers)
                
                for handler in handlers:
                    stats["handler_call_counts"][id(handler)] = handler.call_count
        
        # Find most active handlers
        if stats["handler_call_counts"]:
            sorted_counts = sorted(
                stats["handler_call_counts"].items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]
            stats["most_active_handlers"] = sorted_counts
        
        return stats
    
    def clear_history(self):
        """Clear event history."""
        self.event_history = []
        print("[EventBus] Event history cleared")

class ContextEventBus(EventBus):
    """Specialized event bus for context management events."""
    
    def __init__(self):
        super().__init__()
        self._setup_default_handlers()
    
    def _setup_default_handlers(self):
        """Setup default event handlers for context management."""
        
        # Log all events
        async def log_event(event: Event):
            print(f"[EventLog] {event}")
        
        self.subscribe(log_event)
        
        # Monitor context overflow
        async def handle_context_overflow(event: Event):
            session_id = event.data.get("session_id")
            tokens = event.data.get("tokens")
            limit = event.data.get("limit")
            
            print(f"[ContextMonitor] Session {session_id} overflow: {tokens} > {limit}")
            
            # In a real system, this might trigger alerts or scaling
            return {"action": "logged", "session": session_id}
        
        self.subscribe(
            handle_context_overflow,
            event_types=[EventType.CONTEXT_OVERFLOW]
        )
        
        # Track compaction statistics
        async def track_compaction(event: Event):
            if event.type == EventType.COMPACTION_COMPLETED:
                session_id = event.data.get("session_id")
                tokens_saved = event.data.get("tokens_saved", 0)
                compression_ratio = event.data.get("compression_ratio", 1.0)
                
                print(f"[CompactionTrack] Session {session_id}: saved {tokens_saved} tokens, ratio {compression_ratio:.2f}")
        
        self.subscribe(
            track_compaction,
            event_types=[EventType.COMPACTION_STARTED, EventType.COMPACTION_COMPLETED]
        )
    
    async def publish_session_created(self, session_id: str, config: Dict[str, Any]):
        """Publish session created event."""
        return await self.publish(
            EventType.SESSION_CREATED,
            {"session_id": session_id, "config": config},
            source="session_manager"
        )
    
    async def publish_session_updated(self, session_id: str, changes: Dict[str, Any]):
        """Publish session updated event."""
        return await self.publish(
            EventType.SESSION_UPDATED,
            {"session_id": session_id, "changes": changes},
            source="session_manager"
        )
    
    async def publish_compaction_started(self, session_id: str, trigger: str = "auto"):
        """Publish compaction started event."""
        return await self.publish(
            EventType.COMPACTION_STARTED,
            {"session_id": session_id, "trigger": trigger, "timestamp": time.time()},
            source="compression_engine"
        )
    
    async def publish_compaction_completed(
        self,
        session_id: str,
        tokens_saved: int,
        compression_ratio: float,
        summary_preview: str
    ):
        """Publish compaction completed event."""
        return await self.publish(
            EventType.COMPACTION_COMPLETED,
            {
                "session_id": session_id,
                "tokens_saved": tokens_saved,
                "compression_ratio": compression_ratio,
                "summary_preview": summary_preview[:100],
                "timestamp": time.time()
            },
            source="compression_engine"
        )
    
    async def publish_pruning_completed(
        self,
        session_id: str,
        tokens_pruned: int,
        parts_pruned: int,
        protected_tools: List[str]
    ):
        """Publish pruning completed event."""
        return await self.publish(
            EventType.PRUNING_COMPLETED,
            {
                "session_id": session_id,
                "tokens_pruned": tokens_pruned,
                "parts_pruned": parts_pruned,
                "protected_tools": protected_tools,
                "timestamp": time.time()
            },
            source="pruning_engine"
        )
    
    async def publish_context_overflow(
        self,
        session_id: str,
        current_tokens: int,
        limit: int,
        operations_performed: List[str]
    ):
        """Publish context overflow event."""
        return await self.publish(
            EventType.CONTEXT_OVERFLOW,
            {
                "session_id": session_id,
                "tokens": current_tokens,
                "limit": limit,
                "operations_performed": operations_performed,
                "timestamp": time.time()
            },
            source="context_manager"
        )

# Global event bus instance
global_event_bus = ContextEventBus()
