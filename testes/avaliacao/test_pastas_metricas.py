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
