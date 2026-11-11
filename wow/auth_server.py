"""Servidor de autenticação do WoW (porta 3724, a mesma do jogo real).

Valida a conta e devolve a lista de realms. O jogo em si acontece em outros
processos.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common import HOST, log, recv, send  # noqa: E402

PORT = 3724
REALMS = [
    {"name": "Azralon", "world_port": 8085},
    {"name": "Gallywix", "world_port": 8085},
]


async def handle(reader, writer):
    msg = await recv(reader)
    log("auth", f"conta '{msg['account']}' autenticada -> realms: {', '.join(r['name'] for r in REALMS)}")
    await send(writer, {"ok": True, "realms": REALMS})
    writer.close()


async def main():
    server = await asyncio.start_server(handle, HOST, PORT)
    log("auth", f"escutando em {HOST}:{PORT}")
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
