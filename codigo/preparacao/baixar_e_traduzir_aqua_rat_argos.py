"""AQuA-RAT -> Português (PT-BR)
Autor: Layla Paula

"""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re
import tempfile
import hashlib
import time
from datetime import datetime


# PASTAS  

PASTA_AQUA_RAT = Path('dados/aqua_rat')
ARQUIVO_ORIGINAL = PASTA_AQUA_RAT / 'originais/aqua_rat_original.json'
ARQUIVO_TRADUCOES_EM_ANDAMENTO = PASTA_AQUA_RAT / 'traducoes/aqua_rat_em_processo.jsonl'
ARQUIVO_FINAL = PASTA_AQUA_RAT / 'final/aqua_rat_ptbr_argos.json'
ARQUIVO_FALHAS = PASTA_AQUA_RAT / 'traducoes/falhas_traducao.jsonl'
DIVISOES_DATASET = ('train', 'validation', 'test')
LETRAS_ALTERNATIVAS = 'ABCDE'
ORDEM_CAMPOS = ('id','split','question_en','options_en','rationale_en','correct',
         'question_pt','options_pt','rationale_pt','revisao_necessaria')


PADRAO_CARACTERES_CORROMPIDOS = re.compile(r'â[€€“]|Ã[£©]|\ufffd')
PADRAO_INGLES_NAO_TRADUZIDO = re.compile(r'\b(?:the\s+answer\s+is|then\s+\w+\s+will|'
                          r'when\s+\w+\s*=|hence\s+the|therefore\s+the|'
                          r'with\s+a\s+remainder|friend\s+[PQ]|'
                          r'only\s+[Ii]\s+and\s+[Ii]{2}|'
                          r'how\s+many|how\s+much|eqautions)\b', re.I)
SIMBOLOS_MATEMATICOS = '≠≤≥√∑∫∞±≈∴'
# Linhas essencialmente matemáticas são copiadas literalmente; o modelo não as altera.
PADRAO_LINHA_MATEMATICA = re.compile(r'^[\s\dA-Za-z_.,()\[\]{}+\-*/^=<>!%$€@|:;≠≤≥√∑∫∞±≈∴→⇒]+$')
PADRAO_OPERADORES = re.compile(r'(?:<=|>=|!=|==|[=≠≤≥])')
PADRAO_NUMEROS = re.compile(r'(?<![\w])\d+(?:[.,]\d+)*(?!\w)')


# DOWNLOAD DO DATASET 

def baixar_aqua_rat_se_necessario():
  
    if ARQUIVO_ORIGINAL.exists():
        print(f"Dataset AQuA-RAT original já existe: {ARQUIVO_ORIGINAL}", flush=True)
        print("O original será reutilizado sem nenhuma alteração.", flush=True)
        return "já existia; preservado"

    try:
        from datasets import load_dataset
    except ImportError as erro:
        raise RuntimeError("Instale o downloader: pip install datasets") from erro

    ARQUIVO_ORIGINAL.parent.mkdir(parents=True, exist_ok=True)
    print("Dataset original ausente. Baixando deepmind/aqua_rat (raw)...", flush=True)
    arquivo_temporario = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=ARQUIVO_ORIGINAL.parent,
            prefix=".aqua_original_", suffix=".tmp", delete=False
        ) as arquivo:
            arquivo_temporario = Path(arquivo.name)
            arquivo.write("[\n")
            primeira_questao = True
            total_baixado = 0
            for divisao in DIVISOES_DATASET:
                print(f"Baixando split {divisao}...", flush=True)
                # Iteração streaming evita carregar todo o dataset em RAM.
                conjunto = load_dataset("deepmind/aqua_rat", "raw", split=divisao, streaming=True)
                for indice, item in enumerate(conjunto):
                    questao = {
                        "id": f"aqua_rat_{divisao}_{indice:05d}",
                        "split": divisao,
                        "question_en": item["question"],
                        "options_en": organizar_alternativas(item["options"]),
                        "rationale_en": item.get("rationale", ""),
                        "correct": item["correct"],
                    }
                    if not primeira_questao:
                        arquivo.write(",\n")
                    json.dump(questao, arquivo, ensure_ascii=False)
                    primeira_questao = False
                    total_baixado += 1
            arquivo.write("\n]\n")
            arquivo.flush()
            os.fsync(arquivo.fileno())
        if total_baixado != 97975:
            raise ValueError(f"Esperadas 97.975 questões; recebidas {total_baixado}.")
        os.replace(arquivo_temporario, ARQUIVO_ORIGINAL)
        print(f"Download concluído: {total_baixado:,} questões. Original salvo.", flush=True)
        return "baixado nesta execução"
    finally:
        if arquivo_temporario and arquivo_temporario.exists():
            arquivo_temporario.unlink()


