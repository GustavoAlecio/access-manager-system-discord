# Bot de Assinaturas para Discord

Este projeto é um bot de Discord focado em gerenciamento de assinaturas de um servidor fechado (por exemplo, grupo VIP de apostas).

## O que o bot faz

* Envia mensagem de boas-vindas por DM quando um novo membro entra no servidor.
* Mostra um menu de opções:

  * "Comprar Plano" → envia link para o site de pagamento e suporte no Telegram.
  * "Suporte" → envia link direto do suporte no Telegram.
* Permite que administradores/suporte:

  * Confirmem pagamento e liberem o acesso do usuário usando comandos:

    * `!confirmar @usuario` (abre botões para plano de 30 ou 90 dias)
    * `!liberar30 @usuario`
    * `!liberar90 @usuario`
* Ao liberar o usuário:

  * Atualiza o apelido do membro no servidor para o formato:
    `Nome | DD/MM/AAAA` (data de expiração do plano)
  * Cria (se necessário) e aplica o cargo ASSINANTE.
  * Libera o acesso a um canal de apostas (por ID).
* Possui um loop automático que roda a cada 12 horas:

  * Lê a data de expiração do apelido.
  * Se a assinatura expira hoje, envia DM avisando e um botão para renovação.
  * Se a assinatura está expirada, remove o cargo ASSINANTE e manda DM orientando a renovar.
* Quando o cargo ASSINANTE é removido manualmente:

  * O bot tenta resetar o apelido do usuário.
  * Remove o usuário do dicionário interno de assinaturas ativas.

---

## Requisitos

* Python 3.10+ (recomendado 3.11 ou 3.12)
* Conta no Discord com um bot registrado e o token em mãos.
* Um servidor no Discord (guild) onde o bot será adicionado.
* IDs dos seguintes recursos no Discord:

  * SERVER_ID → ID do servidor
  * SUPORTE_CHANNEL_ID → canal onde a staff acompanha compras/renovações
  * APOSTAS_CHANNEL_ID → canal VIP liberado para assinantes
  * NOTIFICACAO_CHANNEL_ID → (opcional, se for usado no futuro)
  * BOAS_VINDAS_CHANNEL_ID → (opcional, se quiser usar para logs públicos)

---

## Variáveis de ambiente (.env)

Na raiz do projeto, crie um arquivo chamado `.env` com o conteúdo (exemplo):

DISCORD_TOKEN=SEU_TOKEN_DO_BOT_AQUI
SERVER_ID=123456789012345678
SUPORTE_CHANNEL_ID=123456789012345679
APOSTAS_CHANNEL_ID=123456789012345680
NOTIFICACAO_CHANNEL_ID=123456789012345681
BOAS_VINDAS_CHANNEL_ID=123456789012345682

* Substitua SEU_TOKEN_DO_BOT_AQUI pelo token real do bot.
* Todos os IDs são números inteiros que você copia no Discord com o Modo Desenvolvedor ativado (Configurações → Avançado → Modo desenvolvedor → botão direito no canal/servidor → "Copiar ID").

---

## Instalação e execução local

### 1. Clonar o projeto

No seu computador:

git clone SEU_REPOSITORIO_URL.git
cd SEU_REPOSITORIO

### 2. Criar e ativar ambiente virtual

python -m venv .venv

# macOS / Linux

source .venv/bin/activate

# Windows (PowerShell)

# .venv\Scripts\Activate.ps1

### 3. Instalar dependências

Certifique-se de ter um arquivo `requirements.txt` com:

discord.py>=2.3.2
python-dotenv>=1.0.0

Depois rode:

pip install --upgrade pip
pip install -r requirements.txt

### 4. Criar o arquivo `.env`

Na raiz do projeto, crie o `.env` com as variáveis descritas acima.

### 5. Rodar o bot localmente

python bot.py

* Se tudo estiver correto, o bot ficará online no Discord.
* Testes básicos:

  * Entrar no servidor com uma conta de teste (deve receber a DM de boas-vindas).
  * Usar `!confirmar @usuario` ou `!liberar30 @usuario` com uma conta admin.

