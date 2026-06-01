# -*- coding: utf-8 -*-
"""
日志配置模块

该模块提供统一的结构化日志配置，支持：
1. 控制台输出（带颜色）
2. 文件输出（JSON格式）
3. 日志级别控制
4. 自定义日志格式

使用方式：
    from app.services.logger import get_logger
    logger = get_logger(__name__)
    logger.info("日志消息", extra={"key": "value"})
"""

import logging
import json
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler
from app.config import Config

LOG_DIR = Config.LOG_DIR
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)


class JSONFormatter(logging.Formatter):
    """JSON格式日志格式化器"""
    
    def format(self, record):
        log_record = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "message": self._safe_string(record.getMessage()),
            "process": record.process,
            "thread": record.thread
        }
        
        if hasattr(record, 'extra') and record.extra:
            for key, value in record.extra.items():
                log_record[key] = self._safe_string(value)
        
        return json.dumps(log_record, ensure_ascii=False)
    
    def _safe_string(self, value):
        try:
            return str(value)
        except Exception:
            return "N/A"


class ColorFormatter(logging.Formatter):
    """带颜色的控制台日志格式化器"""
    
    COLORS = {
        'DEBUG': '\033[94m',
        'INFO': '\033[92m',
        'WARNING': '\033[93m',
        'ERROR': '\033[91m',
        'CRITICAL': '\033[95m',
        'RESET': '\033[0m'
    }
    
    def format(self, record):
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset = self.COLORS['RESET']
        
        timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')
        message = record.getMessage()
        
        if hasattr(record, 'extra') and record.extra:
            extra_str = json.dumps(record.extra, ensure_ascii=False)
            message = f"{message} | {extra_str}"
        
        return f"{color}[{timestamp}] [{record.levelname}] [{record.module}.{record.funcName}:{record.lineno}] {message}{reset}"


def get_logger(name, level=logging.INFO):
    """获取配置好的日志记录器"""
    logger = logging.getLogger(name)
    
    if logger.handlers:
        return logger
    
    logger.setLevel(level)
    logger.propagate = False
    
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(ColorFormatter())
    logger.addHandler(console_handler)
    
    file_handler = RotatingFileHandler(
        os.path.join(LOG_DIR, 'app.log'),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(JSONFormatter())
    logger.addHandler(file_handler)
    
    error_file_handler = RotatingFileHandler(
        os.path.join(LOG_DIR, 'error.log'),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8'
    )
    error_file_handler.setLevel(logging.ERROR)
    error_file_handler.setFormatter(JSONFormatter())
    logger.addHandler(error_file_handler)
    
    return logger