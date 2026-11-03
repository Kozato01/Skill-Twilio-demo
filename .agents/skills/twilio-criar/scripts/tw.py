#!/usr/bin/env python3
"""Cria e liga recursos da Twilio pela API. Só biblioteca padrão. Rode na raiz do projeto (lê o .env de lá).

    tw.py conta                                    inventário da conta (só leitura)
    tw.py alertas [-n 20]                          últimos erros do Debugger (só leitura)
    tw.py sondar <widget> [prop ...]               formato de um widget do Studio (só leitura)
    tw.py flow <arquivo.json> [--como NOME]        valida e publica um flow; __VAR__ vem do .env
    tw.py numero +55... --flow FW... [--voz] [--sms] [--status URL]
    tw.py ms NOME [--sender XE...] [--numero +55...] [--inbound URL]
    tw.py conversas +55... --flow FW... --servico NOME [--ms MG...]
    tw.py sync NOME [--acl]
    tw.py template <arquivo.json> [--submeter] [--categoria UTILITY]
    tw.py memoria NOME

Quem altera a conta só mostra o plano; para valer, acrescente --aplicar. Credenciais: TWILIO_ACCOUNT_SID e
TWILIO_AUTH_TOKEN, do ambiente ou do .env (o ambiente vence).
"""
import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

MARCADOR = re.compile(r"__([A-Z][A-Z0-9_]*)__")
MARCA_COMMIT = "tw.py"  # revisão sem esta marca foi feita no console
STUDIO = "https://studio.twilio.com/v2"
MESSAGING = "https://messaging.twilio.com/v1"
CONVERSATIONS = "https://conversations.twilio.com/v1"
SYNC = "https://sync.twilio.com/v1"
CONTENT = "https://content.twilio.com/v1"
MEMORY = "https://memory.twilio.com/v1"
SERVERLESS = "https://serverless.twilio.com/v1"
ENV: dict = {}


class ErroTwilio(Exception):
    def __init__(self, status, corpo):
        super().__init__(f"HTTP {status}: {corpo}")
        self.status, self.corpo = status, corpo


def ler_env(caminho=".env") -> dict:
    valores = {}
    p = Path(caminho)
    if p.exists():
        for linha in p.read_text(encoding="utf-8-sig").splitlines():
            m = re.match(r"\s*(?:export\s+)?([A-Za-z_]\w*)\s*=\s*(.*)$", linha)
            if not m:
                continue
            v = m[2].strip()
            if len(v) >= 2 and v[0] in "\"'" and v[-1] == v[0]:
                v = v[1:-1]
            else:
                v = re.sub(r"\s+#.*$", "", v)
            valores[m[1]] = v
    valores.update(os.environ)
    return valores


