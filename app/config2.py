import os
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

class Config:
    # Configuração do banco de dados MySQL
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "mysql+pymysql://usuario:senha@localhost/nome_do_banco")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Configuração do Azure Cosmos DB
    AZURE_COSMOS_URI = os.getenv("AZURE_COSMOS_URI", "https://seu-cosmos-db.documents.azure.com:443/")
    AZURE_COSMOS_KEY = os.getenv("AZURE_COSMOS_KEY", "sua-chave-cosmos-db")
    AZURE_COSMOS_DATABASE = os.getenv("AZURE_COSMOS_DATABASE", "nome-do-container")
