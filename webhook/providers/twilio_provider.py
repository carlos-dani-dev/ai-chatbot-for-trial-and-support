from typing import Any, Dict, Optional

import requests
from requests.auth import HTTPBasicAuth
from twilio.rest import Client

from .protocol import WhatsAppProvider
from ..schemas import IncomingMessage


class TwilioProvider(WhatsAppProvider):

    def __init__(self, acc_sid: str, auth_token: str, wap_number: str):
        self.acc_sid = acc_sid
        self.auth_token = auth_token
        self.wap_number = wap_number
        self.client = Client(acc_sid, auth_token)

    async def parse_incoming(self, raw_data: Dict[str, Any]) -> Optional[IncomingMessage]:
        from_number = (raw_data.get("From") or "").replace("whatsapp:", "")
        if not from_number:
            return None

        body = raw_data.get("Body")
        num_media = int(raw_data.get("NumMedia") or 0)
        media_url = raw_data.get("MediaUrl0")
        content_type = raw_data.get("MediaContentType0")

        message_type = "text"
        if num_media > 0 and content_type:
            if content_type.startswith("audio"):
                message_type = "audio"
            elif content_type.startswith("image"):
                message_type = "image"
            else:
                message_type = "unknown"

        return IncomingMessage(
            from_number=from_number,
            message_type=message_type,
            text=body,
            media_url=media_url,
            media_mime_type=content_type,
            message_id=raw_data.get("MessageSid"),
        )

    def send_message(self, to: str, text: str) -> None:
        to_formatted = to if to.startswith("whatsapp:") else f"whatsapp:{to}"

        self.client.messages.create(
            from_=self.wap_number,
            to=to_formatted,
            body=text,
        )

    def download_media(self, media_url: str) -> bytes:
        response = requests.get(
            media_url,
            auth=HTTPBasicAuth(self.acc_sid, self.auth_token),
            timeout=30,
        )
        response.raise_for_status()
        return response.content

    def baixar_midia(self, referencia: str) -> bytes:
        return self.download_media(referencia)
