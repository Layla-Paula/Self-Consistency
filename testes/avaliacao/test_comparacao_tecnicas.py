"""Testes da avaliação do TCC; executar com python -m unittest discover -s testes -t ."""
import json
import tempfile
import unittest
from pathlib import Path

from codigo.avaliacao import comparacao_tecnicas as ct
from codigo.avaliacao.analise_self_consistency import analisar, votar
from codigo.avaliacao.relatorio_tcc import consolidar


def execucao(tecnica, acertos, ids=None, dataset='gsm8k'):
    ids = ids if ids is not None else [f'q{i}' for i in range(len(acertos))]
    qs = [{'id': i, 'acertou': a, 'tempo_segundos': 2, 'tokens_entrada': 100,
           'tokens_saida': 10, 'resposta': '10' if a else '5'} for i, a in zip(ids, acertos)]
    return {'arquivo': Path('teste.json'), 'dados': {'parametros': {}}, 'questoes': qs,
            'tecnica': tecnica, 'dataset': dataset, 'veredito': dict(zip(ids, acertos))}


class TestMetricas(unittest.TestCase):
    def test_acuracia_wilson(self):
        r = ct.resumo_acuracia(execucao('few_shot', [True] * 20 + [False] * 30))
        self.assertAlmostEqual(r['acuracia'], .4)
        self.assertAlmostEqual(r['ic95'][0], .2764, places=3)

    def test_pendentes_nao_sao_erro(self):
        r = ct.resumo_acuracia(execucao('few_shot', [True, False, None, None]))
        self.assertIsNone(r['acuracia'])
        self.assertEqual((r['minimo'], r['maximo']), (.25, .75))

    def test_falha_tecnica_excluida(self):
        e = execucao('few_shot', [True, False, False])
        e['questoes'][2]['falha_tecnica'] = True
        r = ct.resumo_acuracia(e)
        self.assertEqual((r['avaliadas'], r['falhas_tecnicas']), (2, 1))

    def test_mcnemar_e_intersecao(self):
        a = execucao('few_shot', [True, True, False], ['a', 'b', 'c'])
        b = execucao('chain_of_thought', [True, False, True], ['b', 'c', 'd'])
        r = ct.comparar_pareado(a, b)
        self.assertEqual(r['n_pareado'], 2)
        self.assertEqual((r['so_a'], r['so_b']), (0, 0))
        self.assertEqual(r['questoes_fora_do_par'], 2)

    def test_tempo_ausente_nao_e_zero(self):
        e = execucao('few_shot', [True, False])
        e['questoes'][1]['tempo_segundos'] = None
        r = ct.custo(e)
        self.assertEqual(r['tempo_medio_s'], 2)
        self.assertEqual(r['tempo_medio_s_n'], 1)

    def test_avisos_parametros(self):
        a = execucao('few_shot', [True], ['a'])
        b = execucao('chain_of_thought', [True], ['b'])
        a['dados']['parametros']['maximo_tokens_resposta'] = 500
        b['dados']['parametros']['maximo_tokens_resposta'] = 800
        avisos = ' '.join(ct.avisos_de_comparabilidade({'few_shot': a, 'chain_of_thought': b}))
        self.assertIn('maximo_tokens_resposta', avisos)
        self.assertIn('mesmas questões', avisos)

    def test_votacao_e_empate(self):
        self.assertEqual(votar(['10', '5', '10'], 'gsm8k')['resposta'], '10')
        self.assertTrue(votar(['5', '10'], 'gsm8k')['empate'])
        self.assertEqual(votar(['B', 'b', 'C'], 'aqua_rat')['votos'], 2)

    def test_sc_por_k(self):
        e = execucao('self_consistency', [True, False])
        e['questoes'][0].update(gabarito='10', amostras=[{'resposta_extraida': x} for x in ('10', '5', '10')])
        e['questoes'][1].update(gabarito='10', amostras=[{'resposta_extraida': x} for x in ('5', '10')])
        r = analisar(e)
        self.assertEqual([x['questoes'] for x in r['por_k']], [2, 2, 1])
        self.assertAlmostEqual(r['por_k'][0]['acuracia'], .5)

    def test_sc_completude_media_e_teto(self):
        e = execucao('self_consistency', [True, False, False], ['a', 'b', 'c'])
        e['questoes'][0].update(gabarito='10', amostras=[{'resposta_extraida': x} for x in ('10', '5', '10')])
        e['questoes'][1].update(gabarito='10', amostras=[{'resposta_extraida': x} for x in ('5', '10', '7')])
        r = analisar(e)
        self.assertFalse(r['completo'])
        self.assertEqual(r['questoes_excluidas'], ['c'])
        self.assertAlmostEqual(r['acuracia_amostra_unica_media'], 3 / 6)
        self.assertAlmostEqual(r['acuracia_qualquer_amostra_certa'], 1.0)

    def test_relatorio_mostra_planejadas_e_faixa(self):
        e = execucao('few_shot', [True, False, None, None])
        rel = {'dataset': 'x', 'execucoes': {}, 'avisos': [], 'acuracia': {'few_shot': ct.resumo_acuracia(e)},
               'comparacoes': {}, 'custo': {}, 'falhas': {}, 'self_consistency_amostras': None,
               'custo_beneficio': {}}
        md = ct.para_markdown(rel)
        self.assertIn('faixa 25.00% a 75.00%', md)
        self.assertIn('NÃO é intervalo de confiança', md)

    def test_modo_estrito_bloqueia_pareado(self):
        with tempfile.TemporaryDirectory() as pasta:
            for t, n in (('few_shot', 2), ('chain_of_thought', 3)):
                base = Path(pasta) / t / 'gsm8k'
                base.mkdir(parents=True)
                dados = {'tecnica': t, 'dataset': 'gsm8k', 'status': 'concluido',
                         'parametros': {'modelo': 'm', 'limite': n, 'quantidade_exemplos': 2},
                         'resultados': execucao(t, [True] * n)['questoes']}
                (base / f'{t}_gsm8k_01112026_120000.json').write_text(json.dumps(dados))
            livre = ct.gerar('gsm8k', 'qualquer', 2, pasta=pasta)
            estrito = ct.gerar('gsm8k', 'qualquer', 2, pasta=pasta, estrito=True)
            self.assertFalse(livre['comparavel'])
            self.assertTrue(livre['comparacoes'])
            self.assertEqual(estrito['comparacoes'], {})
            self.assertIn('NÃO comparáveis', ct.para_markdown(estrito))

    def test_votacao_igual_a_dos_experimentos(self):
        from codigo.self_consistency.votacao import normalizar_voto_gsm8k, voto_majoritario
        for r in (['10', '10,0', '5'], ['', '7', '8'], ['1.500', '1500', '3']):
            esperado = voto_majoritario(r, normalizar_voto_gsm8k)
            obtido = votar(r, 'gsm8k')
            self.assertEqual((obtido['resposta'], obtido['votos']),
                             (esperado['vencedora'] or None, esperado['votos']))

    def test_relatorio_com_jsons(self):
        with tempfile.TemporaryDirectory() as pasta:
            for t in ct.TECNICAS:
                base = Path(pasta) / t / 'gsm8k'
                base.mkdir(parents=True)
                dados = {'tecnica': t, 'dataset': 'gsm8k', 'status': 'concluido',
                         'parametros': {'modelo': 'llama3.2', 'limite': 2, 'quantidade_exemplos': 2},
                         'resultados': execucao(t, [True, False])['questoes']}
                (base / f'{t}_gsm8k_01112026_120000.json').write_text(json.dumps(dados))
            rel = ct.gerar('gsm8k', 2, 2, pasta=pasta)
            self.assertEqual(len(rel['comparacoes']), 3)
            self.assertIn('McNemar', ct.para_markdown(rel))
            destino = Path(pasta) / 'comparacao_gsm8k.json'
            destino.write_text(json.dumps(rel, default=str))
            self.assertIn('gsm8k', consolidar(pasta))


