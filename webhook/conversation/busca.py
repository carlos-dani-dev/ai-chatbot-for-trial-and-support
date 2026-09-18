from dataclasses import dataclass, field
from typing import Protocol

from tavily import TavilyClient as _TavilySDK

from .llm import GeradorEstruturado

MAX_RESULTADOS_BUSCA = 5

PROMPT = """Você é um assistente de suporte técnico respondendo por WhatsApp. Um usuário relatou o problema abaixo. Use os resultados de busca pra montar uma resposta curta e direta (2-4 frases), em português, sem jargão técnico desnecessário.

Antes de dizer que não há informação relevante, procure nos resultados dados tangenciais que ainda ajudem — preços de variações ou regiões próximas, disponibilidade parcial, alternativas mencionadas etc. Só diga que não encontrou nada relevante se os resultados realmente não tiverem nenhum dado aproveitável, mesmo que indireto.

Nunca invente um dado que não esteja nos resultados — extrair o que já está lá é diferente de completar o que falta.

{aviso_ja_tentado}
Problema do usuário:
{pergunta}

Resultados da busca:
{resultados}

Resposta:"""

AVISO_JA_TENTADO = """As respostas abaixo já foram dadas antes e o usuário disse que não resolveram — não repita nenhuma delas, tente um ângulo diferente:
{lista}

"""


@dataclass
class ResultadoBusca:
    titulo: str
    url: str
    trecho: str


@dataclass
class RespostaEncontrada:
    texto: str
    fontes: list[str] = field(default_factory=list)


class ClienteBusca(Protocol):
    def pesquisar(self, query: str) -> list[ResultadoBusca]: ...


class BuscadorRespostas(Protocol):
    def buscar(self, pergunta: str, ja_tentado: list[str] | None = None) -> RespostaEncontrada: ...


class TavilyClient:

    def __init__(self, api_key: str, max_resultados: int = MAX_RESULTADOS_BUSCA):
        self._client = _TavilySDK(api_key=api_key)
        self._max_resultados = max_resultados

    def pesquisar(self, query: str) -> list[ResultadoBusca]:
        resposta = self._client.search(query=query, max_results=self._max_resultados)
        return [
            ResultadoBusca(titulo=r.get("title", ""), url=r.get("url", ""), trecho=r.get("content", ""))
            for r in resposta.get("results", [])
        ]


class BuscadorTavily:

    def __init__(self, cliente_busca: ClienteBusca, gerador: GeradorEstruturado):
        self._cliente_busca = cliente_busca
        self._gerador = gerador

    def buscar(self, pergunta: str, ja_tentado: list[str] | None = None) -> RespostaEncontrada:
        resultados = self._cliente_busca.pesquisar(pergunta)
        prompt = self._montar_prompt(pergunta, resultados, ja_tentado)
        texto = self._gerador.gerar(prompt).strip()

        return RespostaEncontrada(texto=texto, fontes=[r.url for r in resultados if r.url])

    @staticmethod
    def _montar_prompt(pergunta: str, resultados: list[ResultadoBusca], ja_tentado: list[str] | None) -> str:
        if resultados:
            blocos = [f"- {r.titulo}: {r.trecho}" for r in resultados]
            texto_resultados = "\n".join(blocos)
        else:
            texto_resultados = "(nenhum resultado encontrado)"

        aviso = ""
        if ja_tentado:
            lista = "\n".join(f"- {r}" for r in ja_tentado)
            aviso = AVISO_JA_TENTADO.format(lista=lista)

        return PROMPT.format(aviso_ja_tentado=aviso, pergunta=pergunta, resultados=texto_resultados)
