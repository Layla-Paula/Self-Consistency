"""Gráficos e Excel gerados a partir das execuções (sem Ollama)."""
import json
import tempfile
import unittest
from pathlib import Path

from codigo.avaliacao import comparar_configuracoes as cc
from codigo.avaliacao.graficos_e_planilhas import formatar_data, formatar_duracao


def execucao(pasta, tecnica, nome, acertos, data, temp=0.0, amostras=None, tokens=1200):
    qs = [{'id': f'q{i}', 'acertou': a, 'tempo_segundos': 60.0, 'tokens_entrada': 100,
           'tokens_saida': 50} for i, a in enumerate(acertos)]
    dados = {'id_execucao': nome, 'tecnica': tecnica, 'dataset': 'gsm8k', 'status': 'concluido',
             'data_inicio': data, 'data_fim': data[:11] + '23:59:00', 'ambiente': {'identificador': 'pc1'},
             'parametros': {'modelo': 'm', 'temperatura': temp, 'maximo_tokens_resposta': tokens,
                            'n_amostras': amostras, 'quantidade_exemplos': 2, 'limite': len(acertos),
                            'ids_exemplos': ['e1', 'e2'], 'ids_questoes': [f'q{i}' for i in range(len(acertos))]},
             'resultados': qs}
    caminho = Path(pasta) / tecnica / 'gsm8k' / 'x' / f'{nome}.json'
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(dados), encoding='utf-8')


class TestFormatos(unittest.TestCase):
    def test_duracao(self):
        self.assertEqual(formatar_duracao(4.62), '4,6 s')
        self.assertEqual(formatar_duracao(91.2), '1 min 31 s')
        self.assertEqual(formatar_duracao(3700), '1 h 01 min')
        self.assertEqual(formatar_duracao(None), '—')

    def test_data(self):
        self.assertEqual(formatar_data('2026-11-08T22:26:46.123'), '08/11/2026 22:26')


class TestPlanilhaEGraficos(unittest.TestCase):
    def test_uma_linha_por_execucao_com_acertos_erros_e_data(self):
        with tempfile.TemporaryDirectory() as d:
            execucao(d, 'few_shot', 'f1', [True, False, False, True], '2026-11-01T10:00:00')
            execucao(d, 'few_shot', 'f2', [True, True, True, False], '2026-11-02T11:30:00')
            execucao(d, 'chain_of_thought', 'c1', [True] * 4, '2026-11-02T12:00:00')
            execucao(d, 'self_consistency', 's1', [True, True, False, True], '2026-11-03T09:05:00',
                     temp=0.7, amostras=5)
            saida = Path(d) / 'saida'
            cc.gerar(d, saida)
            cc.gerar(d, saida, orcamento=(1200,))
            for nome in ('grafico_acuracia_1200_tokens.png', 'grafico_tokens_1200_tokens.png', 'tabelas.xlsx'):
                self.assertGreater((saida / nome).stat().st_size, 0, nome)
            from openpyxl import load_workbook
            wb = load_workbook(saida / 'tabelas.xlsx')
            self.assertEqual(wb.sheetnames, ['Few-shot', 'CoT', 'Self-Consistency', 'Resumo'])
            ws = wb['Few-shot']
            self.assertIn('Atualizado em', ws['A1'].value)
            cab = [c.value for c in ws[2]]
            linhas = [[c.value for c in r] for r in ws.iter_rows(min_row=3)]
            self.assertEqual(len(linhas), 2)                                  # duas execuções, sem juntar
            self.assertEqual(linhas[0][cab.index('Data e hora')], '01/11/2026 10:00')
            self.assertEqual((linhas[0][cab.index('Acertos')], linhas[0][cab.index('Erros')]), (2, 2))
            self.assertEqual(linhas[0][cab.index('Tempo médio/questão (descritivo)')].total_seconds(), 60)
            sc = [c.value for c in wb['Self-Consistency'][2]]
            self.assertIn('Temperatura', sc)
            self.assertIn('Amostras', sc)
            self.assertIn('Máquina', cab)
            self.assertEqual(len(list(wb['Resumo'].iter_rows(min_row=3))), 3)




