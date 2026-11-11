"""Um shard de zona: processo independente, com sua própria porta e estado.

Jogadores conectados a este shard só enxergam uns aos outros; quem está em
outro shard da mesma zona é invisível.
"""
import argparse
import asyncio
import os
import sys
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common import HOST, log, recv, send  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument("--id", required=True)
parser.add_argument("--port", type=int, required=True)
args = parser.parse_args()

clients = {}  # nome -> writer


async def broadcast():
    names = sorted(clients)
    for w in list(clients.values()):
        try:
            await send(w, {"visible": names})
        except ConnectionError:
            pass


async def handle(reader, writer):
    msg = await recv(reader)
    if msg is None:  # sonda do roteador verificando se o shard já subiu
        return
    name = f"{msg['player']}-{msg['realm']}"
    clients[name] = writer
    log(f"shard {args.id}", f"{name} conectou. Visíveis aqui: {', '.join(sorted(clients))}")
    await broadcast()
    try:
        while await recv(reader) is not None:
            pass
    except ConnectionError:
        pass
    clients.pop(name, None)
    log(f"shard {args.id}", f"{name} desconectou ({len(clients)} restantes)")
    await broadcast()


def exit_when_router_dies():
    sys.stdin.read()  # EOF = o processo do roteador terminou
    os._exit(0)


async def main():
    threading.Thread(target=exit_when_router_dies, daemon=True).start()
    server = await asyncio.start_server(handle, HOST, args.port)
    log(f"shard {args.id}", f"processo pid {os.getpid()} escutando em {HOST}:{args.port}")
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
