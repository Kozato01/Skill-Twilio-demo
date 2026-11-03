"""Checagem offline, sem rede e sem credencial real:  python test_tw.py"""
import json
import os
import re
import sys
import tempfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path[:0] = [str(AQUI), str(AQUI.parent / "assets")]
import tw  # noqa: E402

BASE = AQUI.parent / "assets" / "flow-base.json"
VARS = {"PUBLIC_BASE_URL": "https://x.dev/", "STUDIO_TOKEN": 'a"b\\c', "VOZ_PUBLIC_URL": "wss://x.dev/ia/voz",
        "EMPRESA": "Loja Ação"}


def test_env():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / ".env"
        p.write_text('﻿A=1\n# B=2\nC="com # dentro"\nexport D=4 # nota\nE=\n', encoding="utf-8")
        os.environ["D_TW_TESTE"] = "x"
        v = tw.ler_env(str(p))
        del os.environ["D_TW_TESTE"]
    assert v["A"] == "1" and "B" not in v and v["C"] == "com # dentro" and v["D"] == "4" and v["E"] == ""
    assert v["D_TW_TESTE"] == "x"


def test_preencher():
    d = tw.preencher(BASE.read_text(encoding="utf-8"), VARS)
    texto = json.dumps(d, ensure_ascii=False)
    assert "__" not in re.sub(r"__[a-z]", "", texto), "sobrou marcador"
    ia = next(s for s in d["states"] if s["name"] == "ia_mensagem")
    assert ia["properties"]["url"] == "https://x.dev/ia/mensagem"  # barra final da URL não duplica
    assert next(p for p in ia["properties"]["parameters"] if p["key"] == "token")["value"] == 'a"b\\c'  # escapado
    try:
        tw.preencher("{\"a\": \"__NAO_TEM__\"}", {})
    except SystemExit as e:
        assert "NAO_TEM" in str(e)
    else:
        raise AssertionError("marcador faltando passou")


def test_flow_base_sem_transicao_quebrada():
    d = json.loads(BASE.read_text(encoding="utf-8"))
    nomes = {s["name"] for s in d["states"]}
    assert len(nomes) == len(d["states"]) and d["initial_state"] in nomes
    for s in d["states"]:
        for t in s["transitions"]:
            assert t.get("next", s["name"]) in nomes, (s["name"], t)


def rodar_com_duble(argv, respostas=None) -> list:
    """Roda a CLI com a rede trocada por um duplo; devolve as chamadas (método, url)."""
    chamadas = []

    def falso(metodo, url, form=None, corpo_json=None, query=None):
        chamadas.append((metodo, url))
        for trecho, r in (respostas or {}).items():
            if trecho in url:
                return r
        return {}
    original, tw.pedir = tw.pedir, falso
    env = dict(os.environ)
    os.environ.update(TWILIO_ACCOUNT_SID="ACteste", TWILIO_AUTH_TOKEN="segredo")
    try:
        with tempfile.TemporaryDirectory() as d:
            assert tw.main(["--env", str(Path(d) / "nada"), *argv]) == 0
    finally:
        tw.pedir = original
        os.environ.clear()
        os.environ.update(env)
    return chamadas


NUMERO = {"IncomingPhoneNumbers.json": {"incoming_phone_numbers": [{"sid": "PN1", "phone_number": "+5511999990000"}]}}
COMANDOS = [
    (["numero", "+5511999990000", "--flow", "FW1", "--voz"], NUMERO),
    (["ms", "demo", "--sender", "XE1", "--numero", "+5511999990000", "--inbound", "https://x"], NUMERO),
    (["conversas", "+5511999990000", "--flow", "FW1", "--servico", "demo", "--ms", "MG1"], {}),
    (["sync", "demo", "--acl"], {}),
    (["memoria", "demo"], {}),
]


