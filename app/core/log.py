"""
日志配置模块
============

本模块在 import 时自动初始化全局日志系统（基于 loguru）。
配置来源：app_config.yaml 中 logging 段，支持控制台 + 文件双通道输出。

控制台日志输出到 sys.stdout 而非 sys.stderr：
    项目运行时 docker 日志或 IDE 控制台默认只捕获 stdout，
    输出到 stdout 确保日志在以上环境中可见。
"""

import sys
from pathlib import Path

from loguru import logger

from app.conf.app_config import app_config

# 日志格式串，使用 loguru 的 markup 语法：
#   <green>...</green> → 时间戳以绿色显示
#   <level>{level: <8}</level> → 日志级别左对齐占 8 字符，颜色随级别变化
#   <cyan>{name}</cyan> → 模块名以青色显示
#   {function}:{line} → 函数名和行号，定位日志来源
log_format = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan> : <cyan>{function}</cyan>:<cyan>{line}</cyan> - "
    "<level>{message}</level>"
)

# 清除 loguru 默认的 handler（默认只输出到 stderr，格式不符合项目需求）
# 必须在添加自定义 handler 之前调用，否则会出现重复日志
logger.remove()

if app_config.logging.console.enable:
    # sink=sys.stdout：输出到标准输出流
    # level 由 app_config.yaml 控制，生产环境通常设为 INFO 以抑制 DEBUG 噪音
    logger.add(sink=sys.stdout, level=app_config.logging.console.level,
               format=log_format)

if app_config.logging.file.enable:
    # 将相对路径转为绝对路径，避免不同工作目录下日志散落各处
    path = Path(app_config.logging.file.path).resolve()
    # 只创建父目录（如 logs/），不将 app.log 本身当作目录创建
    path.parent.mkdir(parents=True, exist_ok=True)
    logger.add(sink=path, level=app_config.logging.file.level,
               format=log_format,
               # rotation：日志切割策略（如 "10 MB"/"1 day"），防止单文件无限增长
               rotation=app_config.logging.file.rotation,
               # retention：旧日志保留天数，到期自动清理，避免磁盘写满
               retention=app_config.logging.file.retention,
               # 显式指定 utf-8：Windows 默认编码可能为 GBK，中文日志会乱码
               encoding='utf-8')
