"""Consultas orientadas pelo ENUNCIADO aos microdados do Censo Escolar 2025.

Nao usa o ID para escolher consultas, nem usa resposta_esperada/gabarito.
Calcula indicadores verificaveis do CSV e apresenta somente o tema pertinente.
Nao exige arquivos auxiliares JSON nem dicionario externo.
"""
import csv
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

PASTA_CSV = Path('dados/censo_escolar/originais/microdados_2025')

# As regras descrevem TEMAS, nao IDs de questoes. O texto define o tema.
TEMAS = {
 'estrutura': r'escolas.*registrad|total de matriculas da educacao basica|qt_mat_bas nao inclui|estados|\buf\b|municipios distintos|nu_ano_censo|igual a zero|co_rede.*tp_dependencia',
 'administracao': r'rede publica|rede privada|dependencia administrativa|federal|estadual|municipal|escolas privadas|particular|filantrop|comunitaria|confessional|poder_publico_parceria|co_rede',
 'localizacao': r'urbana|rural|localizacao|regioes geograficas|zona rural|zona urbana|terra indigena|quilombola',
 'territorio': r'unidades da federacao|\buf\b|municipio brasileiro|estados|municipios distintos',
 'etapas': r'educacao infantil|ensino fundamental|ensino medio|educacao profissional|\beja\b|creche|pre-escola|serie|anos iniciais|anos finais|tecnico|libras',
 'perfil': r'sexo|feminino|masculino|cor/raca|preto|pardo|amarelo|indigena|nao declarada|faixa etaria|anos de idade|0 a 3|4 a 5|6 a 10|11 a 14|18 anos',
 'turno': r'turno|diurno|noturno|ead|matutino|vespertino|tempo integral',
 'inclusao': r'educacao especial|classes comuns|classes exclusivas|inclusao|libras',
 'transporte': r'transporte escolar|transp_publico|transp_resp',
 'residencia': r'zona de residencia|zr_urb|zr_rur|residencia do aluno',
}

GRUPOS = {
 'administracao': ('CO_REDE','TP_DEPENDENCIA','TP_CATEGORIA_ESCOLA_PRIVADA','IN_PODER_PUBLICO_PARCERIA'),
 'localizacao': ('TP_LOCALIZACAO','TP_LOCALIZACAO_DIFERENCIADA','NO_REGIAO'),
 'territorio': ('SG_UF','CO_MUNICIPIO'),
}

ETAPAS = ('QT_MAT_INF','QT_MAT_INF_CRE','QT_MAT_INF_PRE','QT_MAT_FUND',
 'QT_MAT_FUND_AI','QT_MAT_FUND_AF','QT_MAT_MED','QT_MAT_PROF',
 'QT_MAT_PROF_TEC','QT_MAT_PROF_TEC_CONC','QT_MAT_PROF_TEC_SUBS',
 'QT_MAT_EJA','QT_MAT_EJA_FUND','QT_MAT_EJA_MED','QT_MAT_BAS_LIBRAS')
PERFIL = ('QT_MAT_BAS_FEM','QT_MAT_BAS_MASC','QT_MAT_BAS_ND',
 'QT_MAT_BAS_BRANCA','QT_MAT_BAS_PRETA','QT_MAT_BAS_PARDA',
 'QT_MAT_BAS_AMARELA','QT_MAT_BAS_INDIGENA',
 'QT_MAT_BAS_0_3','QT_MAT_BAS_4_5','QT_MAT_BAS_6_10',
 'QT_MAT_BAS_11_14','QT_MAT_BAS_15_17','QT_MAT_BAS_18_MAIS')
TURNO = ('QT_MAT_BAS_D','QT_MAT_BAS_DM','QT_MAT_BAS_DV',
 'QT_MAT_BAS_N','QT_MAT_BAS_EAD','QT_MAT_BAS_INT')
INCLUSAO = ('QT_MAT_ESP','QT_MAT_ESP_CC','QT_MAT_ESP_CE','QT_MAT_BAS_LIBRAS')
TRANSPORTE = ('QT_TRANSP_PUBLICO','QT_TRANSP_RESP_EST','QT_TRANSP_RESP_MUN')
RESIDENCIA = ('QT_MAT_ZR_URB','QT_MAT_ZR_RUR','QT_MAT_ZR_NA')


def simplificar(texto):
    texto = unicodedata.normalize('NFKD', str(texto).lower())
    return ''.join(c for c in texto if not unicodedata.combining(c))


