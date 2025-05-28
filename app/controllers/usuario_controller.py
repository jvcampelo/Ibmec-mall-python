from flask import Blueprint, request, jsonify
from flask_restx import Namespace, Resource, fields
from app.cosmosdb import container
from app.models.usuario import Usuario

usuario_bp = Blueprint("usuario", __name__)
api = Namespace('usuarios', description='Operações relacionadas a usuários')

# Modelos para documentação Swagger
usuario_model = api.model('Usuario', {
    'id': fields.String(readonly=True, description='Identificador único do usuário'),
    'nome': fields.String(required=True, description='Nome do usuário'),
    'email': fields.String(required=True, description='Email do usuário'),
    'senha': fields.String(required=True, description='Senha do usuário'),
    'cpf': fields.String(required=True, description='CPF do usuário'),
    'dataNascimento': fields.String(description='Data de nascimento do usuário'),
    'telefone': fields.String(description='Telefone do usuário')
})

@api.route('')
class UsuarioList(Resource):
    @api.doc('listar_usuarios')
    @api.marshal_list_with(usuario_model)
    def get(self):
        """Lista todos os usuários"""
        query = "SELECT * FROM usuarios"
        usuarios = list(container.query_items(query=query, enable_cross_partition_query=True))
        return usuarios

    @api.doc('criar_usuario')
    @api.expect(usuario_model)
    @api.marshal_with(usuario_model, code=201)
    def post(self):
        """Cria um novo usuário"""
        dados = request.json
        
        if not dados.get("nome") or not dados.get("email") or not dados.get("senha") or not dados.get("cpf"):
            api.abort(400, "Nome, email, senha e CPF são obrigatórios")

        novo_usuario = Usuario(
            nome=dados["nome"],
            email=dados["email"],
            senha=dados["senha"],
            cpf=dados["cpf"],
            dataNascimento=dados.get("dataNascimento"),
            telefone=dados.get("telefone")
        )

        container.create_item(novo_usuario.to_dict())
        return novo_usuario.to_dict(), 201

@api.route('/<string:usuario_id>')
@api.param('usuario_id', 'Identificador do usuário')
@api.response(404, 'Usuário não encontrado')
class UsuarioResource(Resource):
    @api.doc('buscar_usuario')
    @api.marshal_with(usuario_model)
    def get(self, usuario_id):
        """Busca um usuário pelo ID"""
        query = f"SELECT * FROM usuarios u WHERE u.id = '{usuario_id}'"
        usuarios = list(container.query_items(query=query, enable_cross_partition_query=True))

        if not usuarios:
            api.abort(404, "Usuário não encontrado")

        return usuarios[0]

    @api.doc('atualizar_usuario')
    @api.expect(usuario_model)
    @api.marshal_with(usuario_model)
    def put(self, usuario_id):
        """Atualiza um usuário existente"""
        query = f"SELECT * FROM usuarios u WHERE u.id = '{usuario_id}'"
        usuarios = list(container.query_items(query=query, enable_cross_partition_query=True))

        if not usuarios:
            api.abort(404, "Usuário não encontrado")

        usuario = usuarios[0]
        dados = request.json
        usuario.update({
            "nome": dados.get("nome", usuario["nome"]),
            "email": dados.get("email", usuario["email"]),
            "senha": dados.get("senha", usuario["senha"]),
            "cpf": dados.get("cpf", usuario["cpf"]),
            "dataNascimento": dados.get("dataNascimento", usuario["dataNascimento"]),
            "telefone": dados.get("telefone", usuario["telefone"])
        })

        container.replace_item(item=usuario["id"], body=usuario)
        return usuario

    @api.doc('deletar_usuario')
    @api.response(204, 'Usuário deletado')
    def delete(self, usuario_id):
        """Deleta um usuário"""
        query = f"SELECT * FROM usuarios u WHERE u.id = '{usuario_id}'"
        usuarios = list(container.query_items(query=query, enable_cross_partition_query=True))

        if not usuarios:
            api.abort(404, "Usuário não encontrado")

        container.delete_item(item=usuarios[0]["id"], partition_key=usuarios[0]["cpf"])
        return '', 204

@api.route('/email/<string:email>')
@api.param('email', 'Email do usuário')
@api.response(404, 'Usuário não encontrado')
class UsuarioEmailResource(Resource):
    @api.doc('buscar_usuario_por_email')
    @api.marshal_with(usuario_model)
    def get(self, email):
        """Busca um usuário pelo email"""
        query = f"SELECT * FROM usuarios u WHERE u.email = '{email}'"
        usuarios = list(container.query_items(query=query, enable_cross_partition_query=True))

        if not usuarios:
            api.abort(404, "Usuário não encontrado")

        return usuarios[0]
