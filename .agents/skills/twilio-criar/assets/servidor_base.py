"""Backend mínimo do flow-base.json: POST /ia/mensagem (Studio) e wss /ia/voz (ConversationRelay).

    pip install flask flask-sock twilio python-dotenv
    python servidor_base.py     # porta 8001 (ou PORT); exponha com ngrok ou Cloud Run

.env: STUDIO_TOKEN, TWILIO_AUTH_TOKEN, VOZ_PUBLIC_URL (a wss:// exata do widget, senão a assinatura não confere).
Troque só `responder` pelo seu agente: um cérebro para todos os canais.
"""
import hmac
import json
import logging
import os
import re
import unicodedata

from flask import Flask, jsonify, request
from flask_sock import Sock
from simple_websocket import ConnectionClosed
from twilio.request_validator import RequestValidator

app = Flask(__name__)
sock = Sock(app)
log = logging.getLogger("servidor")
FIM_S = 10  # depois do `end`, quanto esperamos a Twilio fechar


# Empresa fictícia: só para ligar os canais e ensaiar sem LLM. A ordem importa: a primeira linha que casar vence.
ROTEIRO = (  # (palavras, resposta, fim)
    ({"atendente", "pessoa", "humano"}, "Combinado, vou chamar alguém da equipe.", "humano"),
    ({"horario", "horarios", "abre"}, "Atendemos de segunda a sexta, das nove às dezoito.", None),
    ({"preco", "precos", "valor", "valores", "custa"}, "A primeira conversa é sem custo.", None),
    ({"tchau", "obrigado", "obrigada"}, "Até logo!", "encerrar"),
)
OPCOES = "Posso falar de horário e preço, ou chamar alguém da equipe. O que prefere?"


def responder(canal: str, telefone: str, texto: str) -> dict:
    """TROQUE pelo agente, com a mesma assinatura. resposta vazia = humano responde. fim: None | "encerrar" | "humano" (só voz)."""
    sem_acento = "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")
    palavras = set(re.findall(r"\w+", sem_acento))
    for chaves, resposta, fim in ROTEIRO:
        if palavras & chaves:
            return {"resposta": resposta, "fim": fim}
    return {"resposta": OPCOES, "fim": None}


def token_valido(recebido: str) -> bool:
    """O make-http-request do Studio não assina: token compartilhado, e sem token configurado ninguém entra."""
    esperado = os.environ.get("STUDIO_TOKEN")
    return bool(esperado) and hmac.compare_digest(recebido.encode(), esperado.encode())


@app.post("/ia/mensagem")
def mensagem():
    f = request.form
    if not token_valido(f.get("token", "")):
        return jsonify(erro="token inválido"), 401
    r = responder(f.get("canal", ""), f.get("telefone", ""), f.get("texto", ""))
    return jsonify(resposta=r["resposta"] or "")


def assinatura_valida() -> bool:
    """A abertura do WebSocket vem assinada sobre a URL wss:// exata, com parâmetros vazios."""
    token, url = os.environ.get("TWILIO_AUTH_TOKEN"), os.environ.get("VOZ_PUBLIC_URL")
    assinatura = request.headers.get("X-Twilio-Signature", "")
    return bool(token and url and assinatura) and RequestValidator(token).validate(url, {}, assinatura)


def saidas(msg: dict, estado: dict) -> list:
    """Mensagem da Twilio -> mensagens para a Twilio. Responda curto: a fala é lida em voz alta."""
    tipo = msg.get("type")
    if tipo == "setup":
        estado["telefone"] = msg.get("from", "")
    elif tipo == "prompt" and msg.get("last", True):
        r = responder("voz", estado.get("telefone", ""), (msg.get("voicePrompt") or "").strip())
        if r["fim"] or not r["resposta"]:
            estado["fim"] = True
            return [{"type": "end", "handoffData": r["fim"] or "humano"}]  # o Studio fala a despedida
        return [{"type": "text", "token": r["resposta"], "last": True}]
    elif tipo == "error":
        log.warning("erro da ConversationRelay: %s", msg.get("description"))
    return []


@sock.route("/ia/voz")
def voz(ws):
    if not assinatura_valida():
        log.warning("/ia/voz recusado: assinatura inválida")
        return
    estado: dict = {}
    try:
        while not estado.get("fim"):
            for m in saidas(json.loads(ws.receive()), estado):
                ws.send(json.dumps(m, ensure_ascii=False))
        # quem fecha depois do `end` é a Twilio: fechar antes vira 64105 e o flow segue pelo failed
        while ws.receive(timeout=FIM_S) is not None:
            pass
    except ConnectionClosed:
        pass


if __name__ == "__main__":
    # o app.run lê o .env via python-dotenv. 0.0.0.0: em contêiner, 127.0.0.1 não recebe nada.
    # ponytail: servidor de desenvolvimento, serve para demo; troque por um WSGI antes de tráfego real
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8001)), threaded=True)
