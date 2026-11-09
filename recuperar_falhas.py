"""Uso: python recuperar_falhas.py caminho/do/resultado.json"""
import sys
from codigo.self_consistency.executar_self_consistency import recuperar_falhas

if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Uso: python recuperar_falhas.py resultados/.../execucao.json')
    recuperar_falhas(sys.argv[1])
