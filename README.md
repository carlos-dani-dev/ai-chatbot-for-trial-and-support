# Case Dix Digital - WhatsApp Support Chatbot

A technical support chatbot that runs on WhatsApp. It collects the user's contact details, opens a support ticket, searches the web for a solution to the reported problem, and hands the conversation over to a human agent when it cannot solve it.

## Features

- Works with either the Meta WhatsApp Cloud API or Twilio, selected through an environment variable.
- Accepts text and voice messages. Voice messages are transcribed with Gemini.
- Extracts name, email and phone number from free-form text using Gemini with structured JSON output.
- Answers the user's problem by combining a Tavily web search with a Gemini-generated reply.
- Drives the conversation with a fixed state machine and stores each session in SQLite.

## Project structure

- `pyproject.toml`: dependencies, managed with Poetry.
- `webhook/main.py`: FastAPI app and HTTP endpoints.
- `webhook/config.py`: reads `webhook/.env` and builds the dependencies.
- `webhook/schemas.py`: `IncomingMessage`, the internal message format.
- `webhook/providers/`: the `WhatsAppProvider` interface and its Meta and Twilio implementations.
- `webhook/conversation/states.py`: conversation states, the session model and retry limits.
- `webhook/conversation/router.py`: one handler per state.
- `webhook/conversation/llm.py`: Gemini client for text, JSON and audio.
- `webhook/conversation/extracao.py`: contact details extraction.
- `webhook/conversation/busca.py`: web search and answer generation.
- `webhook/conversation/repositorio.py`: SQLite session storage.

## How it was built

### 1. Project setup

The project uses Python 3.11+ and Poetry:

```bash
poetry add fastapi uvicorn python-multipart python-dotenv requests twilio google-genai tavily-python
```

`python-multipart` is needed because Twilio sends webhooks as form data.

### 2. Minimal webhook

The first version only echoed messages back, to confirm that messages arrived and replies went out. That stub is still in `webhook/agent.py`.

`webhook/main.py` exposes three routes:

- `GET /` is a health check.
- `GET /webhook/whatsapp` answers Meta's webhook verification by checking `hub.verify_token` and returning `hub.challenge`.
- `POST /webhook/whatsapp` receives messages as JSON (Meta) or form data (Twilio).

### 3. Provider abstraction

Meta and Twilio send very different payloads. Each provider converts its payload into a shared `IncomingMessage` (sender, type, text, media reference, MIME type, message ID) and implements three methods: `parse_incoming`, `send_message` and `baixar_midia` (download media).

- The Meta provider ignores delivery status events, sends messages through the Graph API, and downloads media in two steps (media ID to URL, then URL to bytes). It retries with exponential backoff on connection errors, timeouts, HTTP 5xx and HTTP 429.
- The Twilio provider reads the form fields, detects the message type from the media content type, and downloads media with basic authentication.

`get_provider()` in `webhook/config.py` picks the provider from `PROVIDER=meta` or `PROVIDER=twilio`. It stops at startup with a clear error if a required credential is missing.

### 4. Conversation state machine

The conversation follows a fixed flow instead of letting the LLM lead it. The LLM is only used for specific tasks: extracting data, transcribing audio and writing answers. This keeps the bot's behavior predictable.

The states are:

1. `INICIO` (start): sends a welcome message asking for name, email and phone number.
2. `AGUARDANDO_DADOS` (waiting for details): extracts details from each message and asks for whatever is still missing.
3. `CONFIRMANDO_DADOS` (confirming details): shows the collected details and asks the user to confirm. A "no" clears the details and goes back to step 2.
4. `AGUARDANDO_OCORRENCIA` (waiting for the issue): the user describes the problem. The bot opens a ticket with an 8-character ID and sends a first answer.
5. `VALIDANDO_RESPOSTA` (validating the answer): asks whether the answer helped. "Yes" ends the conversation. "No" triggers a new search.
6. `AGUARDANDO_HUMANO` (waiting for a human): reached when the bot gives up. Any new message gets a notice that a human agent will take over.
7. `ENCERRADO` (closed): the next message starts a new conversation.

The bot escalates to a human when any of these happens:

