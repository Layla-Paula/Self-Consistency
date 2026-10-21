"""Votação por frequência e seleção semântica cega ao gabarito para o Censo."""
from collections import Counter
import json
import re
import unicodedata

def voto_majoritario(respostas):
    validas = [str(r).strip() for r in respostas if r is not None and str(r).strip()]
    if not validas:
        return {'vencedora': '', 'votos': 0, 'distribuicao': {}, 'houve_empate': False,
                'total_respostas_validas': 0, 'metodo_votacao': 'frequencia_simples'}
    contagem = Counter(validas)
    maior = max(contagem.values())
    vencedoras = [r for r, votos in contagem.items() if votos == maior]
    return {'vencedora': vencedoras[0] if len(vencedoras) == 1 else '',
            'votos': maior, 'distribuicao': dict(contagem),
            'houve_empate': len(vencedoras) > 1,
            'total_respostas_validas': len(validas), 'metodo_votacao': 'frequencia_simples'}

def _canonico(texto):
    texto = unicodedata.normalize('NFKD', str(texto).casefold())
    return ' '.join(''.join(c for c in texto if not unicodedata.combining(c)).split()).strip(' .;')

def _numero_unico(texto):
    """Só canoniza respostas que são literalmente um único número, sem texto explicativo."""
    from codigo.utils import normalizar_numero
    t = str(texto).strip()
    if not re.fullmatch(r'-?\d[\d., ]*%?', t):
        return None
    percentual = t.endswith('%')
    try:
        valor = normalizar_numero(t.rstrip('%').strip())
        if not abs(valor) < float('inf'):
            return None
        return ('percentual:' if percentual else 'numero:') + format(valor, '.12g')
    except (ValueError, TypeError, OverflowError):
        return None

def _json_objeto(texto):
    try:
        return json.loads(str(texto).strip())
    except (ValueError, TypeError):
        achado = re.search(r'\{[\s\S]*?\}', str(texto))
        if achado:
            try:
                return json.loads(achado.group())
            except ValueError:
                pass
    return None

def voto_censo_semantico(pergunta, respostas, consultar_ollama):
    """Seleciona uma candidata por consistência sem usar gabarito ou dados esperados.

    Usa consenso textual/númerico quando inequívoco; para texto aberto, pede
    ao avaliador que selecione UMA das respostas existentes, sem reescrevê-la.
    """
    validas = [(i + 1, str(r).strip()) for i, r in enumerate(respostas) if str(r or '').strip()]
    if not validas:
        resultado = voto_majoritario(respostas)
        resultado['metodo_votacao'] = 'censo_sem_resposta'
        return resultado
    chaves = [(_numero_unico(r) or 'texto:' + _canonico(r)) for _, r in validas]
    contagem = Counter(chaves)
    maximo = max(contagem.values())
    if maximo > len(validas) / 2:
        chave = next(k for k, v in contagem.items() if v == maximo)
        indice = chaves.index(chave)
        return {'vencedora': validas[indice][1], 'votos': maximo,
                'distribuicao': dict(contagem), 'houve_empate': False,
                'total_respostas_validas': len(validas),
                'metodo_votacao': 'censo_equivalencia_deterministica',
                'indice_selecionado': validas[indice][0], 'tentativas_seletor': 0}
    if consultar_ollama is None:
        raise RuntimeError('Seletor semântico do Censo indisponível.')
    opcoes = '\n'.join(f'{i}. {r}' for i, r in validas)
    prompt = ("Você deve escolher a resposta mais consistente entre as candidatas para a MESMA pergunta. "
              "Compare significados, números, categorias e listas. Respostas semanticamente equivalentes "
              "podem estar redigidas de formas diferentes. NÃO consulte gabarito: ele não foi fornecido. "
              "NÃO tente resolver a questão nem invente uma nova resposta. "
              "Escolha somente um índice entre as candidatas; se não houver consenso semântico claro, "
              "retorne indice 0. Responda SOMENTE JSON: "
              '{"indice": 1, "justificativa": "..."}'
              f'\nPERGUNTA:\n{pergunta}\nCANDIDATAS:\n{opcoes}')
    ultimo = 'Seletor não retornou uma escolha válida.'
    for tentativa in range(1, 4):
        info = consultar_ollama(prompt, temperature=0, num_predict=160, retornar_metricas=True)
        if not isinstance(info, dict) or info.get('resposta') is None:
            ultimo = info.get('erro_detalhado', 'Falha técnica do seletor.') if isinstance(info, dict) else 'Falha técnica.'
            continue
        obj = _json_objeto(info['resposta'])
        indice = obj.get('indice') if isinstance(obj, dict) else None
        if type(indice) is int and indice == 0:
            return {'vencedora': '', 'votos': 0, 'distribuicao': dict(contagem),
                    'houve_empate': True, 'total_respostas_validas': len(validas),
                    'metodo_votacao': 'censo_semantica_sem_consenso',
                    'tentativas_seletor': tentativa}
        if type(indice) is int and indice in {i for i, _ in validas}:
            resposta = next(r for i, r in validas if i == indice)
            return {'vencedora': resposta, 'votos': None,
                    'distribuicao': dict(contagem), 'houve_empate': False,
                    'total_respostas_validas': len(validas),
                    'metodo_votacao': 'censo_selecao_semantica_llm',
                    'indice_selecionado': indice, 'tentativas_seletor': tentativa,
                    'justificativa_seletor': str(obj.get('justificativa', ''))}
        ultimo = 'JSON inválido ou índice fora das candidatas.'
    raise RuntimeError(f'Falha técnica no seletor semântico do Censo: {ultimo}')
