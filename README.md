# ARM Monero Miner Dashboard

Dashboard local para controlar e monitorar o [XMRig](https://github.com/xmrig/xmrig) em Android/Termux ARM64 ou ARMv7 32-bit, sem root. O projeto **não implementa RandomX**: compila e executa o motor consolidado XMRig como processo separado.

> Mineração contínua aquece o aparelho, degrada a bateria e pode ser antieconômica. Use somente hardware, carteira e rede sob sua autorização.

## Viabilidade e limitações

- XMRig possui backend CPU ARM; a instalação seleciona `ARM_TARGET=8` em aarch64 ou `ARM_TARGET=7` em Termux `arm`, sem CUDA, OpenCL ou hwloc.
- Em ARMv7/ARMv8l 32-bit, o modo `light` é obrigatório e usa execução interpretada, portanto o desempenho será muito inferior ao ARM64.
- RandomX fast usa aproximadamente 2.080 MB para o dataset mais 256 MB de cache. Com pouca RAM, use `randomx_mode = "light"` (cerca de 256 MB, mas bem mais lento).
- Huge pages e MSR/1GB pages ficam desativados: Android sem root normalmente não permite configurá-los, e MSR é específico de x86.
- Temperatura e frequência dependem dos arquivos permitidos pelo fabricante em `/sys`; o painel mostra **Indisponível** quando bloqueados.
- `cpu_limit` limita a quantidade máxima de threads, não a porcentagem instantânea de cada núcleo.
- Não há estimativa financeira: sem cotação, dificuldade/payout verificáveis e dados do pool, ela seria enganosa.

## Arquitetura

O navegador usa REST e SSE com um backend Python sem dependências externas. Ele inicia o XMRig sem shell e consulta sua API somente em `127.0.0.1`. Controles exigem token aleatório e a carteira é mascarada nas métricas públicas.

```text
Navegador LAN ──HTTP/SSE──> Backend :8080 ──processo/sinais──> XMRig
                                  └──HTTP loopback :18080─────┘
```

## Requisitos e instalação

- Android 8+ recomendado e Termux `aarch64` ou `arm` do [F-Droid ou GitHub oficial](https://github.com/termux/termux-app#installation).
- Aproximadamente 3 GB livres para RandomX auto/fast; use light em aparelhos limitados.
- Carteira pública Monero. Chaves privadas nunca são solicitadas.

```sh
pkg update
pkg install -y git
git clone URL_DESTE_REPOSITORIO arm-monero-dashboard
cd arm-monero-dashboard
./install.sh
```

O instalador valida a arquitetura, instala Python/Clang/CMake/libuv/OpenSSL, baixa uma versão fixada do XMRig e compila em Release. Para testar outra versão: `XMRIG_VERSION=vX.Y.Z ./install.sh`. Não use `curl | sh`.

Edite `config.toml` (criado a partir de `config.example.toml`):

```toml
[miner]
pool = "pool.example.org:3333"
pool_password = "{worker}"
wallet = "SEU_ENDERECO_PUBLICO_MONERO"
worker = "meu-android"
threads = 2
cpu_limit = 50
randomx_mode = "auto"

[server]
dashboard_host = "127.0.0.1"
dashboard_port = 8080
lan_access = false
```

Para acesso LAN, altere **as duas** opções para `dashboard_host = "0.0.0.0"` e `lan_access = true`. Então:

```sh
./start.sh
./status.sh
./stop.sh
```

Abra o endereço impresso por `start.sh`. O IP também pode ser obtido com `ip route get 1`. O token administrativo fica em `data/admin.token` com permissão `0600`; informe-o no painel. `uninstall.sh` não apaga dados automaticamente.

## API e configuração

Todos os campos estão em [`config.example.toml`](config.example.toml). Pool aceita `host:porta`, `stratum+tcp://`, `stratum+ssl://` ou `stratum+tls://`. Threads não podem exceder as CPUs detectadas.

- `GET /api/v1/status` e `GET /api/v1/events`: leitura sanitizada/SSE.
- `POST /api/v1/miner/{start|stop|pause|resume|restart}`: controle autenticado.
- `GET /api/v1/logs`: últimas 500 linhas, autenticado.
- `PUT /api/v1/config`: altera pool, carteira, worker, threads, limite, prioridade e modo com o minerador parado.

Use `Authorization: Bearer TOKEN`:

```sh
TOKEN="$(cat data/admin.token)"
curl -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -X PUT -d '{"threads":2,"cpu_limit":50}' http://127.0.0.1:8080/api/v1/config
```

## Segurança

O padrão escuta apenas no loopback. Habilite LAN explicitamente e somente em rede confiável. HTTP na LAN não cifra o token: não encaminhe a porta no roteador nem exponha o serviço à internet. A API limita o corpo, valida campos/tipos e não aceita comandos. Use reverse proxy com TLS em redes não confiáveis.

## Logs e diagnóstico

- `data/dashboard.log`: backend e saída do XMRig, com rotação.
- `data/launcher.log`: erros anteriores ao servidor.
- `data/xmrig.generated.json`: configuração gerada (inclui carteira pública e token interno local).

Valide com `python -m armminer.server --config config.toml --check`. Se Android encerrar o processo, retire o Termux da otimização de bateria. Opcionalmente use `termux-wake-lock` conscientemente. Para aquecimento, reduza `threads` e `cpu_limit`.

## Testes

```sh
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

No Android, teste compilação aarch64, TLS com o pool, start/pause/resume/stop, acesso por outro aparelho, token inválido, queda de Wi-Fi, tela bloqueada e 30–60 minutos de temperatura/throttling.

## Referências

- [Opções de compilação do XMRig](https://github.com/xmrig/xmrig/blob/master/doc/build/CMAKE_OPTIONS.md)
- [API HTTP do XMRig](https://xmrig.com/docs/miner/api)
- [Memória e otimização RandomX](https://xmrig.com/docs/miner/randomx-optimization-guide)
- [Huge pages no XMRig](https://xmrig.com/docs/miner/hugepages)

Licença do dashboard: MIT. XMRig é separado e distribuído sob GPL-3.0.