def localizar_csv():
    if not PASTA_CSV.is_dir():
        raise FileNotFoundError(f'Pasta de microdados nao encontrada: {PASTA_CSV.resolve()}')
    arquivos = [p for p in PASTA_CSV.rglob('*.csv') if 'matricula' in simplificar(p.stem)]
    preferidos = [p for p in arquivos if p.name.casefold() == 'tabela_matricula_2025_v2.csv']
    if len(preferidos) == 1:
        return preferidos[0]
    if len(arquivos) == 1:
        return arquivos[0]
    raise FileNotFoundError(f'CSV de matriculas ambiguo/ausente em {PASTA_CSV}: {arquivos}')


def abrir_tabela(caminho):
    for codificacao in ('latin-1',):
        try:
            with caminho.open('r', encoding=codificacao) as f:
                amostra = f.read(8192)
            break
        except UnicodeDecodeError:
            continue
    delimitador = ';' if amostra.count(';') > amostra.count(',') else ','
    arquivo = caminho.open('r', encoding=codificacao, newline='')
    return arquivo, csv.DictReader(arquivo, delimiter=delimitador)


def numero(valor):
    s = str(valor or '').strip()
    if not s:
        return 0
    if not re.fullmatch(r'-?\d+', s):
        raise ValueError(f'Valor nao inteiro no CSV: {valor!r}')
    return int(s)


def temas_da_pergunta(pergunta):
    texto = simplificar(pergunta)
    temas = {nome for nome, padrao in TEMAS.items() if re.search(padrao, texto)}
    # Variaveis explicitas: consulta direta, sem depender de uma lista de IDs.
    if 'qt_mat_' in texto:
        temas.add('variaveis_explicitas')
    if not temas:
        raise NotImplementedError('Tema da pergunta nao reconhecido com seguranca; revise o enunciado.')
    return temas


