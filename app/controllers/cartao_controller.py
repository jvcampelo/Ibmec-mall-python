from flask import Blueprint, request, jsonify
from flask_restx import Namespace, Resource, fields
from app.database import db
from app.models.usuario import Usuario
from app.models.cartao import Cartao
from app.request.transacao_request import TransacaoRequest
from app.response.transacao_response import TransacaoResponse
from datetime import datetime
import uuid
from decimal import Decimal
from dateutil.relativedelta import relativedelta
from app.cosmosdb import container

cartao_bp = Blueprint("cartao", __name__)
api = Namespace('cartoes', description='Operações relacionadas a cartões')

# Modelos para documentação Swagger
cartao_model = api.model('Cartao', {
    'id': fields.String(readonly=True, description='Identificador único do cartão'),
    'usuarioId': fields.String(required=True, description='ID do usuário dono do cartão'),
    'numero': fields.String(required=True, description='Número do cartão'),
    'nomeTitular': fields.String(required=True, description='Nome do titular do cartão'),
    'dataValidade': fields.String(required=True, description='Data de validade do cartão'),
    'cvv': fields.String(required=True, description='Código de segurança do cartão'),
    'bandeira': fields.String(required=True, description='Bandeira do cartão'),
    'tipo': fields.String(required=True, description='Tipo do cartão (crédito/débito)'),
    'principal': fields.Boolean(description='Indica se é o cartão principal do usuário')
})

# Criar um novo cartão
@cartao_bp.route("/usuario/<int:id_user>", methods=["POST"])
def create_cartao(id_user):
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"erro": "O corpo da requisição não pode estar vazio"}), 400

        usuario = Usuario.query.get(id_user)
        if not usuario:
            return jsonify({"erro": "Usuário não encontrado"}), 404
        
        # Validar campos obrigatórios
        campos_obrigatorios = ["numero", "nome_impresso", "validade", "cvv", "bandeira"]
        for campo in campos_obrigatorios:
            if not data.get(campo):
                return jsonify({"erro": f"O campo '{campo}' é obrigatório"}), 400
        
        # Verificar se já existe um cartão com o mesmo número para este usuário
        cartao_existente = Cartao.query.filter_by(
            usuario_id=id_user,
            numero=data["numero"]
        ).first()
        
        if cartao_existente:
            return jsonify({"erro": "Já existe um cartão cadastrado com este número para este usuário"}), 400
        
        mes, ano = map(int, data["validade"].split("/"))
        validade = datetime(ano, mes, 1) + relativedelta(day=31)

        novo_cartao = Cartao(
            usuario_id=id_user,
            numero=data["numero"],
            nome_impresso=data["nome_impresso"],
            validade=validade,
            cvv=data["cvv"],
            bandeira=data["bandeira"],
            tipo=data.get("tipo", ""),
            saldo=data.get("saldo", 0.00),
        )

        db.session.add(novo_cartao)
        db.session.commit()

        return jsonify({"mensagem": "Cartão criado com sucesso", "cartao_id": novo_cartao.id}), 201
        
    except ValueError:
        return jsonify({"erro": "Formato de data inválido. Use o formato MM/AAAA"}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"erro": "Erro ao criar cartão"}), 500


# Autorizar uma transação
@cartao_bp.route("/authorize/usuario/<int:id_user>", methods=["POST"])
def authorize_transaction(id_user):
    try:
        data = request.get_json()
        transacao = TransacaoRequest(**data)  # Validação automática com Pydantic

        usuario = Usuario.query.get(id_user)
        if not usuario:
            return jsonify(TransacaoResponse(
                status="NOT_AUTHORIZED",
                codigo_autorizacao=None,
                dt_transacao=datetime.utcnow(),
                message="Usuário não encontrado"
            ).model_dump()), 404

        # Buscar o cartão do usuário
        cartao = Cartao.query.filter_by(usuario_id=id_user, numero=transacao.numero, cvv=transacao.cvv).first()
        if not cartao:
            return jsonify(TransacaoResponse(
                status="NOT_AUTHORIZED",
                codigo_autorizacao=None,
                dt_transacao=datetime.utcnow(),
                message="Cartão não encontrado"
            ).model_dump()), 404
        
         # Pegar a validade informada na requisição
        mes, ano = map(int, transacao.dt_expiracao.split("/"))
        validade_requisicao = datetime(ano, mes, 1) + relativedelta(day=31)

        # Verificar se o cartão está expirado
        if cartao.validade < datetime.utcnow():
            return jsonify(TransacaoResponse(
                status="NOT_AUTHORIZED",
                codigo_autorizacao=None,
                dt_transacao=datetime.utcnow(),
                message="Cartão expirado"
            ).model_dump()), 400
        
        # Verificar se a validade informada na transação bate com a validade cadastrada no banco
        if cartao.validade != validade_requisicao:
            return jsonify(TransacaoResponse(
                status="NOT_AUTHORIZED",
                codigo_autorizacao=None,
                dt_transacao=datetime.utcnow(),
                message="Validade incorreta"
            ).model_dump()), 400

        # Verificar saldo disponível
        if cartao.saldo < Decimal(str(transacao.valor)):
            return jsonify(TransacaoResponse(
                status="NOT_AUTHORIZED",
                codigo_autorizacao=None,
                dt_transacao=datetime.utcnow(),
                message="Saldo insuficiente"
            ).model_dump()), 400

        # Deduzir o valor da compra do saldo
        cartao.saldo -= Decimal(str(transacao.valor))
        db.session.commit()

        # Criar resposta com sucesso
        return jsonify(TransacaoResponse(
            status="AUTHORIZED",
            codigo_autorizacao=uuid.uuid4(),
            dt_transacao=datetime.utcnow(),
            message="Compra autorizada"
        ).model_dump()), 200

    except Exception as e:
        return jsonify({"status": "ERROR", "message": str(e)}), 500

