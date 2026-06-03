# -*- coding: utf-8 -*-
"""
Flask应用工厂模块

该模块提供Flask应用的工厂函数，支持多环境配置（开发/生产/测试）。
"""

import os
from flask import Flask, render_template
from flask_cors import CORS
from app.config import config_by_name


def create_app(config_name='development'):
    """
    创建Flask应用实例（应用工厂模式）
    
    Args:
        config_name (str): 配置环境名称，可选值：development, production, testing
    
    Returns:
        Flask: 配置好的Flask应用实例
    """
    app = Flask(__name__)
    
    # 加载配置
    config = config_by_name.get(config_name, config_by_name['development'])
    app.config.from_object(config)
    
    # 初始化CORS
    CORS(app, origins=config.CORS_ORIGINS)
    
    # 确保数据目录存在
    os.makedirs(config.DATA_DIR, exist_ok=True)
    os.makedirs(config.UPLOAD_DIR, exist_ok=True)
    os.makedirs(config.LOG_DIR, exist_ok=True)
    
    # 设置上传配置
    app.config['UPLOAD_FOLDER'] = config.UPLOAD_DIR
    app.config['MAX_CONTENT_LENGTH'] = config.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    
    # 注册蓝本
    register_blueprints(app)
    
    # 注册错误处理
    register_error_handlers(app)
    
    return app


def register_blueprints(app):
    """
    注册所有API蓝本
    
    Args:
        app (Flask): Flask应用实例
    """
    from app.api import api_bp
    from app.api.schedule import schedule_bp
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(schedule_bp, url_prefix='/api')


def register_error_handlers(app):
    """
    注册错误处理器
    
    Args:
        app (Flask): Flask应用实例
    """
    
    @app.errorhandler(404)
    def not_found(error):
        return {'error': 'Not found'}, 404
    
    @app.errorhandler(400)
    def bad_request(error):
        return {'error': 'Bad request'}, 400
    
    @app.errorhandler(500)
    def internal_error(error):
        return {'error': 'Internal server error'}, 500


# 首页路由（单独注册，不属于任何蓝本）
def register_index_route(app):
    """
    注册首页路由
    
    Args:
        app (Flask): Flask应用实例
    """
    
    @app.route('/')
    def index():
        return render_template('index.html')
    
    @app.route('/uploads/<filename>')
    def uploaded_file(filename):
        from flask import send_from_directory
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)