def percorrer_questoes_originais():
    """Usa ijson se disponível (streaming); sem ele, carrega o original uma vez."""
    if not ARQUIVO_ORIGINAL.exists():
        raise FileNotFoundError(f"Dataset original não encontrado: {ARQUIVO_ORIGINAL}")
    try:
        import ijson
    except ImportError:
        with ARQUIVO_ORIGINAL.open(encoding='utf-8') as f:
            obj = json.load(f)
        yield from (obj['problemas'] if isinstance(obj, dict) else obj)
    else:
        with ARQUIVO_ORIGINAL.open('rb') as f:
            primeiro = f.read(128).lstrip()[:1]
        prefixo = 'problemas.item' if primeiro == b'{' else 'item'
        with ARQUIVO_ORIGINAL.open('rb') as f:
            yield from ijson.items(f, prefixo)



# ORGANIZAR AS ALTERNATIVAS 

def organizar_alternativas(opcoes):
    if isinstance(opcoes, dict):
        return {k: str(opcoes[k]) for k in LETRAS_ALTERNATIVAS}
    saida = {}
    for item in opcoes:
        m = re.match(r'^\s*([A-E])\s*[).:\-]\s*(.*)$', item, re.S)
        if not m:
            raise ValueError(f'Alternativa inválida: {item!r}')
        saida[m.group(1)] = m.group(2).strip()
    if set(saida) != set(LETRAS_ALTERNATIVAS):
        raise ValueError('Alternativas A–E incompletas')
    return {k: saida[k] for k in LETRAS_ALTERNATIVAS}



#  CARREGAR OU INSTALAR O MODELO DE TRADUÇÃO 

def carregar_tradutor_argos():
    try:
        import argostranslate.translate as biblioteca_argos
    except ImportError as e:
        raise RuntimeError('Instale: pip install argostranslate') from e
    idiomas = biblioteca_argos.get_installed_languages()
    idioma_ingles = next((i for i in idiomas if i.code == 'en'), None)
    idioma_portugues = next((i for i in idiomas if i.code == 'pt'), None)
    if idioma_ingles is None or idioma_portugues is None:
        import argostranslate.package as pacotes_argos
        print("Pacote Argos inglês → português ausente. Instalando...", flush=True)
        pacotes_argos.update_package_index()
        pacotes = pacotes_argos.get_available_packages()
        pacote = next((item for item in pacotes if item.from_code == "en" and item.to_code == "pt"), None)
        if pacote is None:
            raise RuntimeError("Modelo Argos en→pt indisponível para download.")
        pacotes_argos.install_from_path(pacote.download())
        idiomas = biblioteca_argos.get_installed_languages()
        idioma_ingles = next((idioma for idioma in idiomas if idioma.code == "en"), None)
        idioma_portugues = next((idioma for idioma in idiomas if idioma.code == "pt"), None)
    if idioma_ingles is None or idioma_portugues is None:
        raise RuntimeError("Não foi possível carregar o modelo Argos en→pt.")
    return idioma_ingles.get_translation(idioma_portugues)


def linha_eh_formula(linha):
    t = linha.strip()
    if not t or not PADRAO_LINHA_MATEMATICA.fullmatch(t):
        return False
    if re.search(r'\b(?:and|or|when|then|the|with|answer|is|are|will|if|for|of|to)\b', t, re.I):
        return False
    return bool(PADRAO_OPERADORES.search(t) or re.search(r'\d\s*[/+*^]\s*\d', t))



# PROTEGER NÚMEROS, MOEDAS E EXPRESSÕES MATEMÁTICAS 


