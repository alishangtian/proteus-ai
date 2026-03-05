
"""
多任务深度研究模块化工具集
优化版本：支持逐步规划、任务下发标志、定期休眠监控
基于用户需求优化：
1. 任务文件夹生成可以使用脚本，但是主任务和子任务前期相关文档的任务规划和写文件需要通过 python 工具执行，这样可以进行逐步规划
2. 任务规划好之后，可以通过脚本形式，通过 api 调用下发任务，任务下发后需要更新当前任务的相关文件，留存任务下发标志
3. 主任务通过定期休眠进行子任务进度的查看
"""

import os
import sys
import json
import re
import shutil
import time
from datetime import datetime


def validate_folder_name(folder_name):
    """
    验证文件夹名称是否为有效的英文名称
    
    Args:
        folder_name: 文件夹名称
    
    Returns:
        tuple: (is_valid, error_message)
    """
    if not folder_name:
        return False, "文件夹名称不能为空"
    
    # 允许的字符: 字母、数字、下划线、连字符、点
    if not re.match(r'^[a-zA-Z0-9_.-]+$', folder_name):
        return False, f"文件夹名称 '{folder_name}' 包含无效字符。只能使用英文、数字、下划线(_)、连字符(-)和点(.)"
    
    # 不能以点开头或结尾
    if folder_name.startswith('.') or folder_name.endswith('.'):
        return False, "文件夹名称不能以点开头或结尾"
    
    # 不能包含连续的点
    if '..' in folder_name:
        return False, "文件夹名称不能包含连续的点"
    
    # 长度限制
    if len(folder_name) > 100:
        return False, "文件夹名称过长，最多100个字符"
    
    # 保留名称检查
    reserved_names = ['con', 'prn', 'aux', 'nul', 'com1', 'com2', 'com3', 'com4', 
                     'com5', 'com6', 'com7', 'com8', 'com9', 'lpt1', 'lpt2', 
                     'lpt3', 'lpt4', 'lpt5', 'lpt6', 'lpt7', 'lpt8', 'lpt9']
    if folder_name.lower() in reserved_names:
        return False, f"文件夹名称 '{folder_name}' 是系统保留名称"
    
    return True, ""
