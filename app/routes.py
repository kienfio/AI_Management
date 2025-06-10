import os
import logging
from flask import jsonify, render_template
from common.shared import get_bot_status, update_bot_status

# 配置日志
logger = logging.getLogger(__name__)

def register_routes(app):
    """注册所有路由"""
    
    @app.route('/')
    def index():
        """主页"""
        status = get_bot_status()
        
        return render_template('index.html',
            bot_status=status,
            port=os.environ.get('PORT', 5000),
            debug=app.debug
        )

    @app.route('/status')
    def status():
        """获取状态"""
        status = get_bot_status()
        
        return jsonify({
            "bot_status": status,
            "service": "running",
            "port": os.environ.get('PORT', 5000)
        })

    @app.route('/health')
    def health():
        """健康检查"""
        return jsonify({
            "status": "healthy",
            "port": os.environ.get('PORT', 5000)
        })

    @app.route('/restart')
    def restart_bot():
        """重启机器人"""
        update_bot_status(restart_count=True)
        # 这里可以添加实际的重启逻辑
        return jsonify({
            "status": "success",
            "message": "重启命令已发送",
            "bot_status": get_bot_status()
        })

    @app.route('/debug')
    def debug_info():
        """调试信息"""
        import sys
        import platform
        import psutil
        
        # 获取进程信息
        process = psutil.Process()
        memory_info = process.memory_info()
        
        debug_data = {
            "bot_status": get_bot_status(),
            "environment": {
                "python_version": sys.version,
                "platform": platform.platform(),
                "cpu_count": psutil.cpu_count(),
                "memory_usage": {
                    "rss": memory_info.rss / (1024 * 1024),  # MB
                    "vms": memory_info.vms / (1024 * 1024)   # MB
                }
            },
            "env_vars": {
                "PORT": os.environ.get("PORT", "未设置"),
                "TELEGRAM_TOKEN": os.environ.get("TELEGRAM_TOKEN", "未设置")[:5] + "..." if os.environ.get("TELEGRAM_TOKEN") else "未设置",
                "GOOGLE_SHEET_ID": os.environ.get("GOOGLE_SHEET_ID", "未设置"),
                "GOOGLE_DRIVE_FOLDER_ID": os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "未设置")
            }
        }
        
        return jsonify(debug_data)

    @app.errorhandler(404)
    def not_found_error(error):
        """404错误处理"""
        return render_template('error.html',
            error_code=404,
            error_message="页面未找到"
        ), 404

    @app.errorhandler(500)
    def internal_error(error):
        """500错误处理"""
        return render_template('error.html',
            error_code=500,
            error_message="服务器内部错误"
        ), 500 
