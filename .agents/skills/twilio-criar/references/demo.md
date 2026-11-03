# Como montar uma boa demo de atendimento com IA

Vale para qualquer negócio. A ideia central: **a Twilio cuida do canal; o backend decide o que responder.** Um agente só
garante a mesma resposta em todo canal, o Studio dá o desenho que o cliente entende e a regra fica testável no código.

## Sumário
1. Roteiro primeiro
2. Ordem de construção
3. Dados e reset
4. O agente
5. Ensaio e véspera
6. Nuvem
7. Ao terminar

---

## 1. Roteiro primeiro

Antes de qualquer recurso, escreva:

- **O problema, em uma frase** que o público repita depois (ex.: "nenhum contato perdido").
- **5 ou 6 cenas, uns 10 minutos.** Para cada uma: o que a pessoa faz, o que aparece na tela ou no telefone, e o que roda por trás.
- **Só construa o que aparece em alguma cena.** O resto vira uma frase: "o próximo nível seria...".
- **Uma cena de impacto.** Costuma ser o agente reconhecer quem chama e lembrar do contato anterior, ou uma pessoa
  assumir a conversa sem perder o histórico.
- **Uma cena de falha controlada**, se o público for técnico: derrubar algo e mostrar o caminho de recuperação convence
  mais do que o caminho feliz.

## 2. Ordem de construção

1. **Backend e agente com um canal só**, o mais barato de testar, com duplos para a Twilio e o LLM.
2. **WhatsApp**: confira a WABA (`tw.py conta`) e se os templates existem *nesta* conta.
3. **Voz** com ConversationRelay. Meça o tempo por turno nos logs desde a primeira ligação.
4. **Painel ou passagem para humano**, se alguma cena pedir.
5. **Nuvem por último**; até lá, ngrok resolve.

O `assets/servidor_base.py` já roda ponta a ponta com respostas fixas: ligue os canais com ele e troque o `responder` depois.
Assim, um problema de canal não se confunde com um problema de agente.

## 3. Dados e reset

- **Negócio e pessoas fictícios**, mas com integrações reais. Diga isso ao público.
- **Datas relativas a hoje no seed** ("amanhã às 14h"): data fixa envelhece e quebra a demo no dia.
- **Reset em um comando**, que deixa tudo pronto para a próxima rodada, e que recuse rodar em banco de produção sem uma flag explícita.
- **O número do apresentador no seed**, para a cena de "reconheceu quem ligou".
- **Um interruptor para o que for caro ou lento** (LLM, produtos pagos), para ensaiar sem gastar.

## 4. O agente

**Estrutura**

- Um cérebro para todos os canais: `responder(canal, telefone, texto)`. O prompt é persona + ajuste por canal + perfil
  do contato + base de conhecimento.
- Sessão por telefone e canal, com prazo (minutos na voz, cerca de 1 h no texto). Sem prazo, conversa antiga ressuscita.
- Ferramentas para tudo que muda dado. O modelo nunca inventa id: usa só os que o perfil e as ferramentas devolveram.
- **Confirmação checada no código, não só no prompt:** repete o que vai fazer e só grava depois do "sim" em uma mensagem
  seguinte. Dado pessoal gravado precisa ser conferido contra o que a pessoa realmente disse: o modelo inventa para
  preencher parâmetro obrigatório.

**Antes de chamar o modelo**

- Urgência ou assunto proibido: resposta fixa, sem IA.
- Saudações e perguntas básicas: resposta fixa por igualdade total do texto normalizado ("oi" sim, "oi, quero comprar" não). Só
  na primeira mensagem e nunca na voz, onde a saudação já tocou.

**Regras de prompt que evitam erros reais**

- Cumprimente uma vez só por conversa. Admita que é IA, se perguntarem.
- Só ofereça o que a ferramenta devolveu; nunca invente horário, valor ou nome. Se não souber, diga e ofereça uma pessoa.
- Se o pedido não puder ser atendido, diga isso antes de oferecer a alternativa.
- "Posso ajudar em mais alguma coisa?" só depois de concluir algo, nunca com algo pela metade.
- Datas: entregue o dia da semana pronto ("amanhã, quinta, 29/10 às 13:00"). Com a data ISO, o modelo erra o dia.

**Voz**

- No máximo 2 frases e cerca de 25 palavras; sem listas, símbolos ou links; horas e datas por extenso.
- Não repita o que a pessoa disse nem anuncie o que vai fazer: diga o resultado.
- Frase de espera só com ferramenta em andamento e demorando (mais de 1 s), sem repetir na ligação.
- Dado sensível pelo teclado (DTMF), nunca em voz alta.

**Modelo**: escolha pelo tempo da resposta, medido com o seu próprio prompt (3 execuções por modelo, compare a mediana). O que
mais pesa por turno é a ida e volta da ferramenta: antes de trocar de modelo, ponha no contexto o que o agente mais consulta.

**Testes**: duplos por padrão, com o duplo do LLM falhando se for chamado sem querer; testes com o LLM real atrás de uma variável.

## 5. Ensaio e véspera

**A demo está pronta quando o roteiro roda 3 vezes seguidas, cronometrado e sem intervenção.** Grave uma dessas rodadas:
o vídeo é o plano B se a rede ou um canal cair.

Na véspera e de novo uma hora antes:

- [ ] `tw.py conta` e `tw.py alertas`: conta certa, destinos certos, nenhum erro novo.
- [ ] **URL de hoje publicada:** ngrok muda de endereço; atualize o `.env` e rode `tw.py flow` de novo.
- [ ] **Janela de 24 h aberta:** quem vai receber mensagem escreve antes para o número, ou o template já está aprovado.
- [ ] Sandbox do WhatsApp, se usar: todos os números já mandaram o `join`.
- [ ] Reset rodado e servidor de voz quente. **Nada de deploy até o fim da apresentação** (64102).
- [ ] Studio → Executions aberto em uma aba, para o público técnico ver o caminho.

## 6. Nuvem

- **Um serviço público para HTTP e outro para a voz.** O WebSocket precisa de URL própria, porque proxy de frontend costuma não repassá-lo.
  Backend com dados, se houver, fechado atrás do serviço público; o flow nunca aponta para ele (dá 403).
- **Cloud Run, voz:** `--min-instances 1` e `--timeout 3600`. Rode com `gunicorn -w 1 --threads 16`: cada ligação prende uma thread.
- **Um processo por serviço** se houver tarefa de fundo; dois mandariam mensagem em dobro.
- **Segredos:** nunca em comando nem em arquivo versionado. Em produção, use um gerenciador de segredos.
- **Derrube depois:** apague os serviços; banco gerenciado não cai junto e segue cobrando.

## 7. Ao terminar

Registre no projeto o que está ligado (números, SIDs, URLs), como subir e derrubar, e as decisões com o custo de cada uma. A
próxima demo começa daí.
