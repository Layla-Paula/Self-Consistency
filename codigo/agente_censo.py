"""Agente Censo: SQL gerado pelo LLM, prevenção de loops e auditoria integral.

Não fornece gabarito ao modelo. Respostas sem evidência não são aceitas como válidas.
MAX_CONSULTAS limita execuções de ferramenta, não impede a rodada final.
"""
import json
import re
import time
from codigo.utils import consultar_ollama

MAX_CONSULTAS = 5
MAX_REPETICOES = 1
MAX_REPAROS = 2


def _comando(texto):
    sql = re.search(r'```sql\s*([\s\S]*?)```', texto, re.I)
    if sql:
        return 'sql', sql.group(1).strip()
    dicionario = re.search(r'(?im)^DICIONARIO\s*:\s*([A-Z][A-Z0-9_]+)\s*$', texto)
    if dicionario:
        return 'dicionario', dicionario.group(1).upper()
    return None, None


def _cortar_apos_comando(texto, tipo):
    """Guarda no histórico só o texto até o comando. O que o modelo escrever depois
    (por exemplo, um resultado inventado) não é observação e não entra no histórico."""
    if tipo == 'sql':
        achado = re.search(r'```sql\s*([\s\S]*?)```', texto, re.I)
    else:
        achado = re.search(r'(?im)^DICIONARIO\s*:\s*([A-Z][A-Z0-9_]+)\s*$', texto)
    return texto[:achado.end()] if achado else texto


def executar_consultas_demonstracao(sessao, exemplos):
    """Roda no CSV real as consultas de cada demonstração (campo consultas_sql do JSON).

    Devolve {id: texto}. Os resultados vêm da base e do dicionário atuais, nunca de
    números copiados à mão. Falha com mensagem clara se alguma consulta der erro."""
    blocos = {}
    for exemplo in exemplos:
        identificador = str(exemplo['id'])
        comandos = exemplo.get('consultas_sql') or []
        if not comandos:
            raise ValueError(
                f'Demonstração {identificador} sem consultas_sql. '
                'Execute baixar_preparar_censo.py para gerar o JSON atualizado.')
        partes = ['Consultas executadas:']
        for numero, comando in enumerate(comandos, 1):
            comando = str(comando).strip()
            if re.match(r'(?i)^DICIONARIO\s*:', comando):
                resultado = sessao.consultar_dicionario(comando.split(':', 1)[1].strip())
                mostrado = comando
            else:
                bruto = sessao.executar_sql(comando)
                resultado = {'colunas': bruto['colunas'], 'linhas': bruto['linhas']}
                mostrado = '```sql\n' + comando + '\n```'
            if isinstance(resultado, dict) and 'erro' in resultado:
                raise ValueError(f'Demonstração {identificador}, consulta {numero} falhou: {resultado["erro"]}')
            partes.append(f'Consulta {numero}:\n{mostrado}\nResultado: '
                          + json.dumps(resultado, ensure_ascii=False, default=str))
        blocos[identificador] = '\n'.join(partes)
    return blocos


def _extrair_resposta_final(texto):
    """Devolve o texto escrito pelo modelo depois de 'Resposta final:', sem blocos SQL,
    sem linhas DICIONARIO e sem saida FERRAMENTA. Nao inventa nada: so recorta o que o modelo escreveu."""
    achado = list(re.finditer(r'(?i)resposta\s+final\s*:?', texto or ''))
    if not achado:
        return None
    resto = texto[achado[-1].end():]
    resto = re.split(r'(?im)^\s*FERRAMENTA\s*:', resto, maxsplit=1)[0]
    resto = re.sub(r'```sql[\s\S]*?```', '', resto, flags=re.I)
    resto = re.sub(r'(?im)^\s*DICIONARIO\s*:.*$', '', resto)
    resto = resto.replace('```', '').strip()
    # Não aceitar outra solicitação de ferramenta como resposta.
    resto = re.split(r'(?im)^\s*(?:DICIONARIO\s*:|```sql)', resto, maxsplit=1)[0].strip()
    return resto or None


def _chave(tipo, comando):
    if tipo == 'sql':
        return tipo, re.sub(r'\s+', ' ', comando).strip().rstrip(';').lower()
    return tipo, comando.upper()


