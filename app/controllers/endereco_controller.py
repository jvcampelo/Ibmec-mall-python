from flask import Blueprint, request, jsonify
from flask_restx import Namespace, Resource, fields
from app.cosmosdb import container
from app.models.endereco import Endereco
from app.models.usuario import Usuario

endereco_bp = Blueprint("endereco", __name__)
api = Namespace('enderecos', description='Operações relacionadas a endereços')

# Modelos para documentação Swagger
endereco_model = api.model('Endereco', {
    'id': fields.String(readonly=True, description='Identificador único do endereço'),
    'usuarioId': fields.String(required=True, description='ID do usuário dono do endereço'),
    'cep': fields.String(required=True, description='CEP do endereço'),
    'logradouro': fields.String(required=True, description='Logradouro do endereço'),
    'numero': fields.String(required=True, description='Número do endereço'),
    'complemento': fields.String(description='Complemento do endereço'),
    'bairro': fields.String(required=True, description='Bairro do endereço'),
    'cidade': fields.String(required=True, description='Cidade do endereço'),
    'estado': fields.String(required=True, description='Estado do endereço'),
    'pais': fields.String(required=True, description='País do endereço')
})

@api.route('')
class EnderecoList(Resource):
    @api.doc('listar_enderecos')
    @api.marshal_list_with(endereco_model)
    def get(self):
        """Lista todos os endereços"""
        query = "SELECT * FROM enderecos"
        enderecos = list(container.query_items(query=query, enable_cross_partition_query=True))
        return enderecos

    @api.doc('criar_endereco')
    @api.expect(endereco_model)
    @api.marshal_with(endereco_model, code=201)
    def post(self):
        """Cria um novo endereço"""
        dados = request.json
        
        if not dados.get("usuarioId") or not dados.get("cep") or not dados.get("logradouro") or not dados.get("numero") or not dados.get("bairro") or not dados.get("cidade") or not dados.get("estado") or not dados.get("pais"):
            api.abort(400, "Todos os campos são obrigatórios exceto complemento")

        novo_endereco = Endereco(
            usuarioId=dados["usuarioId"],
            cep=dados["cep"],
            logradouro=dados["logradouro"],
            numero=dados["numero"],
            complemento=dados.get("complemento"),
            bairro=dados["bairro"],
            cidade=dados["cidade"],
            estado=dados["estado"],
            pais=dados["pais"]
        )

        container.create_item(novo_endereco.to_dict())
        return novo_endereco.to_dict(), 201

@api.route('/<string:endereco_id>')
@api.param('endereco_id', 'Identificador do endereço')
@api.response(404, 'Endereço não encontrado')
class EnderecoResource(Resource):
    @api.doc('buscar_endereco')
    @api.marshal_with(endereco_model)
    def get(self, endereco_id):
        """Busca um endereço pelo ID"""
        query = f"SELECT * FROM enderecos e WHERE e.id = '{endereco_id}'"
        enderecos = list(container.query_items(query=query, enable_cross_partition_query=True))

        if not enderecos:
            api.abort(404, "Endereço não encontrado")

        return enderecos[0]

    @api.doc('atualizar_endereco')
    @api.expect(endereco_model)
    @api.marshal_with(endereco_model)
    def put(self, endereco_id):
        """Atualiza um endereço existente"""
        query = f"SELECT * FROM enderecos e WHERE e.id = '{endereco_id}'"
        enderecos = list(container.query_items(query=query, enable_cross_partition_query=True))

        if not enderecos:
            api.abort(404, "Endereço não encontrado")

        endereco = enderecos[0]
        dados = request.json
        endereco.update({
            "usuarioId": dados.get("usuarioId", endereco["usuarioId"]),
            "cep": dados.get("cep", endereco["cep"]),
            "logradouro": dados.get("logradouro", endereco["logradouro"]),
            "numero": dados.get("numero", endereco["numero"]),
            "complemento": dados.get("complemento", endereco["complemento"]),
            "bairro": dados.get("bairro", endereco["bairro"]),
            "cidade": dados.get("cidade", endereco["cidade"]),
            "estado": dados.get("estado", endereco["estado"]),
            "pais": dados.get("pais", endereco["pais"])
        })

        container.replace_item(item=endereco["id"], body=endereco)
        return endereco

    @api.doc('deletar_endereco')
    @api.response(204, 'Endereço deletado')
    def delete(self, endereco_id):
        """Deleta um endereço"""
        query = f"SELECT * FROM enderecos e WHERE e.id = '{endereco_id}'"
        enderecos = list(container.query_items(query=query, enable_cross_partition_query=True))

        if not enderecos:
            api.abort(404, "Endereço não encontrado")

        container.delete_item(item=enderecos[0]["id"], partition_key=enderecos[0]["usuarioId"])
        return '', 204

