import threading
import logging
import time
import asyncio
# 直接从bot.main导入，避免循环
from bot.main import run_bot

# 配置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class BotManager:
    """Telegram机器人管理器"""
    _instance = None
    _lock = threading.Lock()
    _status = {"running": False, "start_time": None, "restart_count": 0}
    _bot_thread = None
    _event_loop = None

    @classmethod
    def get_instance(cls):
        """获取单例实例"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def get_status(cls):
        """获取机器人状态"""
        with cls._lock:
            return cls._status.copy()

    @classmethod
    def _run_bot(cls):
        """运行机器人的线程函数"""
        try:
            logger.info("正在启动Telegram机器人...")
            with cls._lock:
                cls._status["restart_count"] += 1
                # 创建新的事件循环
                cls._event_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(cls._event_loop)
            
            # 运行机器人
            cls._event_loop.run_until_complete(run_bot())
        except Exception as e:
            logger.error(f"启动机器人时出错: {e}")
        finally:
            with cls._lock:
                cls._status["running"] = False
                # 清理事件循环
                if cls._event_loop and not cls._event_loop.is_closed():
                    try:
                        cls._event_loop.stop()
                        cls._event_loop.close()
                    except Exception as e:
                        logger.error(f"关闭事件循环时出错: {e}")

    @classmethod
    def start(cls):
        """启动机器人"""
        instance = cls.get_instance()
        return instance._ensure_single_instance()

    @classmethod
    def stop(cls):
        """停止机器人"""
        with cls._lock:
            if cls._bot_thread and cls._bot_thread.is_alive():
                logger.info("正在停止机器人...")
                cls._status["running"] = False
                # 停止事件循环
                if cls._event_loop and not cls._event_loop.is_closed():
                    try:
                        cls._event_loop.stop()
                    except Exception as e:
                        logger.error(f"停止事件循环时出错: {e}")
                # 等待线程结束
                cls._bot_thread.join(timeout=5)
                return not cls._bot_thread.is_alive()
            return True

    @classmethod
    def restart(cls):
        """重启机器人"""
        cls.stop()
        return cls.start()

    def _ensure_single_instance(self):
        """确保只有一个机器人实例在运行"""
        with self._lock:
            # 如果有正在运行的线程，先停止它
            if self._bot_thread and self._bot_thread.is_alive():
                logger.info("检测到现有机器人实例，正在停止...")
                self._status["running"] = False
                # 停止事件循环
                if self._event_loop and not self._event_loop.is_closed():
                    try:
                        self._event_loop.stop()
                    except Exception as e:
                        logger.error(f"停止事件循环时出错: {e}")
                # 等待线程结束
                self._bot_thread.join(timeout=5)
                if self._bot_thread.is_alive():
                    logger.warning("无法正常停止现有实例")
                    return False
            
            # 启动新的线程
            self._status["running"] = True
            self._status["start_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
            self._bot_thread = threading.Thread(target=self._run_bot)
            self._bot_thread.daemon = True
            self._bot_thread.start()
            logger.info("新的机器人实例已启动")
            return True 
