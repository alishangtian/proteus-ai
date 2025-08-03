"""模型配置管理模块"""

import os
import yaml
from typing import Dict, Optional
from pathlib import Path
from typing import List
from src.utils.aescipher import AESCipher


class ModelManager:
    """管理LLM模型配置"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_config()
        return cls._instance

    def _init_config(self):
        """初始化配置"""
        # 优先使用环境变量指定的配置路径
        if "PROTEUS_CONFIG_DIR" in os.environ:
            self.config_path = (
                Path(os.environ["PROTEUS_CONFIG_DIR"]) / "models_config.yaml"
            )
        else:
            # 尝试从项目根目录查找conf目录
            current_path = Path(__file__).resolve()
            root_path = None

            # 向上查找直到找到包含conf目录的路径
            for parent in current_path.parents:
                if (parent / "conf").exists():
                    root_path = parent
                    break

            if root_path:
                self.config_path = root_path / "conf" / "models_config.yaml"
            else:
                # 最后尝试固定路径（适用于docker环境）
                self.config_path = Path("/conf/models_config.yaml")

        self._config = self._load_config()

    def _load_config(self) -> Dict:
        """加载YAML配置文件"""
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            raise ValueError(f"加载模型配置文件失败: {str(e)}")

    def get_model_config(self, model_name: str) -> Dict:
        """
        获取指定模型的配置

        Args:
            model_name: 模型名称

        Returns:
            模型配置字典，包含base_url, api_key, model_name

        Raises:
            ValueError: 如果模型配置不存在
        """
        model_config = self._config.get(model_name)
        if not model_config:
            raise ValueError(f"模型配置不存在: {model_name}")

        api_key = AESCipher.decrypt_string(
            ciphertext=model_config["api_key"], key=os.getenv("CRYPTO_SECRET_KEY")
        )
        return {
            "base_url": model_config["base_url"],
            "api_key": api_key,
            "model_name": model_config["model_name"],
            "type": model_config["type"],
        }

    def list_models(self) -> List[str]:
        """获取所有可用的模型名称列表"""
        return list(self._config.keys())