def consultar_censo_agente(prompt, sessao, temperature=0.0, num_predict=1200,
                           retornar_metricas=True, seed=None):
    inicio = time.perf_counter()
    chamadas, consultas, transcricoes = [], [], []
    vistos = set()
    repeticoes = reparos = 0
    motivo = None
    resposta_final = ''
    evidencia = False
    instrucao = (
        '\n\nFERRAMENTAS (quando a pergunta depender de dados, consulte a fonte):\n'
        'SQL: responda SOMENTE com ```sql SELECT ... FROM matriculas ... ``` e aguarde.\n'
        'Dicionário: responda SOMENTE com DICIONARIO: NOME_VARIAVEL e aguarde.\n'
        'Para perguntas sobre significado, definicao, categorias ou inclusoes/exclusoes de uma variavel, CONSULTE PRIMEIRO O DICIONARIO; SQL nao define conceitos.\n'
        'Em consultas por UF ou por região, exclua as escolas sem esse dado: WHERE SG_UF IS NOT NULL AND TRIM(SG_UF) <> \'\' '
        '(para região, NO_REGIAO). Rankings e comparações estaduais ou regionais não incluem essas escolas; totais nacionais incluem.\n'
        'NÃO repita consultas já executadas: resultados anteriores estão no histórico.\n'
        'Quando houver evidências suficientes, responda com Resposta final: ...\n'
        'Se a fonte necessária estiver indisponível, informe isso explicitamente.\n'
        'Não invente números, não use o gabarito e não coloque SQL após a resposta final.\n'
    )
    historico = []

    def chamar(extra=''):
        entrada = prompt + instrucao
        if historico:
            entrada += '\n\nHISTÓRICO DE CONSULTAS:\n' + '\n\n'.join(historico)
        entrada += extra
        opcoes = {} if seed is None else {'seed': seed}
        info = consultar_ollama(entrada, temperature=temperature,
                               num_predict=num_predict, retornar_metricas=True, **opcoes)
        if not isinstance(info, dict):
            info = {'resposta': None, 'erro_detalhado': 'Retorno inválido do Ollama'}
        chamadas.append(info)
        transcricoes.append({'rodada': len(chamadas), 'texto': info.get('resposta'),
                             'tokens_entrada': info.get('prompt_eval_count'),
                             'tokens_saida': info.get('eval_count')})
        return info

    def finalizar(extra, motivo_sucesso):
        """Pede uma resposta final explícita sem executar novas ferramentas."""
        nonlocal resposta_final, motivo, reparos
        while reparos < MAX_REPAROS:
            reparos += 1
            info = chamar(extra)
            if info.get('resposta') is None:
                motivo = 'falha_ollama'
                return
            bruto = str(info['resposta']).strip()
            candidata = _extrair_resposta_final(bruto)
            # Na finalização, somente uma resposta explícita e sem comandos é válida.
            if candidata and evidencia and _comando(bruto)[0] is None:
                resposta_final = candidata
                motivo = motivo_sucesso
                return
        motivo = 'finalizacao_sem_resposta'

    while True:
        info = chamar()
        texto = info.get('resposta')
        if texto is None:
            motivo = 'falha_ollama'
            break
        texto = str(texto).strip()
        tipo, comando = _comando(texto)
        candidata = _extrair_resposta_final(texto)

        if not tipo:
            if candidata and evidencia:
                resposta_final = candidata
                motivo = 'resposta_com_evidencia'
            elif not texto:
                motivo = 'resposta_vazia'
            elif not evidencia:
                motivo = 'resposta_sem_consulta'
            else:
                motivo = 'resposta_sem_formato_final'
            break

        chave = _chave(tipo, comando)
        if chave in vistos:
            repeticoes += 1
            motivo = 'consulta_repetida'
            # Não aceita resposta misturada com consulta repetida.
            # A finalização será solicitada em uma rodada separada,
            # utilizando exclusivamente o histórico das ferramentas executadas.
            break

        if len(consultas) >= MAX_CONSULTAS:
            motivo = 'limite_consultas'
            break

        vistos.add(chave)
        try:
            resultado = (sessao.executar_sql(comando) if tipo == 'sql'
                         else sessao.consultar_dicionario(comando))
        except Exception as erro:
            resultado = {'erro': f'{type(erro).__name__}: {erro}'}
        consultas.append({'tipo': tipo, 'comando': comando, 'resultado': resultado})
        sucesso = isinstance(resultado, dict) and 'erro' not in resultado
        if sucesso:
            evidencia = True
        historico.append('ASSISTENTE:\n' + _cortar_apos_comando(texto, tipo) + '\nFERRAMENTA:\n' +
                         json.dumps(resultado, ensure_ascii=False, default=str))

        # A resposta escrita junto de um comando novo é ignorada (foi escrita antes de ver o
        # resultado). O laço continua: na próxima rodada o modelo já vê a observação real
        # e pode responder ou consultar de novo.
        if len(consultas) >= MAX_CONSULTAS:
            motivo = 'limite_consultas'
            break

    # A resposta final deve vir após evidência real; não fabricar resposta a
    # partir de resultados SQL, nem tratar comandos como resposta textual.
    if motivo in ('consulta_repetida', 'limite_consultas',
                  'resposta_sem_formato_final', 'resposta_vazia') and not resposta_final:
        if motivo == 'consulta_repetida':
            historico.append('SISTEMA: consulta repetida bloqueada. NÃO execute novamente: ' + comando)
        if evidencia:
            finalizar(
                '\n\nAGORA É OBRIGATÓRIO FINALIZAR. Não peça ferramentas, não repita SQL, '
                'não escreva DICIONARIO:. Escreva apenas: Resposta final: ... usando '
                'exclusivamente os resultados reais no histórico. Se insuficientes, '
                'diga explicitamente que os dados consultados não permitem responder.',
                'resposta_apos_finalizacao',
            )
        else:
            motivo = 'finalizacao_sem_evidencia'

    # Preserva TODAS as gerações, inclusive as rejeitadas e as que contêm SQL.
    texto_descartado = '\n\n'.join(
        f"[rodada {t['rodada']}]\n{t['texto']}" for t in transcricoes
        if t['texto'] is not None and t['texto'] != resposta_final
    )
    ultima = chamadas[-1] if chamadas else {}
    saida = dict(ultima)
    duracoes = [float(c.get('tempo_total_segundos') or 0) for c in chamadas]
    total_dur = sum(duracoes)
    def media_ponderada(chave):
        pares = [(float(c[chave]), d) for c, d in zip(chamadas, duracoes)
                 if c.get(chave) is not None and d > 0]
        return round(sum(v * d for v, d in pares) / sum(d for _, d in pares), 2) if pares else None
    picos = [c['ram_ollama_pico_mib'] for c in chamadas if c.get('ram_ollama_pico_mib') is not None]
    saida.update({
        'resposta': resposta_final if ultima.get('resposta') is not None else None,
        'texto_descartado': texto_descartado,
        'transcricoes_censo': transcricoes,
        'motivo_encerramento_censo': motivo,
        'evidencia_consultada': evidencia,
        'consultas_censo': consultas,
        'rodadas_censo': len(chamadas),
        'consultas_repetidas_bloqueadas': repeticoes,
        'sql_executadas': sum(c['tipo'] == 'sql' and 'erro' not in c['resultado'] for c in consultas),
        'dicionario_consultado': sum(c['tipo'] == 'dicionario' and 'erro' not in c['resultado'] for c in consultas),
        'tokens_entrada': sum(c.get('prompt_eval_count') or 0 for c in chamadas),
        'tokens_saida': sum(c.get('eval_count') or 0 for c in chamadas),
        'prompt_eval_count': sum(c.get('prompt_eval_count') or 0 for c in chamadas),
        'eval_count': sum(c.get('eval_count') or 0 for c in chamadas),
        'tempo_total_segundos': round(time.perf_counter() - inicio, 3),
        'cpu_ollama_percentual': media_ponderada('cpu_ollama_percentual'),
        'ram_ollama_pico_mib': max(picos) if picos else None,
        'ram_ollama_media_mib': media_ponderada('ram_ollama_media_mib'),
        'amostras_monitoramento': sum(c.get('amostras_monitoramento') or 0 for c in chamadas),
    })
    return saida if retornar_metricas else saida['resposta']
