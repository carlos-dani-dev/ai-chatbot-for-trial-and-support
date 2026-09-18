import uuid
from dataclasses import dataclass
from typing import Callable

from .busca import BuscadorRespostas
from .extracao import ExtratorDados
from .states import (
    MAX_BUSCAS_RESPOSTA,
    MAX_TENTATIVAS_BUSCA,
    MAX_TENTATIVAS_CONFIRMACAO,
    MAX_TENTATIVAS_DADOS,
    DadosCadastrais,
    Estado,
    Mensagem,
    Sessao,
)


@dataclass
class Dependencias:
    extrator: ExtratorDados
    buscador: BuscadorRespostas


Handler = Callable[[Sessao, str, Dependencias], str]

MENSAGEM_BOAS_VINDAS = (
    "Olá! Sou o assistente de suporte. Pra abrir seu chamado, preciso de três dados:\n\n"
    "• Nome completo\n"
    "• E-mail\n"
    "• Celular\n\n"
    "Pode mandar tudo numa mensagem só ou um de cada vez."
)

_PALAVRAS_SIM = {"sim", "s", "correto", "confirmo", "exato", "isso", "ok", "certo", "positivo"}
_PALAVRAS_NAO = {"não", "nao", "n", "errado", "incorreto", "negativo"}


def _resumo_confirmacao(dados: DadosCadastrais) -> str:
    return (
        "Confirma se entendi certo?\n\n"
        f"Nome: {dados.nome}\n"
        f"E-mail: {dados.email}\n"
        f"Celular: {dados.celular}\n\n"
        'Responda "sim" ou "não".'
    )


def _interpretar_sim_nao(texto: str) -> bool | None:
    normalizado = (texto or "").strip().lower().strip(".,!? ")
    if normalizado in _PALAVRAS_SIM:
        return True
    if normalizado in _PALAVRAS_NAO:
        return False
    return None


def _registrar_estagnacao_dados(sessao: Sessao) -> bool:
    sessao.tentativas_dados += 1
    return sessao.tentativas_dados >= MAX_TENTATIVAS_DADOS


def _registrar_falha_confirmacao(sessao: Sessao) -> bool:
    sessao.tentativas_confirmacao += 1
    return sessao.tentativas_confirmacao >= MAX_TENTATIVAS_CONFIRMACAO


def _registrar_falha_busca(sessao: Sessao) -> bool:
    sessao.tentativas_busca += 1
    return sessao.tentativas_busca >= MAX_TENTATIVAS_BUSCA


def _escalar_para_humano(sessao: Sessao) -> str:
    sessao.estado = Estado.AGUARDANDO_HUMANO
    return "Vou te encaminhar pra um atendente humano — só um momento, por favor."


def handle_inicio(sessao: Sessao, texto: str, deps: Dependencias) -> str:
    sessao.estado = Estado.AGUARDANDO_DADOS
    resposta = MENSAGEM_BOAS_VINDAS
    sessao.historico.append(Mensagem(papel="agente", texto=resposta))
    return resposta


def handle_aguardando_dados(sessao: Sessao, texto: str, deps: Dependencias) -> str:
    faltando_antes = set(sessao.dados.faltando)
    sessao.dados = deps.extrator.extrair(texto, sessao.dados)

    if sessao.dados.completo:
        sessao.estado = Estado.CONFIRMANDO_DADOS
        sessao.tentativas_dados = 0
        resposta = _resumo_confirmacao(sessao.dados)
        sessao.historico.append(Mensagem(papel="agente", texto=resposta))
        return resposta

    progrediu = set(sessao.dados.faltando) < faltando_antes
    if progrediu:
        sessao.tentativas_dados = 0
    elif _registrar_estagnacao_dados(sessao):
        resposta = _escalar_para_humano(sessao)
        sessao.historico.append(Mensagem(papel="agente", texto=resposta))
        return resposta

    resposta = f"Ainda falta: {', '.join(sessao.dados.faltando)}. Pode me mandar?"
    sessao.historico.append(Mensagem(papel="agente", texto=resposta))
    return resposta


