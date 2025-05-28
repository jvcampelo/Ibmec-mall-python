from flask import Blueprint, request, jsonify
from flask_restx import Namespace, Resource, fields
from app.cosmosdb import container
from app.models.pedido import Pedido
from datetime import datetime
from app.models.usuario import Usuario

pedido_bp = Blueprint("pedido", __name__)
api = Namespace('pedidos', description='Operações relacionadas a pedidos')

# Modelos para documentação Swagger
item_pedido_model = api.model('ItemPedido', {
    'produtoId': fields.String(required=True, description='ID do produto'),
    'quantidade': fields.Integer(required=True, description='Quantidade do produto'),
    'precoUnitario': fields.Float(required=True, description='Preço unitário do produto')
})

pedido_model = api.model('Pedido', {
    'id': fields.String(readonly=True, description='Identificador único do pedido'),
    'usuarioId': fields.String(required=True, description='ID do usuário que fez o pedido'),
    'enderecoId': fields.String(required=True, description='ID do endereço de entrega'),
    'cartaoId': fields.String(required=True, description='ID do cartão de pagamento'),
    'itens': fields.List(fields.Nested(item_pedido_model), required=True, description='Lista de itens do pedido'),
    'status': fields.String(required=True, description='Status do pedido'),
    'dataPedido': fields.String(readonly=True, description='Data do pedido'),
    'valorTotal': fields.Float(readonly=True, description='Valor total do pedido')
})

@api.route('')
class PedidoList(Resource):
    @api.doc('listar_pedidos')
    @api.marshal_list_with(pedido_model)
    def get(self):
        """Lista todos os pedidos"""
        query = "SELECT * FROM pedidos"
        pedidos = list(container.query_items(query=query, enable_cross_partition_query=True))
        return pedidos

    @api.doc('criar_pedido')
    @api.expect(pedido_model)
    @api.marshal_with(pedido_model, code=201)
    def post(self):
        """Cria um novo pedido"""
        dados = request.json
        
        if not dados.get("usuarioId") or not dados.get("enderecoId") or not dados.get("cartaoId") or not dados.get("itens"):
            api.abort(400, "Usuário, endereço, cartão e itens são obrigatórios")

        novo_pedido = Pedido(
            usuarioId=dados["usuarioId"],
            enderecoId=dados["enderecoId"],
            cartaoId=dados["cartaoId"],
            itens=dados["itens"],
            status="Pendente"
        )

        container.create_item(novo_pedido.to_dict())
        return novo_pedido.to_dict(), 201

@api.route('/<string:pedido_id>')
@api.param('pedido_id', 'Identificador do pedido')
@api.response(404, 'Pedido não encontrado')
class PedidoResource(Resource):
    @api.doc('buscar_pedido')
    @api.marshal_with(pedido_model)
    def get(self, pedido_id):
        """Busca um pedido pelo ID"""
        query = f"SELECT * FROM pedidos p WHERE p.id = '{pedido_id}'"
        pedidos = list(container.query_items(query=query, enable_cross_partition_query=True))

        if not pedidos:
            api.abort(404, "Pedido não encontrado")

        return pedidos[0]

    @api.doc('atualizar_pedido')
    @api.expect(pedido_model)
    @api.marshal_with(pedido_model)
    def put(self, pedido_id):
        """Atualiza um pedido existente"""
        query = f"SELECT * FROM pedidos p WHERE p.id = '{pedido_id}'"
        pedidos = list(container.query_items(query=query, enable_cross_partition_query=True))

        if not pedidos:
            api.abort(404, "Pedido não encontrado")

        pedido = pedidos[0]
        dados = request.json
        pedido.update({
            "usuarioId": dados.get("usuarioId", pedido["usuarioId"]),
            "enderecoId": dados.get("enderecoId", pedido["enderecoId"]),
            "cartaoId": dados.get("cartaoId", pedido["cartaoId"]),
            "itens": dados.get("itens", pedido["itens"]),
            "status": dados.get("status", pedido["status"])
        })

        container.replace_item(item=pedido["id"], body=pedido)
        return pedido

    @api.doc('deletar_pedido')
    @api.response(204, 'Pedido deletado')
    def delete(self, pedido_id):
        """Deleta um pedido"""
        query = f"SELECT * FROM pedidos p WHERE p.id = '{pedido_id}'"
        pedidos = list(container.query_items(query=query, enable_cross_partition_query=True))

        if not pedidos:
            api.abort(404, "Pedido não encontrado")

        container.delete_item(item=pedidos[0]["id"], partition_key=pedidos[0]["usuarioId"])
        return '', 204

