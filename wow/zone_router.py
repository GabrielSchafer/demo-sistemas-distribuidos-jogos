"""Roteador de zonas (porta 8085): decide em qual SHARD cada jogador fica.

- Cross-realm zone (CRZ): shards são compartilhados entre realms, então uma
  zona com pouca gente junta jogadores de Azralon e Gallywix.
- Sharding: quando um shard enche (SHARD_CAP), um NOVO PROCESSO de shard é
  iniciado em outra porta e os próximos jogadores vão para ele.
- Quando um shard esvazia, o processo é encerrado.
"""
import argparse
import asyncio
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common import HOST, log, recv, send  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument("--cap", type=int, default=4)
args = parser.parse_args()

PORT = 8085
SHARD_SCRIPT = os.path.join(os.path.dirname(__file__), "zone_shard.py")
shards = {}  # id -> {"port", "proc", "players": {nome: realm}}
next_port = 9001
next_id = 1


def describe(shard_id):
    s = shards[shard_id]
    realms = sorted(set(s["players"].values()))
    tag = " (CRZ: " + " + ".join(realms) + ")" if len(realms) > 1 else ""
    return f"{shard_id} {len(s['players'])}/{args.cap}{tag}"


async def spawn_shard(zone):
    global next_port, next_id
    shard_id = f"{zone.lower()}#{next_id}"
    port = next_port
    next_id += 1
    next_port += 1
    proc = subprocess.Popen([sys.executable, "-u", SHARD_SCRIPT, "--id", shard_id, "--port", str(port)],
                            stdin=subprocess.PIPE)  # se o roteador morrer, o shard percebe e encerra
    shards[shard_id] = {"port": port, "proc": proc, "players": {}}
    log("router", f"zona {zone} cheia -> iniciando NOVO processo {shard_id} na porta {port} (pid {proc.pid})"
        if next_id > 2 else f"iniciando processo {shard_id} na porta {port} (pid {proc.pid})")
    await asyncio.sleep(0.4)  # tempo para o processo subir
    for _ in range(50):  # em máquinas lentas pode levar mais: espera a porta aceitar conexão
        try:
            _, w = await asyncio.open_connection(HOST, port)
            w.close()
            break
        except OSError:
            await asyncio.sleep(0.1)
    return shard_id


async def handle(reader, writer):
    msg = await recv(reader)
    op, player, realm = msg["op"], msg["player"], msg.get("realm")
    if op == "enter":
        zone = msg["zone"]
        shard_id = next((sid for sid, s in shards.items() if len(s["players"]) < args.cap), None)
        if shard_id is None:
            shard_id = await spawn_shard(zone)
        shards[shard_id]["players"][player] = realm
        log("router", f"{player}-{realm} entra em {zone} -> {describe(shard_id)}")
        await send(writer, {"ok": True, "shard": shard_id, "port": shards[shard_id]["port"]})
    elif op == "leave":
        sid = msg["shard"]
        shards[sid]["players"].pop(player, None)
        log("router", f"{player}-{realm} saiu -> {describe(sid)}")
        if not shards[sid]["players"] and len(shards) > 1:
            shards[sid]["proc"].terminate()
            del shards[sid]
            log("router", f"{sid} vazio -> processo encerrado ({len(shards)} shard(s) ativos)")
        await send(writer, {"ok": True})
    writer.close()


async def main():
    server = await asyncio.start_server(handle, HOST, PORT)
    log("router", f"escutando em {HOST}:{PORT} — capacidade por shard: {args.cap}")
    try:
        async with server:
            await server.serve_forever()
    finally:
        for s in shards.values():
            s["proc"].terminate()


if __name__ == "__main__":
    asyncio.run(main())
