"""Censo 2025: modelo consulta microdados via SQL; nenhuma soma é pré-calculada no prompt.

Requer apenas biblioteca padrão. Primeira execução importa o CSV para SQLite local.
O banco é cache derivado do CSV, nunca do JSON de gabaritos.
"""
import csv
import hashlib
import json
import os
import re
import sqlite3
import time
from pathlib import Path

PASTA_CSV = Path('dados/censo_escolar/originais/microdados_2025')
PASTA_CACHE = Path('dados/censo_escolar/cache_sql')
CAMINHO_DICIONARIO = Path('dados/censo_escolar/originais/dicionario_variaveis.txt')


def localizar_csv():
    arquivos = sorted(PASTA_CSV.rglob('*.csv')) if PASTA_CSV.exists() else []
    preferidos = [p for p in arquivos if p.name.casefold() == 'tabela_matricula_2025_v2.csv']
    if len(preferidos) == 1:
        return preferidos[0]
    if len(arquivos) == 1:
        return arquivos[0]
    raise FileNotFoundError(f'CSV não encontrado ou ambíguo em {PASTA_CSV}: {arquivos}')


def _leitor_csv(caminho):
    arquivo = caminho.open('r', encoding='latin-1', newline='')
    amostra = arquivo.read(4096)
    arquivo.seek(0)
    delimitador = ';' if amostra.count(';') > amostra.count(',') else ','
    return arquivo, csv.DictReader(arquivo, delimiter=delimitador)


