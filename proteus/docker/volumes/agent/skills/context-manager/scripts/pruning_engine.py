"""
Pruning Engine for OpenCode-style context management.

Implements selective pruning of old tool outputs to free up tokens
while preserving recent and critical conversation context.
"""

import time
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
from models import SessionState, Message, MessagePart, PartType, PruningResult

@dataclass
class PruningStats:
    """Statistics for pruning operation."""
    scanned_messages: int = 0
    scanned_parts: int = 0
    eligible_tool_parts: int = 0
    protected_tools_found: int = 0
    already_compacted: int = 0
    tokens_accumulated: int = 0
    tokens_pruned: int = 0
    parts_pruned: int = 0

class PruningEngine:
    """Engine for pruning old tool outputs."""
    
    def __init__(self):
        self.stats_cache: Dict[str, PruningStats] = {}
        
    def prune_old_tool_outputs(self, session: SessionState) -> PruningResult:
        """
        Prune old tool outputs from session.
        
        Algorithm:
        1. Scan messages from newest to oldest
        2. Skip first 2 conversation turns (recent context)
        3. Stop at first summary message or already compacted tool
        4. Accumulate tool output tokens, protect recent 40k tokens
        5. Prune tool outputs beyond protection threshold
        6. Only prune if at least 20k tokens can be saved
        
        Based on OpenCode's pruning implementation.
        """
        if not session.config.auto_prune:
            return PruningResult(
                session_id=session.id,
                pruned_parts=[],
                tokens_pruned=0,
                protected_tools_preserved=[]
            )
        
        print(f"[Pruning] Starting pruning for session {session.id}")
        
        stats = PruningStats()
        protected_tokens = 0
        parts_to_prune: List[MessagePart] = []
        protected_tools_preserved: List[str] = []
        turns_count = 0
        
        # Track if we've encountered a summary message
        encountered_summary = False
        
        # Scan messages from newest to oldest
        for message in reversed(session.messages):
            stats.scanned_messages += 1
            
            # Stop if we encounter a summary message
            if message.summary:
                encountered_summary = True
                break
            
            # Count user turns (skip first 2 turns)
            if message.role.value == "user":
                turns_count += 1
                if turns_count < 2:
                    continue  # Protect very recent conversation
            
            # Scan parts in this message
            for part in message.parts:
                stats.scanned_parts += 1
                
                if part.type == PartType.TOOL:
                    stats.eligible_tool_parts += 1
                    
                    # Extract tool information
                    tool_info = self._extract_tool_info(part)
                    tool_name = tool_info["name"]
                    
                    # Check if tool is protected
                    if tool_name in session.config.protected_tools:
                        stats.protected_tools_found += 1
                        protected_tools_preserved.append(tool_name)
                        continue
                    
                    # Check if already compacted
                    if part.compacted:
                        stats.already_compacted += 1
                        break  # Stop scanning when hitting already compacted
                    
                    # Estimate tokens (simplified - real implementation would use proper tokenizer)
                    estimated_tokens = part.tokens if part.tokens > 0 else self._estimate_tokens(part)
                    
                    # Accumulate tokens
                    protected_tokens += estimated_tokens
                    stats.tokens_accumulated = protected_tokens
                    
                    # If beyond protection threshold, mark for pruning
                    if protected_tokens > session.config.prune_protect_tokens:
                        parts_to_prune.append(part)
                        stats.tokens_pruned += estimated_tokens
        
        # Check if we have enough tokens to prune
        if stats.tokens_pruned < session.config.prune_minimum_tokens:
            print(f"[Pruning] Insufficient tokens to prune: {stats.tokens_pruned} < {session.config.prune_minimum_tokens}")
            self.stats_cache[session.id] = stats
            return PruningResult(
                session_id=session.id,
                pruned_parts=[],
                tokens_pruned=0,
                protected_tools_preserved=list(set(protected_tools_preserved))
            )
        
        # Actually prune the marked parts
        pruned_part_ids = []
        for part in parts_to_prune:
            pruned_part_ids.append(part.id)
            
            # Preserve tool metadata, clear output
            if isinstance(part.content, dict):
                original_output = part.content.get("output", "")
                part.content["output"] = "[PRUNED: Output removed to save context]"
                part.content["pruned_at"] = time.time()
                part.content["original_output_length"] = len(str(original_output))
                part.compacted = True
                
                # Reduce token estimate
                part.tokens = 100  # Keep minimal tokens for metadata
            else:
                # For non-dict content, replace with placeholder
                part.content = {"tool": "unknown", "output": "[PRUNED]"}
                part.compacted = True
                part.tokens = 50
        
        stats.parts_pruned = len(parts_to_prune)
        self.stats_cache[session.id] = stats
        
        print(f"[Pruning] Pruned {stats.parts_pruned} tool outputs, saved ~{stats.tokens_pruned} tokens")
        
        # Update session statistics
        session.total_tokens -= stats.tokens_pruned
        session.pruned_tokens_total += stats.tokens_pruned
        session.last_pruning_time = time.time()
        
        return PruningResult(
            session_id=session.id,
            pruned_parts=pruned_part_ids,
            tokens_pruned=stats.tokens_pruned,
            protected_tools_preserved=list(set(protected_tools_preserved))
        )
    
    def smart_prune(self, session: SessionState, focus_tokens: int = 30000) -> PruningResult:
        """
        Smarter pruning that considers conversation structure.
        
        Args:
            session: Session to prune
            focus_tokens: Target tokens to keep in focused context
        """
        # Group messages by topic/cluster (simplified)
        clusters = self._cluster_messages(session.messages)
        
        # Keep most recent cluster fully, prune older clusters more aggressively
        if clusters:
            recent_cluster = clusters[-1]
            older_clusters = clusters[:-1]
            
            pruned_parts = []
            total_pruned = 0
            
            for cluster in older_clusters:
                cluster_pruned, cluster_tokens = self._prune_cluster(cluster)
                pruned_parts.extend(cluster_pruned)
                total_pruned += cluster_tokens
            
            return PruningResult(
                session_id=session.id,
                pruned_parts=pruned_parts,
                tokens_pruned=total_pruned,
                protected_tools_preserved=[]
            )
        
        # Fall back to standard pruning
        return self.prune_old_tool_outputs(session)
    
    def _extract_tool_info(self, part: MessagePart) -> Dict[str, Any]:
        """Extract tool information from a message part."""
        if isinstance(part.content, dict):
            return {
                "name": part.content.get("tool_name", "unknown"),
                "status": part.content.get("status", "unknown"),
                "has_output": "output" in part.content
            }
        return {"name": "unknown", "status": "unknown", "has_output": False}
    
    def _estimate_tokens(self, part: MessagePart) -> int:
        """Estimate tokens in a message part."""
        if isinstance(part.content, dict):
            content_str = str(part.content)
        else:
            content_str = str(part.content)
        
        # Rough estimate: 1 token ≈ 4 characters for English text
        return max(1, len(content_str) // 4)
    
    def _cluster_messages(self, messages: List[Message]) -> List[List[Message]]:
        """
        Cluster messages by topic (simplified implementation).
        
        In a real implementation, this would use NLP techniques
        to identify topic boundaries.
        """
        if len(messages) < 10:
            return [messages]  # Single cluster for small conversations
        
        # Simple time-based clustering
        clusters = []
        current_cluster = []
        last_time = None
        
        for msg in messages:
            if last_time is None:
                last_time = msg.timestamp
            
            # If more than 5 minutes between messages, start new cluster
            if msg.timestamp - last_time > 300:  # 5 minutes in seconds
                if current_cluster:
                    clusters.append(current_cluster)
                current_cluster = [msg]
            else:
                current_cluster.append(msg)
            
            last_time = msg.timestamp
        
        if current_cluster:
            clusters.append(current_cluster)
        
        return clusters
    
    def _prune_cluster(self, cluster: List[Message]) -> Tuple[List[str], int]:
        """Prune a cluster of messages."""
        pruned_parts = []
        total_tokens = 0
        
        for msg in cluster:
            for part in msg.parts:
                if part.type == PartType.TOOL and not part.compacted:
                    if isinstance(part.content, dict) and "output" in part.content:
                        # Prune tool output
                        original_length = len(str(part.content["output"]))
                        part.content["output"] = "[CLUSTER_PRUNED]"
                        part.compacted = True
                        part.tokens = 100  # Minimal tokens for metadata
                        
                        pruned_parts.append(part.id)
                        total_tokens += max(0, original_length // 4 - 100)
        
        return pruned_parts, total_tokens
    
    def get_pruning_stats(self, session_id: str) -> PruningStats:
        """Get statistics for previous pruning operation."""
        return self.stats_cache.get(session_id, PruningStats())
    
    def calculate_potential_savings(self, session: SessionState) -> int:
        """
        Calculate potential token savings without actually pruning.
        
        Useful for deciding when to prune.
        """
        # Simplified estimation
        if len(session.messages) < 10:
            return 0
        
        tool_count = 0
        for msg in session.messages[-20:]:  # Look at recent messages
            for part in msg.parts:
                if part.type == PartType.TOOL:
                    tool_count += 1
        
        # Estimate ~500 tokens per tool output on average
        potential_savings = tool_count * 500
        
        # Apply protection threshold
        protected_tokens = min(potential_savings, session.config.prune_protect_tokens)
        return max(0, potential_savings - protected_tokens)
