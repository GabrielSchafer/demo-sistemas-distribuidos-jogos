"""Login server do Tibia (porta 7171).

Só autentica a conta e devolve a lista de mundos. Não guarda estado do jogo:
por isso pode ser pequeno, separado e facilmente replicado.
"""
import asyncio
import os
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common import HOST, log, recv, send  # noqa: E402

PORT = 7171
WORLDS = [
    {"name": "Antica", "port": 7172, "region": "EU"},
    {"name": "Inabra", "port": 7173, "region": "SA"},
]


async def handle(reader, writer):
    msg = await recv(reader)
    if msg and msg.get("op") == "login" and msg.get("password") == "123":
        token = uuid.uuid4().hex[:8]
        log("login", f"conta '{msg['account']}' autenticada (sessão {token}) -> {len(WORLDS)} mundos")
        await send(writer, {"ok": True, "session": token, "worlds": WORLDS})
    else:
        log("login", f"falha de login: {msg}")
        await send(writer, {"ok": False})
    writer.close()


async def main():
    server = await asyncio.start_server(handle, HOST, PORT)
    log("login", f"escutando em {HOST}:{PORT}")
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
