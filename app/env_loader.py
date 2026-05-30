# -*- coding: utf-8 -*-
"""
环境变量加载模块

该模块负责从 .env 文件中加载环境变量，
并设置到系统环境中，供 config.py 使用。
"""

import os


def load_env_file(env_path=".env"):
    """
    从 .env 文件中加载环境变量
    
    Args:
        env_path (str): .env 文件路径
        
    Returns:
        bool: 是否成功加载
    """
    if not os.path.exists(env_path):
        return False
    
    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                
                # 跳过空行和注释
                if not line or line.startswith('#'):
                    continue
                
                # 解析 key=value
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # 移除可能的引号
                    if (value.startswith('"') and value.endswith('"')) or \
                       (value.startswith("'") and value.endswith("'")):
                        value = value[1:-1]
                    
                    # 设置到环境变量
                    os.environ[key] = value
                    
        return True
    except Exception as e:
        print(f"Warning: Failed to load .env file: {e}")
        return False


# 尝试自动加载 .env 文件
load_env_file()
