"""Skills解析管理节点 - 用于加载、检索和发现技能目录中的技能"""

import os
import yaml
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
from .base import BaseNode

logger = logging.getLogger(__name__)


def get_default_skills_dirs() -> List[str]:
    """获取默认技能目录列表"""
    dirs = []
    # 1. 当前用户目录下的 .proteus/skills
    user_dir = Path.home() / ".proteus" / "skills"
    if user_dir.exists():
        dirs.append(str(user_dir))
    # 2. app 目录下的 .proteus/skills (假设为当前工作目录下的 .proteus/skills)
    app_dir = Path.cwd() / ".proteus" / "skills"
    if app_dir.exists():
        dirs.append(str(app_dir))
    # 3. 当前项目目录下的 skills 目录
    project_dir = Path.cwd() / "skills"
    if project_dir.exists():
        dirs.append(str(project_dir))
    # 4. 用户配置的目录（环境变量 PROTEUS_SKILLS_DIR）
    config_dirs = os.environ.get("PROTEUS_SKILLS_DIR")
    if config_dirs:
        for d in config_dirs.split(os.pathsep):
            d = d.strip()
            if d:
                path = Path(d)
                if path.exists():
                    dirs.append(str(path))
    return dirs


def parse_frontmatter(content: str) -> Dict[str, Any]:
    """解析Markdown文件的前置元数据（YAML格式）"""
    lines = content.split("\n")
    if not lines or lines[0] != "---":
        return {}
    frontmatter_lines = []
    for line in lines[1:]:
        if line == "---":
            break
        frontmatter_lines.append(line)
    try:
        frontmatter = yaml.safe_load("\n".join(frontmatter_lines))
        return frontmatter or {}
    except yaml.YAMLError as e:
        logger.warning(f"解析前置元数据失败: {e}")
        return {}


def scan_multiple_skills_directories(skills_dirs: List[str]) -> List[Dict[str, Any]]:
    """扫描多个技能目录，返回合并的技能列表（去重）"""
    all_skills = []
    seen_names = set()
    for dir_path in skills_dirs:
        skills = scan_skills_directory(dir_path)
        for skill in skills:
            if skill["name"] not in seen_names:
                seen_names.add(skill["name"])
                all_skills.append(skill)
    return all_skills


def scan_skills_directory(skills_dir: str) -> List[Dict[str, Any]]:
    """扫描技能目录，返回技能列表"""
    skills = []
    skills_path = Path(skills_dir)
    if not skills_path.exists():
        logger.warning(f"技能目录不存在: {skills_dir}")
        return skills
    for item in skills_path.iterdir():
        if item.is_dir():
            # 检查目录中是否有 SKILL.md 或 skill.md 文件
            skill_md = item / "SKILL.md"
            if not skill_md.exists():
                skill_md = item / "skill.md"
            if skill_md.exists() and skill_md.is_file():
                try:
                    content = skill_md.read_text(encoding="utf-8")
                    frontmatter = parse_frontmatter(content)
                    name = frontmatter.get("name", item.name)
                    description = frontmatter.get("description", "")
                    skills.append(
                        {
                            "name": name,
                            "description": description,
                            "path": str(item.relative_to(skills_path)),
                            "full_path": str(item),
                            "file_path": str(skill_md),
                        }
                    )
                except Exception as e:
                    logger.error(f"读取技能文件失败 {skill_md}: {e}")
    return skills


def get_skill_content(skills_dir: str, skill_name: str) -> Optional[Dict[str, Any]]:
    """根据技能名称获取技能内容"""
    skills = scan_skills_directory(skills_dir)
    for skill in skills:
        if skill["name"] == skill_name:
            try:
                content = Path(skill["file_path"]).read_text(encoding="utf-8")
                return {
                    "name": skill["name"],
                    "description": skill["description"],
                    "content": content,
                    "path": skill["path"],
                    "file_path": skill["file_path"],
                }
            except Exception as e:
                logger.error(f"读取技能内容失败 {skill['file_path']}: {e}")
                return None
    return None




