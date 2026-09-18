from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Literal

MAX_TENTATIVAS_DADOS = 3
MAX_TENTATIVAS_CONFIRMACAO = 3
MAX_TENTATIVAS_BUSCA = 3
MAX_BUSCAS_RESPOSTA = 2


class Estado(str, Enum):
    INICIO = "inicio"
    AGUARDANDO_DADOS = "aguardando_dados"
    CONFIRMANDO_DADOS = "confirmando_dados"
    AGUARDANDO_OCORRENCIA = "aguardando_ocorrencia"
    VALIDANDO_RESPOSTA = "validando_resposta"
    AGUARDANDO_HUMANO = "aguardando_humano"
    ENCERRADO = "encerrado"


TERMINAIS = {Estado.AGUARDANDO_HUMANO, Estado.ENCERRADO}


@dataclass
class DadosCadastrais:
    nome: str = ""
    email: str = ""
    celular: str = ""

    CAMPOS = {"nome": "nome completo", "email": "e-mail", "celular": "celular"}

    @property
    def faltando(self) -> list[str]:
        return [rotulo for campo, rotulo in self.CAMPOS.items() if not getattr(self, campo)]

    @property
    def completo(self) -> bool:
        return not self.faltando

    def limpar(self) -> None:
        self.nome = self.email = self.celular = ""


@dataclass
class Mensagem:
    papel: Literal["usuario", "agente"]
    texto: str
    resposta_busca: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class Sessao:
    telefone: str
    estado: Estado = Estado.INICIO
    dados: DadosCadastrais = field(default_factory=DadosCadastrais)
    ocorrencia: str | None = None
    chamado_id: str | None = None

    tentativas_dados: int = 0
    tentativas_confirmacao: int = 0
    tentativas_busca: int = 0
    buscas_realizadas: int = 0

    historico: list[Mensagem] = field(default_factory=list)

    atualizado_em: datetime = field(default_factory=datetime.now)

    def reiniciar(self) -> None:
        self.estado = Estado.INICIO
        self.dados = DadosCadastrais()
        self.ocorrencia = None
        self.chamado_id = None
        self.tentativas_dados = 0
        self.tentativas_confirmacao = 0
        self.tentativas_busca = 0
        self.buscas_realizadas = 0
        self.historico = []
