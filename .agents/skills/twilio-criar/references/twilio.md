# Twilio: o que usar, como e as armadilhas

## Sumário
1. Studio
2. ConversationRelay (voz)
3. WhatsApp, WABA e templates
4. SMS
5. Sync
6. Functions
7. Conversations e passagem para humano
8. Conversation Memory
9. Webhooks e assinatura
10. Depuração

---

## 1. Studio

- **Um flow só** para mensagem, conversa e ligação (`incomingMessage`, `incomingConversationMessage`,
  `incomingCall`). Mensagem e conversa chamam o mesmo `POST /ia/mensagem` com `canal`, `telefone`, `texto`, `token`.
- **O JSON do flow fica no repositório**, com marcadores (`__PUBLIC_BASE_URL__`, `__STUDIO_TOKEN__`, `__VOZ_PUBLIC_URL__`) que o
  `tw.py flow` preenche a partir do `.env` e publica pela API. Assim a URL muda (ngrok, Cloud Run) sem editar à mão.
- **Valide antes de publicar** com `POST https://studio.twilio.com/v2/Flows/Validate`: o console só diz
  "Something went wrong"; a API diz o widget e o campo. O mesmo endpoint serve para **descobrir propriedades**
  de um widget sem documentação (`tw.py sondar`): propriedade com tipo errado dá 400 com o tipo
  esperado; nome desconhecido passa calado.
- Edição feita no console não volta para o JSON: avise antes de sobrescrever (compare as revisões).
- **Executions** é o primeiro lugar a olhar quando algo falha. Ligações que caíram ficam `active`: encerre pela
  API (`Status=ended`) para limpar.

## 2. ConversationRelay (voz)

A Twilio faz STT e TTS e conversa em **texto** com um WebSocket **seu**. Ela não conecta direto num LLM.

- **No Studio**: widget `run-conversation-relay`. Propriedades com os nomes da TwiML em camelCase:
  `url` (obrigatória, `wss://`), `welcomeGreeting` (aceita Liquid, ex. a saudação vinda de uma Function),
  `welcomeGreetingInterruptible`, `language`, `ttsProvider`, `voice`, `transcriptionProvider`, `speechModel`,
  `interruptible`, `interruptSensitivity`, `dtmfDetection`, `preemptible`, `reportInputDuringAgentSpeech`,
  e `customParameters` (chegam no `setup`). Transições `success` e `failed`; o `handoffData` do `end` fica em
  `{{widgets.<nome>.HandoffData}}`.
- **Mensagens**: Twilio → você: `setup` (callSid, from, customParameters), `prompt` (`voicePrompt`, `last`),
  `dtmf`, `interrupt` (`utteranceUntilInterrupt`), `error`. Você → Twilio: `text` (`token`, `last`), `end`
  (`handoffData` em texto).
- **Segurança**: a abertura do WebSocket vem com `X-Twilio-Signature`; valide com o auth token, a URL `wss://`
  exata e parâmetros vazios. Fail-closed.
- **Fim da ligação**: mande `end` com `handoffData` (`humano` | `encerrar`) e deixe o Studio falar a despedida.
  **Não feche a conexão logo depois do `end`**: espere a Twilio fechar (alguns segundos), senão vira 64105 e o
  flow vai pelo `failed`.
- **Ritmo**: prepare a sessão do agente no `setup` (enquanto a saudação toca); responda curto (~25 palavras);
  se o agente passar de ~0,8 s, mande antes uma frase de espera ("Só um instante, vou ver aqui.").
- **Texto para a fala**: escreva números, datas e abreviações por extenso ("Doutor", "4 de novembro").
- **Voz pt-BR**: Google `pt-BR-Chirp3-HD-*` soa natural (Leda é leve e amigável; Aoede ficou grave). Use a
  mesma voz nos `say-play` do Studio (`Google.pt-BR-Chirp3-HD-Leda`) para não mudar no meio.
- **STT pt-BR**: o Google em pt-BR **não aceita `hints`** (64101). Se faltar precisão em nomes, teste Deepgram.
- **Falha**: na saída `failed`, chame o backend (`make-http-request`) para abrir um retorno pelo WhatsApp na hora,
  com as últimas falas, e diga isso a quem ligou. Só se o backend também falhar, a mensagem de instabilidade.
- **Requisito**: aceitar o *Predictive and Generative AI/ML Features Addendum* no console. É elegível para
  HIPAA com BAA.
- **Hospedagem**: o servidor WebSocket precisa de URL pública própria (um proxy Next.js não repassa WS) e de
  instância quente.

## 3. WhatsApp, WABA e templates

- **Uma conta Twilio = uma WABA.** Trocar de WABA exige apagar os senders e pedir ao suporte para desvincular.
  Para outra WABA sem perder a atual, use uma **subconta**.
- Verificar a WABA da conta: `GET https://messaging.twilio.com/v2/Channels/Senders?Channel=whatsapp` →
  `configuration.waba_id` (não há rota da conta; o sender do Sandbox `+1 415 523 8886` aparece aí).
