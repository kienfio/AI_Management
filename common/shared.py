"""
共享状态和功能模块
用于存放多个模块之间需要共享的状态和功能
"""
import logging
import threading
import time
from multiprocessing import Manager

# 配置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 进程安全的状态管理
manager = Manager()
bot_status = manager.dict({
    "running": False,
    "start_time": None,
    "restart_count": 0
})

# 线程锁
bot_lock = threading.Lock()

def update_bot_status(running=None, start_time=None, restart_count=None):
    """更新机器人状态"""
    with bot_lock:
        if running is not None:
            bot_status["running"] = running
        if start_time is not None:
            bot_status["start_time"] = start_time
        if restart_count is not None:
            bot_status["restart_count"] += 1 if restart_count is True else 0
            
def get_bot_status():
    """获取机器人状态"""
    with bot_lock:
        return dict(bot_status) 