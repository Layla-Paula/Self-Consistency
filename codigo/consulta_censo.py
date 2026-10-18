"""Consulta os CSVs do Censo Escolar 2025 sem carregar tudo na memória.

Importante: as 50 perguntas exigem consultas distintas. As consultas abaixo são
implementações explícitas para perguntas 1, 2, 4, 5, 6 e 7. As demais são
bloqueadas até receberem consultas e, quando necessário, o dicionário de dados.
Nunca usa resposta_esperada para construir o contexto.
"""
import csv
from pathlib import Path

PASTA_CSV = Path('dados/censo_escolar/original/microdados_2025')


def localizar_csv():
    candidatos = list(PASTA_CSV.rglob('*.csv'))
    preferidos = [p for p in candidatos if p.name.casefold() == 'tabela_matricula_2025_v2.csv']
    if preferidos:
        return preferidos[0]
    candidatos = [p for p in candidatos if 'matricula' in p.name.casefold()]
    if len(candidatos) != 1:
        raise FileNotFoundError('Tabela de Matrícula não identificada sem ambiguidade. Confira dados/censo_escolar/original/microdados_2025.')
    return candidatos[0]


def abrir_tabela(caminho):
    for codificacao in ('utf-8-sig', 'latin-1'):
        try:
            with caminho.open(encoding=codificacao) as f:
                amostra = f.read(8192)
            break
        except UnicodeDecodeError:
            continue
    delimitador = ';' if amostra.count(';') > amostra.count(',') else ','
    arquivo = caminho.open(encoding=codificacao, newline='')
    leitor = csv.DictReader(arquivo, delimiter=delimitador)
    return arquivo, leitor


def contexto_censo(questao):
    numero = int(questao['numero'])
    # Questões conceituais e agrupamentos mais complexos exigem consulta específica,
    # para não confundir um resumo genérico com dados suficientes para responder.
    configuracao = {
        1: ('contagem', None),
        2: ('soma', 'QT_MAT_BAS'),
        4: ('distintos', 'SG_UF'),
        5: ('distintos', 'CO_MUNICIPIO'),
        6: ('distintos', 'NU_ANO_CENSO'),
        7: ('zeros', 'QT_MAT_BAS'),
    }.get(numero)
    if configuracao is None:
        raise NotImplementedError(f'Consulta CSV específica ainda não implementada para a questão {numero}. Não será enviada ao Ollama sem dados confiáveis.')
    operacao, coluna = configuracao
    caminho = localizar_csv()
    arquivo, leitor = abrir_tabela(caminho)
    try:
        if coluna and coluna not in (leitor.fieldnames or []):
            raise KeyError(f'Coluna {coluna} ausente de {caminho.name}; não é seguro inferir outra.')
        total = 0
        distintos = set()
        acumulado = 0
        zeros = 0
        for linha in leitor:
            total += 1
            if operacao == 'soma':
                valor = (linha[coluna] or '').strip()
                if valor:
                    acumulado += int(valor)
            elif operacao == 'distintos':
                valor = (linha[coluna] or '').strip()
                if valor:
                    distintos.add(valor)
            elif operacao == 'zeros':
                valor = (linha[coluna] or '').strip()
                if valor and int(valor) == 0:
                    zeros += 1
    finally:
        arquivo.close()
    fonte = f'Fonte consultada: {caminho.name}; linhas de escolas: {total}.'
    if operacao == 'contagem':
        return f'{fonte}\nContagem de registros de escolas: {total}.'
    if operacao == 'soma':
        return f'{fonte}\nSoma de {coluna}: {acumulado}.'
    if operacao == 'distintos':
        valores = ', '.join(sorted(distintos)) if len(distintos) <= 50 else '(muitos valores; somente a quantidade foi disponibilizada)'
        return f'{fonte}\nColuna {coluna}: {len(distintos)} valores distintos. Valores: {valores}.'
    return f'{fonte}\nColuna {coluna}: {zeros} registros iguais a zero.'