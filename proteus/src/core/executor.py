import time
import asyncio
import concurrent.futures
from typing import Dict, Any, AsyncGenerator, Type, Set, List
from concurrent.futures import ThreadPoolExecutor

from .models import NodeResult
from .enums import NodeStatus, WorkflowStatus
from .params import ParamsProcessor
from ..nodes.base import BaseNode

class NodeExecutor:
    """节点执行器"""
    
    def __init__(self, thread_pool: ThreadPoolExecutor, engine=None):
        self._thread_pool = thread_pool
        self._engine = engine
        
    async def execute_node(
        self,
        node: Dict,
        processed_params: Dict[str, Any],
        node_types: Dict[str, Type[BaseNode]]
    ) -> AsyncGenerator[NodeResult, None]:
        """执行单个节点，支持流式返回结果"""
        start_time = time.time()
        
        # 创建初始结果并通知状态为运行中
        initial_result = NodeResult(
            success=True,
            status=NodeStatus.RUNNING,
            start_time=start_time
        )
        yield initial_result

        try:
            node_class = node_types[node["type"]]
            node_instance = node_class()
            # 如果是LoopNode，注入engine
            if node["type"] == "loop_node":
                node_instance.init_engine(self._engine)
            
            # 使用线程池执行节点
            loop = asyncio.get_event_loop()
            if asyncio.iscoroutinefunction(node_instance.execute):
                # 如果是异步生成器方法，直接获取结果流
                if hasattr(node_instance.execute, '__aiter__'):
                    async for intermediate_result in node_instance.execute(processed_params):
                        # 创建中间结果
                        running_result = NodeResult(
                            success=True,
                            status=NodeStatus.RUNNING,
                            data=intermediate_result,
                            start_time=start_time
                        )
                        yield running_result
                        result = intermediate_result
                else:
                    # 如果是普通异步方法，在线程池中等待其完成
                    result = await node_instance.execute(processed_params)
            else:
                # 如果是同步方法，检查是否是生成器
                if hasattr(node_instance.execute, '__iter__'):
                    # 同步生成器方法
                    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                    try:
                        for intermediate_result in await loop.run_in_executor(
                            executor,
                            lambda: list(node_instance.execute(processed_params))
                        ):
                            # 创建中间结果
                            running_result = NodeResult(
                                success=True,
                                status=NodeStatus.RUNNING,
                                data=intermediate_result,
                                start_time=start_time
                            )
                            yield running_result
                            result = intermediate_result
                    finally:
                        executor.shutdown(wait=False)
                else:
                    # 普通同步方法
                    result = await loop.run_in_executor(
                        self._thread_pool,
                        node_instance.execute,
                        processed_params
                    )
            
            end_time = time.time()
            final_result = NodeResult(
                success=True,
                status=NodeStatus.COMPLETED,
                data=result if 'result' in locals() else None,
                start_time=start_time,
                end_time=end_time
            )
            yield final_result

        except Exception as e:
            end_time = time.time()
            error_result = NodeResult(
                success=False,
                status=NodeStatus.FAILED,
                error=str(e),
                start_time=start_time,
                end_time=end_time
            )
            yield error_result

    def _check_dependencies(
        self,
        node_id: str,
        dependencies: Dict[str, Set[str]],
        results: Dict[str, NodeResult]
    ) -> bool:
        """检查节点依赖是否满足"""
        for dep_id in dependencies[node_id]:
            if dep_id not in results or not results[dep_id].success:
                return False
        return True

    def _get_downstream_nodes(
        self,
        node_id: str,
        nodes: List[Dict],
        dependencies: Dict[str, Set[str]],
        results: Dict[str, NodeResult]
    ) -> List[Dict]:
        """获取可执行的下游节点"""
        return [
            n for n in nodes
            if node_id in dependencies[n["id"]]
            and all(
                dep in results and results[dep].success
                for dep in dependencies[n["id"]]
            )
        ]
