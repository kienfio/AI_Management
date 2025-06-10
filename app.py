import os
import threading
import logging
import atexit
import time
from flask import Flask, render_template, jsonify
from main import main as start_bot

# 配置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 创建Flask应用
app = Flask(__name__)

# 状态变量
bot_status = {"running": False, "start_time": None, "restart_count": 0}
bot_thread = None
bot_lock = threading.Lock()

def cleanup():
    """清理函数，确保在应用关闭时正确关闭机器人"""
    global bot_thread, bot_status
    with bot_lock:
        if bot_thread and bot_thread.is_alive():
            logger.info("正在关闭机器人线程...")
            bot_status["running"] = False
            bot_thread.join(timeout=5)
            logger.info("机器人线程已关闭")

# 注册清理函数
atexit.register(cleanup)

def run_telegram_bot():
    """运行Telegram机器人的线程函数"""
    global bot_status
    try:
        logger.info("正在启动Telegram机器人...")
        with bot_lock:
            bot_status["restart_count"] += 1
        start_bot()
    except Exception as e:
        logger.error(f"启动机器人时出错: {e}")
    finally:
        with bot_lock:
            bot_status["running"] = False

def ensure_single_instance():
    """确保只有一个机器人实例在运行"""
    global bot_thread, bot_status
    with bot_lock:
        # 如果有正在运行的线程，先停止它
        if bot_thread and bot_thread.is_alive():
            logger.info("检测到现有机器人实例，正在停止...")
            bot_status["running"] = False
            bot_thread.join(timeout=5)
            if bot_thread.is_alive():
                logger.warning("无法正常停止现有实例")
                return False
        
        # 启动新的线程
        bot_status["running"] = True
        bot_status["start_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
        bot_thread = threading.Thread(target=run_telegram_bot)
        bot_thread.daemon = True
        bot_thread.start()
        logger.info("新的机器人实例已启动")
        return True

# 路由：主页
@app.route('/')
def index():
    port = os.environ.get('PORT', 5000)
    return jsonify({
        "status": "running",
        "message": "AI财务管理机器人服务已启动",
        "port": port,
        "bot_status": bot_status
    })

# 路由：状态检查
@app.route('/status')
def status():
    port = os.environ.get('PORT', 5000)
    return jsonify({
        "bot_status": bot_status,
        "service": "running",
        "port": port
    })

# 路由：健康检查
@app.route('/health')
def health():
    return jsonify({
        "status": "healthy",
        "port": os.environ.get('PORT', 5000)
    })

# 路由：重启机器人
@app.route('/restart')
def restart_bot():
    if ensure_single_instance():
        return jsonify({
            "status": "success",
            "message": "机器人已重启",
            "bot_status": bot_status
        })
    else:
        return jsonify({
            "status": "error",
            "message": "重启失败",
            "bot_status": bot_status
        }), 500

# 启动机器人线程
ensure_single_instance()

# 记录端口信息
port = os.environ.get('PORT', 5000)
logger.info(f"Flask应用准备在端口 {port} 上启动")

# 主程序入口
if __name__ == '__main__':
    # 启动Web服务
    app.run(host='0.0.0.0', port=port) 
