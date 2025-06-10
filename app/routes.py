import os
import logging
from flask import jsonify, render_template
from multiprocessing import Manager

# 配置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 创建进程安全的状态管理器
manager = Manager()
bot_status = manager.dict({
    "running": False,
    "start_time": None,
    "restart_count": 0
})

# 使用进程锁
bot_lock = manager.Lock()

def register_routes(app):
    """注册所有路由"""
    
    @app.route('/')
    def index():
        """主页"""
        with bot_lock:
            status = dict(bot_status)
        
        return render_template('index.html',
            bot_status=status,
            port=os.environ.get('PORT', 5000),
            debug=app.debug
        )

    @app.route('/status')
    def status():
        """获取状态"""
        with bot_lock:
            status = dict(bot_status)
        
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
        with bot_lock:
            bot_status["restart_count"] += 1
            # 这里可以添加实际的重启逻辑
            return jsonify({
                "status": "success",
                "message": "重启命令已发送",
                "bot_status": dict(bot_status)
            })

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
