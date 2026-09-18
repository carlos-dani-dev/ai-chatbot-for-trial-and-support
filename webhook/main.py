import logging
from collections import OrderedDict
from typing import Any, Dict

from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import PlainTextResponse

from .config import get_buscador, get_extrator, get_provider, get_sessao_repo, get_transcritor, settings
from .conversation.router import Dependencias, processar
from .conversation.states import Sessao
from .schemas import IncomingMessage


logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("case-dix-digital")

app = FastAPI(title="WhatsApp support Agent - Webhook")
provider = get_provider()
deps = Dependencias(extrator=get_extrator(), buscador=get_buscador())
sessao_repo = get_sessao_repo()
transcritor = get_transcritor()

MIME_TYPE_AUDIO_PADRAO = "audio/ogg"

_handled_ids: "OrderedDict[str, None]" = OrderedDict()
_HANDLED_MAX = 512


def _is_duplicate(message_id: str | None) -> bool:
    if not message_id:
        return False
    if message_id in _handled_ids:
        return True
    _handled_ids[message_id] = None
    while len(_handled_ids) > _HANDLED_MAX:
        _handled_ids.popitem(last=False)
    return False


def _transcrever(message: IncomingMessage) -> str | None:
    try:
        audio = provider.baixar_midia(message.media_url)
        texto = transcritor.transcrever(audio, mime_type=message.media_mime_type or MIME_TYPE_AUDIO_PADRAO)
        logger.info("Áudio transcrito | de=%s | texto=%r", message.from_number, texto)
        return texto
    except Exception:
        logger.exception("Falha ao transcrever áudio de %s", message.from_number)
        return None


def _processar_e_responder(message: IncomingMessage) -> None:
    if message.message_type == "audio":
        texto = _transcrever(message)
        if texto is None:
            _send_aviso(message.from_number, "Não consegui entender o áudio. Pode tentar de novo ou escrever?")
            return
    else:
        texto = message.text or ""

    sessao = sessao_repo.carregar(message.from_number) or Sessao(telefone=message.from_number)
    try:
        reply = processar(sessao, texto, deps)
        provider.send_message(message.from_number, reply)
        logger.info("Resposta enviada para %s | estado=%s", message.from_number, sessao.estado.value)
    except Exception:
        logger.exception("Falha ao processar/enviar a resposta para %s", message.from_number)
    finally:
        try:
            sessao_repo.salvar(sessao)
        except Exception:
            logger.exception("Falha ao salvar a sessão de %s", message.from_number)


def _send_aviso(from_number: str, texto: str) -> None:
    try:
        provider.send_message(from_number, texto)
    except Exception:
        logger.exception("Falha ao avisar %s", from_number)


@app.get("/")
def health_check():
    return {"status": "ok", "service": "whatsapp-support-agent", "provider": settings.provider_name}


@app.get("/webhook/whatsapp")
def verify_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == settings.meta_verify_token:
        return PlainTextResponse(challenge, status_code=200)

    return PlainTextResponse("Forbidden", status_code=403)


async def _read_body(request: Request) -> Dict[str, Any]:
    content_type = request.headers.get("content-type", "")

    if "application/json" in content_type:
        return await request.json()

    return dict(await request.form())


@app.post("/webhook/whatsapp")
async def receive_wap_message(request: Request, background: BackgroundTasks):
    try:
        raw_data = await _read_body(request)
        message = await provider.parse_incoming(raw_data)
    except Exception:
        logger.exception("Falha ao interpretar o payload recebido")
        return PlainTextResponse("", status_code=200)

    if message is None:
        logger.info("Evento ignorado (status de entrega ou callback administrativo)")
        return PlainTextResponse("", status_code=200)

    if _is_duplicate(message.message_id):
        logger.info("Reentrega ignorada | id=%s", message.message_id)
        return PlainTextResponse("", status_code=200)

    logger.info(
        "Mensagem recebida | de=%s | tipo=%s | texto=%r | media_url=%s",
        message.from_number, message.message_type, message.text, message.media_url,
    )

    aceita = (message.message_type == "text" and message.text) or (
        message.message_type == "audio" and message.media_url
    )
    if not aceita:
        background.add_task(
            _send_aviso,
            message.from_number,
            "No momento eu só consigo processar mensagens de texto ou áudio. Pode escrever ou gravar o que precisa?",
        )
        return PlainTextResponse("", status_code=200)

    background.add_task(_processar_e_responder, message)
    return PlainTextResponse("", status_code=200)