class TestCorrecoesMetodologicas(unittest.TestCase):
    def test_curva_fixa_mantem_mesmas_questoes(self):
        e = execucao('self_consistency', [True, False])
        e['questoes'][0].update(gabarito='10', amostras=[{'resposta_extraida': x} for x in ('10', '5', '10')])
        e['questoes'][1].update(gabarito='10', amostras=[{'resposta_extraida': x} for x in ('5', '10')])
        r = analisar(e)
        self.assertEqual([x['questoes'] for x in r['por_k_mesmas_questoes']], [1, 1, 1])
        self.assertEqual([x['questoes'] for x in r['por_k']], [2, 2, 1])

    def test_custo_beneficio_usa_somente_pares_com_tempo(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivos = {}
            for tecnica in ct.TECNICAS:
                qs = execucao(tecnica, [True, False], ['a', 'b'])['questoes']
                if tecnica == 'few_shot':
                    qs[1]['tempo_segundos'] = None
                if tecnica == 'self_consistency':
                    qs[0]['tempo_segundos'] = 6
                    qs[1]['tempo_segundos'] = 100
                dados = {'tecnica': tecnica, 'dataset': 'gsm8k', 'status': 'concluido',
                         'parametros': {'modelo': 'm', 'quantidade_exemplos': 2, 'ids_exemplos': [1, 2]},
                         'resultados': qs}
                arq = Path(pasta) / f'{tecnica}.json'
                arq.write_text(json.dumps(dados))
                arquivos[tecnica] = arq
            r = ct.gerar('gsm8k', arquivos=arquivos)
            cb = r['custo_beneficio']['few_shot__vs__self_consistency']
            self.assertEqual(cb['n_tempo_pareado'], 1)
            self.assertEqual(cb['tempo_adicional_s'], 4)

    def test_ids_numericos_e_textuais(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / 'execucao.json'
            arquivo.write_text(json.dumps({'dataset': 'gsm8k', 'tecnica': 'few_shot',
                                           'resultados': [{'id': 12, 'acertou': True}]}))
            e = ct.carregar_execucao(arquivo)
            self.assertEqual(e['questoes'][0]['id'], '12')
            self.assertTrue(e['veredito']['12'])

    def test_metadados_ausentes_bloqueiam_estrito(self):
        a = execucao('few_shot', [True])
        b = execucao('chain_of_thought', [True])
        motivos = ct.motivos_nao_comparavel({'few_shot': a, 'chain_of_thought': b})
        self.assertTrue(any('ausente' in x for x in motivos))

    def test_tabela_custo_beneficio_tem_celulas_alinhadas(self):
        rel = {'dataset': 'x', 'execucoes': {}, 'avisos': [], 'acuracia': {}, 'comparacoes': {},
               'custo': {}, 'falhas': {}, 'self_consistency_amostras': None,
               'custo_beneficio': {'few_shot__vs__self_consistency': {
                   'ganho_pp_pareado': 10.0, 'tempo_adicional_s': 5.0, 'n_tempo_pareado': 4,
                   'multiplicador_tempo': 3.0, 'ganho_pp_por_segundo_adicional': 2.0,
                   'tokens_adicionais_medios': 100.0, 'ganho_pp_por_1000_tokens_adicionais': 100.0}}}
        linhas = ct.para_markdown(rel).split('## Custo-benefício')[1].split('## Falhas')[0].splitlines()
        tabela = [l for l in linhas if l.startswith('|')]
        self.assertEqual(len({l.count('|') for l in tabela}), 1)


class TestRelatorioTccSemDados(unittest.TestCase):
    def test_sem_comparacoes_nao_gera_traceback(self):
        from codigo.avaliacao import relatorio_tcc
        with tempfile.TemporaryDirectory() as pasta:
            self.assertEqual(relatorio_tcc.main(['--pasta', pasta]), 1)


if __name__ == '__main__':
    unittest.main()
