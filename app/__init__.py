from flask import Flask
from asgiref.wsgi import WsgiToAsgi

def create_app():
    """创建并配置Flask应用"""
    app = Flask(__name__)
    
    # 导入路由
    from app.routes import register_routes
    register_routes(app)
    
    # 将WSGI应用转换为ASGI应用，以支持异步路由
    asgi_app = WsgiToAsgi(app)
    
    # 保留对原始WSGI应用的引用
    asgi_app._wsgi_app = app
    
    return asgi_app 