def test_sem_aplicar_nao_escreve():
    for argv, respostas in COMANDOS:
        escritas = [c for c in rodar_com_duble(argv, respostas) if c[0] != "GET"]
        assert not escritas, (argv, escritas)


def test_com_aplicar_escreve():
    chamadas = rodar_com_duble(["numero", "+5511999990000", "--flow", "FW1", "--voz", "--aplicar"], NUMERO)
    assert ("POST", "https://api.twilio.com/2010-04-01/Accounts/ACteste/IncomingPhoneNumbers/PN1.json") in chamadas


def test_template_e_flow_sem_aplicar():
    with tempfile.TemporaryDirectory() as d:
        t = Path(d) / "t.json"
        t.write_text('{"friendly_name": "x"}', encoding="utf-8")
        assert not [c for c in rodar_com_duble(["template", str(t), "--submeter"]) if c[0] != "GET"]
    os.environ.update(VARS)
    try:  # a validação é POST mas não cria nada; ela é a única escrita permitida no plano
        chamadas = rodar_com_duble(["flow", str(BASE)])
    finally:
        for k in VARS:
            del os.environ[k]
    assert [c for c in chamadas if c[0] != "GET"] == [("POST", f"{tw.STUDIO}/Flows/Validate")]


def test_e164():
    assert tw.e164("+5511999990000")
    for ruim in ("5511999990000", "+55 11 99999", "whatsapp:+55119"):
        try:
            tw.e164(ruim)
        except tw.argparse.ArgumentTypeError:
            continue
        raise AssertionError(ruim)


def test_servidor_base():
    try:
        import servidor_base as s
        from twilio.request_validator import RequestValidator
    except ImportError as e:
        print(f"  pulado: {e}")
        return
    os.environ.update(STUDIO_TOKEN="t", TWILIO_AUTH_TOKEN="a", VOZ_PUBLIC_URL="wss://x/ia/voz")
    try:
        cliente = s.app.test_client()
        assert cliente.post("/ia/mensagem", data={"texto": "oi", "token": "errado"}).status_code == 401
        assert cliente.post("/ia/mensagem", data={"texto": "oi", "token": "t"}).json["resposta"]
        boa = RequestValidator("a").compute_signature("wss://x/ia/voz", {})
        with s.app.test_request_context(headers={"X-Twilio-Signature": boa}):
            assert s.assinatura_valida()
        with s.app.test_request_context(headers={"X-Twilio-Signature": "ruim"}):
            assert not s.assinatura_valida()
        del os.environ["STUDIO_TOKEN"]  # sem token configurado, ninguém entra
        assert cliente.post("/ia/mensagem", data={"token": ""}).status_code == 401
        assert s.responder("voz", "", "quero falar com uma PESSOA")["fim"] == "humano"
        assert s.responder("voz", "", "Qual o preço?") == s.responder("voz", "", "qual o preco")  # acento não muda
        assert s.responder("voz", "", "obrigado, qual o horário?")["fim"] is None  # pergunta vence a despedida
        assert s.responder("voz", "", "tchau")["fim"] == "encerrar"
        assert s.responder("voz", "", "boa noite")["resposta"] == s.OPCOES  # palavra inteira, não pedaço
        e: dict = {}
        s.saidas({"type": "setup", "from": "+55"}, e)
        assert s.saidas({"type": "prompt", "voicePrompt": "oi"}, e)[0]["type"] == "text"
        original, s.responder = s.responder, lambda *_: {"resposta": "tchau", "fim": "encerrar"}
        assert s.saidas({"type": "prompt", "voicePrompt": "tchau"}, e) == [{"type": "end", "handoffData": "encerrar"}]
        s.responder = original
        assert e["fim"]
    finally:
        for k in ("STUDIO_TOKEN", "TWILIO_AUTH_TOKEN", "VOZ_PUBLIC_URL"):
            os.environ.pop(k, None)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    for nome, f in list(globals().items()):
        if nome.startswith("test_"):
            print(nome)
            f()
    print("tudo ok")
