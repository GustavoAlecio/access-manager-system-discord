import os
from dotenv import load_dotenv

load_dotenv()

# Variáveis de ambiente
TOKEN = os.getenv("DISCORD_TOKEN")
SERVER_ID = int(os.getenv("SERVER_ID"))
SUPORTE_CHANNEL_ID = int(os.getenv("SUPORTE_CHANNEL_ID"))
APOSTAS_CHANNEL_ID = int(os.getenv("APOSTAS_CHANNEL_ID"))
NOTIFICACAO_CHANNEL_ID = int(os.getenv("NOTIFICACAO_CHANNEL_ID"))
CARGO_ASSINANTE_NOME = "ASSINANTE"

# Configurações do bot
PREFIXO = "!"
TEMPO_TIMEOUT_VIEW = 172800  # 48 horas em segundos
INTERVALO_CHECAGEM = 12  # horas

# URLs
URL_COMPRA = "https://gustavocorrea.com.br/"
URL_SUPORTE = "https://t.me/suportegstv"