# Atualizar o saldo de um cartão
@cartao_bp.route("/saldo/<int:id_cartao>", methods=["PUT"])
def update_saldo(id_cartao):
    try:
        data = request.get_json()
        
        if 'saldo' not in data:
            return jsonify({"message": "O campo 'saldo' é obrigatório"}), 400
            
        cartao = Cartao.query.get(id_cartao)
        if not cartao:
            return jsonify({"message": "Cartão não encontrado"}), 404
        
        # Soma o novo valor ao saldo atual do cartão
        cartao.saldo += Decimal(str(data['saldo']))
        db.session.commit()
        
        return jsonify({
            "message": "Saldo atualizado com sucesso",
            "cartao_id": cartao.id,
            "saldo": float(cartao.saldo)
        }), 200
        
    except Exception as e:
        return jsonify({"status": "ERROR", "message": str(e)}), 500
        
# Deletar um cartão
@cartao_bp.route("/<int:id_cartao>", methods=["DELETE"])
def delete_cartao(id_cartao):
    try:
        cartao = Cartao.query.get(id_cartao)
        if not cartao:
            return jsonify({"message": "Cartão não encontrado"}), 404
            
        db.session.delete(cartao)
        db.session.commit()
        
        return jsonify({"message": "Cartão deletado com sucesso"}), 200
        
    except Exception as e:
        return jsonify({"status": "ERROR", "message": str(e)}), 500

@cartao_bp.route("/usuario/<int:id_user>", methods=["GET"])
def listar_cartoes_usuario(id_user):
    try:
        usuario = Usuario.query.get(id_user)
        if not usuario:
            return jsonify({"erro": "Usuário não encontrado"}), 404
            
        cartoes = Cartao.query.filter_by(usuario_id=id_user).all()
        if not cartoes:
            return jsonify({"erro": "Nenhum cartão encontrado para este usuário"}), 404
            
        resultado = []
        for cartao in cartoes:
            mes = cartao.validade.month
            ano = cartao.validade.year
            validade_formatada = f"{mes:02d}/{ano}"
            
            resultado.append({
                "id": cartao.id,
                "numero": cartao.numero,
                "nome_impresso": cartao.nome_impresso,
                "validade": validade_formatada,
                "cvv": cartao.cvv,
                "bandeira": cartao.bandeira,
                "tipo": cartao.tipo,
                "saldo": float(cartao.saldo)
            })
            
        return jsonify(resultado), 200
            
    except Exception as e:
        return jsonify({"erro": "Erro ao listar cartões"}), 500

@api.route('')
class CartaoList(Resource):
    @api.doc('listar_cartoes')
    @api.marshal_list_with(cartao_model)
    def get(self):
        """Lista todos os cartões"""
        query = "SELECT * FROM cartoes"
        cartoes = list(container.query_items(query=query, enable_cross_partition_query=True))
        return cartoes

    @api.doc('criar_cartao')
    @api.expect(cartao_model)
    @api.marshal_with(cartao_model, code=201)
    def post(self):
        """Cria um novo cartão"""
        dados = request.json
        
        if not dados.get("usuarioId") or not dados.get("numero") or not dados.get("nomeTitular") or not dados.get("dataValidade") or not dados.get("cvv") or not dados.get("bandeira") or not dados.get("tipo"):
            api.abort(400, "Todos os campos são obrigatórios exceto principal")

        novo_cartao = Cartao(
            usuarioId=dados["usuarioId"],
            numero=dados["numero"],
            nomeTitular=dados["nomeTitular"],
            dataValidade=dados["dataValidade"],
            cvv=dados["cvv"],
            bandeira=dados["bandeira"],
            tipo=dados["tipo"],
            principal=dados.get("principal", False)
        )

        container.create_item(novo_cartao.to_dict())
        return novo_cartao.to_dict(), 201