class SessaoCenso:
    def __init__(self):
        self.caminho = localizar_csv()
        arq, leitor = abrir_tabela(self.caminho)
        try:
            self.colunas = tuple(leitor.fieldnames or ())
        finally:
            arq.close()
        if 'QT_MAT_BAS' not in self.colunas or 'CO_ENTIDADE' not in self.colunas:
            raise ValueError('Tabela nao corresponde ao layout esperado de matriculas.')
        self._dados = None
        self.cache = {}

    def plano(self, questao):
        pergunta = str(questao.get('pergunta') or questao.get('enunciado') or '').strip()
        if not pergunta:
            raise ValueError(f"Questao {questao.get('id')} sem pergunta")
        temas = temas_da_pergunta(pergunta)
        explicitas = set(re.findall(r'\b(?:QT|CO|TP|IN|NU|SG|NO)_[A-Z0-9_]+\b', pergunta.upper()))
        faltantes = sorted(explicitas - set(self.colunas))
        if faltantes:
            raise KeyError(f'Variaveis citadas no enunciado ausentes no CSV: {faltantes}')
        return {'temas': temas, 'variaveis': explicitas}

    def _carregar(self):
        if self._dados is not None:
            return
        # Um unico percurso pelo CSV para todas as questoes e demonstracoes.
        somas = Counter()
        grupos = defaultdict(lambda: defaultdict(lambda: [0, 0]))
        regiao = defaultdict(lambda: [0, 0])
        ufs = defaultdict(int)
        municipios = defaultdict(int)
        anos = Counter()
        total = 0
        zeros = 0
        codigos_escolas = set()
        # Somamos somente variaveis de quantidade, nao codigos categoricos.
        colunas_qt = [c for c in self.colunas if c.startswith('QT_')]
        arq, leitor = abrir_tabela(self.caminho)
        try:
            for linha in leitor:
                total += 1
                codigos_escolas.add(linha['CO_ENTIDADE'])
                bas = numero(linha['QT_MAT_BAS'])
                zeros += (bas == 0)
                for coluna in colunas_qt:
                    somas[coluna] += numero(linha[coluna])
                anos[str(linha.get('NU_ANO_CENSO','')).strip()] += 1
                for grupo in GRUPOS['administracao'] + GRUPOS['localizacao']:
                    if grupo == 'NO_REGIAO':
                        continue
                    if grupo not in linha:
                        continue
                    chave = str(linha[grupo] or '').strip()
                    if chave:
                        grupos[grupo][chave][0] += 1
                        grupos[grupo][chave][1] += bas
                nome_regiao = str(linha.get('NO_REGIAO') or '').strip()
                loc = str(linha.get('TP_LOCALIZACAO') or '').strip()
                if nome_regiao:
                    regiao[nome_regiao][0] += bas
                    if loc == '2':
                        regiao[nome_regiao][1] += bas
                uf = str(linha.get('SG_UF') or '').strip()
                if uf:
                    ufs[uf] += bas
                municipio = str(linha.get('CO_MUNICIPIO') or '').strip()
                if municipio:
                    municipios[(uf, municipio, str(linha.get('NO_MUNICIPIO') or '').strip())] += bas
        finally:
            arq.close()
        self._dados = dict(somas=somas, grupos=grupos, regiao=regiao,
                           ufs=ufs, municipios=municipios, anos=anos,
                           total=total, escolas=len(codigos_escolas), zeros=zeros)

    def consultar(self, questao):
        chave = str(questao.get('id') or questao.get('pergunta'))
        if chave in self.cache:
            return self.cache[chave]
        plano = self.plano(questao)
        self._carregar()
        d = self._dados
        temas = plano['temas']
        pergunta = str(questao.get('pergunta') or questao.get('enunciado'))
        linhas = [f'Fonte: {self.caminho.name}; registros: {d["total"]}; escolas distintas (CO_ENTIDADE): {d["escolas"]}.',
                  f'Matriculas QT_MAT_BAS: {d["somas"]["QT_MAT_BAS"]}.']
        if 'estrutura' in temas:
            linhas += [f'Escolas com QT_MAT_BAS igual a zero: {d["zeros"]}.',
                      f'Anos observados (NU_ANO_CENSO): {dict(d["anos"])}.',
                      f'UFs distintas: {len(d["ufs"])}; municipios distintos: {len({m[1] for m in d["municipios"]})}.',
                      f'UFs: {", ".join(sorted(d["ufs"]))}.']
        if 'administracao' in temas or 'localizacao' in temas:
            for grupo in (GRUPOS['administracao'] if 'administracao' in temas else ()) + (('TP_LOCALIZACAO','TP_LOCALIZACAO_DIFERENCIADA') if 'localizacao' in temas else ()):
                if grupo not in d['grupos']:
                    continue
                linhas.append(f'Agrupamento por {grupo} (codigo: escolas; matriculas; media por escola):')
                for codigo, (escolas, matriculas) in sorted(d['grupos'][grupo].items()):
                    linhas.append(f'  {codigo}: {escolas}; {matriculas}; {matriculas/escolas:.2f}')
        if 'localizacao' in temas:
            linhas.append('Regioes (matriculas totais; matriculas em escolas rurais; percentual rural):')
            for reg, (t, rural) in sorted(d['regiao'].items()):
                linhas.append(f'  {reg}: {t}; {rural}; {100*rural/t:.2f}%' if t else f'  {reg}: sem matriculas')
        if 'territorio' in temas:
            linhas.append('Matriculas por UF: ' + '; '.join(f'{k}={v}' for k,v in sorted(d['ufs'].items(), key=lambda x:-x[1])))
            top = sorted(d['municipios'].items(), key=lambda x:-x[1])[:10]
            linhas.append('10 municipios com mais matriculas: ' + '; '.join(f'{nome}/{uf} ({codigo})={valor}' for (uf,codigo,nome),valor in top))
        # Identifica o tema pela pergunta, nao pelo numero da questao.
        conjuntos = {'etapas':ETAPAS, 'perfil':PERFIL, 'turno':TURNO,
                     'inclusao':INCLUSAO, 'transporte':TRANSPORTE, 'residencia':RESIDENCIA}
        for tema, colunas in conjuntos.items():
            if tema in temas:
                linhas.append(f'Indicadores do tema {tema}:')
                linhas.extend(f'  {c}: {d["somas"][c]}' for c in colunas if c in self.colunas)
        # Series especificas sao reconhecidas pelo texto da pergunta.
        t = simplificar(pergunta)
        if 'serie' in t or 'ano especifico' in t:
            if 'fundamental' in t:
                colunas = [f'QT_MAT_FUND_AI_{i}' for i in range(1,6)] + [f'QT_MAT_FUND_AF_{i}' for i in range(6,10)]
            elif 'medio' in t:
                colunas = [f'QT_MAT_MED_{i}' for i in range(1,4)]
            else:
                colunas = []
            linhas.extend(f'{c}: {d["somas"][c]}' for c in colunas if c in self.colunas)
        # Variaveis mencionadas explicitamente sao sempre consultadas.
        for c in sorted(plano['variaveis']):
            if c.startswith('QT_'):
                linhas.append(f'Soma solicitada {c}: {d["somas"][c]}')
        linhas.append('Categorias codificadas devem ser interpretadas conforme a documentacao oficial.')
        linhas.append('Estatisticas descritivas nao demonstram causalidade; interpretacoes exigem cautela.')
        resultado = '\n'.join(linhas)
        self.cache[chave] = resultado
        return resultado


def verificar_consultas(questoes):
    sessao = SessaoCenso()
    erros = []
    for q in questoes:
        try:
            sessao.plano(q)
        except (ValueError, KeyError, NotImplementedError) as e:
            erros.append(f'{q.get("id")}: {e}')
    if erros:
        raise ValueError('Enunciados nao processaveis:\n' + '\n'.join(erros))
    return True


def contexto_censo(questao):
    return SessaoCenso().consultar(questao)