class TestGraficosComparaveis(unittest.TestCase):
    def ag(self, t, d, tokens, acc=0.5, execs=1, limite=200, exemplos=10, amostras=None):
        return {'tecnica': t, 'dataset': d, 'tokens': tokens, 'acuracia_media': acc, 'execucoes': execs,
                'limite': limite, 'exemplos': exemplos, 'n_amostras': amostras, 'temperatura': 0.0, 'conjunto': 'c1'}

    def test_so_orcamentos_com_as_tres_tecnicas_e_mesmas_questoes(self):
        from codigo.avaliacao.graficos_e_planilhas import escolher_comparaveis
        ags = [self.ag('few_shot', 'gsm8k', 1200), self.ag('chain_of_thought', 'gsm8k', 1200),
               self.ag('self_consistency', 'gsm8k', 1200, execs=5, amostras=5),
               self.ag('self_consistency', 'gsm8k', 2400, amostras=5),       # sem Few/CoT de 2400
               self.ag('chain_of_thought', 'gsm8k', 2400),
               self.ag('few_shot', 'censo', 1200, limite=None, exemplos=6),
               self.ag('chain_of_thought', 'censo', 1200, limite=5, exemplos=5),   # outras questões
               self.ag('self_consistency', 'censo', 1200, limite=None, exemplos=6)]
        r = escolher_comparaveis(ags)
        self.assertEqual(list(r), [1200])
        self.assertEqual(list(r[1200]), ['gsm8k'])             # Censo e 2400 ficam fora
        self.assertEqual(r[1200]['gsm8k']['self_consistency']['execucoes'], 5)

    def test_cria_acuracia_e_tokens_para_cada_orcamento(self):
        ags = [self.ag(t, 'gsm8k', k, amostras=5 if t == 'self_consistency' else None)
               for t in ('few_shot', 'chain_of_thought', 'self_consistency') for k in (1200, 2400)]
        for a in ags:
            a['tempo_medio_s'] = 10.0
        with tempfile.TemporaryDirectory() as d:
            from codigo.avaliacao.graficos_e_planilhas import gerar_graficos
            (Path(d) / 'grafico_tempo_2400_tokens.png').write_bytes(b'x')   # sobra antiga
            criados = gerar_graficos(ags, Path(d))
            self.assertEqual(sorted(criados), ['grafico_acuracia_1200_tokens.png', 'grafico_acuracia_2400_tokens.png',
                                               'grafico_tokens_1200_tokens.png', 'grafico_tokens_2400_tokens.png'])
            self.assertEqual(sorted(p.name for p in Path(d).glob('grafico_*.png')), sorted(criados))

    def test_sem_tempo_isolado_nao_cria_grafico_de_tempo(self):
        ags = [self.ag(t, 'gsm8k', 2400, amostras=5 if t == 'self_consistency' else None)
               for t in ('few_shot', 'chain_of_thought', 'self_consistency')]
        for a in ags:
            a['tempo_medio_s'] = None
        with tempfile.TemporaryDirectory() as d:
            from codigo.avaliacao.graficos_e_planilhas import gerar_graficos
            antigo = Path(d) / 'grafico_tempo_2400_tokens.png'
            antigo.write_bytes(b'x')
            criados = gerar_graficos(ags, Path(d))
            self.assertNotIn('grafico_tempo_2400_tokens.png', criados)
            self.assertFalse(antigo.exists())           # o gráfico de tempo antigo some
            self.assertIn('grafico_tokens_2400_tokens.png', criados)


if __name__ == '__main__':
    unittest.main()


class TestJuntarMaquinas(unittest.TestCase):
    def test_une_grupos_so_diferentes_na_maquina(self):
        from codigo.avaliacao.graficos_e_planilhas import juntar_maquinas, escolher_comparaveis
        def ag(tec, maq, acc, n, ex, tok):
            return {'dataset': 'gsm8k', 'limite': 200, 'exemplos': 10, 'tecnica': tec, 'temperatura': 0.0,
                    'tokens': 2400, 'n_amostras': None, 'conjunto': 'c1', 'maquina': maq, 'execucoes': ex,
                    'acuracia_media': acc, 'avaliadas_total': n, 'questoes_avaliadas': 200,
                    'tokens_entrada_medio': tok, 'tokens_saida_medio': 0, 'tokens_validas_total': n,
                    'com_acuracia': ex, 'acuracia_min': acc, 'acuracia_max': acc}
        ags = [ag('few_shot', 'DESKTOP', 0.11, 200, 1, 1000), ag('few_shot', 'não informada', 0.09, 200, 1, 1000),
               ag('chain_of_thought', 'não informada', 0.6, 200, 1, 2000),
               ag('self_consistency', 'não informada', 0.7, 200, 1, 10000)]
        ags[-1]['n_amostras'] = 5
        ags[-1]['temperatura'] = 0.7
        j = juntar_maquinas(ags)
        fs = [a for a in j if a['tecnica'] == 'few_shot']
        self.assertEqual(len(fs), 1)
        self.assertAlmostEqual(fs[0]['acuracia_media'], 0.10)
        self.assertEqual(fs[0]['execucoes'], 2)
        rep = escolher_comparaveis(ags)[2400]['gsm8k']['few_shot']
        self.assertAlmostEqual(rep['acuracia_media'], 0.10)