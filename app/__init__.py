from flask import Flask

def create_app():
    """创建并配置Flask应用"""
    app = Flask(__name__)
    
    # 导入路由
    from app.routes import register_routes
    register_routes(app)
    
    return app 