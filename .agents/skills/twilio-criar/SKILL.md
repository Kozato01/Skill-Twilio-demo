---
name: twilio-criar
description: Cria e liga recursos na conta Twilio pela API, em segundos e sem clicar no console — flow do Studio, número de voz ou SMS apontando para o flow, Messaging Service, sender de WhatsApp no pool, Address do Conversations, serviço Sync, template do WhatsApp (Content), store do Conversation Memory, Functions e servidor ConversationRelay. Use sempre que o pedido for criar, publicar, configurar, ligar, trocar ou conferir algo da Twilio ("publica o flow", "liga esse número no flow", "cria um template", "o que tem nessa conta", "sobe o WhatsApp e a voz para um cliente novo"), mesmo sem citar a skill. Use também para planejar, montar e ensaiar uma demo ou POC de atendimento com IA por WhatsApp ou voz, de qualquer negócio.
---

# Twilio: criar rápido

Tudo passa por uma CLI só, sem dependências: `python <pasta desta skill>/scripts/tw.py <comando>`, **rodada na raiz
do projeto** (lê `TWILIO_ACCOUNT_SID` e `TWILIO_AUTH_TOKEN` do `.env` de lá; o ambiente vence).

## Como trabalhar

1. **Comece por `tw.py conta`.** Mostra de qual conta é a credencial e o que já existe. Evita criar duplicado e
   mexer na conta errada, e responde na hora "o que está ligado?". Se o projeto tem mais de uma conta, confira o nome
   antes de seguir.
2. **Rode o comando sem `--aplicar`.** Ele só lê a conta, valida e mostra o plano.
3. **Mostre o plano e peça confirmação antes de `--aplicar`** quando o recurso já atende gente ou gera custo:
   publicar sobre flow existente, trocar destino de número em uso, submeter template à Meta. Recurso novo e sem
   tráfego pode seguir direto, se o pedido já era criá-lo.
4. **Guarde o que saiu.** Os comandos imprimem linhas `NOME=SID`: ponha no `.env` e nos documentos do projeto. O `numero`
   imprime o destino anterior: anote, é o que permite desfazer.

Os comandos são idempotentes: rodar de novo encontra o recurso pelo nome em vez de duplicar.

## O que usar

| Pedido | Comando |
|---|---|
| Ver a conta, inclusive SIDs de Function para o `run-function` | `tw.py conta` |
| Ver erros recentes | `tw.py alertas -n 20` |
| Criar ou atualizar flow | `tw.py flow studio/x.json [--como NOME]` |
| Número → flow | `tw.py numero +55... --flow FW... --voz --sms [--status URL]` |
| Messaging Service + pool | `tw.py ms NOME --sender XE... --numero +55... [--inbound URL]` |
| WhatsApp entrando pelo Conversations | `tw.py conversas +55... --flow FW... --servico NOME --ms MG...` |
| Serviço Sync | `tw.py sync NOME [--acl]` (use `--acl` se guardar dado de cliente) |
| Template de WhatsApp | `tw.py template x.json [--submeter] [--categoria UTILITY]` |
| Store do Conversation Memory | `tw.py memoria NOME` |
| Formato de widget sem documentação | `tw.py sondar run-conversation-relay url voice` |

## Modelos em `assets/`

Copie para o projeto e adapte; não edite aqui.

- **`flow-base.json`**: mensagem, conversa e ligação em um flow só, com caminhos de falha. O `tw.py flow` troca cada
  `__VAR__` pela variável de mesmo nome no `.env` e recusa publicar se faltar alguma. Precisa de `PUBLIC_BASE_URL`,
  `STUDIO_TOKEN`, `VOZ_PUBLIC_URL` e `EMPRESA`. Salve com o nome que o flow deve ter: o nome do arquivo vira o nome do flow.
- **`servidor_base.py`**: o outro lado do flow, com `POST /ia/mensagem` e `wss /ia/voz`, já com token, assinatura e o
  fechamento certo da ligação. Vem com respostas fixas de uma empresa fictícia, para testar os canais sem LLM; depois,
  troque só a função `responder` pelo agente.