class SessaoCenso:
    def __init__(self):
        self.caminho = localizar_csv()
        arq, leitor = _leitor_csv(self.caminho)
        try:
            self.colunas = tuple(leitor.fieldnames or ())
        finally:
            arq.close()
        if not {'CO_ENTIDADE', 'QT_MAT_BAS'}.issubset(self.colunas):
            raise ValueError('CSV não contém as colunas essenciais.')
        self.colunas_numericas = {c for c in self.colunas if c.startswith('QT_')}
        self.banco = PASTA_CACHE / 'matriculas_2025.sqlite3'
        self.marca = PASTA_CACHE / 'matriculas_2025.fonte.json'
        self._preparado = False

    def plano(self, questao):
        pergunta = str(questao.get('pergunta') or questao.get('enunciado') or '').strip()
        if not pergunta:
            raise ValueError('Questão sem enunciado.')
        return {'pergunta': pergunta}

    def consultar(self, questao):
        """Retorna SOMENTE esquema e documentação, nunca resultados de consultas."""
        self.plano(questao)
        lista = ', '.join(self.colunas)
        texto = (
            'Fonte: Tabela_Matricula_2025_V2.csv. Tabela SQL: matriculas.\n'
            f'Colunas disponíveis: {lista}\n'
            'Colunas QT_* são inteiros; outras colunas são texto. '
            'Códigos categóricos devem ser comparados como strings, por exemplo TP_LOCALIZACAO = \'2\'.\n'
            'Para contar escolas, use COUNT(DISTINCT CO_ENTIDADE). '
            'Para somar matrículas, use SUM(QT_MAT_BAS). '
            'Você deve formular e executar consultas; nenhum total foi fornecido antecipadamente.'
        )
        if CAMINHO_DICIONARIO.exists():
            texto += '\nDicionário oficial disponível por ferramenta: DICIONARIO: CODIGO_DA_VARIAVEL.'
        else:
            texto += '\nDicionário oficial NÃO fornecido. Não afirme ter consultado definições oficiais.'
        return texto

    def preparar_banco(self):
        if self._preparado:
            return
        PASTA_CACHE.mkdir(parents=True, exist_ok=True)
        stat = self.caminho.stat()
        fonte = {'arquivo': str(self.caminho.resolve()), 'bytes': stat.st_size,
                 'mtime_ns': stat.st_mtime_ns, 'colunas': self.colunas}
        if self.banco.exists() and self.marca.exists():
            try:
                if json.loads(self.marca.read_text(encoding='utf-8')) == fonte:
                    self._preparado = True
                    return
            except (ValueError, OSError):
                pass
        temporario = self.banco.with_suffix('.tmp.sqlite3')
        temporario.unlink(missing_ok=True)
        conexao = sqlite3.connect(temporario)
        try:
            campos = ', '.join('"' + c + '" ' + ('INTEGER' if c in self.colunas_numericas else 'TEXT')
                              for c in self.colunas)
            conexao.execute(f'CREATE TABLE matriculas ({campos})')
            insercao = 'INSERT INTO matriculas VALUES (' + ','.join('?' for _ in self.colunas) + ')'
            arq, leitor = _leitor_csv(self.caminho)
            try:
                lote = []
                for linha in leitor:
                    valores = []
                    for coluna in self.colunas:
                        valor = (linha.get(coluna) or '').strip()
                        if coluna in self.colunas_numericas:
                            valores.append(int(valor) if valor else None)
                        else:
                            valores.append(valor or None)
                    lote.append(tuple(valores))
                    if len(lote) >= 250:
                        conexao.executemany(insercao, lote)
                        lote.clear()
                if lote:
                    conexao.executemany(insercao, lote)
            finally:
                arq.close()
            conexao.commit()
        except Exception:
            conexao.close()
            temporario.unlink(missing_ok=True)
            raise
        conexao.close()
        os.replace(temporario, self.banco)
        self.marca.write_text(json.dumps(fonte, ensure_ascii=False), encoding='utf-8')
        self._preparado = True

    def executar_sql(self, consulta):
        consulta = str(consulta).strip().rstrip(';').strip()
        if not re.match(r'^(SELECT|WITH)\b', consulta, flags=re.I):
            raise ValueError('A ferramenta aceita somente SELECT ou WITH ... SELECT.')
        if ';' in consulta or len(consulta) > 6000:
            raise ValueError('Somente uma consulta SQL curta por chamada.')
        self.preparar_banco()
        conexao = sqlite3.connect(f'file:{self.banco.resolve().as_posix()}?mode=ro', uri=True)
        inicio = time.monotonic()
        try:
            # Mesmo WITH que tente modificar dados não tem autorização.
            permitidos = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ,
                          sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_RECURSIVE}
            conexao.set_authorizer(lambda acao, a, b, db, fonte:
                                   sqlite3.SQLITE_OK if acao in permitidos else sqlite3.SQLITE_DENY)
            conexao.set_progress_handler(lambda: 1 if time.monotonic() - inicio > 12 else 0, 20000)
            cursor = conexao.execute(consulta)
            nomes = [item[0] for item in cursor.description or []]
            linhas = cursor.fetchmany(31)
            truncado = len(linhas) > 30
            resultado = [dict(zip(nomes, linha)) for linha in linhas[:30]]
            return {'colunas': nomes, 'linhas': resultado, 'truncado': truncado,
                    'duracao_sql_segundos': round(time.monotonic() - inicio, 3)}
        finally:
            conexao.close()

    def consultar_dicionario(self, variavel):
        """Busca somente o cabecalho exato da variavel no dicionario oficial."""
        if not CAMINHO_DICIONARIO.is_file():
            return {'erro': 'Dicionário oficial não encontrado.'}
        variavel = str(variavel).strip().upper()
        if not re.fullmatch(r'[A-Z][A-Z0-9_]{2,80}', variavel):
            return {'erro': 'Código de variável inválido.'}
        texto = CAMINHO_DICIONARIO.read_text(encoding='utf-8')
        for bloco in re.split(r'\n\s*\n', texto):
            linhas = bloco.strip().splitlines()
            if linhas and linhas[0].strip().upper() == f'VARIÁVEL: {variavel}':
                return {'variavel': variavel, 'trechos': [bloco.strip()]}
        return {'erro': f'{variavel} não encontrada no dicionário.'}


def verificar_consultas(questoes):
    sessao = SessaoCenso()
    for questao in questoes:
        sessao.plano(questao)
    return True


def contexto_censo(questao):
    return SessaoCenso().consultar(questao)
