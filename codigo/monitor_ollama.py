
import threading
import time
try:
    import psutil
except ImportError:
    psutil = None


def _processos():
    if psutil is None:
        return []
    encontrados = []
    for p in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            nome = (p.info['name'] or '').lower()
            cmd = ' '.join(p.info['cmdline'] or []).lower()
            # Servidor e runners Ollama; não inclui Python nem todo o sistema.
            if ('ollama' in nome or 'ollama runner' in cmd) and 'ollama' in (nome + ' ' + cmd):
                encontrados.append(p)
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
            continue
    return encontrados


class MonitorOllama:
    def __init__(self, intervalo=0.1):
        self.intervalo = intervalo
        self._parar = threading.Event()
        self._thread = None
        self._amostras = []
        self._cpu_inicial = {}
        # Maior tempo de CPU já visto de cada processo. Não é apagado quando o processo
        # termina, e inclui processos que começaram DEPOIS do início da medição.
        self._cpu_ultimo = {}
        self._inicio = None
        self._fim = None

    def _capturar(self):
        rss = 0
        cpus = {}
        pids = []
        for p in _processos():
            try:
                with p.oneshot():
                    t = p.cpu_times()
                    cpus[p.pid] = t.user + t.system
                    rss += p.memory_info().rss
                    pids.append(p.pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
                continue
        return cpus, rss / 1048576, pids

    def _executar(self):
        while not self._parar.wait(self.intervalo):
            self._registrar()

    def _registrar(self):
        cpus, rss, pids = self._capturar()
        for pid, valor in cpus.items():
            self._cpu_ultimo[pid] = max(valor, self._cpu_ultimo.get(pid, 0.0))
        if pids:
            self._amostras.append((rss, pids))

    def __enter__(self):
        self._inicio = time.perf_counter()
        if psutil is not None:
            self._cpu_inicial, _, _ = self._capturar()
            self._registrar()
            self._thread = threading.Thread(target=self._executar, daemon=True)
            self._thread.start()
        return self

    def __exit__(self, *args):
        self._fim = time.perf_counter()
        if self._thread is not None:
            self._parar.set()
            self._thread.join(timeout=2)
            self._registrar()

    def resultado(self):
        base = {'cpu_ollama_percentual': None, 'ram_ollama_pico_mib': None,
                'ram_ollama_media_mib': None, 'amostras_monitoramento': len(self._amostras),
                'metodo_recursos': 'processos_ollama_cpu_time_rss_100ms_v2'}
        if not self._amostras or self._inicio is None or self._fim is None:
            return base
        duracao = max(self._fim - self._inicio, 1e-9)
        # Processo que já existia: CPU gasta desde o início da medição.
        # Processo novo (por exemplo, o runner que carrega o modelo nesta chamada): toda a sua CPU.
        deltas = [max(0.0, valor - self._cpu_inicial.get(pid, 0.0))
                  for pid, valor in self._cpu_ultimo.items()]
        rss = [item[0] for item in self._amostras]
        base.update(cpu_ollama_percentual=round(100 * sum(deltas) / duracao, 2) if deltas else None,
                    ram_ollama_pico_mib=round(max(rss), 2),
                    ram_ollama_media_mib=round(sum(rss) / len(rss), 2))
        return base
