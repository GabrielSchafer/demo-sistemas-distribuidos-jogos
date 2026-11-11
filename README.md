# Demo: sistemas distribuídos em MMORPGs (Tibia × WoW)

Python 3.8+ puro, sem dependências. Cada componente é um processo separado; comunicação só por TCP (JSON por linha).

## Rodar os cenários

Dentro da pasta `demo-sd` (no Linux/macOS, troque `python` por `python3`):

```
python demo.py tibia            # dispatcher único: só um jogador pega o item
python demo.py tibia --unsafe   # uma thread por ação: o item DUPLICA
python demo.py tibia --crash    # Antica cai, Inabra segue; Antica volta com rollback
python demo.py wow              # cross-realm zone + shards criados e encerrados sob demanda
```

Cada cenário dura de 15 a 25 segundos e termina sozinho com "fim da demonstração".

## O que cada cenário mostra

| Cenário | Conceito de SD | O que observar no log |
|---|---|---|
| `tibia` | Ordem total via fila única | Todas as ações em `[Antica/dispatcher]`; Alice pega, Bob recebe "já não está no chão" |
| `tibia --unsafe` | Condição de corrida | Linhas vêm de `worker-alice` e `worker-bob`; aparece `⚠ ITEM DUPLICADO` |
| `tibia --crash` | Isolamento de falhas e checkpoint | Inabra continua salvando; Antica volta do save e a moeda da Carol some |
| `wow` | Particionamento dinâmico | `CRZ: Azralon + Gallywix` no mesmo shard; `iniciando NOVO processo elwynn#2`; Varian sozinho no shard novo |

## Arquitetura

```
TIBIA                                   WORLD OF WARCRAFT
cliente ──► login_server :7171          cliente ──► auth_server :3724
   │         (só autentica)                │
   └──────► game_server Antica :7172       └──► zone_router :8085 (escolhe o shard)
            game_server Inabra :7173                 │
            ├ thread rede                            ├──► zone_shard elwynn#1 :9001 (processo)
            ├ thread dispatcher (toda a lógica)      ├──► zone_shard elwynn#2 :9002 (processo)
            └ thread scheduler (só agenda)           └──► ... criados e destruídos sob demanda
```

Cada caixa é um **processo separado**, e eles só conversam por **TCP** (mensagens JSON, uma por linha).


## Problemas comuns

- **`python` não é reconhecido**: instale pelo python.org e marque "Add Python to PATH", ou tente `py demo.py tibia` no Windows.
- **Address already in use / porta em uso**: sobrou um processo de uma execução interrompida. Feche o terminal e abra outro, ou rode `taskkill /F /IM python.exe` (Windows) ou `pkill -f demo-sd` (Linux/macOS).
- **Acentos estranhos no Windows**: rode `chcp 65001` antes da demo.

> Simulação didática. O servidor oficial do Tibia é fechado e a Blizzard não publica a arquitetura do WoW. O modelo do Tibia segue o servidor aberto The Forgotten Server, e o do WoW segue o comportamento documentado de sharding e cross-realm zones.
