"""Recorte das primeiras N questões, comparações pareadas e máquinas por período (sem Ollama)."""
import json
import tempfile
import unittest
from pathlib import Path

from codigo.avaliacao import comparar_configuracoes as cc


def run(pasta, tecnica, nome, verdictos, ids, exemplos_ids=('e1', 'e2'), temp=0.0, tokens=1200,
        amostras=None, data='2026-11-01T10:00:00', dataset='gsm8k', limite=None, ambiente=None,
        falhas=()):
    """Cria uma execução em que o i-ésimo id recebe o veredito correspondente."""
    qs = [{'id': i, 'acertou': None if k in falhas else v, 'falha_tecnica': k in falhas,
           'tempo_segundos': 1.0, 'tokens_entrada': 10, 'tokens_saida': 5}
          for k, (i, v) in enumerate(zip(ids, verdictos))]
    dados = {'id_execucao': nome, 'tecnica': tecnica, 'dataset': dataset, 'status': 'concluido',
             'data_inicio': data,
             'parametros': {'modelo': 'm', 'temperatura': temp, 'maximo_tokens_resposta': tokens,
                            'n_amostras': amostras, 'quantidade_exemplos': len(exemplos_ids),
                            'limite': limite if limite is not None else len(ids),
                            'ids_questoes': list(ids), 'ids_exemplos': list(exemplos_ids)},
             'resultados': qs}
    if ambiente:
        dados['ambiente'] = ambiente
    caminho = Path(pasta) / tecnica / dataset / 'x' / f'{nome}.json'
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(dados), encoding='utf-8')
    return caminho


IDS = [f'q{i}' for i in range(10)]


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pasta = Path(self.tmp.name)


class TestRecorte(Base):
    def test_execucao_maior_e_avaliada_so_nas_primeiras_n_questoes(self):
        # 10 questões; nas 4 primeiras acerta 2, nas outras 6 acerta tudo
        run(self.pasta, 'few_shot', 'grande', [True, True, False, False] + [True] * 6, IDS)
        run(self.pasta, 'chain_of_thought', 'pequena', [True, False, True, True], IDS[:4])
        linhas = {l['id_execucao']: l for l in cc.coletar(self.pasta, recortar=4)}
        self.assertEqual((linhas['grande']['avaliadas'], linhas['grande']['acertos']), (4, 2))
        self.assertEqual(linhas['grande']['limite'], 4)
        self.assertTrue(linhas['grande']['recorte'])
        self.assertEqual(linhas['grande']['limite'], linhas['pequena']['limite'])
        self.assertEqual(len(cc.agregar(list(linhas.values()))), 2)

    def test_exclui_quem_tem_menos_questoes_ordem_ou_exemplos_diferentes(self):
        run(self.pasta, 'few_shot', 'ok', [True] * 10, IDS)
        run(self.pasta, 'few_shot', 'curta', [True] * 3, IDS[:3])
        run(self.pasta, 'few_shot', 'ordem_outra', [True] * 10, IDS[::-1])
        run(self.pasta, 'few_shot', 'exemplos_outros', [True] * 10, IDS, exemplos_ids=('z1', 'z2'))
        linhas, avisos = cc.coletar_com_avisos(self.pasta, recortar=4)
        nomes = sorted(l['id_execucao'] for l in linhas)
        # 'exemplos_outros' forma outro grupo (outro conjunto de demonstrações) e fica à parte
        self.assertEqual(nomes, ['exemplos_outros', 'ok'])
        textos = ' '.join(avisos)
        self.assertIn('curta', textos)
        self.assertIn('ordem_outra', textos)

    def test_sem_recorte_nada_muda(self):
        run(self.pasta, 'few_shot', 'a', [True] * 10, IDS)
        [l] = cc.coletar(self.pasta)
        self.assertFalse(l['recorte'])
        self.assertEqual(l['avaliadas'], 10)

    def test_filtro_de_limite_vale_para_o_recorte(self):
        run(self.pasta, 'few_shot', 'a', [True] * 10, IDS)
        self.assertEqual(len(cc.coletar(self.pasta, recortar=4, limite=4)), 1)
        self.assertEqual(len(cc.coletar(self.pasta, recortar=4, limite=10)), 0)


