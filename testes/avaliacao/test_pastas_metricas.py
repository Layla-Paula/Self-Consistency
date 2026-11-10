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
    def _arquivo(self, pasta, nome, ini, fim, limite=200):
        d = Path(pasta) / 'few_shot' / 'gsm8k' / f'limite_{limite}_exemplos_10'
        d.mkdir(parents=True, exist_ok=True)
        (d / f'{nome}.json').write_text(json.dumps({
            'dataset': 'gsm8k', 'tecnica': 'few_shot', 'data_inicio': ini, 'data_fim': fim,
            'parametros': {'limite': limite}, 'resultados': []}), encoding='utf-8')
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