PADRAO_TRECHOS_PROTEGIDOS = re.compile(
    r"(?<![\w])(?:[$€£₹]|Rs\.?)\s*\d[\d.,]*(?:\s*[%])?"  # Moedas.
    r"|(?<![\w])(?:[A-Za-z]{1,3}|\d+(?:[.,]\d+)?)\s*(?:≠|≤|≥|!=|<=|>=|==|=|@|[+*/^]|(?<!\s)-(?!\s))\s*(?:√\s*)?[A-Za-z0-9]+(?:[.,]\d+)?(?:\s*(?:[+*/^=≠≤≥-])\s*[A-Za-z0-9]+)*"  # Fórmulas.
    r"|√\s*(?:\([^)]+\)|[A-Za-z0-9]+)(?:\s*[+*/^-]\s*[A-Za-z0-9]+)*"  # Raízes.
    r"|(?<![\w])\d+(?:[.,]\d+)*(?:[A-Za-z](?![A-Za-z])|\s*%|-(?:km|m|cm|kg|g|mile|year|digit)s?)?"  # Números.
    r"|[≠≤≥√∑∫∞±≈∴⇒→]"  # Símbolos individuais.
)


def traduzir_parte_sem_matematica(tradutor, parte):
    """Traduz apenas palavras; conserva espaços externos do trecho."""
    if not parte.strip() or not re.search(r'[A-Za-z]', parte):
        return parte
    inicio = len(parte) - len(parte.lstrip())
    fim = len(parte) - len(parte.rstrip())
    texto = parte.strip()
    traducao = tradutor.translate(texto)
    if not isinstance(traducao, str) or not traducao.strip():
        raise ValueError('Tradutor retornou texto vazio')
    return parte[:inicio] + traducao.strip() + (parte[len(parte)-fim:] if fim else '')


# TERMOS MATEMÁTICOS E FINANCEIROS IMPORTANTES 

# Estas substituições pontuais não dependem da escolha de palavras do Argos.
# A proteção é aplicada antes da tradução; os termos abaixo não são enviados ao modelo.
# Reconhece qualificadores entre "odd/even" e "integer/number", inclusive
# quando a ordem muda: "positive even integer" e "even positive integer".
# Nunca traduz "even" isoladamente: fora da matemática pode significar "até".
PADRAO_PARIDADE = re.compile(
    r"\b(?:(?:positive|negative|nonnegative|non-negative|nonpositive|non-positive)\s+)?"
    r"(?:odd|even)\s+"
    r"(?:(?:positive|negative|nonnegative|non-negative|nonpositive|non-positive)\s+)?"
    r"(?:integers?|numbers?|whole\s+numbers?)\b",
    re.I,
)
PADRAO_TERMOS_IMPORTANTES = re.compile(r"\b(?:tip|value\s+of\s+a)\b", re.I)


def traduzir_termo_importante(termo, linha_original):
    """Retorna PT apenas quando o contexto permite uma tradução segura."""
    normalizado = re.sub(r'\s+', ' ', termo.lower())
    if PADRAO_PARIDADE.fullmatch(termo):
        palavras = re.findall(r'[a-z]+(?:-[a-z]+)?', normalizado)
        paridade = 'ímpar' if 'odd' in palavras else 'par'
        qualificadores = {
            'positive': 'positivo', 'negative': 'negativo',
            'nonnegative': 'não negativo', 'non-negative': 'não negativo',
            'nonpositive': 'não positivo', 'non-positive': 'não positivo',
        }
        qualificacao = next((qualificadores[p] for p in palavras if p in qualificadores), '')
        # "whole number" significa número inteiro; evita "número todo".
        base = 'número inteiro' if 'whole' in palavras else (
            'número' if 'number' in palavras or 'numbers' in palavras else 'inteiro'
        )
        return ' '.join(x for x in (base, qualificacao, paridade) if x)
    if normalizado == 'value of a':
        return 'valor de a'
    # "tip" só vira gorjeta em um contexto claramente financeiro.
    if normalizado == 'tip' and re.search(
        r'\b(?:lunch|restaurant|waiter|bill|paid|pay|spend|meal|dinner)\b|[$€£₹]|\d\s*%',
        linha_original, re.I
    ):
        return 'gorjeta'
    return None


