from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from ..schemas import IncomingMessage


class WhatsAppProvider(ABC):

    @abstractmethod
    async def parse_incoming(self, raw_data: Dict[str, Any]) -> Optional[IncomingMessage]:
        raise NotImplementedError

    @abstractmethod
    def send_message(self, to: str, text: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def baixar_midia(self, referencia: str) -> bytes:
        raise NotImplementedError
