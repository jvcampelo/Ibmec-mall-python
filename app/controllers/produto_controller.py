from flask import Blueprint, request, jsonify
from flask_restx import Namespace, Resource, fields
from app.cosmosdb import container
from app.models.produto import Produto

produto_bp = Blueprint("produto", __name__)
api = Namespace('produtos', description='Operações relacionadas a produtos')

# Modelos para documentação Swagger
produto_model = api.model('Produto', {
    'id': fields.String(readonly=True, description='Identificador único do produto'),
    'produtoCategoria': fields.String(required=True, description='Categoria do produto'),
    'nome': fields.String(required=True, description='Nome do produto'),
    'preco': fields.Float(required=True, description='Preço do produto'),
    'urlImagem': fields.String(description='URL da imagem do produto'),
    'descricao': fields.String(description='Descrição do produto')
})

@api.route('')
class ProdutoList(Resource):
    @api.doc('listar_produtos')
    @api.marshal_list_with(produto_model)
    def get(self):
        """Lista todos os produtos"""
        query = "SELECT * FROM produtos"
        produtos = list(container.query_items(query=query, enable_cross_partition_query=True))
        return produtos

    @api.doc('criar_produto')
    @api.expect(produto_model)
    @api.marshal_with(produto_model, code=201)
    def post(self):
        """Cria um novo produto"""
        dados = request.json
        
        if not dados.get("produtoCategoria") or not dados.get("nome") or not dados.get("preco"):
            api.abort(400, "Categoria, nome e preço são obrigatórios")

        novo_produto = Produto(
            produtoCategoria=dados["produtoCategoria"],
            nome=dados["nome"],
            preco=dados["preco"],
            urlImagem=dados.get("urlImagem"),
            descricao=dados.get("descricao")
        )

        container.create_item(novo_produto.to_dict())
        return novo_produto.to_dict(), 201

@api.route('/<string:produto_id>')
@api.param('produto_id', 'Identificador do produto')
@api.response(404, 'Produto não encontrado')
class ProdutoResource(Resource):
    @api.doc('buscar_produto')
    @api.marshal_with(produto_model)
    def get(self, produto_id):
        """Busca um produto pelo ID"""
        query = f"SELECT * FROM produtos p WHERE p.id = '{produto_id}'"
        produtos = list(container.query_items(query=query, enable_cross_partition_query=True))

        if not produtos:
            api.abort(404, "Produto não encontrado")

        return produtos[0]

    @api.doc('atualizar_produto')
    @api.expect(produto_model)
    @api.marshal_with(produto_model)
    def put(self, produto_id):
        """Atualiza um produto existente"""
        query = f"SELECT * FROM produtos p WHERE p.id = '{produto_id}'"
        produtos = list(container.query_items(query=query, enable_cross_partition_query=True))

        if not produtos:
            api.abort(404, "Produto não encontrado")

        produto = produtos[0]
        dados = request.json
        produto.update({
            "produtoCategoria": dados.get("produtoCategoria", produto["produtoCategoria"]),
            "nome": dados.get("nome", produto["nome"]),
            "preco": dados.get("preco", produto["preco"]),
            "urlImagem": dados.get("urlImagem", produto["urlImagem"]),
            "descricao": dados.get("descricao", produto["descricao"]),
        })

        container.replace_item(item=produto["id"], body=produto)
        return produto

    @api.doc('deletar_produto')
    @api.response(204, 'Produto deletado')
    def delete(self, produto_id):
        """Deleta um produto"""
        query = f"SELECT * FROM produtos p WHERE p.id = '{produto_id}'"
        produtos = list(container.query_items(query=query, enable_cross_partition_query=True))

        if not produtos:
            api.abort(404, "Produto não encontrado")

        container.delete_item(item=produtos[0]["id"], partition_key=produtos[0]["produtoCategoria"])
        return '', 204

@api.route('/nome/<string:nome>')
@api.param('nome', 'Nome do produto')
@api.response(404, 'Produto não encontrado')
class ProdutoNomeResource(Resource):
    @api.doc('buscar_produto_por_nome')
    @api.marshal_with(produto_model)
    def get(self, nome):
        """Busca um produto pelo nome"""
        query = f"SELECT * FROM produtos p WHERE p.nome = '{nome}'"
        produtos = list(container.query_items(query=query, enable_cross_partition_query=True))

        if not produtos:
            api.abort(404, "Produto não encontrado")

        return produtos[0]