- 3 messages in a row add no new contact details.
- 3 failed confirmations.
- 3 invalid replies while validating an answer.
- 2 searches that did not solve the problem.

These limits are constants at the top of `states.py`.

### 5. Router

`router.py` maps each state to a handler function. The entry point, `processar()`, does four things:

1. Resets a closed session.
2. Records the user's message in the history.
3. Replies with the human handover notice if the session is waiting for a human.
4. Otherwise calls the handler for the current state.

Yes/no answers are matched against fixed word lists instead of using the LLM.

The extractor and the search service are passed in as dependencies, so the router does not depend on any external SDK.

### 6. Gemini client

`llm.py` wraps the Gemini API (model `gemini-flash-lite-latest`) and provides three things:

- `gerar()` (generate) returns plain text, or JSON that follows a Pydantic schema when one is given.
- `transcrever()` (transcribe) converts audio to text. It also turns spelled-out numbers and email symbols into their written form.
- Every call is tried up to 3 times with exponential backoff when the server returns an error.

### 7. Contact details extraction

`extracao.py` asks Gemini to return only the name, email and phone number that appear explicitly in the text, as JSON.

Results are merged into the session one field at a time, so users can send their details across several messages. The extractor also cleans up the values: it trims the name, lowercases the email, and keeps only the digits of the phone number. A phone number is accepted only if it has 10 to 13 digits.

### 8. Answer search

`busca.py` searches Tavily for the user's problem and keeps up to 5 results. It then asks Gemini to write a short answer from those results: 2 to 4 sentences, in plain Portuguese, without inventing facts.

If the user says the first answer did not help, the previous answers are added to the prompt with an instruction to try a different approach.

### 9. Session storage

Each webhook call is a separate request, so the conversation state has to be saved between messages.

`repositorio.py` stores the whole session as JSON in a SQLite table keyed by phone number, using an upsert. `main.py` saves the session in a `finally` block, so progress is kept even if sending the reply fails.

### 10. Voice messages

For audio messages, the provider downloads the file and Gemini transcribes it. The default MIME type is `audio/ogg`. The transcribed text then goes through the same flow as a text message.

If transcription fails, the user is asked to try again or type the message. Images and other message types get a reply saying that only text and audio are supported.

### 11. Webhook reliability

Providers resend a webhook if they don't get a quick `200`. To handle this:

- The endpoint always returns `200` right away and does the slow work (LLM calls, search, sending) in a background task.
- The IDs of the last 512 messages are kept in memory, and repeated deliveries are ignored.
- Errors are logged and never crash the app.

## Running locally

Requirements:

- Python 3.11+ and Poetry.
- A Gemini API key and a Tavily API key.
- A Meta developer app with WhatsApp enabled, or a Twilio WhatsApp sandbox.
- An HTTPS tunnel such as ngrok.

Install the dependencies:

```bash
poetry install
```

Create `webhook/.env`:

```
PROVIDER=meta

META_ACCESS_TOKEN=...
META_PHONE_NUMBER_ID=...
META_VERIFY_TOKEN=my_verify_token

TWILIO_ACC_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_WAP_NUMBER=whatsapp:+14155238886

GEMINI_API_KEY=...
TAVILY_API_KEY=...
```

You only need the credentials for the provider you selected. The `.env` file is ignored by git.

Start the server:

```bash
poetry run uvicorn webhook.main:app --reload --port 8000
```

Expose it with `ngrok http 8000`, then register `https://<your-tunnel>/webhook/whatsapp` as the webhook URL:

- On Meta, use the same verify token as in `.env` and subscribe to the `messages` field.
- On Twilio, set it as the "When a message comes in" URL with method POST.

Sessions are stored in `webhook/conversation/sessoes.db`. To reset all conversations, delete this file while the server is stopped.

## Next steps

- Add unit tests for the router that use fake extractor and search services.
- Verify webhook signatures from Meta and Twilio.
- Build a way for human agents to take over escalated sessions.
- Move message deduplication out of memory, so the app can run with multiple workers.
- Remove the unused `webhook/agent.py`, and stop tracking `__pycache__/` and `sessoes.db` in git.