def pedir(metodo, url, form=None, corpo_json=None, query=None) -> dict:
    conta, token = ENV.get("TWILIO_ACCOUNT_SID"), ENV.get("TWILIO_AUTH_TOKEN")
    if not conta or not token:
        raise SystemExit("faltam TWILIO_ACCOUNT_SID e TWILIO_AUTH_TOKEN (no .env da pasta atual ou no ambiente)")
    if query:
        url += "?" + urllib.parse.urlencode(query)
    dados, cabecalhos = None, {"Accept": "application/json"}
    cabecalhos["Authorization"] = "Basic " + base64.b64encode(f"{conta}:{token}".encode()).decode()
    if form is not None:
        dados = urllib.parse.urlencode(form).encode()
        cabecalhos["Content-Type"] = "application/x-www-form-urlencoded"
    elif corpo_json is not None:
        dados = json.dumps(corpo_json).encode()
        cabecalhos["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=dados, headers=cabecalhos, method=metodo)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            bruto = r.read()
    except urllib.error.HTTPError as e:
        texto = e.read().decode("utf-8", "replace")
        try:
            raise ErroTwilio(e.code, json.loads(texto)) from None
        except json.JSONDecodeError:
            raise ErroTwilio(e.code, texto[:300]) from None
    return json.loads(bruto) if bruto else {}


def api_conta() -> str:
    return f"https://api.twilio.com/2010-04-01/Accounts/{ENV.get('TWILIO_ACCOUNT_SID')}"


def url_flow(flow_sid: str) -> str:
    return f"https://webhooks.twilio.com/v1/Accounts/{ENV['TWILIO_ACCOUNT_SID']}/Flows/{flow_sid}"


def listar(url, chave, **query) -> list:
    # ponytail: só a primeira página (100 itens); pagine se uma conta de demo passar disso
    return pedir("GET", url, query={"PageSize": 100, **query}).get(chave, [])


def achar(url, chave, nome, campo="friendly_name"):
    return next((x for x in listar(url, chave) if x.get(campo) == nome), None)


def fazer(args, descricao, metodo, url, **kw):
    """O único caminho de escrita: sem --aplicar, só descreve e devolve None."""
    if not args.aplicar:
        print(f"[plano] {descricao}")
        return None
    r = pedir(metodo, url, **kw)
    print(f"ok: {descricao}")
    return r


def fim_do_plano(args) -> None:
    if not args.aplicar:
        print("nada foi alterado; repita com --aplicar para valer")


# --- leitura ---------------------------------------------------------------------------------------------------------
def secao(titulo, funcao) -> None:
    print(f"\n## {titulo}")
    try:
        linhas = list(funcao())
        print("\n".join(linhas) if linhas else "(nada)")
    except ErroTwilio as e:
        print(f"(não lido: HTTP {e.status})")


def aprovacao(c: dict) -> str:
    a = c.get("approval_requests") or {}
    return a.get("status") or "sem aprovação"


def linhas_funcoes():
    for s in listar(f"{SERVERLESS}/Services", "services"):
        yield f"{s['sid']}  {s['unique_name']}"
        for e in listar(f"{SERVERLESS}/Services/{s['sid']}/Environments", "environments"):
            yield f"  ambiente {e['sid']}  {e['unique_name']}  https://{e.get('domain_name')}"
        for f in listar(f"{SERVERLESS}/Services/{s['sid']}/Functions", "functions"):
            yield f"  função   {f['sid']}  {f['friendly_name']}"


def cmd_conta(_):
    a = pedir("GET", f"{api_conta()}.json")
    print(f"Conta: {a['friendly_name']}  {a['sid']}  ({a['status']}, {a['type']})")
    secao("Números", lambda: (f"{n['phone_number']}  {n['sid']}  voz={n.get('voice_url') or '-'}  "
                              f"sms={n.get('sms_url') or '-'}"
                              for n in listar(f"{api_conta()}/IncomingPhoneNumbers.json", "incoming_phone_numbers")))
    secao("WhatsApp senders", lambda: (f"{s['sender_id']}  {s['sid']}  {s.get('status')}  "
                                       f"waba={(s.get('configuration') or {}).get('waba_id')}"
                                       for s in pedir("GET", "https://messaging.twilio.com/v2/Channels/Senders",
                                                      query={"Channel": "whatsapp", "PageSize": 100}).get("senders", [])))
    secao("Messaging Services", lambda: (f"{s['sid']}  {s['friendly_name']}  inbound={s.get('inbound_request_url') or '-'}"
                                         for s in listar(f"{MESSAGING}/Services", "services")))
    secao("Studio", lambda: (f"{f['sid']}  {f['friendly_name']}  {f['status']}  rev={f['revision']}"
                             for f in listar(f"{STUDIO}/Flows", "flows")))
    secao("Functions", linhas_funcoes)
    secao("Sync", lambda: (f"{s['sid']}  {s['friendly_name']}  acl={s.get('acl_enabled')}"
                           for s in listar(f"{SYNC}/Services", "services")))
    secao("Conversations", lambda: (f"{s['sid']}  {s['friendly_name']}"
                                    for s in listar(f"{CONVERSATIONS}/Services", "services")))
    secao("Conversations: endereços", lambda: (f"{x['address']}  {x['sid']}  {x.get('auto_creation')}"
                                               for x in listar(f"{CONVERSATIONS}/Configuration/Addresses",
                                                               "address_configurations")))
    secao("Templates", lambda: (f"{c['sid']}  {c['friendly_name']}  {c.get('language')}  {aprovacao(c)}"
                                for c in listar(f"{CONTENT}/ContentAndApprovals", "contents")))
    secao("Conversation Memory", lambda: (f"{s.get('id')}  {s.get('displayName')}" for s in lojas_memoria()))


def cmd_alertas(args):
    for a in listar("https://monitor.twilio.com/v1/Alerts", "alerts", PageSize=args.n):
        texto = urllib.parse.unquote_plus(a.get("alert_text") or "")[:160]
        print(f"{a.get('date_created')}  {a.get('error_code')}  {a.get('resource_sid')}  {texto}")


def validar(definicao: dict, nome: str) -> list:
    """Erros do Studio com widget e campo (o import do console só diz "Something went wrong")."""
    try:
        pedir("POST", f"{STUDIO}/Flows/Validate",
              form={"FriendlyName": nome, "Status": "published", "Definition": json.dumps(definicao)})
        return []
    except ErroTwilio as e:
        if e.status != 400 or not isinstance(e.corpo, dict):
            raise
        erros = (e.corpo.get("details") or {}).get("errors") or [{"message": e.corpo.get("message")}]
        return [f"{x.get('message', '')} @ {x.get('property_path', '')}" for x in erros]


def cmd_sondar(args):
    def sonda(props, transicoes):
        return validar({"description": "sonda", "initial_state": "Trigger", "flags": {"allow_concurrent_calls": True},
                        "states": [{"name": "Trigger", "type": "trigger", "properties": {},
                                    "transitions": [{"event": "incomingCall", "next": "w"}]},
                                   {"name": "w", "type": args.widget, "properties": props,
                                    "transitions": transicoes}]}, "sonda")
    print("eventos:", sonda({}, [{"event": "x"}])[:3])
    for p in args.props:  # tipo errado de propósito: propriedade conhecida responde o tipo esperado
        print(f"{p:32}", next((x for x in sonda({p: [1]}, []) if p in x), "desconhecida (ou aceita qualquer coisa)"))


# --- flow ------------------------------------------------------------------------------------------------------------
def preencher(texto: str, env: dict) -> dict:
    faltando = sorted({n for n in MARCADOR.findall(texto) if not env.get(n)})
    if faltando:
        raise SystemExit(f"faltam no .env: {', '.join(faltando)}")

    def valor(m):
        v = env[m[1]].rstrip("/") if m[1].endswith("URL") else env[m[1]]
        return json.dumps(v, ensure_ascii=False)[1:-1]  # o valor entra num texto JSON: aspas e barras escapadas
    return json.loads(MARCADOR.sub(valor, texto))


def revisoes_do_console(flow_sid: str) -> list:
    achadas = []
    for r in listar(f"{STUDIO}/Flows/{flow_sid}/Revisions", "revisions", PageSize=30):
        if (r.get("commit_message") or "").startswith(MARCA_COMMIT):
            break
        achadas.append(f"rev {r.get('revision')}: {r.get('commit_message') or '(sem mensagem)'}")
    return achadas


def cmd_flow(args):
    arquivo = Path(args.arquivo)
    nome = args.como or arquivo.stem
    definicao = preencher(arquivo.read_text(encoding="utf-8"), ENV)
    erros = validar(definicao, nome)
    if erros:
        raise SystemExit(f"{arquivo} inválido:\n  " + "\n  ".join(erros))
    print(f"ok: {arquivo} válido")
    existente = achar(f"{STUDIO}/Flows", "flows", nome)
    form = {"Status": "published", "Definition": None, "CommitMessage": MARCA_COMMIT}
    if existente:
        sid = existente["sid"]
        if console := revisoes_do_console(sid):
            print("atenção: revisões feitas no console serão sobrescritas (o layout é mantido; o histórico fica no Studio):")
            print("  " + "\n  ".join(console))
        atual = pedir("GET", f"{STUDIO}/Flows/{sid}")["definition"]["states"]
        posicoes = {s["name"]: s.get("properties", {}).get("offset") for s in atual}
        for s in definicao["states"]:  # quem arruma o desenho é o console; o JSON manda no resto
            if posicoes.get(s["name"]):
                s.setdefault("properties", {})["offset"] = posicoes[s["name"]]
        form["Definition"] = json.dumps(definicao)
        r = fazer(args, f"publicar {nome} sobre {sid} (rev {existente['revision']})", "POST",
                  f"{STUDIO}/Flows/{sid}", form=form)
    else:
        form.update(FriendlyName=nome, Definition=json.dumps(definicao))
        r = fazer(args, f"criar o flow {nome}", "POST", f"{STUDIO}/Flows", form=form)
    if r:
        print(f"SID: {r['sid']}  rev {r.get('revision')}\nwebhook: {url_flow(r['sid'])}")
    fim_do_plano(args)


# --- canais ----------------------------------------------------------------------------------------------------------
def e164(texto: str) -> str:
    if not re.fullmatch(r"\+\d{8,15}", texto):
        raise argparse.ArgumentTypeError(f"{texto}: use E.164, ex. +5511999990000")
    return texto


def achar_numero(numero: str) -> dict:
    achados = pedir("GET", f"{api_conta()}/IncomingPhoneNumbers.json", query={"PhoneNumber": numero}) \
        .get("incoming_phone_numbers", [])
    if not achados:
        raise SystemExit(f"{numero} não está nesta conta (confira com: tw.py conta)")
    return achados[0]


def cmd_numero(args):
    if not (args.voz or args.sms or args.status):
        raise SystemExit("diga o que ligar: --voz, --sms e/ou --status URL")
    n = achar_numero(args.numero)
    print(f"hoje: voz={n.get('voice_url') or '-'}  sms={n.get('sms_url') or '-'}  status={n.get('status_callback') or '-'}")
    form = {}
    if args.voz or args.sms:
        if not args.flow:
            raise SystemExit("--voz e --sms pedem --flow FW...")
        destino = url_flow(args.flow)
        if args.voz:
            form.update(VoiceUrl=destino, VoiceMethod="POST")
        if args.sms:
            form.update(SmsUrl=destino, SmsMethod="POST")
    if args.status:
        form["StatusCallback"] = args.status
    fazer(args, f"{args.numero}: {sorted(form)}", "POST", f"{api_conta()}/IncomingPhoneNumbers/{n['sid']}.json", form=form)
    fim_do_plano(args)


def no_pool(args, descricao, url, form) -> None:
    try:
        fazer(args, descricao, "POST", url, form=form)
    except ErroTwilio as e:
        if e.status != 409:  # 409: já estava no pool, é o que queríamos
            raise
        print(f"já estava: {descricao}")


def cmd_ms(args):
    ms = achar(f"{MESSAGING}/Services", "services", args.nome)
    if not ms:
        ms = fazer(args, f"criar o Messaging Service {args.nome}", "POST", f"{MESSAGING}/Services",
                   form={"FriendlyName": args.nome})
    sid = ms["sid"] if ms else "<novo>"
    if ms:
        print(f"MESSAGING_SERVICE_SID={sid}")
    if args.inbound:
        fazer(args, f"entrada de {args.nome} -> {args.inbound}", "POST", f"{MESSAGING}/Services/{sid}",
              form={"InboundRequestUrl": args.inbound, "UseInboundWebhookOnNumber": "false"})
    if args.sender:
        no_pool(args, f"sender {args.sender} no pool", f"{MESSAGING}/Services/{sid}/ChannelSenders", {"Sid": args.sender})
    if args.numero:
        no_pool(args, f"número {args.numero} no pool", f"{MESSAGING}/Services/{sid}/PhoneNumbers",
                {"PhoneNumberSid": achar_numero(args.numero)["sid"]})
    fim_do_plano(args)


def cmd_conversas(args):
    if args.numero.startswith("+1555"):
        print("atenção: número +1 555 costuma recusar Address (erro 51001)")
    endereco = f"whatsapp:{args.numero}"
    servico = achar(f"{CONVERSATIONS}/Services", "services", args.servico)
    if not servico:
        servico = fazer(args, f"criar o serviço {args.servico}", "POST", f"{CONVERSATIONS}/Services",
                        form={"FriendlyName": args.servico})
    if servico:
        print(f"CONVERSATIONS_SERVICE_SID={servico['sid']}")
    if args.ms:
        fazer(args, f"Messaging Service padrão -> {args.ms}, timers PT1H/P1D", "POST", f"{CONVERSATIONS}/Configuration",
              form={"DefaultMessagingServiceSid": args.ms, "DefaultInactiveTimer": "PT1H", "DefaultClosedTimer": "P1D"})
    if achar(f"{CONVERSATIONS}/Configuration/Addresses", "address_configurations", endereco, "address"):
        print(f"já existe: Address de {endereco} (apague no console para trocar o flow)")
    else:
        fazer(args, f"Address {endereco} -> {args.flow}", "POST", f"{CONVERSATIONS}/Configuration/Addresses",
              form={"Type": "whatsapp", "Address": endereco, "AutoCreation.Enabled": "true",
                    "AutoCreation.Type": "studio", "AutoCreation.StudioFlowSid": args.flow,
                    "AutoCreation.ConversationServiceSid": servico["sid"] if servico else "<novo>"})
    fim_do_plano(args)


def cmd_sync(args):
    s = achar(f"{SYNC}/Services", "services", args.nome)
    if s:
        print(f"já existe (acl={s.get('acl_enabled')})")
    else:
        form = {"FriendlyName": args.nome}
        if args.acl:
            form["AclEnabled"] = "true"
        s = fazer(args, f"criar o Sync {args.nome} (acl={args.acl})", "POST", f"{SYNC}/Services", form=form)
    if s:
        print(f"SYNC_SERVICE_SID={s['sid']}")
    fim_do_plano(args)


def cmd_template(args):
    corpo = json.loads(Path(args.arquivo).read_text(encoding="utf-8"))
    nome = corpo["friendly_name"]
    t = achar(f"{CONTENT}/Content", "contents", nome)
    if t:
        print(f"já existe: {nome}")
    else:
        t = fazer(args, f"criar o template {nome}", "POST", f"{CONTENT}/Content", corpo_json=corpo)
    if t:
        print(f"CONTENT_SID={t['sid']}")
    if args.submeter:
        sid = t["sid"] if t else "<novo>"
        fazer(args, f"SUBMETER {nome} à Meta como {args.categoria}", "POST",
              f"{CONTENT}/Content/{sid}/ApprovalRequests/whatsapp", corpo_json={"name": nome, "category": args.categoria})
    fim_do_plano(args)


def lojas_memoria() -> list:
    ids = pedir("GET", f"{MEMORY}/ControlPlane/Stores").get("stores", [])
    return [pedir("GET", f"{MEMORY}/ControlPlane/Stores/{i}") for i in ids]


def cmd_memoria(args):
    if len(args.nome) > 32:
        raise SystemExit("o nome do store tem no máximo 32 caracteres")
    achado = next((s for s in lojas_memoria() if s.get("displayName") == args.nome), None)
    if not achado:
        pedido = fazer(args, f"criar o store {args.nome}", "POST", f"{MEMORY}/ControlPlane/Stores",
                       corpo_json={"displayName": args.nome, "description": "demo, sem dado real"})
        for _ in range(20 if pedido is not None else 0):  # a criação é assíncrona
            time.sleep(3)
            achado = next((s for s in lojas_memoria() if s.get("displayName") == args.nome), None)
            if achado:
                break
    if achado:
        print(f"CONVERSATION_MEMORY_STORE_ID={achado['id']}")
    fim_do_plano(args)


def montar_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tw.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--env", default=".env", help="arquivo com as credenciais (padrão: .env da pasta atual)")
    sub = p.add_subparsers(dest="comando", required=True)

    def novo(nome, funcao, escreve=True):
        c = sub.add_parser(nome)
        c.set_defaults(funcao=funcao)
        if escreve:
            c.add_argument("--aplicar", action="store_true", help="sem isto, só mostra o plano")
        return c

    novo("conta", cmd_conta, escreve=False)
    c = novo("alertas", cmd_alertas, escreve=False)
    c.add_argument("-n", type=int, default=20)
    c = novo("sondar", cmd_sondar, escreve=False)
    c.add_argument("widget")
    c.add_argument("props", nargs="*")
    c = novo("flow", cmd_flow)
    c.add_argument("arquivo")
    c.add_argument("--como")
    c = novo("numero", cmd_numero)
    c.add_argument("numero", type=e164)
    c.add_argument("--flow")
    c.add_argument("--voz", action="store_true")
    c.add_argument("--sms", action="store_true")
    c.add_argument("--status")
    c = novo("ms", cmd_ms)
    c.add_argument("nome")
    c.add_argument("--sender")
    c.add_argument("--numero", type=e164)
    c.add_argument("--inbound")
    c = novo("conversas", cmd_conversas)
    c.add_argument("numero", type=e164)
    c.add_argument("--flow", required=True)
    c.add_argument("--servico", required=True)
    c.add_argument("--ms")
    c = novo("sync", cmd_sync)
    c.add_argument("nome")
    c.add_argument("--acl", action="store_true")
    c = novo("template", cmd_template)
    c.add_argument("arquivo")
    c.add_argument("--submeter", action="store_true")
    c.add_argument("--categoria", default="UTILITY")
    c = novo("memoria", cmd_memoria)
    c.add_argument("nome")
    return p


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = montar_parser().parse_args(argv)
    ENV.clear()
    ENV.update(ler_env(args.env))
    try:
        args.funcao(args)
    except ErroTwilio as e:
        c = e.corpo if isinstance(e.corpo, dict) else {"message": e.corpo}
        print(f"erro HTTP {e.status}, código {c.get('code')}: {c.get('message')} {c.get('more_info') or ''}", file=sys.stderr)
        return 1
    except urllib.error.URLError as e:
        print(f"sem conexão com a Twilio: {e.reason}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
