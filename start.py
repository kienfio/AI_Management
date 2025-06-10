import os
import logging
import asyncio
import uvicorn
from app import create_app
from bot.webhook import setup_webhook

# 配置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def init_webhook():
    """初始化webhook"""
    logger.info("正在初始化webhook...")
    success = await setup_webhook()
    if success:
        logger.info("Webhook初始化成功")
    else:
        logger.error("Webhook初始化失败")

def run_server():
    """运行Web服务器"""
    # 获取应用
    app = create_app()
    
    # 获取端口
    port = int(os.environ.get('PORT', 5000))
    
    # 设置服务器配置
    config = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
    
    # 创建服务器
    server = uvicorn.Server(config)
    
    # 初始化webhook
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(init_webhook())
    
    # 运行服务器
    logger.info(f"启动Web服务器，监听端口 {port}...")
    server.run()

if __name__ == '__main__':
    logger.info("启动应用...")
    try:
        run_server()
    except Exception as e:
        logger.error(f"启动服务器时出错: {e}")
        import traceback
        logger.error(traceback.format_exc()) 
