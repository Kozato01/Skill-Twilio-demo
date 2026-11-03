# Skill-Twilio-demo

Skill para criar recursos da Twilio pela API, sem clicar no console, e para planejar e ensaiar demos de atendimento com IA por WhatsApp e voz.

## Como usar

Peça ao assistente o que precisa, por exemplo:

- "O que tem nessa conta?"
- "Publica esse flow."
- "Liga esse número no flow."
- "Monta uma demo de atendimento para uma loja."

As credenciais vêm do `.env` do seu projeto (`TWILIO_ACCOUNT_SID` e `TWILIO_AUTH_TOKEN`). **Nada muda na conta sem `--aplicar`.**

## O que tem aqui

Tudo fica em `.agents/skills/twilio-criar/`:

| Arquivo | Para quê |
|---|---|
| `SKILL.md` | Instruções da skill |
| `scripts/tw.py` | CLI que cria e liga os recursos |
| `assets/` | Modelos de flow, servidor, template e Functions |
| `references/demo.md` | Como planejar, montar e ensaiar uma demo |
| `references/twilio.md` | Detalhes e armadilhas de cada produto |

## Testes

```bash
python .agents/skills/twilio-criar/scripts/test_tw.py
```

Rodam offline, sem credencial e sem gastar nada.