@api.route('/usuario/<string:usuario_id>')
@api.param('usuario_id', 'ID do usuário')
@api.response(404, 'Nenhum pedido encontrado')
class PedidoUsuarioResource(Resource):
    @api.doc('buscar_pedidos_por_usuario')
    @api.marshal_list_with(pedido_model)
    def get(self, usuario_id):
        """Busca todos os pedidos de um usuário"""
        query = f"SELECT * FROM pedidos p WHERE p.usuarioId = '{usuario_id}'"
        pedidos = list(container.query_items(query=query, enable_cross_partition_query=True))

        if not pedidos:
            api.abort(404, "Nenhum pedido encontrado para este usuário")

        return pedidos

@api.route('/<string:pedido_id>/status')
@api.param('pedido_id', 'Identificador do pedido')
@api.param('status', 'Novo status do pedido')
@api.response(404, 'Pedido não encontrado')
class PedidoStatusResource(Resource):
    @api.doc('atualizar_status_pedido')
    @api.response(204, 'Status do pedido atualizado')
    def put(self, pedido_id):
        """Atualiza o status de um pedido"""
        status = request.args.get('status')
        if not status:
            api.abort(400, "Status é obrigatório")

        query = f"SELECT * FROM pedidos p WHERE p.id = '{pedido_id}'"
        pedidos = list(container.query_items(query=query, enable_cross_partition_query=True))

        if not pedidos:
            api.abort(404, "Pedido não encontrado")

        pedido = pedidos[0]
        pedido["status"] = status
        container.replace_item(item=pedido["id"], body=pedido)

        return '', 204

# Buscar pedidos por ID
@pedido_bp.route("/<int:id_pedido>", methods=["GET"])
def buscar_pedido_por_id(id_pedido):
    pedido = Pedido.query.get_or_404(id_pedido)

    return jsonify({
        "id": pedido.id_pedido,
        "cliente": pedido.nome_cliente,
        "produto": pedido.nome_produto,
        "data": pedido.data_pedido.strftime("%d/%m/%Y"),
        "valor": pedido.valor_total,
        "status": pedido.status
    })

# Buscar pedidos de um cliente
@pedido_bp.route("/nome/<string:nome_cliente>", methods=["GET"])
def listar_pedidos_por_nome(nome_cliente):
    pedidos = Pedido.query.filter(
        Pedido.nome_cliente.ilike(f"%{nome_cliente}%")
    ).all()

    return jsonify([
        {
            "id": p.id_pedido,
            "cliente": p.nome_cliente,
            "produto": p.nome_produto,
            "data": p.data_pedido.strftime("%d/%m/%Y"),
            "valor": p.valor_total,
            "status": p.status
        } for p in pedidos
    ])

# Criar um pedido
@pedido_bp.route("/", methods=["POST"])
def criar_pedido():
    dados = request.json
    # Obriga que os campos de nome de cliente, nome do produto e valor total do pedido necessariamente estejam escritos
    if not dados.get("nome_cliente") or not dados.get("nome_produto") or not dados.get("valor_total"):
        return jsonify({"erro": "Nome do cliente, nome dos produtos, preço e data da compra são obrigatórios"}), 400
    usuario = Usuario.query.filter(Usuario.nome.ilike(dados["nome_cliente"])).first()
    if not usuario:
        return jsonify({"erro": "Usuário não encontrado para o nome fornecido"}), 404

    novo_pedido = Pedido(
        nome_cliente=dados["nome_cliente"],
        data_pedido=datetime.strptime(dados["data_pedido"], "%Y-%m-%d"),
        nome_produto=dados["nome_produto"],
        valor_total=dados["valor_total"],
        status=dados["status"],
        id_usuario=usuario.id
    )

    db.session.add(novo_pedido)
    db.session.commit()
    return jsonify({"mensagem": "Pedido criado com sucesso", "id_pedido": novo_pedido.id_pedido}), 201

# Atualizar um pedido
@pedido_bp.route("/<int:id_pedido>", methods=["PUT"])
def atualizar_pedido(id_pedido):
    pedido = Pedido.query.get_or_404(id_pedido)
    data = request.json

    pedido.nome_cliente = data.get("nome_cliente", pedido.nome_cliente)
    pedido.data_pedido = datetime.strptime(data["data_pedido"], "%Y-%m-%d")
    pedido.nome_produto = data.get("nome_produto", pedido.nome_produto)
    pedido.valor_total = data.get("valor_total", pedido.valor_total)
    pedido.status = data.get("status", pedido.status)

    db.session.commit()
    return jsonify({"mensagem": "Pedido atualizado"})

# Deletar um pedido
@pedido_bp.route("/<int:id_pedido>", methods=["DELETE"])
def deletar_pedido(id_pedido):
    pedido = Pedido.query.get_or_404(id_pedido)
    db.session.delete(pedido)
    db.session.commit()
    return jsonify({"mensagem": "Pedido deletado"})
