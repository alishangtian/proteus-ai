from typing import Dict, Any
import json
import logging
import time
import requests
from .base import BaseNode
from ..api.llm_api import call_llm_api
from ..api.config import API_CONFIG

logger = logging.getLogger(__name__)


class WeatherForecastNode(BaseNode):
    """天气预报节点 - 使用彩云天气API获取天气信息

    参数:
        latitude (float): 纬度
        longitude (float): 经度
        version (str, optional): API版本，默认为2.6
        token (str, optional): 彩云天气API Token，默认从配置获取

    返回:
        dict: 包含执行状态、错误信息和天气信息
    """

    def __init__(self):
        super().__init__()
        self.api_version = API_CONFIG["caiyun_api_version"]
        self.token = API_CONFIG["caiyun_token"]

    async def get_realtime_weather(
        self, longitude: float, latitude: float, version: str, token: str
    ) -> Dict:
        """获取实时天气数据"""
        url = f"https://api.caiyunapp.com/v{version}/{token}/{longitude},{latitude}/realtime"
        response = requests.get(url)
        response.raise_for_status()
        weather_data = response.json()
        return weather_data["result"]["realtime"]

    async def get_daily_forecast(
        self, longitude: float, latitude: float, version: str, token: str
    ) -> Dict:
        """获取三天预报数据"""
        url = (
            f"https://api.caiyunapp.com/v{version}/{token}/{longitude},{latitude}/daily"
        )
        params = {"dailysteps": "3"}
        response = requests.get(url, params=params)
        response.raise_for_status()
        weather_data = response.json()
        return weather_data["result"]["daily"]

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        start_time = time.time()
        try:
            # 获取参数
            latitude = float(params.get("latitude", 0))
            longitude = float(params.get("longitude", 0))
            version = params.get("version", self.api_version)
            token = params.get("token", self.token)

            if not latitude or not longitude:
                raise ValueError("latitude和longitude参数不能为空")

            # 获取实时天气和三天预报
            realtime_data = await self.get_realtime_weather(
                longitude, latitude, version, token
            )
            daily_data = await self.get_daily_forecast(
                longitude, latitude, version, token
            )

            # 组合数据
            weather_data = {"realtime": realtime_data, "daily": daily_data}

            end_time = time.time()
            execution_time = end_time - start_time
            logger.info(
                f"天气数据获取成功: 经度{longitude},纬度{latitude}, 耗时: {execution_time:.2f} 秒"
            )

            return {"success": True, "error": None, "data": weather_data}

        except requests.Timeout:
            end_time = time.time()
            execution_time = end_time - start_time
            error_msg = "请求超时"
            logger.error(f"{error_msg}, 耗时: {execution_time:.2f} 秒")
            return {"success": False, "error": error_msg, "data": None}

        except requests.RequestException as e:
            end_time = time.time()
            execution_time = end_time - start_time
            error_msg = f"请求错误: {str(e)}"
            logger.error(f"{error_msg}, 耗时: {execution_time:.2f} 秒")
            return {"success": False, "error": error_msg, "data": None}

        except Exception as e:
            end_time = time.time()
            execution_time = end_time - start_time
            error_msg = f"未知错误: {str(e)}"
            logger.error(f"{error_msg}, 耗时: {execution_time:.2f} 秒")
            return {"success": False, "error": error_msg, "data": None}

    async def agent_execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        execution_result = await self.execute(params)
        if execution_result["success"]:
            weather_data = execution_result["data"]
            messages = [
                {
                    "role": "user",
                    "content": f"""请分析并总结以下天气数据：
实时天气预报：{json.dumps(weather_data['realtime'], ensure_ascii=False)}
未来三天天气预报：{json.dumps(weather_data['daily'], ensure_ascii=False)}""",
                },
            ]
            weather_result = await call_llm_api(messages, None)
            return {"result": weather_result}
        else:
            return {"result": f"获取天气信息失败: {execution_result['error']}"}
