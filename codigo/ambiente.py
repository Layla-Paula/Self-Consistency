"""Metadados de origem da execução; não altera a medição do tempo.

Configuração opcional na raiz do projeto: config_maquina.json
  {"identificador": "pc1"}  # Windows
  {"identificador": "pc2"}  # Linux

Não copiar o mesmo config_maquina.json para os dois computadores.
"""
import json
import os
import platform
import socket
from pathlib import Path


def _identificador_configurado():
    valor = os.environ.get('TCC_MAQUINA', '').strip()
    if valor:
        return valor
    caminho = Path('config_maquina.json')
    if caminho.is_file():
        dados = json.loads(caminho.read_text(encoding='utf-8'))
        if not isinstance(dados, dict):
            raise ValueError('config_maquina.json deve conter um objeto JSON.')
        valor = str(dados.get('identificador') or '').strip()
        if valor:
            return valor
    return None


def ambiente_atual():
    """Registra identidade configurada, sistema e características do equipamento."""
    nome = platform.node() or socket.gethostname()
    dados = {
        'identificador': _identificador_configurado(),
        'maquina': nome,
        'sistema': platform.system(),
        'versao_sistema': platform.release(),
        'arquitetura': platform.machine(),
        'processador': platform.processor() or None,
        'nucleos_logicos': os.cpu_count(),
        'python': platform.python_version(),
    }
    try:
        import psutil
        dados['ram_total_gib'] = round(psutil.virtual_memory().total / 1024**3, 2)
        dados['nucleos_fisicos'] = psutil.cpu_count(logical=False)
    except ImportError:
        dados['ram_total_gib'] = None
        dados['nucleos_fisicos'] = None
    return dados


if __name__ == '__main__':
    print(json.dumps(ambiente_atual(), ensure_ascii=False, indent=2))