class TestPareadas(Base):
    def montar(self):
        run(self.pasta, 'few_shot', 'f', [False] * 8 + [True, False], IDS, tokens=1200)
        run(self.pasta, 'chain_of_thought', 'c', [True] * 7 + [False] * 3, IDS, tokens=1200)
        run(self.pasta, 'self_consistency', 's_a', [True] * 9 + [False], IDS, temp=0.7, amostras=5, tokens=1200)
        run(self.pasta, 'self_consistency', 's_b', [True] * 8 + [False] * 2, IDS, temp=0.3, amostras=5, tokens=1200)
        run(self.pasta, 'self_consistency', 's_c', [True] * 9 + [False], IDS, temp=0.7, amostras=5, tokens=2400)
        run(self.pasta, 'self_consistency', 's_d', [True] * 6 + [False] * 4, IDS, temp=0.7, amostras=3, tokens=2400)
        return cc.comparacoes_pareadas(cc.coletar(self.pasta))

    def test_pares_entre_tecnicas_so_com_o_mesmo_orcamento_de_tokens(self):
        pares = [x for x in self.montar() if x['tipo'] == 'tecnicas']
        self.assertTrue(pares)
        self.assertTrue(all(x['fator'] == '1200 tokens' for x in pares))       # SC de 2400 não entra: sem Few/CoT de 2400
        combos = {(x['a'].split(' /')[0], x['b'].split(' /')[0]) for x in pares}
        self.assertEqual(combos, {('Few-shot', 'CoT'), ('Few-shot', 'SC'), ('CoT', 'SC')})

    def test_mcnemar_confere_com_a_contagem_manual(self):
        pares = self.montar()
        fc = next(x for x in pares if x['tipo'] == 'tecnicas' and x['a'].startswith('Few-shot') and x['b'].startswith('CoT'))
        # Few: só acerta q8. CoT: acerta q0..q6. Só A=1 (q8), Só B=7 (q0..q6)
        self.assertEqual((fc['n'], fc['so_a'], fc['so_b']), (10, 1, 7))
        self.assertAlmostEqual(fc['diferenca_pp'], 100 * (0.7 - 0.1))
        self.assertAlmostEqual(fc['p'], 0.0703125, places=6)        # 2*P(X<=1 | n=8, p=.5)

    def test_efeito_de_um_parametro_isolado(self):
        fatores = {x['fator'] for x in self.montar() if x['tipo'] == 'fator'}
        self.assertEqual(fatores, {'temperatura', 'tokens', 'amostras'})

    def test_so_compara_configuracoes_que_diferem_em_um_unico_parametro(self):
        fatores = [x for x in self.montar() if x['tipo'] == 'fator']
        for x in fatores:
            # nenhum par muda temperatura E tokens ao mesmo tempo
            a, b = x['a'], x['b']
            self.assertFalse(('t=0.3' in a and '2400' in b) or ('t=0.3' in b and '2400' in a))

    def test_referencia_prefere_zero_falhas_e_ignora_suspeita(self):
        run(self.pasta, 'self_consistency', 'com_falha', [True] * 10, IDS, temp=0.7, amostras=5,
            data='2026-11-09T10:00:00', falhas=(0,))
        run(self.pasta, 'self_consistency', 'limpa_antiga', [True] * 5 + [False] * 5, IDS, temp=0.7, amostras=5,
            data='2026-11-01T10:00:00')
        linhas = cc.coletar(self.pasta)
        ref = cc.escolher_referencia(linhas)
        self.assertEqual(ref['id_execucao'], 'limpa_antiga')           # a recente tem falha técnica

    def test_pendente_nao_entra_nas_pareadas(self):
        run(self.pasta, 'chain_of_thought', 'c', [True] * 10, IDS)
        run(self.pasta, 'few_shot', 'f', [None] * 10, IDS)
        self.assertEqual(cc.comparacoes_pareadas(cc.coletar(self.pasta)), [])

    def test_relatorio_traz_as_secoes_e_nao_vaza_campo_interno(self):
        self.montar()
        saida = self.pasta / 'saida'
        linhas, ags, texto = cc.gerar(self.pasta, saida, recortar=10, detalhado=True)
        self.assertIn('Comparação entre técnicas', texto)
        self.assertIn('Efeito de um parâmetro isolado', texto)
        self.assertIn('p (McNemar exato)', texto)
        dados = json.loads((saida / 'metricas_gerais.json').read_text(encoding='utf-8'))
        self.assertTrue(dados['comparacoes_pareadas'])
        self.assertFalse(any('_execucao' in e for e in dados['execucoes']))
        self.assertFalse(list(saida.glob('*.csv')))


