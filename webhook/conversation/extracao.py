from typing import Protocol

from pydantic import BaseModel

from .llm import GeradorEstruturado
from .states import DadosCadastrais

PROMPT = """Extraia do texto abaixo, SE ESTIVEREM PRESENTES, três dados: nome completo, e-mail e celular.

Regras:
- Preencha um campo só se ele aparecer explicitamente no texto. Não invente, não infira, não complete.
- celular: normalize pra conter só dígitos (DDD + número), sem espaço, parênteses ou traço.
- Dado que não aparece no texto: deixe o campo null. Não repita o texto de volta.

Texto:
{texto}"""


class _CamposExtraidos(BaseModel):
    nome: str | None = None
    email: str | None = None
    celular: str | None = None


class ExtratorDados(Protocol):
    def extrair(self, texto: str, atual: DadosCadastrais) -> DadosCadastrais: ...


class ExtratorLLM:

    def __init__(self, gerador: GeradorEstruturado):
        self._gerador = gerador

    def extrair(self, texto: str, atual: DadosCadastrais) -> DadosCadastrais:
        dados = DadosCadastrais(nome=atual.nome, email=atual.email, celular=atual.celular)

        bruto = self._gerador.gerar(PROMPT.format(texto=texto or ""), schema=_CamposExtraidos)
        extraido = _CamposExtraidos.model_validate_json(bruto)

        if not dados.nome and extraido.nome:
            dados.nome = extraido.nome.strip()

        if not dados.email and extraido.email:
            dados.email = extraido.email.strip().lower()

        if not dados.celular and extraido.celular:
            digitos = "".join(c for c in extraido.celular if c.isdigit())
            if 10 <= len(digitos) <= 13:
                dados.celular = digitos

        return dados