def traduzir_linha_protegida(tradutor, linha):
 
    if not linha.strip() or linha_eh_formula(linha) or not re.search(r'[A-Za-z]', linha):
        return linha

    # Enumerações romanas de questões (I., II., III.) não são palavras.
    marcador_romano = re.match(r'^(\s*)(I|II|III|IV|V|VI|VII|VIII|IX|X)(\.\s+)', linha)
    prefixo = marcador_romano.group(0) if marcador_romano else ''
    conteudo = linha[len(prefixo):]

    # Mescla termos de domínio e trechos matemáticos sem sobrepor intervalos.
    protegidos = [(m.start(), m.end(), m.group(), None)
                  for m in PADRAO_TRECHOS_PROTEGIDOS.finditer(conteudo)]
    for m in list(PADRAO_PARIDADE.finditer(conteudo)) + list(PADRAO_TERMOS_IMPORTANTES.finditer(conteudo)):
        traducao_fixa = traduzir_termo_importante(m.group(), conteudo)
        if traducao_fixa is not None and not any(
            m.start() < fim and m.end() > inicio
            for inicio, fim, _, _ in protegidos
        ):
            protegidos.append((m.start(), m.end(), m.group(), traducao_fixa))
    protegidos.sort(key=lambda item: item[0])

    partes = []
    ultima_posicao = 0
    for inicio, fim, original, traducao_fixa in protegidos:
        partes.append(traduzir_parte_sem_matematica(
            tradutor, conteudo[ultima_posicao:inicio]))
        # Fórmulas são copiadas; termos importantes recebem tradução controlada.
        partes.append(traducao_fixa if traducao_fixa is not None else original)
        ultima_posicao = fim
    partes.append(traduzir_parte_sem_matematica(tradutor, conteudo[ultima_posicao:]))
    return prefixo + ''.join(partes)


# TRADUZIR TEXTO SEM MODIFICAR LINHAS MATEMÁTICAS 

def traduzir_texto(tradutor, texto):
    """Traduz cada linha, mantendo fórmulas, números e moedas literalmente."""
    if not isinstance(texto, str) or not texto.strip():
        return ''
    return '\n'.join(traduzir_linha_protegida(tradutor, linha)
                     for linha in texto.split('\n'))


# VERIFICAR POSSÍVEIS PROBLEMAS NA TRADUÇÃO 

def traducao_precisa_revisao(orig, idioma_portugues):
    """Somente problemas fortes; não equivale a revisão semântica."""
    if orig.strip() and not idioma_portugues.strip():
        return True
    if PADRAO_CARACTERES_CORROMPIDOS.search(idioma_portugues) and not PADRAO_CARACTERES_CORROMPIDOS.search(orig):
        return True
    if PADRAO_INGLES_NAO_TRADUZIDO.search(idioma_portugues):
        return True
    # Confere símbolos matemáticos inequívocos, não espaços ou pontuação.
    if any(orig.count(s) != idioma_portugues.count(s) for s in SIMBOLOS_MATEMATICOS):
        return True
    # Compara valores exatamente: 60.00 e 60,00 são diferentes.
    def extrair_numeros(s):
        return Counter(PADRAO_TRECHOS_PROTEGIDOS.findall(s))
    if extrair_numeros(orig) != extrair_numeros(idioma_portugues):
        return True
    return False



# TRADUZIR UMA QUESTÃO COMPLETA 

def traduzir_questao(questao_original, tradutor):
    questao_traduzida = {k: questao_original[k] for k in ('id','split','question_en','rationale_en','correct')}
    questao_traduzida['options_en'] = organizar_alternativas(questao_original['options_en'])
    questao_traduzida['question_pt'] = traduzir_texto(tradutor, questao_traduzida['question_en'])
    questao_traduzida['options_pt'] = {k: traduzir_texto(tradutor, questao_traduzida['options_en'][k]) for k in LETRAS_ALTERNATIVAS}
    questao_traduzida['rationale_pt'] = traduzir_texto(tradutor, questao_traduzida['rationale_en'])
    questao_traduzida['revisao_necessaria'] = (traducao_precisa_revisao(questao_traduzida['question_en'], questao_traduzida['question_pt'])
        or traducao_precisa_revisao(questao_traduzida['rationale_en'], questao_traduzida['rationale_pt'])
        or any(traducao_precisa_revisao(questao_traduzida['options_en'][k], questao_traduzida['options_pt'][k]) for k in LETRAS_ALTERNATIVAS))
    return {k: questao_traduzida[k] for k in ORDEM_CAMPOS}



# RETOMAR PROGRESSO APÓS INTERRUPÇÃO 

