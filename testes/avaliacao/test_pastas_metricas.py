"""Organização das saídas: comparação por dataset em subpasta, relatório geral em relatorios/geral."""
import json
import tempfile
import unittest
from pathlib import Path

from codigo.avaliacao import relatorio_tcc


def comparacao(dataset):
    return {'dataset': dataset, 'comparavel': True,
            'acuracia': {'few_shot': {'avaliadas': 2, 'acertos': 1, 'acuracia': .5, 'pendentes': 0}},
            'custo': {'few_shot': {'tempo_medio_s': 2.0}}}


class TestPastas(unittest.TestCase):
    def test_sintese_le_as_subpastas_por_dataset_e_grava_em_geral(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            for ds in ('gsm8k', 'aqua_rat'):
                (base / ds).mkdir()
                (base / ds / f'comparacao_{ds}.json').write_text(json.dumps(comparacao(ds)), encoding='utf-8')
            self.assertEqual(relatorio_tcc.main(['--pasta', str(base)]), 0)
            self.assertTrue((base / 'geral' / 'sintese_tcc.md').exists())
            texto = (base / 'geral' / 'sintese_tcc.md').read_text(encoding='utf-8')
            self.assertIn('gsm8k', texto)
            self.assertIn('aqua_rat', texto)

    def test_ainda_aceita_o_arquivo_direto_na_pasta(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'comparacao_gsm8k.json').write_text(json.dumps(comparacao('gsm8k')), encoding='utf-8')
            self.assertIn('gsm8k', relatorio_tcc.consolidar(d))


if __name__ == '__main__':
    unittest.main()


class TestTempoSemExecucoesDeTeste(unittest.TestCase):
    def test_execucao_de_500_questoes_nao_entra_no_tempo(self):
        from codigo.avaliacao.comparar_configuracoes import agregar
        base = dict(dataset='gsm8k', limite=200, exemplos=10, tecnica='chain_of_thought', temperatura=0.0,
                    tokens=1200, n_amostras=None, maquina='não informada', acuracia=60.0, suspeita=False,
                    avaliadas=200, acertos=120, pendentes=0, falhas_tecnicas=0, tokens_entrada_medio=1.0,
                    tokens_saida_medio=1.0, amostras_sem_extracao=0, total_amostras=1, id_execucao='x')
        linhas = [dict(base, tempo_medio_s=20.0, limite_original=200, id_execucao='a'),
                  dict(base, tempo_medio_s=5.0, limite_original=500, id_execucao='b')]
        ag = agregar(linhas)[0]
        self.assertEqual(ag['tempo_medio_s'], 20.0)       # só a de 200 conta no tempo
        self.assertEqual(ag['execucoes'], 2)              # mas as duas contam na acurácia


class TestExecucoesIsoladas(unittest.TestCase):
    def _arquivo(self, pasta, nome, ini, fim, limite=200, maquina='pc1'):
        d = Path(pasta) / 'few_shot' / 'gsm8k' / f'limite_{limite}_exemplos_10'
        d.mkdir(parents=True, exist_ok=True)
        (d / f'{nome}.json').write_text(json.dumps({
            'dataset': 'gsm8k', 'tecnica': 'few_shot', 'data_inicio': ini, 'data_fim': fim,
            'parametros': {'limite': limite}, 'resultados': [],
            'ambiente': {'identificador': maquina} if maquina else {}}), encoding='utf-8')
        return str(d / f'{nome}.json')

    def test_marca_sobreposicao_e_ignora_outro_pc(self):
        from codigo.avaliacao.comparar_configuracoes import _marcar_isoladas
        with tempfile.TemporaryDirectory() as t:
            a = self._arquivo(t, 'a', '2026-11-01T10:00:00', '2026-11-01T11:00:00')
            b = self._arquivo(t, 'b', '2026-11-01T10:30:00', '2026-11-01T12:00:00')      # sobrepõe a
            c = self._arquivo(t, 'c', '2026-11-02T10:00:00', '2026-11-02T11:00:00')      # sozinha
            e = self._arquivo(t, 'e', '2026-11-02T10:10:00', '2026-11-02T10:50:00', limite=500)  # outro PC
            linhas = [{'arquivo': x} for x in (a, b, c)]
            _marcar_isoladas(linhas, [a, b, c, e])
            self.assertEqual([l['isolada'] for l in linhas], [False, False, True])


    def test_sobreposicao_so_conta_na_mesma_maquina(self):
        from codigo.avaliacao.comparar_configuracoes import _marcar_isoladas
        with tempfile.TemporaryDirectory() as t:
            a = self._arquivo(t, 'a', '2026-11-01T10:00:00', '2026-11-01T11:00:00', maquina='pc1')
            b = self._arquivo(t, 'b', '2026-11-01T10:30:00', '2026-11-01T12:00:00', maquina='pc2')
            c = self._arquivo(t, 'c', '2026-11-03T10:00:00', '2026-11-03T11:00:00', maquina=None)
            linhas = [{'arquivo': x} for x in (a, b, c)]
            _marcar_isoladas(linhas, [a, b, c])
            # a e b se sobrepõem, mas em PCs diferentes; c não tem máquina: tempo só descritivo
            self.assertEqual([l['isolada'] for l in linhas], [True, True, False])


class TestTokensMesmoConjunto(unittest.TestCase):
    def test_sc_so_conta_questao_com_todas_as_geracoes_e_entrada_com_saida(self):
        from codigo.avaliacao.comparacao_tecnicas import custo
        am = lambda n, ent=10, sai=20: [{'tokens_entrada': ent, 'tokens_saida': sai} for _ in range(n)]
        qs = [{'tokens_entrada': 50, 'tokens_saida': 100, 'amostras': am(5)},
              {'tokens_entrada': 20, 'tokens_saida': 40, 'amostras': am(2)},                 # faltam gerações
              {'tokens_entrada': 50, 'tokens_saida': None, 'amostras': am(5)},               # saída ausente
              {'tokens_entrada': 70, 'tokens_saida': 140, 'amostras': am(5, 14, 28)},
              {'tokens_entrada': 50, 'tokens_saida': 100, 'amostras': []},                    # sem gerações salvas
              {'tokens_entrada': 99, 'tokens_saida': 99, 'amostras': am(5)}]                 # total != soma
        c = custo({'questoes': qs, 'dados': {'parametros': {'n_amostras': 5}}})
        self.assertEqual(c['tokens_entrada_medio'], 60.0)
        self.assertEqual(c['tokens_saida_medio'], 120.0)
        self.assertEqual(c['tokens_entrada_medio_n'], 2)
        self.assertEqual(c['tokens_total_medio'], 180.0)


    def test_acuracia_ponderada_pelas_questoes_validas(self):
        from codigo.avaliacao.comparar_configuracoes import agregar
        base = dict(dataset='gsm8k', limite=200, exemplos=10, tecnica='few_shot', temperatura=0.0, tokens=1200,
                    n_amostras=None, maquina='pc1', suspeita=False, pendentes=0, falhas_tecnicas=0,
                    tempo_medio_s=None, tokens_entrada_medio=1.0, tokens_saida_medio=1.0, conjunto='x', tokens_validas_n=1)
        linhas = [dict(base, acuracia=0.5, avaliadas=200, id_execucao='a'),
                  dict(base, acuracia=1.0, avaliadas=100, id_execucao='b')]
        ag = agregar(linhas)[0]
        self.assertAlmostEqual(ag['acuracia_media'], 200 / 300)      # (100+100)/(200+100), não 0,75
        self.assertEqual(ag['avaliadas_total'], 300)

    def test_graficos_exigem_o_mesmo_conjunto_de_questoes(self):
        from codigo.avaliacao.graficos_e_planilhas import escolher_comparaveis
        def ag(t, conj):
            return dict(dataset='gsm8k', tokens=1200, limite=200, exemplos=10, tecnica=t, conjunto=conj,
                        acuracia_media=0.5, execucoes=1, n_amostras=None)
        self.assertEqual(escolher_comparaveis([ag('few_shot', 'A'), ag('chain_of_thought', 'A'),
                                               ag('self_consistency', 'B')]), {})
        self.assertIn(1200, escolher_comparaveis([ag('few_shot', 'A'), ag('chain_of_thought', 'A'),
                                                  ag('self_consistency', 'A')]))


    def test_tokens_ponderados_pelas_questoes_com_tokens_completos(self):
        from codigo.avaliacao.comparar_configuracoes import agregar
        base = dict(dataset='gsm8k', limite=200, exemplos=10, tecnica='few_shot', temperatura=0.0, tokens=1200,
                    n_amostras=None, maquina='pc1', suspeita=False, pendentes=0, falhas_tecnicas=0, acuracia=0.5,
                    avaliadas=100, tempo_medio_s=None, conjunto='x')
        linhas = [dict(base, tokens_entrada_medio=100.0, tokens_saida_medio=10.0, tokens_validas_n=300, id_execucao='a'),
                  dict(base, tokens_entrada_medio=200.0, tokens_saida_medio=20.0, tokens_validas_n=100, id_execucao='b')]
        ag = agregar(linhas)[0]
        self.assertAlmostEqual(ag['tokens_entrada_medio'], 125.0)     # não 150
        self.assertAlmostEqual(ag['tokens_saida_medio'], 12.5)
        self.assertEqual(ag['tokens_validas_total'], 400)

    def test_sem_ids_de_exemplos_o_conjunto_nao_e_verificavel(self):
        from codigo.avaliacao.comparar_configuracoes import _impressao_conjunto
        ex = {'questoes': [{'id': 1}, {'id': 2}]}
        self.assertIsNone(_impressao_conjunto({'parametros': {}}, ex))
        self.assertIsNotNone(_impressao_conjunto({'parametros': {'ids_exemplos': ['9']}}, ex))
        from codigo.avaliacao.graficos_e_planilhas import escolher_comparaveis
        ag = lambda t: dict(dataset='gsm8k', tokens=1200, limite=200, exemplos=10, tecnica=t, conjunto=None,
                            acuracia_media=0.5, execucoes=1, n_amostras=None)
        self.assertEqual(escolher_comparaveis([ag('few_shot'), ag('chain_of_thought'), ag('self_consistency')]), {})

    def test_tokens_sem_registros_completos_nao_tem_media(self):
        from codigo.avaliacao.comparar_configuracoes import _media_ponderada
        self.assertIsNone(_media_ponderada([{'tokens_entrada_medio': 100.0, 'tokens_validas_n': 0}],
                                           'tokens_entrada_medio'))
        self.assertIsNone(_media_ponderada([{'tokens_entrada_medio': 100.0}], 'tokens_entrada_medio'))
