"""Clientes simulados do Tibia.

Cada bot faz login no login server, recebe a lista de mundos e abre uma
conexão direta com o game server escolhido. Aos ~5s, Alice e Bob tentam pegar
o MESMO item no MESMO instante — o teste de consistência.
"""
import asyncio
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common import HOST, log, recv, request, send  # noqa: E402

LOGIN_PORT = 7171
BOTS = [("alice", "Antica"), ("bob", "Antica"), ("carol", "Antica"), ("dani", "Inabra"), ("edu", "Inabra")]
CRASH = "--crash" in sys.argv
DURATION = 14 if CRASH else 10


async def connect(name, world_name):
    login = await request(LOGIN_PORT, {"op": "login", "account": name, "password": "123"})
    world = next(w for w in login["worlds"] if w["name"] == world_name)
    log(f"bot:{name}", f"login ok, conectando direto em {world_name} (porta {world['port']})")
    reader, writer = await asyncio.open_connection(HOST, world["port"])
    await send(writer, {"op": "enter", "player": name})
    await recv(reader)
    return reader, writer


async def act(conn, cmd):
    reader, writer = conn
    await send(writer, cmd)
    return await recv(reader)


async def wander(name, conn, stop):
    try:
        while not stop.is_set():
            r = await act(conn, {"op": "move", "player": name, "dx": random.choice([-1, 0, 1]), "dy": random.choice([-1, 0, 1])})
            if r is None:
                raise ConnectionError
            await asyncio.sleep(random.uniform(0.6, 1.4))
    except (ConnectionError, OSError):
        log(f"bot:{name}", "conexão perdida com o servidor do mundo!")


async def main():
    conns = {}
    for name, world in BOTS:
        conns[name] = await connect(name, world)
        await asyncio.sleep(0.3)

    stop = asyncio.Event()
    walkers = [asyncio.create_task(wander(n, c, stop)) for n, c in conns.items() if n not in ("alice", "bob")]

    await asyncio.sleep(3)
    log("bots", ">>> Alice e Bob clicam no mesmo item no mesmo instante")
    a, b = await asyncio.gather(
        act(conns["alice"], {"op": "pickup", "player": "alice", "item": "mpa-1"}),
        act(conns["bob"], {"op": "pickup", "player": "bob", "item": "mpa-1"}),
    )
    log("bots", f"resultado: alice={'pegou' if a['ok'] else 'não pegou'}, bob={'pegou' if b['ok'] else 'não pegou'}")

    if CRASH:
        await asyncio.sleep(6.5)
        r = await act(conns["carol"], {"op": "pickup", "player": "carol", "item": "coin-1"})
        log("bots", f">>> carol pegou uma moeda DEPOIS do último save: {'ok' if r['ok'] else 'falhou'}")
        await asyncio.sleep(DURATION - 6.5)
    else:
        await asyncio.sleep(DURATION)
    stop.set()
    for t in walkers:
        t.cancel()


if __name__ == "__main__":
    asyncio.run(main())
