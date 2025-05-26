import json
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, Optional, Type, List, Callable, AsyncGenerator, Tuple

from .enums import NodeStatus, WorkflowStatus
from .models import NodeResult
from .validator import WorkflowValidator
from .params import ParamsProcessor
from .executor import NodeExecutor
from ..nodes.base import BaseNode

class WorkflowEngine:
    """工作流执行引擎"""
    
    def __init__(self, max_workers: int = 4):
        self._node_types: Dict[str, Type[BaseNode]] = {}
        self._running_workflows: Dict[str, asyncio.Task] = {}
        self._workflow_status: Dict[str, WorkflowStatus] = {}
        self._workflow_progress: Dict[str, Dict[str, NodeResult]] = {}
        self._thread_pool = ThreadPoolExecutor(max_workers=max_workers)
        self._node_callbacks: List[Callable[[str, str, NodeResult], None]] = []
        self._node_executor = NodeExecutor(self._thread_pool, self)
        
    def register_node_type(self, type_name: str, node_class: Type[BaseNode]):
        """注册节点类型"""
        self._node_types[type_name] = node_class

    def validate_workflow(self, workflow: Dict) -> bool:
        """验证工作流的DAG结构"""
        return WorkflowValidator.validate_workflow(workflow, self._node_types)
        
    def get_workflow_status(self, workflow_id: str) -> Optional[WorkflowStatus]:
        """获取工作流状态"""
        return self._workflow_status.get(workflow_id)
        
    def get_workflow_progress(self, workflow_id: str) -> Optional[Dict[str, NodeResult]]:
        """获取工作流进度"""
        return self._workflow_progress.get(workflow_id)
        
    async def pause_workflow(self, workflow_id: str):
        """暂停工作流"""
        if workflow_id in self._running_workflows:
            self._workflow_status[workflow_id] = WorkflowStatus.PAUSED
            
    async def resume_workflow(self, workflow_id: str):
        """恢复工作流"""
        if workflow_id in self._workflow_status:
            if self._workflow_status[workflow_id] == WorkflowStatus.PAUSED:
                self._workflow_status[workflow_id] = WorkflowStatus.RUNNING
                
    async def cancel_workflow(self, workflow_id: str):
        """取消工作流"""
        if workflow_id in self._running_workflows:
            self._running_workflows[workflow_id].cancel()
            self._workflow_status[workflow_id] = WorkflowStatus.CANCELLED
            
    def register_node_callback(self, callback: Callable[[str, str, NodeResult], None]):
        """注册节点执行回调函数"""
        self._node_callbacks.append(callback)

    def _notify_node_completion(self, workflow_id: str, node_id: str, result: NodeResult) -> Dict[str, Any]:
        """通知节点执行完成"""
        for callback in self._node_callbacks:
            try:
                callback_result = callback(workflow_id, node_id, result)
                if callback_result:
                    return callback_result
            except Exception as e:
                print(f"回调函数执行失败: {str(e)}")
        
        return {
            "node_id": node_id,
            "success": result.success,
            "status": result.status.value,
            "data": result.data if result.success else None,
            "error": result.error if not result.success else None
        }

    async def _check_workflow_status(self, workflow_id: str) -> bool:
        """检查工作流状态"""
        while self._workflow_status[workflow_id] == WorkflowStatus.PAUSED:
            await asyncio.sleep(1)
        return self._workflow_status[workflow_id] != WorkflowStatus.CANCELLED

    async def _process_node(
        self,
        node: Dict,
        workflow_id: str,
        dependencies: Dict[str, Any],
        nodes: List[Dict],
        results: Dict[str, NodeResult]
    ):
        """处理单个节点"""
        node_id = node["id"]
        
        # 检查工作流状态
        if self._workflow_status[workflow_id] == WorkflowStatus.CANCELLED:
            return
            
        # 检查依赖
        if not self._node_executor._check_dependencies(node_id, dependencies, results):
            results[node_id] = NodeResult(
                success=False,
                status=NodeStatus.FAILED,
                error="依赖节点执行失败"
            )
            self._workflow_progress[workflow_id] = results.copy()
            return
            
        # 处理参数
        context = node.get("context", {})
        processed_params = ParamsProcessor.process_params(node["params"], results, context)
            
        # 执行节点并处理中间结果
        final_result = None
        async for result in self._node_executor.execute_node(node, processed_params, self._node_types):
            # 更新最新结果
            results[node_id] = result
            # 更新工作流进度
            self._workflow_progress[workflow_id] = results.copy()
            # 通知节点状态更新
            self._notify_node_completion(workflow_id, node_id, result)
            # 保存最终结果
            if result.status in [NodeStatus.COMPLETED, NodeStatus.FAILED]:
                final_result = result
        
        # 处理下游节点
        if final_result and final_result.success:
            downstream_nodes = self._node_executor._get_downstream_nodes(
                node_id, nodes, dependencies, results
            )
            
            # 创建下游节点的任务
            tasks = []
            for n in downstream_nodes:
                # 为下游节点添加context
                n_with_context = {**n, "context": context}
                task = asyncio.create_task(
                    self._process_node(n_with_context, workflow_id, dependencies, nodes, results)
                )
                tasks.append(task)
            
            # 等待所有下游节点完成
            if tasks:
                await asyncio.gather(*tasks)

    async def _process_node_stream(
        self,
        node: Dict,
        workflow_id: str,
        dependencies: Dict[str, Any],
        nodes: List[Dict],
        results: Dict[str, NodeResult]
    ) -> AsyncGenerator[Tuple[str, NodeResult], None]:
        """流式处理单个节点"""
        node_id = node["id"]
        
        # 检查工作流状态
        if self._workflow_status[workflow_id] == WorkflowStatus.CANCELLED:
            return
            
        # 检查依赖
        if not self._node_executor._check_dependencies(node_id, dependencies, results):
            result = NodeResult(
                success=False,
                status=NodeStatus.FAILED,
                error="依赖节点执行失败"
            )
            results[node_id] = result
            self._workflow_progress[workflow_id] = results.copy()
            yield node_id, result
            return
            
        # 处理参数
        context = node.get("context", {})
        processed_params = ParamsProcessor.process_params(node["params"], results, context)
            
        # 执行节点并处理中间结果
        running_status_sent = False
        async for result in self._node_executor.execute_node(node, processed_params, self._node_types):
            # 更新最新结果
            if result.status == NodeStatus.RUNNING:
                if not running_status_sent:
                    running_status_sent = True
                    results[node_id] = result
                    # 更新工作流进度
                    self._workflow_progress[workflow_id] = results.copy()
                    # 通知节点状态更新并返回结果
                    self._notify_node_completion(workflow_id, node_id, result)
                    yield node_id, result
                # 如果已经发送过 RUNNING 状态，只更新数据
                elif result.data:
                    results[node_id].data = result.data
            else:
                # 对于非 RUNNING 状态（COMPLETED/FAILED），正常处理
                results[node_id] = result
                # 更新工作流进度
                self._workflow_progress[workflow_id] = results.copy()
                # 通知节点状态更新并返回结果
                self._notify_node_completion(workflow_id, node_id, result)
                yield node_id, result
                
            # 如果节点执行完成且成功，处理下游节点
            if result.status == NodeStatus.COMPLETED and result.success:
                downstream_nodes = self._node_executor._get_downstream_nodes(
                    node_id, nodes, dependencies, results
                )
                
                # 直接处理下游节点
                for n in downstream_nodes:
                    # 为下游节点添加context
                    n_with_context = {**n, "context": context}
                    async for node_result in self._process_node_stream(
                        n_with_context, workflow_id, dependencies, nodes, results
                    ):
                        yield node_result

    async def execute_workflow_stream(
        self,
        workflow_json: str,
        workflow_id: str,
        global_params: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[Tuple[str, NodeResult], None]:
        """流式执行工作流"""
        workflow = json.loads(workflow_json)
        
        # 验证工作流
        self.validate_workflow(workflow)
        
        nodes = workflow["nodes"]
        edges = workflow.get("edges", [])  # edges字段可选，默认为空列表
        
        # 构建节点依赖图
        dependencies: Dict[str, Any] = {node["id"]: set() for node in nodes}
        for edge in edges:
            dependencies[edge["to"]].add(edge["from"])
            
        # 初始化工作流状态
        self._workflow_status[workflow_id] = WorkflowStatus.RUNNING
        self._workflow_progress[workflow_id] = {}
        results: Dict[str, NodeResult] = {}
        
        try:
            # 获取入口节点（没有入度的节点）
            entry_nodes = [
                node for node in nodes
                if not dependencies[node["id"]]
            ]
            
            # 处理入口节点
            for node in entry_nodes:
                # 将context添加到节点中
                node_with_context = {**node, "context": context} if context else node
                # 创建异步生成器任务
                async for node_result in self._process_node_stream(
                    node_with_context,
                    workflow_id,
                    dependencies,
                    nodes,
                    results
                ):
                    yield node_result
                    
            # 检查是否所有节点都执行成功
            all_success = all(
                node["id"] in results and results[node["id"]].success
                for node in nodes
            )
            
            # 更新工作流最终状态
            self._workflow_status[workflow_id] = (
                WorkflowStatus.COMPLETED if all_success
                else WorkflowStatus.FAILED
            )
            
        except asyncio.CancelledError:
            self._workflow_status[workflow_id] = WorkflowStatus.CANCELLED
            raise
        except Exception as e:
            self._workflow_status[workflow_id] = WorkflowStatus.FAILED
            raise
        finally:
            if workflow_id in self._running_workflows:
                del self._running_workflows[workflow_id]

    async def execute_workflow(
        self,
        workflow_json: str,
        workflow_id: str,
        global_params: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, NodeResult]:
        """执行工作流"""
        workflow = json.loads(workflow_json)
        
        # 验证工作流
        self.validate_workflow(workflow)
        
        nodes = workflow["nodes"]
        edges = workflow.get("edges", [])  # edges字段可选，默认为空列表
        
        # 构建节点依赖图
        dependencies: Dict[str, Any] = {node["id"]: set() for node in nodes}
        for edge in edges:
            dependencies[edge["to"]].add(edge["from"])
            
        # 初始化工作流状态
        self._workflow_status[workflow_id] = WorkflowStatus.RUNNING
        self._workflow_progress[workflow_id] = {}
        results: Dict[str, NodeResult] = {}
        
        try:
            # 获取入口节点（没有入度的节点）
            entry_nodes = [
                node for node in nodes
                if not dependencies[node["id"]]
            ]
            
            # 创建入口节点的任务
            tasks = []
            for node in entry_nodes:
                # 将context添加到节点中
                node_with_context = {**node, "context": context} if context else node
                task = asyncio.create_task(
                    self._process_node(
                        node_with_context,
                        workflow_id,
                        dependencies,
                        nodes,
                        results
                    )
                )
                tasks.append(task)
                
            # 等待所有任务完成
            await asyncio.gather(*tasks)
            
            # 检查是否所有节点都执行成功
            all_success = all(
                node["id"] in results and results[node["id"]].success
                for node in nodes
            )
            
            # 更新工作流最终状态
            self._workflow_status[workflow_id] = (
                WorkflowStatus.COMPLETED if all_success
                else WorkflowStatus.FAILED
            )
            
            return results
            
        except asyncio.CancelledError:
            self._workflow_status[workflow_id] = WorkflowStatus.CANCELLED
            raise
        except Exception as e:
            self._workflow_status[workflow_id] = WorkflowStatus.FAILED
            raise
        finally:
            if workflow_id in self._running_workflows:
                del self._running_workflows[workflow_id]
