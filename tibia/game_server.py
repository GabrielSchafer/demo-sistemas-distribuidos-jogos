"""Game server do Tibia: um processo por mundo.

Três threads, como no The Forgotten Server:
  - rede (asyncio): recebe pacotes e só os coloca na fila
  - dispatcher: ÚNICA thread que mexe no estado do mundo, uma ação por vez
  - scheduler: não mexe no mundo; só agenda tarefas (respawn, server save) na fila

Com --unsafe, cada ação roda na própria thread, sem fila: é o que acontece
quando se tenta paralelizar a lógica sem locks (e o item duplica).
"""
import argparse
import asyncio
import json
import os
import queue
import random
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common import HOST, log, recv, send  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument("--name", required=True)
parser.add_argument("--port", type=int, required=True)
parser.add_argument("--unsafe", action="store_true")
parser.add_argument("--save-every", type=float, default=10.0)
parser.add_argument("--restore", action="store_true", help="carrega o último server save ao iniciar")
args = parser.parse_args()

WORLD = args.name
world = {
    "players": {},  # nome -> {"pos": [x, y], "inv": [...]}
    "ground": {"mpa-1": {"name": "Magic Plate Armor", "pos": [5, 5]}},
}
cmd_q = queue.Queue()
loop = None
coin_seq = 0


def tlog(msg):
    log(f"{WORLD}/{threading.current_thread().name}", msg)


def apply(cmd):
    """Lógica do jogo. Em modo seguro, só a thread dispatcher chama isto."""
    global coin_seq
    op = cmd["op"]
    if op == "enter":
        world["players"].setdefault(cmd["player"], {"pos": [random.randint(0, 9), random.randint(0, 9)], "inv": []})
        tlog(f"{cmd['player']} entrou no mundo ({len(world['players'])} online)")
        return {"ok": True}
    if op == "move":
        p = world["players"][cmd["player"]]
        p["pos"][0] += cmd["dx"]
        p["pos"][1] += cmd["dy"]
        return {"ok": True, "pos": p["pos"]}
    if op == "pickup":
        item_id = cmd["item"]
        if item_id in world["ground"]:          # 1) verifica
            time.sleep(0.05)                     #    (janela de corrida)
            item = world["ground"].pop(item_id, None) or {"name": item_id}  # 2) remove
            world["players"][cmd["player"]]["inv"].append(item_id)          # 3) entrega
            tlog(f"{cmd['player']} pegou {item['name']}")
            owners = [n for n, p in world["players"].items() if item_id in p["inv"]]
            if len(owners) > 1:
                tlog(f"⚠ ITEM DUPLICADO: {item['name']} está com {', '.join(owners)}")
            return {"ok": True}
        tlog(f"{cmd['player']} tentou pegar {item_id}, mas já não está no chão")
        return {"ok": False}
    if op == "respawn":
        coin_seq += 1
        world["ground"][f"coin-{coin_seq}"] = {"name": "gold coin", "pos": [random.randint(0, 9), random.randint(0, 9)]}
        tlog(f"respawn executado (itens no chão: {len(world['ground'])})")
        return {"ok": True}
    if op == "save":
        tlog("SERVER SAVE: mundo congelado, gravando snapshot...")
        os.makedirs("saves", exist_ok=True)
        path = os.path.join("saves", f"{WORLD}.json")
        with open(path, "w") as f:
            json.dump({**world, "saved_at": time.strftime("%H:%M:%S"), "coin_seq": coin_seq}, f, indent=1)
        tlog(f"SERVER SAVE concluído -> {path} ({len(world['players'])} jogadores, {len(world['ground'])} itens no chão)")
        return {"ok": True}
    return {"ok": False, "error": "op desconhecida"}


def dispatcher():
    while True:
        cmd, fut = cmd_q.get()
        result = apply(cmd)
        if fut is not None:
            loop.call_soon_threadsafe(fut.set_result, result)


def scheduler():
    last_save = time.time()
    while True:
        time.sleep(5)
        tlog("agendando respawn na fila do dispatcher")
        cmd_q.put(({"op": "respawn"}, None))
        if time.time() - last_save >= args.save_every:
            tlog("agendando SERVER SAVE na fila do dispatcher")
            cmd_q.put(({"op": "save"}, None))
            last_save = time.time()


async def submit(cmd):
    fut = loop.create_future()
    if args.unsafe:
        # Sem fila: cada ação numa thread própria, concorrendo pelo mesmo estado.
        def run():
            res = apply(cmd)
            loop.call_soon_threadsafe(fut.set_result, res)
        threading.Thread(target=run, name=f"worker-{cmd.get('player', '?')}").start()
    else:
        cmd_q.put((cmd, fut))
    return await fut


async def handle(reader, writer):
    while True:
        msg = await recv(reader)
        if msg is None:
            break
        result = await submit(msg)
        await send(writer, result)
    writer.close()


def restore():
    global world, coin_seq
    path = os.path.join("saves", f"{WORLD}.json")
    if not os.path.exists(path):
        tlog("nenhum server save encontrado: mundo começa do estado inicial")
        return
    with open(path) as f:
        snap = json.load(f)
    coin_seq = snap.pop("coin_seq", 0)
    saved_at = snap.pop("saved_at", "?")
    world = snap
    tlog(f"RESTAURADO do server save das {saved_at} — tudo depois disso foi perdido (rollback)")
    for name, p in world["players"].items():
        tlog(f"  {name}: inventário = {p['inv'] or 'vazio'}")


async def main():
    global loop
    loop = asyncio.get_running_loop()
    threading.current_thread().name = "rede"
    if args.restore:
        restore()
    threading.Thread(target=dispatcher, name="dispatcher", daemon=True).start()
    threading.Thread(target=scheduler, name="scheduler", daemon=True).start()
    server = await asyncio.start_server(handle, HOST, args.port)
    mode = "INSEGURO (uma thread por ação)" if args.unsafe else "seguro (dispatcher único)"
    tlog(f"mundo {WORLD} escutando em {HOST}:{args.port} — modo {mode}")
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