---

## Deploy na Google Cloud – Compute Engine (VM Linux)

A ideia aqui é rodar o bot em uma VM Linux (Ubuntu/Debian) na GCP, com o bot rodando como um serviço systemd para ficar ligado 24/7.

### Passo 1 – Criar a VM na GCP

1. Acesse o console da Google Cloud.
2. Vá em Compute Engine → Instâncias de VM.
3. Clique em Criar instância.
4. Sugestão de configuração:

   * Série/máquina: e2-micro ou similar (baixo custo).
   * Sistema operacional: Ubuntu LTS ou Debian.
   * Disco: 10 GB ou mais (pouco uso, só código e logs).
5. Libere acesso SSH (padrão).
6. Crie a instância.

### Passo 2 – Acessar a VM

No console da GCP, clique em SSH na instância que você criou.

### Passo 3 – Instalar dependências na VM

Dentro da VM (Ubuntu/Debian):

sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-venv python3-pip git

### Passo 4 – Clonar o projeto na VM

Escolha uma pasta, por exemplo `/opt`:

cd /opt
sudo mkdir discord-bot
sudo chown $USER:$USER discord-bot
cd discord-bot

git clone SEU_REPOSITORIO_URL.git .

(Obs: o ponto final faz o git clonar direto na pasta atual.)

### Passo 5 – Criar ambiente virtual e instalar requirements

python3 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt

### Passo 6 – Criar o `.env` na VM

Ainda dentro da pasta do projeto:

nano .env

Cole o mesmo conteúdo de `.env` que você usa localmente (token e IDs), salve e feche.

ctr + o
ctr + x

### Passo 7 – Testar o bot manualmente na VM

Com o ambiente virtual ativo:

python bot_discord.py

* Verifique no Discord se o bot ficou online.
* Se estiver ok, pare o processo com Ctrl + C.
* Em seguida, configure como serviço.

---

## Rodando o bot como serviço (systemd)

Vamos fazer o bot iniciar sozinho ao ligar a VM e reiniciar se cair.

### Passo 8 – Criar o arquivo de serviço systemd

sudo nano /etc/systemd/system/discord-bot.service

Conteúdo sugerido:

[Unit]
Description=Discord Bot de Assinaturas
After=network.target

[Service]
Type=simple
User=gctecnologia2
WorkingDirectory=/opt/discord-bot
ExecStart=/opt/discord-bot/.venv/bin/python /opt/discord-bot/bot_discord.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target

* Substitua SEU_USUARIO pelo usuário retornado pelo comando `whoami`.
* Ajuste WorkingDirectory e ExecStart se tiver usado outro caminho.

Salve o arquivo.

### Passo 9 – Recarregar o systemd e iniciar o serviço

sudo systemctl daemon-reload
sudo systemctl start discord-bot
sudo systemctl enable discord-bot

* `start` → inicia o serviço agora.
* `enable` → inicia automaticamente quando a VM ligar.

### Passo 10 – Verificar status e logs

Status:

sudo systemctl status discord-bot

Logs em tempo real:

sudo journalctl -u discord-bot -f

Se algo der erro (token inválido, permissão, etc.), aparecerá aqui.

---

## Atualizando o bot em produção

Quando fizer alterações no código:

1. Acesse a VM via SSH.
2. Vá até a pasta do bot:

cd /opt/discord-bot
git pull
source .venv/bin/activate
pip install -r requirements.txt   # se houver novas dependências

3. Reinicie o serviço:

sudo systemctl restart discord-bot

4. Verifique se subiu sem erros:

sudo systemctl status discord-bot

---

## Arquivos importantes do projeto

* bot.py → arquivo principal do bot (toda a lógica que interage com o Discord).
* .env → credenciais e IDs do servidor/canais.
* requirements.txt → dependências Python.
* bot.log → arquivo de log local gerenciado pelo RotatingFileHandler do código.



python -m venv .venv
source .venv/bin/activate   # macOS / Linux
# no Windows: .venv\Scripts\activate

pip install --upgrade pip
pip install -r requirements.txt

python bot.py
