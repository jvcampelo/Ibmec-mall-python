from flask import Flask
from flask_restx import Api
from app.database import db
from app.config import Config
from app.controllers.usuario_controller import usuario_bp, api as usuario_api
from app.controllers.endereco_controller import endereco_bp, api as endereco_api
from app.controllers.cartao_controller import cartao_bp, api as cartao_api
from app.controllers.produto_controller import produto_bp, api as produto_api
from app.controllers.pedido_controller import pedido_bp, api as pedido_api

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Configuração do Swagger
    api = Api(
        title='E-commerce API',
        version='1.0',
        description='API para sistema de e-commerce',
        doc='/'
    )

    # Adiciona os namespaces ao API
    api.add_namespace(usuario_api)
    api.add_namespace(endereco_api)
    api.add_namespace(cartao_api)
    api.add_namespace(produto_api)
    api.add_namespace(pedido_api)

    # Inicializa o API com a aplicação
    api.init_app(app)

    db.init_app(app)

    # Registra os blueprints
    app.register_blueprint(usuario_bp, url_prefix="/usuario")
    app.register_blueprint(endereco_bp, url_prefix="/endereco")
    app.register_blueprint(cartao_bp, url_prefix="/cartao")
    app.register_blueprint(produto_bp, url_prefix="/produto")
    app.register_blueprint(pedido_bp, url_prefix="/pedido")

    return app
