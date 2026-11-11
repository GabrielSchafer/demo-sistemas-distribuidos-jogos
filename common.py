"""Utilitários compartilhados: protocolo JSON-por-linha sobre TCP e log."""
import asyncio
import json
import sys
import time

HOST = "127.0.0.1"


def log(src, msg):
    # uma única escrita por linha: processos que compartilham o terminal não se misturam
    sys.stdout.write(f"{time.strftime('%H:%M:%S')} [{src}] {msg}\n")
    sys.stdout.flush()


async def send(writer, obj):
    writer.write((json.dumps(obj) + "\n").encode())
    await writer.drain()


async def recv(reader):
    line = await reader.readline()
    return json.loads(line) if line else None


async def request(port, obj, host=HOST):
    """Abre conexão, envia um pedido, lê uma resposta e fecha."""
    reader, writer = await asyncio.open_connection(host, port)
    await send(writer, obj)
    resp = await recv(reader)
    writer.close()
    return resp
