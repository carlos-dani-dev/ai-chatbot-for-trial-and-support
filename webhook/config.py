import os
from pathlib import Path

from dotenv import load_dotenv

ENV_FILE = Path(__file__).resolve().parent / ".env"
load_dotenv(ENV_FILE)


class Settings:

    provider_name: str = os.getenv("PROVIDER", "meta").strip().lower()

    twilio_acc_sid: str = os.getenv("TWILIO_ACC_SID", "")
    twilio_auth_token: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    twilio_wap_number: str = os.getenv("TWILIO_WAP_NUMBER", "")

    meta_access_token: str = os.getenv("META_ACCESS_TOKEN", "")
    meta_phone_number_id: str = os.getenv("META_PHONE_NUMBER_ID", "")
    meta_verify_token: str = os.getenv("META_VERIFY_TOKEN", "meu_token_de_verificacao")

    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")

    tavily_api_key: str = os.getenv("TAVILY_API_KEY", "")


settings = Settings()


def _require(**values: str) -> None:
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise RuntimeError(f"Faltam em {ENV_FILE}: {', '.join(missing)}")


def get_provider():

    if settings.provider_name == "meta":
        _require(
            META_ACCESS_TOKEN=settings.meta_access_token,
            META_PHONE_NUMBER_ID=settings.meta_phone_number_id,
        )
        from .providers.meta_provider import MetaProvider

        return MetaProvider(
            access_token=settings.meta_access_token,
            phone_number_id=settings.meta_phone_number_id,
            verify_token=settings.meta_verify_token,
        )

    _require(
        TWILIO_ACC_SID=settings.twilio_acc_sid,
        TWILIO_AUTH_TOKEN=settings.twilio_auth_token,
        TWILIO_WAP_NUMBER=settings.twilio_wap_number,
    )
    from .providers.twilio_provider import TwilioProvider

    return TwilioProvider(
        acc_sid=settings.twilio_acc_sid,
        auth_token=settings.twilio_auth_token,
        wap_number=settings.twilio_wap_number,
    )


def get_extrator():
    _require(GEMINI_API_KEY=settings.gemini_api_key)

    from .conversation.extracao import ExtratorLLM
    from .conversation.llm import GeminiClient

    return ExtratorLLM(GeminiClient(api_key=settings.gemini_api_key))


def get_buscador():
    _require(GEMINI_API_KEY=settings.gemini_api_key, TAVILY_API_KEY=settings.tavily_api_key)

    from .conversation.busca import BuscadorTavily, TavilyClient
    from .conversation.llm import GeminiClient

    return BuscadorTavily(
        cliente_busca=TavilyClient(api_key=settings.tavily_api_key),
        gerador=GeminiClient(api_key=settings.gemini_api_key),
    )


def get_sessao_repo():
    from .conversation.repositorio import SessaoRepoSQLite

    return SessaoRepoSQLite()


def get_transcritor():
    _require(GEMINI_API_KEY=settings.gemini_api_key)

    from .conversation.llm import GeminiClient

    return GeminiClient(api_key=settings.gemini_api_key)
