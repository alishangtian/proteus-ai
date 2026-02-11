"""
Main Context Manager for OpenCode-style context management.

Orchestrates compression and pruning operations to manage
conversation context within token limits.
"""

import time
import asyncio
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from models import (
    SessionState, Message, MessageType, TokenCount,
    SessionConfig, ModelLimits, OperationResult,
    CompactionResult, PruningResult, SessionStats
)
from compression_engine import CompressionEngine
from pruning_engine import PruningEngine

@dataclass
class ContextManagerConfig:
    """Configuration for the context manager."""
    default_model_limits: ModelLimits = ModelLimits(
        context_limit=128000,
        input_limit=120000,
        output_limit=8000
    )
    enable_monitoring: bool = True
    max_sessions: int = 1000
    session_timeout_seconds: int = 86400  # 24 hours
    cleanup_interval_seconds: int = 3600   # 1 hour

class OpenCodeContextManager:
    """Main orchestrator for context management operations."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the context manager.
        
        Args:
            config: Optional configuration dictionary. If None, defaults are used.
        """
        self.sessions: Dict[str, SessionState] = {}
        self.config = self._load_config(config)
        self.compression_engine = CompressionEngine()
        self.pruning_engine = PruningEngine()
        self.monitoring_stats: Dict[str, Any] = {}
        
        # Start background cleanup if enabled
        if self.config.enable_monitoring:
            self._start_background_cleanup()
    
    def _load_config(self, user_config: Optional[Dict[str, Any]]) -> SessionConfig:
        """Load configuration from user input or use defaults."""
        if user_config is None:
            return SessionConfig()
        
        # Map user config to SessionConfig fields
        return SessionConfig(
            auto_compact=user_config.get("auto_compact", True),
            auto_prune=user_config.get("auto_prune", True),
            prune_protect_tokens=user_config.get("prune_protect_tokens", 40000),
            prune_minimum_tokens=user_config.get("prune_minimum_tokens", 20000),
            output_token_max=user_config.get("output_token_max", 32000),
            protected_tools=user_config.get("protected_tools", ["skill", "code_search", "file_read"]),
            enable_caching=user_config.get("enable_caching", True),
            cache_size=user_config.get("cache_size", 100),
            background_pruning=user_config.get("background_pruning", True),
            incremental_counting=user_config.get("incremental_counting", True)
        )
    
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
        """
        if session_id in self.sessions:
            raise ValueError(f"Session {session_id} already exists")
        
        if model_limits is None:
            model_limits = ModelLimits(
                context_limit=128000,
                input_limit=120000,
                output_limit=8000
            )
        
        if config is None:
            config = self.config
        
        session = SessionState(
            id=session_id,
            messages=[],
            config=config,
            model_limits=model_limits
        )
        
        self.sessions[session_id] = session
        
        if self.config.enable_monitoring:
            self.monitoring_stats[session_id] = {
                "created_at": time.time(),
                "message_count": 0,
                "compactions": 0,
                "prunings": 0,
                "total_tokens_processed": 0
            }
        
        print(f"[Context Manager] Created session {session_id} with model limits: {model_limits.context_limit} tokens")
        return session
    
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
        """
        if session_id not in self.sessions:
            raise ValueError(f"Session {session_id} not found")
        
        session = self.sessions[session_id]
        
        # Add message to session
        session.messages.append(message)
        
        # Update token count (incremental if enabled)
        if session.config.incremental_counting:
            session.total_tokens += message.tokens.total
        else:
            # Recalculate total (expensive)
            session.total_tokens = sum(msg.tokens.total for msg in session.messages)
        
        # Update monitoring
        if self.config.enable_monitoring:
            stats = self.monitoring_stats.get(session_id, {})
            stats["message_count"] = stats.get("message_count", 0) + 1
            stats["total_tokens_processed"] = stats.get("total_tokens_processed", 0) + message.tokens.total
        
        result = OperationResult(message_added=True)
        
        # Trigger automatic operations if enabled
        if trigger_operations:
            operations = await self._check_and_handle_overflow(session)
            
            # Merge results
            result.compaction_performed = operations.get("compaction_performed", False)
            result.compaction_result = operations.get("compaction_result")
            result.pruning_performed = operations.get("pruning_performed", False)
            result.pruning_result = operations.get("pruning_result")
            
            if operations.get("warnings"):
                result.warnings.extend(operations["warnings"])
        
        return result
    
    async def _check_and_handle_overflow(self, session: SessionState) -> Dict[str, Any]:
        """
        Check for context overflow and handle with compression/pruning.
        
        Returns:
            Dictionary with operation results
        """
        result = {
            "compaction_performed": False,
            "pruning_performed": False,
            "warnings": []
        }
        
        # Check if context is overflowing
        if not self._is_context_overflow(session):
            return result
        
        print(f"[Context Manager] Context overflow detected for session {session.id}: "
              f"{session.total_tokens} > {session.model_limits.usable_context}")
        
        # Step 1: Try pruning first (less destructive)
        if session.config.auto_prune:
            pruning_result = await self._perform_pruning(session)
            
            if pruning_result.tokens_pruned > 0:
                result["pruning_performed"] = True
                result["pruning_result"] = pruning_result
                
                # Recheck after pruning
                if not self._is_context_overflow(session):
                    print(f"[Context Manager] Pruning resolved overflow, saved {pruning_result.tokens_pruned} tokens")
                    return result
        
        # Step 2: If still overflowing, perform compression
        if session.config.auto_compact and self._is_context_overflow(session):
            compaction_result = await self._perform_compression(session)
            
            if compaction_result.tokens_saved > 0:
                result["compaction_performed"] = True
                result["compaction_result"] = compaction_result
                
                # Update session stats
                session.compaction_count += 1
                session.last_compaction_time = time.time()
        
        # Step 3: If still overflowing after compression, warn
        if self._is_context_overflow(session):
            warning = (f"Context still overflowing after compression/pruning: "
                      f"{session.total_tokens} > {session.model_limits.usable_context}")
            result["warnings"].append(warning)
            print(f"[WARNING] {warning}")
        
        return result
    
    def _is_context_overflow(self, session: SessionState) -> bool:
        """Check if session context is overflowing."""
        if not session.config.auto_compact:
            return False
        
        usable_context = session.model_limits.usable_context
        if usable_context <= 0:
            return False
        
        return session.total_tokens > usable_context
    
    async def _perform_pruning(self, session: SessionState) -> PruningResult:
        """Perform pruning operation."""
        if session.config.background_pruning:
            # Run in background thread to avoid blocking
            return await asyncio.to_thread(
                self.pruning_engine.prune_old_tool_outputs,
                session
            )
        else:
            return self.pruning_engine.prune_old_tool_outputs(session)
    
    async def _perform_compression(self, session: SessionState) -> CompactionResult:
        """Perform compression operation."""
        return await self.compression_engine.compact_conversation(session, auto=True)
    
    async def manual_compact(self, session_id: str) -> CompactionResult:
        """Manually trigger compression for a session."""
        if session_id not in self.sessions:
            raise ValueError(f"Session {session_id} not found")
        
        session = self.sessions[session_id]
        result = await self.compression_engine.compact_conversation(session, auto=False)
        
        # Update session
        session.compaction_count += 1
        session.last_compaction_time = time.time()
        
        # Update token count (recalculate after compression)
        session.total_tokens = sum(msg.tokens.total for msg in session.messages)
        
        return result
    
    def manual_prune(self, session_id: str) -> PruningResult:
        """Manually trigger pruning for a session."""
        if session_id not in self.sessions:
            raise ValueError(f"Session {session_id} not found")
        
        session = self.sessions[session_id]
        result = self.pruning_engine.prune_old_tool_outputs(session)
        
        # Update session
        session.last_pruning_time = time.time()
        
        return result
    
    def get_session(self, session_id: str) -> Optional[SessionState]:
        """Get session by ID."""
        return self.sessions.get(session_id)
    
    def get_session_stats(self, session_id: str) -> Optional[SessionStats]:
        """Get statistics for a session."""
        session = self.get_session(session_id)
        if session is None:
            return None
        
        return SessionStats.from_session(session)
    
    def list_sessions(self) -> List[str]:
        """List all session IDs."""
        return list(self.sessions.keys())
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        if session_id in self.sessions:
            del self.sessions[session_id]
            
            if session_id in self.monitoring_stats:
                del self.monitoring_stats[session_id]
            
            print(f"[Context Manager] Deleted session {session_id}")
            return True
        
        return False
    
    def get_compaction_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Get history of compaction operations for a session."""
        session = self.get_session(session_id)
        if session is None:
            return []
        
        # Extract compaction messages
        history = []
        for msg in session.messages:
            if msg.role == MessageType.COMPACTION or msg.summary:
                history.append({
                    "timestamp": msg.timestamp,
                    "message_id": msg.id,
                    "summary_preview": msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
                })
        
        return history
    
    def export_session_summary(self, session_id: str) -> Dict[str, Any]:
        """Export comprehensive session summary."""
        session = self.get_session(session_id)
        if session is None:
            raise ValueError(f"Session {session_id} not found")
        
        stats = self.get_session_stats(session_id)
        
        return {
            "session_id": session_id,
            "created_at": min([msg.timestamp for msg in session.messages]) if session.messages else time.time(),
            "message_count": len(session.messages),
            "total_tokens": session.total_tokens,
            "token_usage_percentage": session.token_usage_percentage,
            "compaction_count": session.compaction_count,
            "pruned_tokens_total": session.pruned_tokens_total,
            "model_limits": {
                "context_limit": session.model_limits.context_limit,
                "input_limit": session.model_limits.input_limit,
                "output_limit": session.model_limits.output_limit,
                "usable_context": session.model_limits.usable_context
            },
            "config": {
                "auto_compact": session.config.auto_compact,
                "auto_prune": session.config.auto_prune,
                "prune_protect_tokens": session.config.prune_protect_tokens,
                "protected_tools": session.config.protected_tools
            },
            "recent_activity": [
                {
                    "role": msg.role.value,
                    "timestamp": msg.timestamp,
                    "tokens": msg.tokens.total,
                    "content_preview": msg.content[:50] + "..." if len(msg.content) > 50 else msg.content
                }
                for msg in session.messages[-5:]
            ] if session.messages else []
        }
    
    def _start_background_cleanup(self):
        """Start background cleanup task for expired sessions."""
        async def cleanup_task():
            while True:
                await asyncio.sleep(self.config.cleanup_interval_seconds)
                self._cleanup_expired_sessions()
        
        # Start background task (in real implementation would use proper task management)
        # For now, just mark that cleanup would happen
        print("[Context Manager] Background cleanup enabled")
    
    def _cleanup_expired_sessions(self):
        """Clean up sessions that have expired."""
        current_time = time.time()
        expired_sessions = []
        
        for session_id, session in self.sessions.items():
            # Find oldest message timestamp
            if session.messages:
                oldest_message = min(session.messages, key=lambda m: m.timestamp)
                session_age = current_time - oldest_message.timestamp
                
                if session_age > self.config.session_timeout_seconds:
                    expired_sessions.append(session_id)
        
        # Delete expired sessions
        for session_id in expired_sessions:
            print(f"[Context Manager] Cleaning up expired session: {session_id}")
            self.delete_session(session_id)
        
        # Limit total sessions
        if len(self.sessions) > self.config.max_sessions:
            # Remove oldest sessions
            sessions_by_age = sorted(
                self.sessions.items(),
                key=lambda item: min([m.timestamp for m in item[1].messages]) if item[1].messages else current_time
            )
            
            sessions_to_remove = sessions_by_age[:len(self.sessions) - self.config.max_sessions]
            for session_id, _ in sessions_to_remove:
                print(f"[Context Manager] Removing session {session_id} due to max sessions limit")
                self.delete_session(session_id)
    
    def get_monitoring_stats(self) -> Dict[str, Any]:
        """Get overall monitoring statistics."""
        total_sessions = len(self.sessions)
        total_messages = sum(len(session.messages) for session in self.sessions.values())
        total_tokens = sum(session.total_tokens for session in self.sessions.values())
        total_compactions = sum(session.compaction_count for session in self.sessions.values())
        total_pruned_tokens = sum(session.pruned_tokens_total for session in self.sessions.values())
        
        return {
            "total_sessions": total_sessions,
            "total_messages": total_messages,
            "total_tokens": total_tokens,
            "total_compactions": total_compactions,
            "total_pruned_tokens": total_pruned_tokens,
            "avg_tokens_per_session": total_tokens / total_sessions if total_sessions > 0 else 0,
            "avg_messages_per_session": total_messages / total_sessions if total_sessions > 0 else 0,
            "session_ids": list(self.sessions.keys())
        }