@api.route('/usuario/<string:usuario_id>')
@api.param('usuario_id', 'ID do usuário')
@api.response(404, 'Nenhum endereço encontrado')
class EnderecoUsuarioResource(Resource):
    @api.doc('buscar_enderecos_por_usuario')
    @api.marshal_list_with(endereco_model)
    def get(self, usuario_id):
        """Busca todos os endereços de um usuário"""
        query = f"SELECT * FROM enderecos e WHERE e.usuarioId = '{usuario_id}'"
        enderecos = list(container.query_items(query=query, enable_cross_partition_query=True))

        if not enderecos:
            api.abort(404, "Nenhum endereço encontrado para este usuário")

        return enderecos

@endereco_bp.route("/usuario/<int:usuario_id>", methods=["POST"])
def criar_endereco(usuario_id):
    dados = request.json
    
    if not Usuario.query.get(usuario_id):
        return jsonify({"erro": "Usuário não encontrado"}), 404
    
    # Validar campos obrigatórios
    campos_obrigatorios = ["logradouro", "bairro", "cidade", "uf", "cep"]
    for campo in campos_obrigatorios:
        if not dados.get(campo):
            return jsonify({"erro": f"O campo '{campo}' é obrigatório"}), 400
    
    endereco = Endereco(
        usuario_id=usuario_id,
        logradouro=dados["logradouro"],
        complemento=dados.get("complemento"),
        bairro=dados["bairro"],
        cidade=dados["cidade"],
        uf=dados["uf"],
        cep=dados["cep"],
        pais=dados.get("pais", "Brasil"),
        tipo=dados.get("tipo")
    )
    
    try:
        db.session.add(endereco)
        db.session.commit()
        return jsonify({"mensagem": "Endereço criado com sucesso", "id": endereco.id}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"erro": "Erro ao criar endereço"}), 500

@endereco_bp.route("/usuario/<int:usuario_id>", methods=["GET"])
def listar_enderecos(usuario_id):
    if not Usuario.query.get(usuario_id):
        return jsonify({"erro": "Usuário não encontrado"}), 404
        
    enderecos = Endereco.query.filter_by(usuario_id=usuario_id).all()
    if not enderecos:
        return jsonify({"erro": "Nenhum endereço encontrado para este usuário"}), 404
        
    return jsonify([{
        "id": e.id,
        "logradouro": e.logradouro,
        "complemento": e.complemento,
        "bairro": e.bairro,
        "cidade": e.cidade,
        "uf": e.uf,
        "cep": e.cep,
        "pais": e.pais,
        "tipo": e.tipo
    } for e in enderecos]), 200

@endereco_bp.route("/<int:endereco_id>", methods=["PUT"])
def atualizar_endereco(endereco_id):
    endereco = Endereco.query.get(endereco_id)
    if not endereco:
        return jsonify({"erro": "Endereço não encontrado"}), 404
    
    dados = request.json
    if not dados:
        return jsonify({"erro": "O corpo da requisição não pode estar vazio"}), 400
    
    endereco.logradouro = dados.get("logradouro", endereco.logradouro)
    endereco.complemento = dados.get("complemento", endereco.complemento)
    endereco.bairro = dados.get("bairro", endereco.bairro)
    endereco.cidade = dados.get("cidade", endereco.cidade)
    endereco.uf = dados.get("uf", endereco.uf)
    endereco.cep = dados.get("cep", endereco.cep)
    endereco.pais = dados.get("pais", endereco.pais)
    endereco.tipo = dados.get("tipo", endereco.tipo)
    
    try:
        db.session.commit()
        return jsonify({"mensagem": "Endereço atualizado com sucesso"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"erro": "Erro ao atualizar endereço"}), 500

@endereco_bp.route("/<int:endereco_id>", methods=["DELETE"])
def deletar_endereco(endereco_id):
    endereco = Endereco.query.get(endereco_id)
    if not endereco:
        return jsonify({"erro": "Endereço não encontrado"}), 404
    
    db.session.delete(endereco)
    db.session.commit()
    
    return jsonify({"mensagem": "Endereço deletado com sucesso"}), 200