"""异步任务管理器"""
import asyncio
from typing import Dict, Optional, Any
import uuid
from enum import Enum

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class TaskManager:
    def __init__(self):
        self.tasks: Dict[str, dict] = {}
        self.queue = asyncio.Queue()
        self.current_task: Optional[str] = None
        self.lock = asyncio.Lock()
        self.task_futures: Dict[str, asyncio.Future] = {}
        self._consumer_task: Optional[asyncio.Task] = None

    async def start(self):
        """启动任务消费者"""
        self._consumer_task = asyncio.create_task(self._consume_tasks())

    async def _consume_tasks(self):
        """消费任务队列"""
        while True:
            task_id = await self.queue.get()
            async with self.lock:
                self.current_task = task_id
                self.tasks[task_id]["status"] = TaskStatus.RUNNING.value
            
            try:
                task_func = self.tasks[task_id]["func"]
                result = await task_func()
                async with self.lock:
                    self.tasks[task_id]["result"] = result
                    self.tasks[task_id]["status"] = TaskStatus.COMPLETED.value
            except Exception as e:
                async with self.lock:
                    self.tasks[task_id]["error"] = str(e)
                    self.tasks[task_id]["status"] = TaskStatus.FAILED.value
            finally:
                async with self.lock:
                    self.current_task = None
                self.queue.task_done()

    async def submit_task(self, task_func) -> str:
        """提交新任务到队列
        
        Args:
            task_func: 异步任务函数
            
        Returns:
            任务ID
        """
        task_id = str(uuid.uuid4())
        async with self.lock:
            self.tasks[task_id] = {
                "id": task_id,
                "func": task_func,
                "status": TaskStatus.PENDING.value,
                "result": None,
                "error": None
            }
            # 创建并保存future对象
            future = asyncio.Future()
            self.task_futures[task_id] = future
            # 包装任务函数以支持取消
            async def wrapped_task():
                try:
                    result = await task_func()
                    future.set_result(result)
                    return result
                except asyncio.CancelledError:
                    future.cancel()
                    raise
                except Exception as e:
                    future.set_exception(e)
                    raise
            
            self.tasks[task_id]["func"] = wrapped_task
            
        await self.queue.put(task_id)
        return task_id

    async def get_task_status(self, task_id: str) -> Optional[dict]:
        """获取任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务状态字典或None(如果任务不存在)
        """
        async with self.lock:
            return self.tasks.get(task_id)

    async def _execute_task(self, task_id: str, coro) -> None:
        """执行任务并更新状态"""
        try:
            self.current_task = task_id
            self.tasks[task_id]["status"] = TaskStatus.RUNNING.value
            result = await coro
            self.tasks[task_id]["status"] = TaskStatus.COMPLETED.value
            self.tasks[task_id]["result"] = result
        except asyncio.CancelledError:
            self.tasks[task_id]["status"] = TaskStatus.CANCELLED.value
            self.tasks[task_id]["error"] = "Task cancelled"
        except Exception as e:
            self.tasks[task_id]["status"] = TaskStatus.FAILED.value
            self.tasks[task_id]["error"] = str(e)
        finally:
            self.current_task = None
            self.task_futures.pop(task_id, None)

    async def cancel_task(self, task_id: str) -> bool:
        """取消指定任务
        
        Args:
            task_id: 要取消的任务ID
            
        Returns:
            bool: 是否成功取消
        """
        async with self.lock:
            if task_id not in self.tasks:
                return False
                
            # 如果任务在队列中但未开始执行
            if task_id not in self.task_futures:
                self.tasks[task_id]["status"] = TaskStatus.CANCELLED.value
                self.tasks[task_id]["error"] = "Task cancelled before execution"
                return True
                
            future = self.task_futures[task_id]
            if not future.done():
                future.cancel()
                self.tasks[task_id]["status"] = TaskStatus.CANCELLED.value
                self.tasks[task_id]["error"] = "Task cancelled during execution"
                return True
                
            return False

# 全局任务管理器实例
task_manager = TaskManager()