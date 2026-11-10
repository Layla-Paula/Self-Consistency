"""Recupera as falhas técnicas do Self-Consistency (só refaz o que falhou).

Uso (na raiz do projeto):
  python recuperar_falhas.py resultados/self_consistency            # pasta inteira
  python recuperar_falhas.py resultados/self_consistency/censo      # só um dataset
  python recuperar_falhas.py caminho/execucao.json                  # um arquivo
  python recuperar_falhas.py resultados/self_consistency --simular  # só lista, não executa
Opções: --rodadas N (repete até zerar as falhas, padrão 3), --incluir-totais.
"""
import argparse
from codigo.self_consistency.executar_self_consistency import recuperar

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('caminho', help='pasta (recursiva) ou arquivo .json de uma execução')
    p.add_argument('--simular', action='store_true', help='só mostra o que seria recuperado')
    p.add_argument('--rodadas', type=int, default=3)
    p.add_argument('--incluir-totais', action='store_true',
                   help='também refaz execuções em que TODAS as questões falharam')
    a = p.parse_args()
    opcoes = dict(simular=a.simular, rodadas=a.rodadas, incluir_totais=a.incluir_totais)
    from pathlib import Path
    recuperar(a.caminho, **(opcoes if Path(a.caminho).is_dir() else {}))
