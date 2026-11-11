"""Orquestrador da demonstração.

Sobe cada componente como um PROCESSO separado (comunicação só por TCP) e
mostra os logs de todos no mesmo terminal, coloridos por componente.

  python demo.py tibia            # dispatcher único: consistência garantida
  python demo.py tibia --unsafe   # uma thread por ação: item duplica
  python demo.py tibia --crash    # derruba Antica: Inabra segue, Antica volta com rollback
  python demo.py wow              # cross-realm zones + sharding dinâmico
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import threading
import time

os.system("")  # habilita cores ANSI no terminal do Windows
HERE = os.path.dirname(os.path.abspath(__file__))
RESET = "\033[0m"
PALETTE = {
    "login": "\033[33m", "auth": "\033[33m",
    "dispatcher": "\033[36m", "scheduler": "\033[35m", "rede": "\033[34m", "worker": "\033[31m",
    "router": "\033[35m", "shard": "\033[36m", "bot": "\033[32m", "bots": "\033[1;32m",
}
procs = []


def color_for(line):
    if "⚠" in line:
        return "\033[1;31m"
    m = re.search(r"\[([^\]]+)\]", line)
    if not m:
        return ""
    tag = m.group(1)
    for key, col in PALETTE.items():
        if key in tag:
            return col
    return ""


def pump(proc):
    for line in proc.stdout:
        line = line.rstrip()
        if "SERVER SAVE" in line:
            print(f"\033[1;33m{line}{RESET}", flush=True)
        else:
            print(f"{color_for(line)}{line}{RESET}", flush=True)


def launch(rel, *args):
    env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8")
    p = subprocess.Popen([sys.executable, "-u", os.path.join(HERE, rel), *args],
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                         encoding="utf-8", env=env, cwd=HERE)
    procs.append(p)
    threading.Thread(target=pump, args=(p,), daemon=True).start()
    return p


def banner(text):
    print(f"\n\033[1m{'=' * 70}\n  {text}\n{'=' * 70}{RESET}\n", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scenario", choices=["tibia", "wow"])
    ap.add_argument("--unsafe", action="store_true", help="Tibia: sem dispatcher único")
    ap.add_argument("--crash", action="store_true", help="Tibia: derruba e reinicia o mundo Antica")
    a = ap.parse_args()
    try:
        if a.scenario == "tibia":
            banner("TIBIA — login server + 2 mundos (1 processo cada) + 5 clientes"
                   + ("  [MODO INSEGURO]" if a.unsafe else ""))
            shutil.rmtree(os.path.join(HERE, "saves"), ignore_errors=True)
            launch("tibia/login_server.py")
            extra = ["--unsafe"] if a.unsafe else []
            antica = launch("tibia/game_server.py", "--name", "Antica", "--port", "7172", *extra)
            launch("tibia/game_server.py", "--name", "Inabra", "--port", "7173", *extra)
            time.sleep(1)
            bots = launch("tibia/bots.py", *(["--crash"] if a.crash else []))
            if a.crash:
                time.sleep(12.5)
                antica.kill()
                banner("CRASH: o processo do mundo Antica foi morto à força. Inabra continua no ar.")
                time.sleep(3)
                banner("Reiniciando Antica a partir do último server save...")
                launch("tibia/game_server.py", "--name", "Antica", "--port", "7172", "--restore")
            bots.wait()
            time.sleep(1)
        else:
            banner("WORLD OF WARCRAFT — auth + roteador de zonas + shards sob demanda")
            launch("wow/auth_server.py")
            launch("wow/zone_router.py", "--cap", "4")
            time.sleep(1)
            launch("wow/bots.py").wait()
            time.sleep(1)
        banner("fim da demonstração")
    except KeyboardInterrupt:
        pass
    finally:
        for p in procs:
            p.terminate()


if __name__ == "__main__":
    main()
