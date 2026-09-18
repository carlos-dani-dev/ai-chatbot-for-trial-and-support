import json
import sqlite3
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Protocol

from .states import DadosCadastrais, Estado, Mensagem, Sessao

DB_PATH_PADRAO = Path(__file__).resolve().parent / "sessoes.db"


class SessaoRepo(Protocol):
    def carregar(self, telefone: str) -> Sessao | None: ...
    def salvar(self, sessao: Sessao) -> None: ...


class SessaoRepoSQLite:

    def __init__(self, db_path: Path | str = DB_PATH_PADRAO):
        self._db_path = str(db_path)

    def _conectar(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessoes (
                telefone TEXT PRIMARY KEY,
                dados TEXT NOT NULL,
                atualizado_em TEXT NOT NULL
            )
            """
        )
        return conn

    def carregar(self, telefone: str) -> Sessao | None:
        with self._conectar() as conn:
            linha = conn.execute("SELECT dados FROM sessoes WHERE telefone = ?", (telefone,)).fetchone()

        return _desserializar(linha[0]) if linha else None

    def salvar(self, sessao: Sessao) -> None:
        sessao.atualizado_em = datetime.now()
        bruto = _serializar(sessao)

        with self._conectar() as conn:
            conn.execute(
                """
                INSERT INTO sessoes (telefone, dados, atualizado_em) VALUES (?, ?, ?)
                ON CONFLICT(telefone) DO UPDATE SET dados = excluded.dados, atualizado_em = excluded.atualizado_em
                """,
                (sessao.telefone, bruto, sessao.atualizado_em.isoformat()),
            )


def _serializar(sessao: Sessao) -> str:
    return json.dumps(asdict(sessao), default=lambda o: o.isoformat(), ensure_ascii=False)


def _desserializar(bruto: str) -> Sessao:
    dado = json.loads(bruto)

    dado["estado"] = Estado(dado["estado"])
    dado["dados"] = DadosCadastrais(**dado["dados"])
    dado["historico"] = [
        Mensagem(
            papel=m["papel"],
            texto=m["texto"],
            resposta_busca=m.get("resposta_busca"),
            timestamp=datetime.fromisoformat(m["timestamp"]),
        )
        for m in dado["historico"]
    ]
    dado["atualizado_em"] = datetime.fromisoformat(dado["atualizado_em"])

    return Sessao(**dado)