- **Self Sign-up**: no popup, "Add a new phone number" (nunca "Use a display name only": o número fornecido
  pela Meta não é suportado e dá "Phone Number is missing"). Número que só recebe voz: aponte o webhook de voz
  para `https://twimlets.com/voicemail?Email=...` e escolha *Phone call*; mais rápido ainda é baixar a gravação
  da última ligação e transcrever com o LLM.
- **Templates (Content)** são por conta e precisam de aprovação da Meta (categoria Utility). Fora da janela de
  24 h, só template. Guarde o texto espelhado no código para o SMS de fallback.
- **Nono dígito**: a Meta entrega o remetente brasileiro sem o 9 (`+551199990000`). Normalize num ponto só:
  `55` + DDD + 8 dígitos começando em 6–9 ganha o 9.
- Número já registrado em outro lugar dá 410 ou "já está registrado": desligue a verificação em duas etapas e
  remova o número da outra WABA (ou apague a conta no app) antes de cadastrar.

## 4. SMS

- No Brasil sai por **short code**: quem recebe não vê o número e **a resposta não volta**. SMS é **aviso**:
  explique o motivo e mande o link `https://wa.me/<número>`. Nunca "posso ajudar por aqui?" nem "responda SAIR".
- O Messaging Service precisa de um número com SMS no pool, senão 21704.

## 5. Sync

- **Sinais**: Documents com só `{atualizado_em, ids}` publicados depois do commit; painel e site assinam e
  buscam o dado na API. Uma Function pública gera o token de leitura.
- **Fichas** (dados de cliente para leitura rápida, ex. na ligação): **Map em serviço separado com ACL**, que o
  token público não alcança. Chave = telefone; valor = resumo curto (sem CPF, endereço, saúde). É cache:
  atualize no gancho do commit e tenha um script de reconstrução.
- Limites: 16 KiB por item; **20 escritas/s por objeto** (o Map conta inteiro); acima de 1 KiB o limite aperta;
  Stream: 4 KiB e 30/s. Reconstrução a ~8/s.
- O Sync **não é memória**: não lê conversa nem resume. Para isso, seção 8.

## 6. Functions

- Para o que **a Twilio ou o navegador chamam direto**, rápido (≤ 10 s) e sem banco: token do Sync, validação
  de telefone (Lookup gratuito), base de conhecimento (Assets), `caller-check` antes da ligação.
- **Visibilidade pelo nome do arquivo**: `x.protected.js` = só chamada assinada pela Twilio (403 sem assinatura).
- Deploy, na raiz do projeto: `npx twilio-run deploy --service-sid <ZS…> --runtime node22 --env functions/.env`.
  Credenciais e variáveis vêm desse arquivo (`ACCOUNT_SID` e `AUTH_TOKEN`, sem `TWILIO_`; só esses dois não sobem).
- `caller-check` nunca deve falhar: sem item, devolve a saudação geral. Não fale dado do cliente na saudação:
  quem atende pode não ser ele.

## 7. Conversations e passagem para humano

- WhatsApp entra pelo Conversations com um **Address** que dispara o flow (`auto_creation_type=studio`);
  o chat do site também vira Conversation. A recepção responde pelo painel.
- Estado `ia → aguardando → humano`, devolve à IA se ninguém assumir em X min; fora do horário, avisa.
- Transferir **ligação** para pessoa com ficha e fila é trabalho de **Flex** (TaskRouter). Sem Flex, só
  `connect-call-to` para um número fixo.

## 8. Conversation Memory

- Memória gerenciada por perfil (telefone): observações, resumos, traits; `Recall` devolve o relevante.
- Dá para usar **só pela API**, sem Orchestrator: `POST /v1/ControlPlane/Stores` (displayName ≤ 32), `POST
  /Stores/{id}/Profiles/Lookup` (`idType: phone`, E.164), `POST /Stores/{id}/Profiles` + `/Identifiers`,
  `POST …/Observations` (`content`, `occurredAt`, `source`), `POST …/Recall`, `GET`/`DELETE …/Observations`.
  A regra de identidade `phone` vem por padrão.
- O **Orchestrator** captura todo o tráfego do número sozinho (inclusive transcreve ligações, com custo): só
  ligue num número dedicado.
- **Não é elegível para HIPAA nem para dado sensível.** Em saúde, só demo com dados fictícios e um interruptor
  (`MEMORIA=twilio|local`).

## 9. Webhooks e assinatura

- Status de mensagem e de chamada: valide `X-Twilio-Signature` contra `PUBLIC_BASE_URL + path` (o proxy/ngrok
  termina TLS). Sem token configurado, recuse.
- Callback longo (baixar e transcrever áudio): responda 204 na hora e processe em thread.
- Mídia: só baixe da API da própria conta (`https://api.twilio.com/2010-04-01/Accounts/<AC>/`), senão a
  credencial vai para qualquer URL; não guarde áudio, só a transcrição.

## 10. Depuração

| Onde | Para quê |
|---|---|
| Monitor → Errors (Debugger), `GET monitor.twilio.com/v1/Alerts` | o código de erro de qualquer produto |
| Studio → Executions (+ `/Context`) | o caminho de uma ligação ou mensagem, widget por widget |
| Logs do servidor de voz | tempo por turno (logue "turno …: agente em X s") |
| `GET /Calls?To=…` + `/Recordings` | achar uma ligação e a gravação |