- **`template-botoes.json`**: template com botões e texto de reserva.
- **`functions/`**: `sync-token.js` e `caller-check.protected.js` (saudação pelo nome). Deploy, na raiz do projeto e com
  Node 20 ou 22: `npx twilio-run deploy --service-name NOME --runtime node22 --env functions/.env`. O `functions/.env` leva
  `ACCOUNT_SID` e `AUTH_TOKEN` (nesses nomes, sem `TWILIO_`: são os únicos que não sobem para a Function) e as variáveis
  das Functions. **Nunca aponte `--env` para o `.env` da raiz:** o `TWILIO_AUTH_TOKEN` subiria junto. Depois, pegue os SIDs
  em `tw.py conta` para o widget `run-function`.

## Se o pedido for uma demo

Leia [references/demo.md](references/demo.md) antes de criar recursos e **escreva o roteiro primeiro**: 5 ou 6 cenas, e só
se constrói o que aparece nelas. O guia cobre a ordem de construção, dados e reset, regras do agente, ensaio e checklist da
véspera. Nenhum modelo aqui é de um setor específico: adapte ao negócio pedido.

## Do zero até atender (WhatsApp + voz)

Gere o token do Studio (`python -c "import secrets; print(secrets.token_urlsafe(32))"`) e ponha as variáveis no `.env`. Então:

```
tw.py conta
tw.py flow studio/atendimento.json --aplicar          # guarde o FW...
tw.py ms atendimento --sender XE... --aplicar         # guarde o MG...
tw.py conversas +55... --flow FW... --servico atendimento --ms MG... --aplicar
tw.py numero +55... --flow FW... --voz --aplicar
```

Teste mandando uma mensagem e ligando. Se algo falhar, comece por `tw.py alertas`, depois Studio → Executions.

## O que a API não resolve

Avise o usuário destes passos em vez de tentar contorná-los:

- **Comprar número**: gera custo e, no Brasil, exige Regulatory Bundle. Console.
- **Registrar o sender de WhatsApp**: Self Sign-up no console (no popup, "Add a new phone number").
- **API key**: crie no console (Account → API keys). O segredo aparece uma vez só e não deve passar por esta conversa.
- **Aceitar o AI/ML Addendum**: requisito da ConversationRelay, no console.
- **Aprovação do template**: a Meta decide; acompanhe o status em `tw.py conta`.

## Armadilhas mais comuns

| Sintoma | Causa | Correção |
|---|---|---|
| Studio com 403, tudo parou | flow publicado com a URL de um backend fechado, ou ngrok velho | `PUBLIC_BASE_URL` = serviço público; publique de novo |
| 64101 ao abrir a ligação | `hints` com STT Google pt-BR | tirar `hints` |
| 64102 | WebSocket frio ou deploy no meio da ligação | não subir a voz durante teste; `min-instances 1` |
| 64105 depois da despedida | servidor fechou logo após o `end` | esperar a Twilio fechar (`servidor_base.py` já faz) |
| Ligação recusada, assinatura inválida | `VOZ_PUBLIC_URL` diferente da URL do widget | a mesma `wss://` exata nos dois lados |
| 21655 | `CONTENT_SID` de outra conta | recriar o template nesta conta (`tw.py template`) |
| 63016 | fora da janela de 24 h sem template aprovado | template aprovado, ou a pessoa escreve primeiro |
| 63112 | nome em análise ou sender restringido pela Meta | conferir o WhatsApp Manager; trocar de sender |
| 51001 | número +1 555 não aceita Address | entrar pelo Messaging Service (`ms --inbound`) |
| 21704 | Messaging Service sem número com SMS | `tw.py ms NOME --numero +...` |
| Mensagem chega e o flow não dispara | sender fora do pool | `tw.py ms NOME --sender XE...` |
| Mesmo celular vira dois contatos | a Meta entrega o Brasil sem o nono dígito | normalizar o telefone em um ponto só |

Detalhes de cada produto (propriedades da ConversationRelay, limites do Sync, Memory, assinatura de webhooks, depuração):
[references/twilio.md](references/twilio.md). Leia a seção do produto quando for além do que os modelos cobrem.

## Regras

- **Credencial não entra em comando, arquivo versionado nem resposta.** Vem do `.env`; o JSON do flow só tem marcadores.
- **Uma conta Twilio = uma WABA.** Confira `waba=` em `tw.py conta` antes de cadastrar sender ou template.
- **Dado sensível não vai para Sync público nem para o Memory**, que não é elegível para HIPAA: em saúde, só dado fictício.
- **Teste automatizado não envia nada de verdade:** use duplos para a Twilio e o LLM.

Mudou o `tw.py`? Rode `python scripts/test_tw.py` (offline, não gasta nada).
