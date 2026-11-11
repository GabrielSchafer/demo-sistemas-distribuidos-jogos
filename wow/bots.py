"""Jogadores simulados do WoW chegando e saindo de Elwynn Forest.

Primeiro chegam poucos (CRZ junta realms), depois muitos (novos shards sobem),
depois saem (shards vazios são encerrados).
"""
import asyncio
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common import HOST, log, recv, request, send  # noqa: E402

AUTH_PORT = 3724
PLAYERS = [
    ("Thrall", "Azralon"), ("Jaina", "Gallywix"), ("Anduin", "Azralon"), ("Sylvanas", "Gallywix"),
    ("Varian", "Azralon"), ("Tyrande", "Gallywix"), ("Illidan", "Azralon"), ("Arthas", "Gallywix"),
    ("Malfurion", "Azralon"), ("Garrosh", "Gallywix"),
]


async def play(name, realm, delay, stay):
    await asyncio.sleep(delay)
    auth = await request(AUTH_PORT, {"account": name.lower()})
    world_port = next(r["world_port"] for r in auth["realms"] if r["name"] == realm)
    route = await request(world_port, {"op": "enter", "player": name, "realm": realm, "zone": "Elwynn"})
    reader, writer = await asyncio.open_connection(HOST, route["port"])
    await send(writer, {"player": name, "realm": realm})
    first = await recv(reader)
    others = [p for p in first["visible"] if not p.startswith(name + "-")]
    log(f"bot:{name}", f"estou em {route['shard']} e vejo {len(others)} jogador(es): {', '.join(others) or 'ninguém'}")
    await asyncio.sleep(stay)
    writer.close()
    await request(world_port, {"op": "leave", "player": name, "realm": realm, "shard": route["shard"]})


async def main():
    random.seed(7)
    tasks = []
    for i, (name, realm) in enumerate(PLAYERS):
        tasks.append(play(name, realm, delay=i * 0.9, stay=random.uniform(9, 13)))
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
