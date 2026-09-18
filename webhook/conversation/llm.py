import time
from typing import Protocol

from google import genai
from google.genai import errors, types
from pydantic import BaseModel

MODELO_PADRAO = "gemini-flash-lite-latest"
TENTATIVAS_PADRAO = 3

PROMPT_TRANSCRICAO = (
    "Transcreva o áudio a seguir literalmente, em português. Números e "
    "e-mails soletrados devem virar a forma escrita normal (ex: \"oito seis "
    "nove\" -> \"869\", \"arroba\" -> \"@\"). Devolva só a transcrição, sem "
    "comentário, sem aspas."
)


class GeradorEstruturado(Protocol):
    def gerar(self, prompt: str, schema: type[BaseModel] | None = None) -> str: ...


class Transcritor(Protocol):
    def transcrever(self, audio: bytes, mime_type: str) -> str: ...


class GeminiClient:

    def __init__(self, api_key: str, modelo: str = MODELO_PADRAO, tentativas: int = TENTATIVAS_PADRAO):
        self._client = genai.Client(api_key=api_key)
        self._modelo = modelo
        self._tentativas = tentativas

    def gerar(self, prompt: str, schema: type[BaseModel] | None = None) -> str:
        config = None
        if schema is not None:
            config = types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema,
            )
        return self._chamar(prompt, config=config)

    def transcrever(self, audio: bytes, mime_type: str) -> str:
        conteudo = [PROMPT_TRANSCRICAO, types.Part.from_bytes(data=audio, mime_type=mime_type)]
        return self._chamar(conteudo).strip()

    def _chamar(self, contents, config=None) -> str:
        for tentativa in range(self._tentativas):
            try:
                resposta = self._client.models.generate_content(
                    model=self._modelo,
                    contents=contents,
                    config=config,
                )
                return resposta.text
            except errors.ServerError:
                if tentativa == self._tentativas - 1:
                    raise
                time.sleep(2**tentativa)