class TestMaquinas(Base):
    def test_periodos_por_dia_tecnica_e_dataset(self):
        run(self.pasta, 'self_consistency', 'a', [True] * 4, IDS[:4], data='2026-11-05T08:00:00', amostras=3, temp=.7)
        run(self.pasta, 'self_consistency', 'b', [True] * 4, IDS[:4], data='2026-11-07T08:00:00', amostras=3, temp=.7)
        run(self.pasta, 'few_shot', 'c', [True] * 4, IDS[:4], data='2026-11-05T09:00:00')
        mapa = {'periodos': [
            {'de': '2026-11-05', 'ate': '2026-11-06', 'maquina': 'pc2', 'tecnica': 'self_consistency'},
            {'de': '2026-11-01', 'ate': '2026-11-30', 'maquina': 'pc1'}]}
        por_id = {l['id_execucao']: l['maquina'] for l in cc.coletar(self.pasta, mapa=mapa)}
        self.assertEqual(por_id, {'a': 'pc2', 'b': 'pc1', 'c': 'pc1'})      # vale o primeiro período que casa

    def test_execucao_explicita_vence_o_periodo_e_ambiente_vence_tudo(self):
        run(self.pasta, 'few_shot', 'a', [True] * 4, IDS[:4], data='2026-11-05T09:00:00')
        run(self.pasta, 'few_shot', 'b', [True] * 4, IDS[:4], data='2026-11-05T09:00:00',
            ambiente={'sistema': 'Linux', 'maquina': 'ubuntu-lab'})
        mapa = {'periodos': [{'de': '2026-11-01', 'ate': '2026-11-30', 'maquina': 'pc1'}],
                'execucoes': {'a': 'pc2'}, 'apelidos': {'ubuntu-lab': 'pc2'}}
        por_id = {l['id_execucao']: l['maquina'] for l in cc.coletar(self.pasta, mapa=mapa)}
        self.assertEqual(por_id, {'a': 'pc2', 'b': 'pc2'})

    def test_ambiente_sem_apelido_mostra_o_nome_gravado(self):
        run(self.pasta, 'few_shot', 'a', [True] * 4, IDS[:4], ambiente={'sistema': 'Windows', 'maquina': 'LAHYL-PC'})
        self.assertEqual(cc.coletar(self.pasta)[0]['maquina'], 'LAHYL-PC')

    def test_arquivo_de_maquinas_formato_completo_e_valores_vazios(self):
        arq = self.pasta / 'maq.json'
        arq.write_text(json.dumps({'execucoes': {'a': '', 'b': 'pc1'}, 'periodos': [{'de': '2026-01-01'}],
                                   'apelidos': {'X': 'pc2'}, '_ajuda': 'x'}), encoding='utf-8')
        m = cc.carregar_maquinas(arq)
        self.assertEqual(m['execucoes'], {'b': 'pc1'})
        self.assertEqual(m['periodos'], [])                 # sem 'maquina' é ignorado
        self.assertEqual(m['apelidos'], {'X': 'pc2'})

    def test_modelo_mostra_quantas_execucoes_por_dia(self):
        a = run(self.pasta, 'few_shot', 'a', [True] * 4, IDS[:4], data='2026-11-05T09:00:00')
        b = run(self.pasta, 'few_shot', 'b', [True] * 4, IDS[:4], data='2026-11-05T10:00:00')
        modelo = cc.modelo_de_maquinas([a, b])
        self.assertEqual(modelo['_execucoes_por_dia'], {'2026-11-05': 2})


class TestSemMaquina(Base):
    def test_sem_nenhuma_maquina_a_coluna_e_o_aviso_somem(self):
        run(self.pasta, 'few_shot', 'a', [True] * 4, IDS[:4])
        _, _, texto = cc.gerar(self.pasta, self.pasta / 's', detalhado=True)
        self.assertNotIn('Máquina', texto)
        self.assertNotIn('sem máquina informada', texto)

    def test_com_alguma_maquina_a_coluna_aparece(self):
        run(self.pasta, 'few_shot', 'a', [True] * 4, IDS[:4], ambiente={'sistema': 'Linux', 'maquina': 'x'})
        _, _, texto = cc.gerar(self.pasta, self.pasta / 's', detalhado=True)
        self.assertIn('Máquina', texto)


if __name__ == '__main__':
    unittest.main()
