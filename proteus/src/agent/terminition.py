from abc import ABC, abstractmethod
import re
import time
from typing import List
import logging

logger = logging.getLogger(__name__)

class TerminationCondition(ABC):
    """终止条件抽象基类
    
    所有具体的终止条件类都应该继承这个基类并实现should_terminate方法。
    should_terminate方法接收agent实例和运行时上下文信息，返回是否应该终止执行。
    
    Attributes:
        description (str): 终止条件的描述信息
    """
    def __init__(self, description: str = None):
        self.description = description or self.__doc__.strip()
        
    @abstractmethod
    def should_terminate(self, agent: 'Agent', **kwargs) -> bool:  # 使用字符串类型注解避免循环引用
        """判断是否应该终止agent执行
        
        Args:
            agent: Agent实例
            **kwargs: 运行时上下文信息，可能包含:
                - current_step: 当前执行步数
                - current_action: 当前执行的工具名称
                - current_thought: 当前的思考内容
                - current_observation: 当前的观察结果
                - final_answer: 最终答案
                - error_occurred: 是否发生错误
                
        Returns:
            bool: 是否应该终止执行
        """
        pass

class ToolTerminationCondition(TerminationCondition):
    """在指定工具被调用后终止执行"""
    def __init__(self, tool_names: List[str], description: str = None):
        """
        Args:
            tool_names: 触发终止的工具名称列表
            description: 终止条件描述
        """
        super().__init__(description)
        self.tool_names = tool_names

    def should_terminate(self, agent: 'Agent', **kwargs) -> bool:
        current_action = kwargs.get('current_action')
        if current_action in self.tool_names:
            logger.info(f"Tool termination condition met: {current_action}")
            return True
        return False

class TextMatchTerminationCondition(TerminationCondition):
    """在指定文本模式匹配成功后终止执行"""
    def __init__(self, pattern: str, mode: str = 'final_answer', description: str = None):
        """
        Args:
            pattern: 要匹配的正则表达式模式
            mode: 匹配模式，可选值:
                - final_answer: 匹配最终答案
                - thinking: 匹配思考内容
                - observation: 匹配观察结果
            description: 终止条件描述
        """
        super().__init__(description)
        self.pattern = pattern
        self.mode = mode
        self._compiled_pattern = re.compile(pattern)

    def should_terminate(self, agent: 'Agent', **kwargs) -> bool:
        target_text = ""
        if self.mode == 'final_answer':
            target_text = kwargs.get('final_answer', '')
        elif self.mode == 'thinking':
            target_text = kwargs.get('current_thought', '')
        elif self.mode == 'observation':
            target_text = kwargs.get('current_observation', '')
            
        if self._compiled_pattern.search(target_text):
            logger.info(f"Text match termination condition met: {self.pattern} in {self.mode}")
            return True
        return False

class StepLimitTerminationCondition(TerminationCondition):
    """在达到最大执行步数后终止执行"""
    def __init__(self, max_steps: int, description: str = None):
        """
        Args:
            max_steps: 最大执行步数
            description: 终止条件描述
        """
        super().__init__(description)
        self.max_steps = max_steps

    def should_terminate(self, agent: 'Agent', **kwargs) -> bool:
        current_step = kwargs.get('current_step', 0)
        if current_step >= self.max_steps:
            logger.info(f"Step limit termination condition met: {current_step} >= {self.max_steps}")
            return True
        return False

class TimeoutTerminationCondition(TerminationCondition):
    """在执行超时后终止执行"""
    def __init__(self, timeout_seconds: float, description: str = None):
        """
        Args:
            timeout_seconds: 超时时间(秒)
            description: 终止条件描述
        """
        super().__init__(description)
        self.timeout_seconds = timeout_seconds
        self.start_time = time.time()

    def should_terminate(self, agent: 'Agent', **kwargs) -> bool:
        elapsed_time = time.time() - self.start_time
        if elapsed_time > self.timeout_seconds:
            logger.info(f"Timeout termination condition met: {elapsed_time:.2f}s > {self.timeout_seconds}s")
            return True
        return False

class ErrorTerminationCondition(TerminationCondition):
    """在错误次数达到上限后终止执行"""
    def __init__(self, max_errors: int = 3, description: str = None):
        """
        Args:
            max_errors: 最大允许错误次数
            description: 终止条件描述
        """
        super().__init__(description)
        self.max_errors = max_errors
        self.error_count = 0

    def should_terminate(self, agent: 'Agent', **kwargs) -> bool:
        if kwargs.get('error_occurred', False):
            self.error_count += 1
            logger.warning(f"Error count increased to {self.error_count}")
            
        if self.error_count >= self.max_errors:
            logger.info(f"Error count termination condition met: {self.error_count} >= {self.max_errors}")
            return True
        return False

class CompositeTerminationCondition(TerminationCondition):
    """组合多个终止条件"""
    def __init__(self, conditions: List[TerminationCondition], mode: str = 'any', description: str = None):
        """
        Args:
            conditions: 终止条件列表
            mode: 组合模式:
                - any: 满足任一条件即终止
                - all: 需满足所有条件才终止
            description: 终止条件描述
        """
        super().__init__(description)
        self.conditions = conditions
        self.mode = mode
        
        # 验证条件列表
        if not conditions:
            raise ValueError("Conditions list cannot be empty")
        if not all(isinstance(c, TerminationCondition) for c in conditions):
            raise TypeError("All conditions must be instances of TerminationCondition")

    def should_terminate(self, agent: 'Agent', **kwargs) -> bool:
        results = [c.should_terminate(agent, **kwargs) for c in self.conditions]
        
        if self.mode == 'any':
            should_stop = any(results)
            if should_stop:
                triggered = [c.description for c, r in zip(self.conditions, results) if r]
                logger.info(f"Composite termination condition met (any): {triggered}")
            return should_stop
        else:
            should_stop = all(results)
            if should_stop:
                logger.info("Composite termination condition met (all)")
            return should_stop
