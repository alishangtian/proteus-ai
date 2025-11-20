import re
import json
import logging
from typing import Dict, Any, Optional

from src.utils.langfuse_wrapper import langfuse_wrapper
from proteus.src.api.llm_api import call_llm_api

logger = logging.getLogger(__name__)


class LLMResponseParser:
    """
    负责解析LLM响应，提取结构化信息，并处理工具参数。
    """

    def __init__(self, model_name: str, reasoner_model_name: Optional[str] = None):
        self.model_name = model_name
        self.reasoner_model_name = reasoner_model_name

    @langfuse_wrapper.observe_decorator(
        name="_parse_action", capture_input=True, capture_output=True
    )
    async def parse_action(self, response_text: str) -> Dict[str, Any]:
        """从输入文本中提取结构化 JSON 数据

        功能：
        - 从输入文本中提取结构化的 JSON 数据
        - 支持两种输入格式：
          1. Thought + Action + Action Input 格式
          2. Thought + Answer 格式

        Args:
            response_text: 输入的响应文本

        Returns:
            Dict[str, Any]: 结构化的 JSON 数据，格式为：
            {
                "thinking": "思考过程",
                "tool": {
                    "name": "工具名称",
                    "params": "参数"
                }
            }
        """
        try:
            # 1. 尝试直接解析为JSON（如果输入已经是JSON格式）
            try:
                parsed_json = json.loads(response_text.strip())
                if (
                    isinstance(parsed_json, dict)
                    and "thinking" in parsed_json
                    and "tool" in parsed_json
                ):
                    # 如果 params 字段是字符串，尝试再次解析为JSON对象
                    if isinstance(parsed_json["tool"].get("params"), str):
                        try:
                            parsed_json["tool"]["params"] = json.loads(
                                parsed_json["tool"]["params"]
                            )
                        except json.JSONDecodeError:
                            pass  # 如果不是有效的JSON字符串，则保持原样
                    logger.debug("直接JSON解析成功")
                    return parsed_json
            except json.JSONDecodeError:
                pass

            # 2. 优先使用正则表达式解析
            regex_result = await self._parse_with_regex(response_text)

            # 如果正则表达式解析成功，直接返回结果
            if regex_result and regex_result.get("tool", {}).get("name"):
                logger.debug("正则表达式解析成功")
                return regex_result

            # 3. 当正则表达式解析失败时，使用LLM进行结构化提取
            logger.info("正则表达式解析失败，尝试使用LLM进行解析")
            llm_extracted_result = await self.extract_from_response(response_text)
            if llm_extracted_result:
                return llm_extracted_result

            # 如果所有解析方法都失败，返回一个默认的错误处理结果
            logger.warning(
                f"所有解析方法均失败，无法从响应中提取有效action: {response_text}"
            )
            return {
                "thinking": "无法解析LLM响应，请检查输出格式。",
                "tool": {
                    "name": "final_answer",
                    "params": "无法解析LLM响应，请检查输出格式。",
                },
            }

        except Exception as e:
            logger.error(f"解析action失败: {e}", exc_info=True)
            # 返回默认的错误处理结果
            return {
                "thinking": f"解析错误: {str(e)}",
                "tool": {
                    "name": "final_answer",
                    "params": "解析失败，无法提供有效答案",
                },
            }

    @langfuse_wrapper.observe_decorator(
        name="extract_from_response", capture_input=True, capture_output=True
    )
    async def extract_from_response(self, response_text: str) -> Dict[str, Any]:
        try:
            # 构建优化的提示词
            extraction_prompt = self._build_extraction_prompt(response_text)

            # 调用LLM进行提取
            model_to_use = self.reasoner_model_name or self.model_name
            if not model_to_use:
                logger.error("没有可用的模型进行LLM提取")
                return {}

            model_response = await call_llm_api(
                [{"role": "user", "content": extraction_prompt}],
                model_name=model_to_use,
            )

            # 处理返回值（可能是tuple或直接是字符串）
            if isinstance(model_response, tuple) and len(model_response) == 2:
                extracted_text = model_response[0]
            else:
                extracted_text = model_response

            # 解析提取的JSON
            try:
                result = json.loads(extracted_text.strip())
                if isinstance(result, dict) and result:
                    # 如果 params 字段是字符串，尝试再次解析为JSON对象
                    if isinstance(result.get("tool", {}).get("params"), str):
                        try:
                            result["tool"]["params"] = json.loads(
                                result["tool"]["params"]
                            )
                        except json.JSONDecodeError:
                            pass  # 如果不是有效的JSON字符串，则保持原样
                    logger.info("LLM解析成功")
                    return result
            except json.JSONDecodeError:
                logger.warning(f"LLM提取的内容不是有效JSON: {extracted_text}")
            return {}
        except Exception as e:
            logger.warning(f"使用LLM提取结构化数据失败: {e}", exc_info=True)
            return {}

    def _build_extraction_prompt(self, response_text: str) -> str:
        """构建优化的LLM提取提示词

        Args:
            response_text: 原始响应文本

        Returns:
            str: 优化后的提示词
        """
        return f"""你是一个专业的文本解析器，专门从AI助手的响应中提取结构化信息。

请从以下文本中提取思考过程和工具调用信息，并严格按照JSON格式输出。

## 输出格式要求：

### 格式一：工具调用模式
如果文本包含 "Action:" 和 "Action Input:"，请输出：
{{
    "thinking": "Thought后面的思考内容",
    "tool": {{
        "name": "Action后面的工具名称",
        "params": Action Input后面的参数（如果参数是JSON格式，请解析为JSON对象；否则保持字符串）
    }}
}}

### 格式二：最终答案模式
如果文本包含 "Answer:"，请输出：
{{
    "thinking": "Thought后面的思考内容",
    "tool": {{
        "name": "final_answer",
        "params": "Answer后面的完整答案内容"
    }}
}}

### 格式三：无法解析
如果文本中没有明确的结构化信息，请输出：
{{}}

## 解析规则：
1. 提取 "Thought:" 后面的内容作为 thinking
2. 如果有 "Action:" 和 "Action Input:"，提取对应内容
3. 如果有 "Answer:"，将工具名设为 "final_answer"，参数为答案内容
4. Action Input 如果是JSON格式，请解析为JSON对象；否则保持字符串格式
5. 只输出JSON，不要包含任何解释文字

## 待解析文本：
{response_text}

请输出解析结果："""

    @langfuse_wrapper.observe_decorator(
        name="_parse_with_regex", capture_input=True, capture_output=True
    )
    def _is_json(self, text: str) -> bool:
        """判断字符串是否是有效的JSON"""
        try:
            json.loads(text)
            return True
        except (json.JSONDecodeError, TypeError):
            return False

    async def _format_python_execute_params(self, code_content: str) -> Dict[str, Any]:
        """
        将 Python 代码块格式化为 python_execute 工具所需的参数结构。
        """
        # 检测并去除 Markdown 代码块标识
        markdown_code_block_pattern = r"```(?:python\n)?(.*?)```"
        markdown_match = re.search(markdown_code_block_pattern, code_content, re.DOTALL)

        if markdown_match:
            cleaned_code_content = markdown_match.group(1).strip()
        else:
            cleaned_code_content = await self._parse_params_with_llm(code_content)
            return cleaned_code_content

        return {
            "code": cleaned_code_content,
            "language": "python",
            "enable_network": True,
        }

    async def _parse_with_regex(self, response_text: str) -> Dict[str, Any]:
        """使用正则表达式解析响应文本

        Args:
            response_text: 输入的响应文本

        Returns:
            Dict[str, Any]: 解析后的结构化数据
        """
        try:
            # 尝试从Markdown代码块中提取内容
            markdown_code_block_pattern = r"```(?:[a-zA-Z0-9]+\n)?(.*?)```"
            markdown_match = re.search(
                markdown_code_block_pattern, response_text, re.DOTALL
            )

            # 检查原始响应文本是否完全被代码块包裹
            full_markdown_match = re.fullmatch(
                markdown_code_block_pattern, response_text, re.DOTALL
            )

            if full_markdown_match:
                # 如果整个响应文本都是一个代码块，则直接使用其内容进行解析
                text = full_markdown_match.group(1).strip()
                logger.debug("从完整的Markdown代码块中提取内容进行解析")
            else:
                # 否则，使用原始文本
                text = response_text.strip()

            # 初始化变量
            thinking = ""
            tool_name = ""
            tool_params = ""

            # 优化的正则表达式模式，支持多行内容提取
            # 使用非贪婪匹配和更精确的边界检测
            thought_pattern = r"Thought:\s*(.*?)(?=\n(?:Action|Answer):|$)"
            action_pattern = r"Action:\s*(.*?)(?=\nAction Input:|$)"
            action_input_pattern = (
                r"Action Input:\s*(.*?)(?=\n(?:Thought|Action|Answer):|$)"
            )
            answer_pattern = r"Answer:\s*(.*?)(?=\n(?:Thought|Action):|$)"

            # 提取 Thought - 支持多行内容
            thought_match = re.search(thought_pattern, text, re.DOTALL | re.IGNORECASE)
            if thought_match:
                thinking = thought_match.group(1).strip()
            else:
                # 如果没有匹配到 Thought，则直接返回 final_answer
                logger.warning(f"未匹配到 Thought，直接返回 final_answer: {text}")
                return {
                    "thinking": "未检测到明确的思考过程，直接返回最终答案。",
                    "tool": {"name": "final_answer", "params": text},
                }

            # 检查是否包含 Answer（最终答案模式）- 提取所有后续内容
            answer_match = re.search(answer_pattern, text, re.DOTALL | re.IGNORECASE)
            if answer_match:
                tool_name = "final_answer"
                # 提取Answer后的所有内容，包括换行
                tool_params = answer_match.group(1).strip()
            else:
                # 新增：支持方括号格式的Action模式
                # 格式1：Action: tool_name[param1=value1, param2=value2, ...]
                # 格式2：Action: tool_name[{"key": "value", ...}]
                # 使用 DOTALL 标志使 . 能匹配换行符,支持多行JSON
                action_bracket_pattern = r"Action:\s*([^[\s]+)\[(.*?)\]"

                # 首先尝试方括号格式的Action (使用DOTALL支持多行JSON)
                bracket_action_match = re.search(
                    action_bracket_pattern, text, re.DOTALL | re.IGNORECASE
                )
                if bracket_action_match:
                    tool_name = bracket_action_match.group(1).strip()
                    params_str = bracket_action_match.group(2).strip()

                    # 解析方括号中的参数(支持JSON格式和键值对格式)
                    tool_params = self._parse_bracket_params(params_str)
                else:
                    # 提取标准格式的 Action 和 Action Input
                    action_match = re.search(
                        action_pattern, text, re.DOTALL | re.IGNORECASE
                    )
                    if action_match:
                        tool_name = action_match.group(1).strip()

                    action_input_match = re.search(
                        action_input_pattern, text, re.DOTALL | re.IGNORECASE
                    )
                    if action_input_match:
                        # 提取Action Input后的所有内容，包括换行
                        action_input_text = action_input_match.group(1).strip()
                        logger.info(f"尝试处理转义字符 {action_input_text}")

                        # 尝试解析 Action Input 为 JSON，处理转义字符
                        try:
                            # 尝试解析为JSON，如果失败，可能是包含转义字符的字符串
                            tool_params = json.loads(action_input_text)
                        except json.JSONDecodeError as e:
                            logger.error(f"解析失败 异常 {e}")
                            tool_params = action_input_text
                            # 在返回之前，如果工具是 python_execute，则格式化 params
                            if tool_name == "python_execute":
                                tool_params = await self._format_python_execute_params(
                                    tool_params
                                )
                        except Exception as e:
                            # 其他异常，直接使用原始字符串
                            logger.error(f"其他异常，异常 {e}")
                            tool_params = action_input_text
                            # 在返回之前，如果工具是 python_execute，则格式化 params
                            if tool_name == "python_execute":
                                tool_params = await self._format_python_execute_params(
                                    tool_params
                                )
                    else:
                        tool_params = ""

            # 如果没有找到有效的工具名称，尝试更宽松的匹配
            if not tool_name:
                # 尝试更宽松的模式匹配，处理可能的格式变化
                loose_answer_pattern = r"(?:Answer|答案|回答)[:：]\s*(.*)"
                loose_answer_match = re.search(
                    loose_answer_pattern, text, re.DOTALL | re.IGNORECASE
                )
                if loose_answer_match:
                    tool_name = "final_answer"
                    tool_params = loose_answer_match.group(1).strip()
                else:
                    logger.warning(f"无法从文本中提取有效的工具调用: {text}")
                    # 如果仍然没有找到工具名称，并且之前也没有匹配到 Thought，则返回一个默认的 final_answer
                    return {
                        "thinking": "无法从文本中提取有效的工具调用，直接返回最终答案。",
                        "tool": {"name": "final_answer", "params": text},
                    }

            # 如果 tool_params是字符串，尝试使用_parse_params_with_llm解析参数为 json
            if isinstance(tool_params, str) and tool_name == "python_execute":
                parsed_params = await self._parse_params_with_llm(tool_params)
                return parsed_params

            return {
                "thinking": thinking,
                "tool": {"name": tool_name, "params": tool_params},
            }

        except Exception as e:
            logger.error(f"正则表达式解析失败: {e}", exc_info=True)
            return {
                "thinking": f"解析错误: {str(e)}",
                "tool": {
                    "name": "final_answer",
                    "params": "解析失败，无法提供有效答案",
                },
            }

    def _parse_bracket_params(self, params_str: str) -> Dict[str, Any]:
        """解析方括号中的参数字符串

        Args:
            params_str: 参数字符串，支持以下格式：
                1. JSON格式: {"key": "value", "num": 123}
                2. 键值对格式: query=通义 DeepResearch, language=zh, max_results=5

        Returns:
            Dict[str, Any]: 解析后的参数字典
        """
        try:
            if not params_str.strip():
                return {}

            # 优先尝试解析为JSON格式
            # 检查是否以 { 开头，这是JSON对象的标志
            params_str_stripped = params_str.strip()
            if params_str_stripped.startswith("{") and params_str_stripped.endswith(
                "}"
            ):
                try:
                    parsed_json = json.loads(params_str_stripped)
                    if isinstance(parsed_json, dict):
                        logger.info(f"成功解析JSON格式参数: {parsed_json}")
                        return parsed_json
                except json.JSONDecodeError as e:
                    logger.warning(f"JSON解析失败，尝试键值对格式: {e}")
                    # JSON解析失败，继续尝试键值对格式

            # 如果不是JSON格式或JSON解析失败，尝试使用 _is_json 方法检查
            if self._is_json(params_str):
                parsed = json.loads(params_str)
                if isinstance(parsed, dict):
                    return parsed

            # 解析键值对格式
            params = {}
            # 使用正则表达式分割参数，支持包含逗号的值
            # 匹配 key=value 格式，value可以包含空格和特殊字符
            # 改进：处理值中可能包含的等号，例如 "key=value=with=equals"
            param_pattern = r"([^=,]+?)\s*=\s*([^,]*?)(?=,\s*[^=,]+=|$)"

            # 尝试更灵活的匹配，处理可能没有逗号分隔的情况
            matches = re.findall(param_pattern, params_str)
            if not matches and "=" in params_str:  # 如果没有逗号分隔，但有等号
                parts = params_str.split("=", 1)
                if len(parts) == 2:
                    matches = [(parts[0], parts[1])]

            for key, value in matches:
                key = key.strip()
                value = value.strip()

                # 尝试转换数值类型
                if value.isdigit():
                    params[key] = int(value)
                elif value.lower() in ("true", "false"):
                    params[key] = value.lower() == "true"
                elif value.replace(".", "", 1).isdigit():
                    params[key] = float(value)
                else:
                    # 移除可能的引号
                    if (value.startswith('"') and value.endswith('"')) or (
                        value.startswith("'") and value.endswith("'")
                    ):
                        value = value[1:-1]
                    params[key] = value

            return params

        except Exception as e:
            logger.warning(
                f"解析方括号参数失败: {e}, 原始字符串: {params_str}", exc_info=True
            )
            # 如果解析失败，返回原始字符串
            return params_str

    @langfuse_wrapper.observe_decorator(
        name="_parse_params_with_llm", capture_input=True, capture_output=True
    )
    async def _parse_params_with_llm(self, params_str: str) -> Dict[str, Any]:
        """
        使用LLM解析字符串参数为JSON对象。
        """
        try:
            # 构建用于解析参数的提示词
            prompt = f"""你是一个专业的JSON解析器。请将以下字符串解析为JSON对象。
如果输入本身就是有效的JSON字符串，请直接返回该JSON。
如果输入不是JSON，但可以被合理地转换为JSON（例如，键值对形式），请进行转换。
如果无法转换为JSON，请返回一个空字典 {{}}。

请注意：
1. 只输出JSON，不要包含任何解释文字，不要包含任何 md 代码块标签。
2. 如果值是字符串，请确保用双引号括起来。
3. 如果值是布尔值或数字，请直接使用。
4. 当你认为输入的字符串是代码时，需要对代码进行合理的优化，防止存在语法错误

待解析字符串：
{params_str}

请输出解析结果："""

            model_to_use = self.reasoner_model_name or self.model_name
            if not model_to_use:
                logger.error("没有可用的模型进行LLM参数解析")
                return {}

            model_response = await call_llm_api([{"role": "user", "content": prompt}])

            if isinstance(model_response, tuple) and len(model_response) == 2:
                extracted_text = model_response[0]
            else:
                extracted_text = model_response

            try:
                result = json.loads(extracted_text.strip())
                if isinstance(result, dict):
                    logger.info("LLM参数解析成功")
                    return result
            except json.JSONDecodeError:
                logger.warning(f"LLM解析的参数内容不是有效JSON: {extracted_text}")
            return {}
        except Exception as e:
            logger.warning(f"使用LLM解析参数失败: {e}", exc_info=True)
            return {}
