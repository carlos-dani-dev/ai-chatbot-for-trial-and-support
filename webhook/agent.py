from .schemas import IncomingMessage


def build_reply(message: IncomingMessage) -> str:
    if message.message_type == "text":
        recebido = f'Recebi sua mensagem de texto: "{message.text}"'
    else:
        recebido = f"Recebi um arquivo do tipo '{message.message_type}'"

    return (
        "✅ Webhook funcionando!\n\n"
        f"{recebido}\n\n"
        "Esta é uma resposta automática de teste — em breve o agente vai "
        "processar isso de verdade."
    )