class SkillsExtractNode(BaseNode):
    """Skills解析管理节点 - 用于加载、检索和发现技能目录中的技能"""

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行节点

        Args:
            params: 节点参数，包含：
                - action: 操作类型，可选值: 'list', 'get', 'getContent'
                - skill_name: 技能名称（当action为'get'或'getContent'时必需）
                - skills_dir: 技能目录路径（可选，默认为'./src/skills'）

        Returns:
            Dict[str, Any]: 执行结果，包含'success'、'error'、'data'等字段
        """
        action = params.get("action", "list")
        skills_dir = params.get("skills_dir", "./src/skills")

        # 确定要扫描的目录列表
        if "skills_dir" not in params:
            # 用户未显式提供 skills_dir，使用默认目录列表
            skills_dirs = get_default_skills_dirs()
        else:
            # 用户提供了 skills_dir，可能是单个目录或由 os.pathsep 分隔的多个目录
            if isinstance(skills_dir, str):
                # 按分隔符拆分
                dirs = [d.strip() for d in skills_dir.split(os.pathsep) if d.strip()]
                skills_dirs = dirs if dirs else [skills_dir]
            else:
                # 假设已经是列表
                skills_dirs = skills_dir

        # 检查所有目录是否存在（至少一个存在）
        existing_dirs = [d for d in skills_dirs if os.path.exists(d)]
        if not existing_dirs:
            return {
                "success": False,
                "error": f"技能目录不存在: {skills_dirs}",
                "data": None,
            }

        try:
            if action == "list":
                skills = scan_multiple_skills_directories(existing_dirs)
                return {
                    "success": True,
                    "error": None,
                    "data": {"skills": skills, "count": len(skills)},
                }
            elif action == "get":
                skill_name = params.get("skill_name")
                if not skill_name:
                    return {
                        "success": False,
                        "error": "缺少参数 skill_name",
                        "data": None,
                    }
                # 扫描所有目录查找技能
                all_skills = scan_multiple_skills_directories(existing_dirs)
                target_skill = None
                for skill in all_skills:
                    if skill["name"] == skill_name:
                        target_skill = skill
                        break
                if target_skill:
                    try:
                        content = Path(target_skill["file_path"]).read_text(
                            encoding="utf-8"
                        )
                        # 获取技能目录下的所有文件列表
                        skill_path = Path(target_skill["full_path"])
                        all_files = []
                        for file in skill_path.rglob("*"):
                            if file.is_file():
                                rel_path = str(file.relative_to(skill_path))
                                all_files.append(rel_path)
                        return {
                            "success": True,
                            "error": None,
                            "data": {
                                "name": target_skill["name"],
                                "description": target_skill["description"],
                                "content": content,
                                "path": target_skill["path"],
                                "file_path": target_skill["file_path"],
                                "files": all_files,
                            },
                        }
                    except Exception as e:
                        logger.error(
                            f"读取技能内容失败 {target_skill['file_path']}: {e}"
                        )
                        return {
                            "success": False,
                            "error": f"读取技能内容失败: {e}",
                            "data": None,
                        }
                else:
                    return {
                        "success": False,
                        "error": f"未找到技能: {skill_name}",
                        "data": None,
                    }
            elif action == "getContent":
                skill_name = params.get("skill_name")
                file_path = params.get("file_path")
                if not skill_name or not file_path:
                    return {
                        "success": False,
                        "error": "缺少参数 skill_name 或 file_path",
                        "data": None,
                    }
                # 扫描所有目录查找技能
                all_skills = scan_multiple_skills_directories(existing_dirs)
                target_skill = None
                for skill in all_skills:
                    if skill["name"] == skill_name:
                        target_skill = skill
                        break
                if not target_skill:
                    return {
                        "success": False,
                        "error": f"未找到技能: {skill_name}",
                        "data": None,
                    }
                # 构建完整文件路径并检查安全性
                skill_path = Path(target_skill["full_path"])
                target_file = skill_path / file_path
                try:
                    # 确保目标文件在技能目录内
                    target_file_resolved = target_file.resolve()
                    skill_path_resolved = skill_path.resolve()
                    try:
                        target_file_resolved.relative_to(skill_path_resolved)
                    except ValueError:
                        return {
                            "success": False,
                            "error": "文件路径不在技能目录内",
                            "data": None,
                        }
                    content = target_file.read_text(encoding="utf-8")
                    return {
                        "success": True,
                        "error": None,
                        "data": {
                            "skill_name": skill_name,
                            "file_path": file_path,
                            "content": content,
                        },
                    }
                except Exception as e:
                    logger.error(f"读取文件失败 {target_file}: {e}")
                    return {
                        "success": False,
                        "error": f"读取文件失败: {e}",
                        "data": None,
                    }
            else:
                return {
                    "success": False,
                    "error": f"不支持的操作类型: {action}",
                    "data": None,
                }
        except Exception as e:
            logger.error(f"执行SkillsExtractNode失败: {e}", exc_info=True)
            return {"success": False, "error": str(e), "data": None}

    async def agent_execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """智能体调用节点，将结果转换为统一格式

        Args:
            params: 节点参数

        Returns:
            Dict[str, Any]: 执行结果，包含纯文本格式的'result'键
        """
        try:
            execute_result = await self.execute(params)
            if not execute_result.get("success"):
                error_message = execute_result.get("error", "未知错误")
                result_text = f"技能提取失败。错误信息：{error_message}"
                return {"result": result_text, **execute_result}

            data = execute_result.get("data")
            action = params.get("action", "list")

            if action == "list":
                skills = data.get("skills", [])
                if not skills:
                    result_text = "技能目录为空。"
                else:
                    skill_items = []
                    for i, skill in enumerate(skills, 1):
                        skill_items.append(
                            f"{i}. {skill['name']}: {skill['description']}"
                        )
                    result_text = "技能列表:\n" + "\n".join(skill_items)
            elif action == "get":
                result_text = f"技能名称: {data.get('name', '未知')}\n"
                result_text += f"描述: {data.get('description', '')}\n"
                result_text += f"文件路径: {data.get('file_path', '')}\n"
                files = data.get('files', [])
                if files:
                    result_text += f"技能目录下文件 ({len(files)}):\n" + "\n".join(f"  - {f}" for f in files) + "\n"
                else:
                    result_text += "技能目录下无其他文件。\n"
                result_text += "内容:\n"
                content = data.get("content", "")
                result_text += content
            elif action == "getContent":
                result_text = f"技能名称: {data.get('skill_name', '未知')}\n"
                result_text += f"文件路径: {data.get('file_path', '')}\n"
                result_text += "文件内容:\n"
                content = data.get("content", "")
                result_text += content
            else:
                result_text = f"未知操作类型: {action}"

            return {"result": result_text, **execute_result}
        except Exception as e:
            error_msg = f"SkillsExtractNode agent_execute 出错: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                "result": error_msg,
                "success": False,
                "error": str(e),
                "data": None,
            }
