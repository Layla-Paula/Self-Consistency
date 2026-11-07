import json
import os
import sys
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, RAIZ)

from codigo import revisao_humana as rh  # noqa: E402


class TestWilson(unittest.TestCase):
    def test_valores_conhecidos(self):
        lo, hi = rh.intervalo_wilson(20, 50)
        self.assertAlmostEqual(lo, 0.2764, places=3)
        self.assertAlmostEqual(hi, 0.5381, places=3)

    def test_extremos(self):
        self.assertEqual(rh.intervalo_wilson(0, 0), (0.0, 0.0))
        lo, hi = rh.intervalo_wilson(0, 44)
        self.assertAlmostEqual(lo, 0.0)
        self.assertGreater(hi, 0.0)
        lo, hi = rh.intervalo_wilson(44, 44)
        self.assertAlmostEqual(hi, 1.0)

    def test_largura_com_n_pequeno(self):
        lo, hi = rh.intervalo_wilson(25, 50)
        self.assertGreater(hi - lo, 0.25)  # ~±14 pp


class TestMcNemar(unittest.TestCase):
    def test_sem_discordancia(self):
        self.assertEqual(rh.mcnemar_exato(0, 0), 1.0)

    def test_simetrico(self):
        self.assertEqual(rh.mcnemar_exato(3, 9), rh.mcnemar_exato(9, 3))

    def test_valor_conhecido(self):
        self.assertAlmostEqual(rh.mcnemar_exato(2, 10), 0.03857, places=4)

    def test_empate_perfeito(self):
        self.assertEqual(rh.mcnemar_exato(5, 5), 1.0)

    def test_pareado_usa_so_ids_em_comum(self):
        a = {'q1': True, 'q2': False, 'q3': True, 'extra': True}
        b = {'q1': False, 'q2': False, 'q3': True}
        r = rh.comparar_pareado(a, b)
        self.assertEqual((r['n'], r['so_a'], r['so_b']), (3, 1, 0))


class TestKappa(unittest.TestCase):
    def test_concordancia_total(self):
        a = {'1': True, '2': False, '3': True, '4': False}
        self.assertAlmostEqual(rh.kappa_cohen(a, dict(a))['kappa'], 1.0)

    def test_acaso(self):
        a = {'1': True, '2': True, '3': False, '4': False}
        b = {'1': True, '2': False, '3': True, '4': False}
        self.assertAlmostEqual(rh.kappa_cohen(a, b)['kappa'], 0.0)

    def test_discordancia_total_e_negativo(self):
        a = {'1': True, '2': False}
        b = {'1': False, '2': True}
        self.assertLess(rh.kappa_cohen(a, b)['kappa'], 0)

    def test_sem_questoes_em_comum(self):
        self.assertIsNone(rh.kappa_cohen({'a': True}, {'b': True})['kappa'])


QUESTOES = [
    {'id': 'q1', 'acertou': True},
    {'id': 'q2', 'acertou': False},
    {'id': 'q3', 'acertou': None, 'revisao_necessaria': True, 'tipo_resultado': 'avaliacao_pendente'},
    {'id': 'q4', 'acertou': None, 'revisao_necessaria': True, 'tipo_resultado': 'avaliacao_pendente'},
]


class TestResumo(unittest.TestCase):
    def test_limites_antes_da_revisao(self):
        r = rh.resumo(QUESTOES)
        self.assertEqual((r['certos_automaticos'], r['pendentes']), (1, 2))
        self.assertAlmostEqual(r['minimo'], 0.25)
        self.assertAlmostEqual(r['maximo'], 0.75)

    def test_pendentes(self):
        self.assertEqual([q['id'] for q in rh.pendentes(QUESTOES)], ['q3', 'q4'])

    def test_revisao_parcial_nao_fecha_acuracia(self):
        revs = [{'id': 'q3', 'revisor': 'layla', 'acertou': True, 'criterio': 'x'}]
        r = rh.resumo(QUESTOES, revs, 'layla')
        self.assertEqual(r['faltam_revisar'], 1)
        self.assertNotIn('acuracia_final', r)

    def test_revisao_completa(self):
        revs = [{'id': 'q3', 'revisor': 'layla', 'acertou': True, 'criterio': 'x'},
                {'id': 'q4', 'revisor': 'layla', 'acertou': False, 'criterio': 'y'}]
        r = rh.resumo(QUESTOES, revs, 'layla')
        self.assertAlmostEqual(r['acuracia_final'], 0.5)
        self.assertIn('ic95', r)

    def test_revisao_de_outro_revisor_nao_conta(self):
        revs = [{'id': 'q3', 'revisor': 'prof', 'acertou': True, 'criterio': 'x'}]
        self.assertEqual(rh.resumo(QUESTOES, revs, 'layla')['faltam_revisar'], 2)

    def test_arquivo_original_nao_e_alterado(self):
        with tempfile.TemporaryDirectory() as pasta:
            arq = os.path.join(pasta, 'r.json')
            texto = json.dumps({'resultados': QUESTOES})
            with open(arq, 'w') as f:
                f.write(texto)
            rh.caminho_revisoes(arq).write_text('[]')
            self.assertTrue(str(rh.caminho_revisoes(arq)).endswith('r.revisoes.json'))
            with open(arq) as f:
                self.assertEqual(f.read(), texto)


if __name__ == '__main__':
    unittest.main()