def carregar_ids_ja_traduzidos():
   
    ids_traduzidos = set()
    if not ARQUIVO_TRADUCOES_EM_ANDAMENTO.exists():
        return ids_traduzidos
    with ARQUIVO_TRADUCOES_EM_ANDAMENTO.open('rb+') as f:
        pos = 0
        while True:
            linha = f.readline()
            if not linha:
                break
            try:
                questao_original = json.loads(linha)
                if tuple(questao_original.keys()) != ORDEM_CAMPOS:
                    raise RuntimeError('Processo no formato antigo; reinicie com --refazer-tudo --confirmar-reinicio.')
                ids_traduzidos.add(questao_original['id'])
                pos = f.tell()
            except (ValueError, KeyError, UnicodeDecodeError):
                f.truncate(pos)
                print('Última linha incompleta do processo descartada.', flush=True)
                break
    return ids_traduzidos



# GERAR O JSON FINAL

def atualizar_json_final(total_esperado, parcial=False):
    """Publica snapshot atômico do JSONL, inclusive em testes limitados."""
    ARQUIVO_FINAL.parent.mkdir(parents=True, exist_ok=True)
    tmp = None
    contadores = Counter()
    with ARQUIVO_TRADUCOES_EM_ANDAMENTO.open(encoding='utf-8') as entrada:
        for linha in entrada:
            questao_original = json.loads(linha)
            if not all(k in questao_original for k in ORDEM_CAMPOS):
                raise ValueError(f'Campos incompletos: {questao_original.get("id")}')
            contadores['total'] += 1
            contadores[questao_original['split']] += 1
            contadores['revisao'] += bool(questao_original['revisao_necessaria'])
    if contadores['total'] > total_esperado:
        raise ValueError('O arquivo de progresso possui mais questões que o original.')
    if not parcial and contadores['total'] != total_esperado:
        raise ValueError('A tradução não está completa.')
    info = {
        'nome': 'AQuA-RAT traduzido para português' if not parcial else 'AQuA-RAT - tradução parcial',
        'fonte_original': 'deepmind/aqua_rat',
        'configuracao': 'raw',
        'metodo_traducao': 'Argos Translate (en-pt)',
        'total_registros': total_esperado,
        'splits': {'train': 97467, 'validation': 254, 'test': 254} if total_esperado == 97975
                  else {s: contadores[s] for s in DIVISOES_DATASET},
        'registros_traduzidos': contadores['total'],
        'registros_pendentes': total_esperado - contadores['total'],
        'traducao_concluida': not parcial,
        'questoes_com_revisao_necessaria': contadores['revisao'],
    }
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=ARQUIVO_FINAL.parent,
                                         prefix='.aqua_final_', suffix='.tmp', delete=False) as f:
            tmp = Path(f.name)
            f.write('{\n  "dataset_info": ')
            json.dump(info, f, ensure_ascii=False, indent=2)
            f.write(',\n  "problemas": [\n')
            with ARQUIVO_TRADUCOES_EM_ANDAMENTO.open(encoding='utf-8') as entrada:
                for indice, linha in enumerate(entrada):
                    if indice:
                        f.write(',\n')
                    questao_formatada = json.dumps(json.loads(linha), ensure_ascii=False, indent=2)
                    f.write('\n'.join('    ' + trecho for trecho in questao_formatada.splitlines()))
            f.write('\n  ]\n}\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, ARQUIVO_FINAL)
    finally:
        if tmp and tmp.exists():
            tmp.unlink()
    return contadores


def carregar_assinaturas_json_anterior():
    """Lê só os campos PT do JSON anterior, para contabilizar alterações reais."""
    if not ARQUIVO_FINAL.exists():
        return {}
    try:
        import ijson
    except ImportError:
        print('Comparação com o JSON anterior indisponível (instale ijson).', flush=True)
        return {}
    assinaturas = {}
    with ARQUIVO_FINAL.open('rb') as f:
        for questao_traduzida in ijson.items(f, 'problemas.item'):
            dados = (questao_traduzida.get('question_pt'), questao_traduzida.get('options_pt'), questao_traduzida.get('rationale_pt'))
            resumo = hashlib.sha256(json.dumps(dados, sort_keys=True, ensure_ascii=False).encode()).digest()
            assinaturas[questao_traduzida['id']] = resumo
    return assinaturas



# EXECUTAR A TRADUÇÃO E MOSTRAR O PROGRESSO 

def executar_traducao(argumentos):
    # O original é garantido antes de qualquer descarte do progresso anterior.
    situacao_original = baixar_aqua_rat_se_necessario()
    if argumentos.refazer_tudo:
        if not argumentos.confirmar_reinicio:
            raise SystemExit('Para reiniciar, informe --refazer-tudo --confirmar-reinicio.')
        if ARQUIVO_TRADUCOES_EM_ANDAMENTO.exists():
            ARQUIVO_TRADUCOES_EM_ANDAMENTO.unlink()
            print('Progresso antigo descartado; todas as questões serão retraduzidas.')

    assinaturas_antigas = carregar_assinaturas_json_anterior()
    ids_traduzidos = carregar_ids_ja_traduzidos()
    ARQUIVO_TRADUCOES_EM_ANDAMENTO.parent.mkdir(parents=True, exist_ok=True)

    # Conta os registros antes de carregar o modelo, permitindo barra com total real.
    total_esperado = sum(1 for _ in percorrer_questoes_originais())
    pendentes = total_esperado - len(ids_traduzidos)
    quantidade_a_traduzir = min(pendentes, argumentos.limite) if argumentos.limite is not None else pendentes
    print(f'Total no original: {total_esperado:,}; já traduzidas: {len(ids_traduzidos):,}; '
          f'a traduzir nesta execução: {quantidade_a_traduzir:,}.'.replace(',', '.'), flush=True)

    from tqdm.auto import tqdm
    import warnings
    import logging
    logging.getLogger('stanza').setLevel(logging.ERROR)
    logging.getLogger('stanza.pipeline').setLevel(logging.ERROR)
    logging.getLogger('stanza.pipeline.core').setLevel(logging.ERROR)
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore', message="Can't initialize NVML")
        tradutor = carregar_tradutor_argos() if quantidade_a_traduzir else None

    questoes_traduzidas = questoes_alteradas = questoes_iguais = questoes_para_revisao = quantidade_falhas = 0
    interrompido = False
    questoes_tentadas = 0
    ARQUIVO_FALHAS.parent.mkdir(parents=True, exist_ok=True)
    with ARQUIVO_TRADUCOES_EM_ANDAMENTO.open('a', encoding='utf-8') as saida:
        barra = tqdm(total=quantidade_a_traduzir, desc='Traduzindo AQuA-RAT', unit='questão',
                     dynamic_ncols=True, mininterval=1, smoothing=0.15)
        try:
            for questao_original in percorrer_questoes_originais():
                if questao_original['id'] in ids_traduzidos:
                    continue
                # O limite conta tentativas, inclusive falhas, para evitar loops.
                if questoes_tentadas >= quantidade_a_traduzir:
                    break
                questoes_tentadas += 1
                barra.set_postfix_str(f'ID: {questao_original["id"]}', refresh=False)
                traducao = None
                for tentativa in range(1, argumentos.tentativas + 1):
                    try:
                        traducao = traduzir_questao(questao_original, tradutor)
                        break
                    except Exception as erro:
                        if tentativa < argumentos.tentativas:
                            tqdm.write(f'Tentativa {tentativa}/{argumentos.tentativas} falhou em '
                                       f'{questao_original["id"]}: {erro}')
                            time.sleep(0.5)
                        else:
                            quantidade_falhas += 1
                            registro_falha = {
                                'id': questao_original['id'],
                                'split': questao_original['split'],
                                'erro': str(erro),
                                'tipo_erro': type(erro).__name__,
                                'tentativas': argumentos.tentativas,
                                'data': datetime.now().isoformat(timespec='seconds'),
                            }
                            with ARQUIVO_FALHAS.open('a', encoding='utf-8') as arquivo_falhas:
                                arquivo_falhas.write(json.dumps(registro_falha, ensure_ascii=False) + '\n')
                                arquivo_falhas.flush()
                                os.fsync(arquivo_falhas.fileno())
                            tqdm.write(f'Falha registrada em {questao_original["id"]}: {erro}. '
                                       'Prosseguindo para a próxima questão.')
                if traducao is None:
                    barra.update(1)
                    continue
                saida.write(json.dumps(traducao, ensure_ascii=False) + '\n')
                questoes_traduzidas += 1
                questoes_para_revisao += bool(traducao['revisao_necessaria'])
                antigo = assinaturas_antigas.get(questao_original['id'])
                if antigo is not None:
                    dados = (traducao['question_pt'], traducao['options_pt'], traducao['rationale_pt'])
                    atual = hashlib.sha256(json.dumps(dados, sort_keys=True, ensure_ascii=False).encode()).digest()
                    if atual != antigo:
                        questoes_alteradas += 1
                    else:
                        questoes_iguais += 1
                barra.update(1)
                if questoes_traduzidas % argumentos.salvar_cada == 0:
                    saida.flush()
                    os.fsync(saida.fileno())
        except KeyboardInterrupt:
            interrompido = True
            tqdm.write('Interrompido pelo usuário; salvando o progresso.')
        finally:
            saida.flush()
            os.fsync(saida.fileno())
            barra.close()

    total_ja_gravado = len(carregar_ids_ja_traduzidos())
    traducao_concluida = total_ja_gravado == total_esperado and not quantidade_falhas
    if total_ja_gravado:
        # Só publica após persistir o progresso; evita arquivo final incompleto.
        contadores = atualizar_json_final(total_esperado, parcial=not traducao_concluida)
        situacao_json = 'COMPLETO' if traducao_concluida else 'PARCIAL (atualizado)'
    else:
        contadores = Counter()
        situacao_json = 'NÃO GERADO (nenhuma questão gravada)'

    print('\n' + '=' * 52)
    print('RESUMO DA EXECUÇÃO')
    print('=' * 52)
    print(f'Original: {situacao_original}.')
    print(f'Questões traduzidas nesta execução: {questoes_traduzidas:,}'.replace(',', '.'))
    print(f'Questões acumuladas no progresso: {total_ja_gravado:,}'.replace(',', '.'))
    print(f'Questões pendentes: {total_esperado - total_ja_gravado:,}'.replace(',', '.'))
    print(f'Questões alteradas em relação ao JSON anterior: {questoes_alteradas:,}'.replace(',', '.'))
    print(f'Questões sem alteração em relação ao JSON anterior: {questoes_iguais:,}'.replace(',', '.'))
    print(f'Questões sem registro no JSON anterior: {questoes_traduzidas - questoes_alteradas - questoes_iguais:,}'.replace(',', '.'))
    print(f'Questões sinalizadas para revisão nesta execução: {questoes_para_revisao:,}'.replace(',', '.'))
    print(f'Total sinalizado no arquivo publicado: {contadores["revisao"]:,}'.replace(',', '.'))
    print(f'Falhas nesta execução: {quantidade_falhas}')
    print(f'Registro de falhas (histórico): {ARQUIVO_FALHAS}')
    print('Questões com falha não foram marcadas como traduzidas; serão tentadas novamente em futuras execuções.')
    print(f'JSON final: {situacao_json} — {ARQUIVO_FINAL}')
    print(f'Progresso para retomada: {ARQUIVO_TRADUCOES_EM_ANDAMENTO}')
    if interrompido:
        print('Execução interrompida; dados salvos.')
    if not traducao_concluida:
        print('Para continuar: python -m codigo.preparacao.baixar_e_traduzir_aqua_rat_argos --continuar')




def main():
    analisador = argparse.ArgumentParser(description='Traduz AQuA-RAT com barra, retomada e JSON parcial atualizado.')
    grupo_modos = analisador.add_mutually_exclusive_group()
    grupo_modos.add_argument('--refazer-tudo', action='store_true', help='Inicia nova tradução, preservando final antigo.')
    grupo_modos.add_argument('--continuar', action='store_true', help='Retoma do arquivo em traducoes/.')
    analisador.add_argument('--confirmar-reinicio', action='store_true', help='Descarta processo anterior ao refazer tudo.')
    analisador.add_argument('--limite', type=int, help='Traduz no máximo N novas questões para teste.')
    analisador.add_argument('--tentativas', type=int, default=3, help='Tentativas por questão antes de registrar falha e continuar.')
    analisador.add_argument('--salvar-cada', type=int, default=20, help='Sincroniza o progresso em disco a cada N questões.')
    argumentos = analisador.parse_args()
    if argumentos.limite is not None and argumentos.limite <= 0:
        analisador.error('--limite deve ser positivo')
    if argumentos.tentativas <= 0:
        analisador.error('--tentativas deve ser positivo')
    if argumentos.salvar_cada <= 0:
        analisador.error('--salvar-cada deve ser positivo')
    executar_traducao(argumentos)

if __name__ == '__main__':
    main()