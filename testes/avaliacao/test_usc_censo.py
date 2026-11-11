"""Teste do juiz de consenso exploratório, com juiz simulado (sem Ollama)."""
import json
import tempfile
import unittest
from pathlib import Path

from codigo.avaliacao import usc_censo as u


class TestUSC(unittest.TestCase):
    def test_ler_escolha(self):
        self.assertEqual(u.ler_escolha('A resposta mais consistente é a Resposta 3', 5), 2 + 1)
        self.assertIsNone(u.ler_escolha('Resposta 9', 5))
        self.assertIsNone(u.ler_escolha('', 5))

    def test_escolher_tenta_ate_tres(self):
        saidas = iter(['??', 'nada', 'Resposta 2'])
        i, _, t = u.escolher('p', ['a', 'b'], lambda *a, **k: {'resposta': next(saidas)})
        self.assertEqual((i, t), (1, 3))

    def test_aplicar_nao_altera_original_e_so_chama_se_divergem(self):
        with tempfile.TemporaryDirectory() as d:
            arq = Path(d) / 'sc.json'
            qs = [{'id': 'c1', 'resposta': '10', 'acertou': True, 'respostas_extraidas': ['10', '10', '10']},
                  {'id': 'c2', 'resposta': '5', 'acertou': False, 'respostas_extraidas': ['5', '7', '5']}]
            arq.write_text(json.dumps({'dataset': 'censo', 'tecnica': 'self_consistency',
                                       'status': 'concluido', 'resultados': qs, 'parametros': {}}))
            antes = arq.read_text()
            chamadas = []

            def juiz(prompt, **k):
                chamadas.append(prompt)
                return {'resposta': 'Resposta 2'}
            base = {'c1': {'pergunta': 'p1', 'resposta_esperada': '10'},
                    'c2': {'pergunta': 'p2', 'resposta_esperada': '7'}}
            res = u.aplicar(arq, base, juiz)
            self.assertEqual(len(chamadas), 1)
            self.assertEqual(res['resumo']['mudaram'], 1)
            self.assertEqual(arq.read_text(), antes)
            self.assertIn('Questão', u.relatorio_md(res))


if __name__ == '__main__':
    unittest.main()