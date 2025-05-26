from typing import List, Dict, Any, Union
from .base import BaseNode
from ..core.models import NodeResult
import json
import asyncio
import logging

logger = logging.getLogger(__name__)


class LoopNode(BaseNode):
    def __init__(self):
        super().__init__()
        self._engine = None
        logger.info("LoopNode initialized")

    def init_engine(self, engine: any):
        """初始化执行引擎,但不注册loop节点"""
        self._engine = engine

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        array = params.get("array", [])
        workflow_json = params.get("workflow_json")

        # 支持字符串、数字、对象或数组类型
        if not isinstance(array, list):
            if isinstance(array, (str, int, float, dict)):
                array = [array]
                logger.debug(f"Converting non-list input to array: {array}")
            else:
                error_msg = "参数 'array' 必须是字符串、数字、对象或数组类型"
                logger.error(error_msg)
                raise ValueError(error_msg)

        if not isinstance(workflow_json, dict):
            raise ValueError("参数 'workflow_json' 必须是字典类型")

        # 获取并行度参数,默认为1(串行执行)
        parallel_degree = params.get("parallel_degree", 3)
        if not isinstance(parallel_degree, int) or parallel_degree < 1:
            raise ValueError("parallel_degree必须是大于0的整数")

        results = []
        # 按并行度分组执行
        for i in range(0, len(array), parallel_degree):
            batch = array[i : i + parallel_degree]
            tasks = []

            for index, item in enumerate(batch, start=i):
                # 创建循环项上下文，支持更丰富的引用方式
                loop_context = {
                    "index": index,  # 当前索引，可通过 $index 引用
                    "item": item,  # 当前项，可通过 $item 引用（如果是对象可以用 $item.field_name）
                    "length": len(array),  # 总长度，可通过 $length 引用
                    "first": index == 0,  # 是否第一项，可通过 $first 引用
                    "last": index == len(array) - 1,  # 是否最后一项，可通过 $last 引用
                }

                # 创建一个新的工作流ID
                workflow_id = f"loop_workflow_{id(item)}"

                # 合并全局上下文和循环项上下文
                workflow_context = {**loop_context}

                # 创建异步任务
                task = self._execute_workflow(
                    workflow_json=workflow_json,
                    workflow_id=workflow_id,
                    context=workflow_context,
                )
                tasks.append(task)

            # 并行执行当前批次的任务
            logger.info(
                f"Executing batch {i//parallel_degree + 1} with {len(batch)} items"
            )
            batch_results = await asyncio.gather(*tasks)
            # 处理批次结果
            for result in batch_results:
                item_result = dict()
                for key, value in result.items():
                    if isinstance(value, NodeResult):
                        item_result[key] = value.to_data()
                results.append(item_result)
        execution_summary = {
            "results": results,  # 包含所有JSON格式的结果
            "total": len(array),  # 保持数字类型
            "success": True,  # 使用布尔类型
        }
        logger.info(f"Loop execution completed. Total items processed: {len(array)}")
        return execution_summary

    async def agent_execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行节点并将结果转换为统一格式

        将循环执行结果转换为包含循环统计信息和每个迭代结果的文本。

        Args:
            params: 节点参数

        Returns:
            Dict[str, Any]: 执行结果，包含纯文本格式的'result'键
        """
        try:
            execute_result = await self.execute(params)

            # 组织循环执行结果信息
            result_text = (
                f"Loop execution completed:\n"
                f"- Total items: {execute_result['total']}\n"
                f"- Parallel degree: {params.get('parallel_degree', 3)}\n\n"
                f"Results by iteration:\n"
            )

            # 添加每个迭代的结果
            for i, item_result in enumerate(execute_result["results"]):
                result_text += f"\nIteration {i + 1}:\n"
                for key, value in item_result.items():
                    if isinstance(value, dict):
                        # 如果是字典，格式化显示
                        result_text += f"  {key}:\n"
                        for sub_key, sub_value in value.items():
                            result_text += f"    {sub_key}: {sub_value}\n"
                    else:
                        result_text += f"  {key}: {value}\n"

            return {"result": result_text}
        except Exception as e:
            return {"result": f"Error: {str(e)}", "error": str(e)}

    async def _execute_workflow(
        self, workflow_json: Dict[str, Any], workflow_id: str, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        # 延迟导入 WorkflowEngine 以避免循环导入
        from ..core.engine import WorkflowEngine

        """
        执行工作流
        
        Args:
            workflow_json: 工作流定义
            workflow_id: 工作流ID
            context: 循环上下文变量
        """
        if not self._engine:
            error_msg = "LoopNode未初始化执行引擎"
            logger.error(error_msg)
            raise ValueError(error_msg)

        # 创建一个新的执行引擎实例,复制原引擎的节点类型(除了loop节点)
        sub_engine = WorkflowEngine()
        for type_name, node_class in self._engine._node_types.items():
            if not isinstance(self, node_class):  # 不注册loop节点类型
                sub_engine.register_node_type(type_name, node_class)

        # 传递循环上下文，但不预处理workflow_json中的参数
        workflow_results = await sub_engine.execute_workflow(
            workflow_json=json.dumps(workflow_json),
            workflow_id=workflow_id,
            context=context,
        )
        return workflow_results