def handle_confirmando_dados(sessao: Sessao, texto: str, deps: Dependencias) -> str:
    resposta_sim_nao = _interpretar_sim_nao(texto)

    if resposta_sim_nao is None:
        if _registrar_falha_confirmacao(sessao):
            resposta = _escalar_para_humano(sessao)
            sessao.historico.append(Mensagem(papel="agente", texto=resposta))
            return resposta
        resposta = 'Não entendi. Responda "sim" se os dados estão certos, ou "não" pra corrigir.'
        sessao.historico.append(Mensagem(papel="agente", texto=resposta))
        return resposta

    if resposta_sim_nao:
        sessao.estado = Estado.AGUARDANDO_OCORRENCIA
        sessao.tentativas_dados = 0
        sessao.tentativas_confirmacao = 0
        resposta = "Perfeito! Agora me conta qual é o problema ou dúvida que você está enfrentando."
        sessao.historico.append(Mensagem(papel="agente", texto=resposta))
        return resposta

    sessao.dados.limpar()
    if _registrar_falha_confirmacao(sessao):
        resposta = _escalar_para_humano(sessao)
        sessao.historico.append(Mensagem(papel="agente", texto=resposta))
        return resposta

    sessao.estado = Estado.AGUARDANDO_DADOS
    resposta = (
        "Sem problemas! Vamos coletar novamente nome, e-mail e celular. "
        "Pode mandar tudo numa mensagem só ou um de cada vez."
    )
    sessao.historico.append(Mensagem(papel="agente", texto=resposta))
    return resposta


def handle_aguardando_ocorrencia(sessao: Sessao, texto: str, deps: Dependencias) -> str:
    sessao.ocorrencia = texto
    sessao.chamado_id = uuid.uuid4().hex[:8]

    resultado = deps.buscador.buscar(texto)
    sessao.buscas_realizadas = 1
    resposta = (
        f"Chamado #{sessao.chamado_id} aberto!\n\n"
        f"{resultado.texto}\n\n"
        'Isso ajudou a resolver sua dúvida? Responda "sim" ou "não".'
    )
    sessao.historico.append(Mensagem(papel="agente", texto=resposta, resposta_busca=resultado.texto))
    sessao.estado = Estado.VALIDANDO_RESPOSTA
    return resposta


def handle_validando_resposta(sessao: Sessao, texto: str, deps: Dependencias) -> str:
    resposta_sim_nao = _interpretar_sim_nao(texto)

    if resposta_sim_nao:
        sessao.estado = Estado.ENCERRADO
        resposta = "Que bom que ajudou! Encerrando o atendimento por aqui. Qualquer coisa, é só chamar de novo."
        sessao.historico.append(Mensagem(papel="agente", texto=resposta))
        return resposta

    if resposta_sim_nao is None:
        if _registrar_falha_busca(sessao):
            resposta = _escalar_para_humano(sessao)
            sessao.historico.append(Mensagem(papel="agente", texto=resposta))
            return resposta
        resposta = 'Não entendi. A resposta ajudou a resolver sua dúvida? Responda "sim" ou "não".'
        sessao.historico.append(Mensagem(papel="agente", texto=resposta))
        return resposta

    if sessao.buscas_realizadas >= MAX_BUSCAS_RESPOSTA:
        resposta = (
            f"{_escalar_para_humano(sessao)} "
            "A busca automática não encontrou uma resposta que resolvesse sua dúvida."
        )
        sessao.historico.append(Mensagem(papel="agente", texto=resposta))
        return resposta

    ja_tentado = [m.resposta_busca for m in sessao.historico if m.resposta_busca]
    resultado = deps.buscador.buscar(sessao.ocorrencia or texto, ja_tentado=ja_tentado)
    sessao.buscas_realizadas += 1
    resposta = f"{resultado.texto}\n\nIsso ajudou a resolver sua dúvida? Responda \"sim\" ou \"não\"."
    sessao.historico.append(Mensagem(papel="agente", texto=resposta, resposta_busca=resultado.texto))
    return resposta


HANDLERS: dict[Estado, Handler] = {
    Estado.INICIO: handle_inicio,
    Estado.AGUARDANDO_DADOS: handle_aguardando_dados,
    Estado.CONFIRMANDO_DADOS: handle_confirmando_dados,
    Estado.AGUARDANDO_OCORRENCIA: handle_aguardando_ocorrencia,
    Estado.VALIDANDO_RESPOSTA: handle_validando_resposta,
}

_MENSAGEM_AGUARDANDO_HUMANO = "Seu chamado já foi encaminhado a um atendente. Em breve alguém continua por aqui."


def processar(sessao: Sessao, texto: str, deps: Dependencias) -> str:
    if sessao.estado == Estado.ENCERRADO:
        sessao.reiniciar()

    sessao.historico.append(Mensagem(papel="usuario", texto=texto))

    if sessao.estado == Estado.AGUARDANDO_HUMANO:
        sessao.historico.append(Mensagem(papel="agente", texto=_MENSAGEM_AGUARDANDO_HUMANO))
        return _MENSAGEM_AGUARDANDO_HUMANO

    handler = HANDLERS.get(sessao.estado)
    if handler is None:
        raise NotImplementedError(f"Handler ainda não implementado para {sessao.estado}")

    return handler(sessao, texto, deps)