@api.route('/<string:cartao_id>')
@api.param('cartao_id', 'Identificador do cartão')
@api.response(404, 'Cartão não encontrado')
class CartaoResource(Resource):
    @api.doc('buscar_cartao')
    @api.marshal_with(cartao_model)
    def get(self, cartao_id):
        """Busca um cartão pelo ID"""
        query = f"SELECT * FROM cartoes c WHERE c.id = '{cartao_id}'"
        cartoes = list(container.query_items(query=query, enable_cross_partition_query=True))

        if not cartoes:
            api.abort(404, "Cartão não encontrado")

        return cartoes[0]

    @api.doc('atualizar_cartao')
    @api.expect(cartao_model)
    @api.marshal_with(cartao_model)
    def put(self, cartao_id):
        """Atualiza um cartão existente"""
        query = f"SELECT * FROM cartoes c WHERE c.id = '{cartao_id}'"
        cartoes = list(container.query_items(query=query, enable_cross_partition_query=True))

        if not cartoes:
            api.abort(404, "Cartão não encontrado")

        cartao = cartoes[0]
        dados = request.json
        cartao.update({
            "usuarioId": dados.get("usuarioId", cartao["usuarioId"]),
            "numero": dados.get("numero", cartao["numero"]),
            "nomeTitular": dados.get("nomeTitular", cartao["nomeTitular"]),
            "dataValidade": dados.get("dataValidade", cartao["dataValidade"]),
            "cvv": dados.get("cvv", cartao["cvv"]),
            "bandeira": dados.get("bandeira", cartao["bandeira"]),
            "tipo": dados.get("tipo", cartao["tipo"]),
            "principal": dados.get("principal", cartao["principal"])
        })

        container.replace_item(item=cartao["id"], body=cartao)
        return cartao

    @api.doc('deletar_cartao')
    @api.response(204, 'Cartão deletado')
    def delete(self, cartao_id):
        """Deleta um cartão"""
        query = f"SELECT * FROM cartoes c WHERE c.id = '{cartao_id}'"
        cartoes = list(container.query_items(query=query, enable_cross_partition_query=True))

        if not cartoes:
            api.abort(404, "Cartão não encontrado")

        container.delete_item(item=cartoes[0]["id"], partition_key=cartoes[0]["usuarioId"])
        return '', 204

@api.route('/usuario/<string:usuario_id>')
@api.param('usuario_id', 'ID do usuário')
@api.response(404, 'Nenhum cartão encontrado')
class CartaoUsuarioResource(Resource):
    @api.doc('buscar_cartoes_por_usuario')
    @api.marshal_list_with(cartao_model)
    def get(self, usuario_id):
        """Busca todos os cartões de um usuário"""
        query = f"SELECT * FROM cartoes c WHERE c.usuarioId = '{usuario_id}'"
        cartoes = list(container.query_items(query=query, enable_cross_partition_query=True))

        if not cartoes:
            api.abort(404, "Nenhum cartão encontrado para este usuário")

        return cartoes

@api.route('/usuario/<string:usuario_id>/principal')
@api.param('usuario_id', 'ID do usuário')
@api.response(404, 'Cartão principal não encontrado')
class CartaoPrincipalResource(Resource):
    @api.doc('buscar_cartao_principal')
    @api.marshal_with(cartao_model)
    def get(self, usuario_id):
        """Busca o cartão principal de um usuário"""
        query = f"SELECT * FROM cartoes c WHERE c.usuarioId = '{usuario_id}' AND c.principal = true"
        cartoes = list(container.query_items(query=query, enable_cross_partition_query=True))

        if not cartoes:
            api.abort(404, "Cartão principal não encontrado")

        return cartoes[0]

    @api.doc('definir_cartao_principal')
    @api.param('cartao_id', 'ID do cartão a ser definido como principal')
    @api.response(204, 'Cartão principal atualizado')
    def put(self, usuario_id):
        """Define um cartão como principal"""
        cartao_id = request.args.get('cartao_id')
        if not cartao_id:
            api.abort(400, "ID do cartão é obrigatório")

        # Primeiro, remove o status de principal de todos os cartões do usuário
        query = f"SELECT * FROM cartoes c WHERE c.usuarioId = '{usuario_id}'"
        cartoes = list(container.query_items(query=query, enable_cross_partition_query=True))
        
        for cartao in cartoes:
            cartao["principal"] = False
            container.replace_item(item=cartao["id"], body=cartao)

        # Depois, define o novo cartão principal
        query = f"SELECT * FROM cartoes c WHERE c.id = '{cartao_id}' AND c.usuarioId = '{usuario_id}'"
        cartoes = list(container.query_items(query=query, enable_cross_partition_query=True))

        if not cartoes:
            api.abort(404, "Cartão não encontrado")

        cartao = cartoes[0]
        cartao["principal"] = True
        container.replace_item(item=cartao["id"], body=cartao)

        return '', 204

