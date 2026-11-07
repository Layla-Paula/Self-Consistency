"""Testes de extração, votação e protocolo (valem para as três técnicas)."""
import json
import os
import sys
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, RAIZ)

from codigo.utils import (comparar_numeros, extrair_gabarito_aqua_rat,  # noqa: E402
                          extrair_gabarito_censo, extrair_gabarito_gsm8k,
                          extrair_letra_resposta, extrair_resposta_numerica,
                          normalizar_numero)
from codigo.self_consistency.votacao import (normalizar_voto_gsm8k,  # noqa: E402
                                             voto_censo_semantico, voto_majoritario)
from codigo.protocolo_experimentos import (ordem_exemplos_censo, resolver_limite,  # noqa: E402
                                           selecionar_exemplos_comuns)


class TestNumeros(unittest.TestCase):
    def test_formatos_brasileiros(self):
        casos = {'1.000': 1000, '1.234,56': 1234.56, '12,5': 12.5, '1,234.56': 1234.56,
                 '72': 72, '-3': -3, '3.637': 3637, '0,5': 0.5}
        for texto, valor in casos.items():
            with self.subTest(texto=texto):
                self.assertAlmostEqual(normalizar_numero(texto), valor)

    def test_comparar_numeros(self):
        self.assertTrue(comparar_numeros('1.000', '1000'))
        self.assertTrue(comparar_numeros('12,5', '12.5'))
        self.assertFalse(comparar_numeros('12', '13'))
        self.assertFalse(comparar_numeros('abc', '12'))
        self.assertFalse(comparar_numeros('', '12'))
        self.assertFalse(comparar_numeros('inf', '12'))

    def test_chave_de_voto_gsm8k(self):
        self.assertEqual(normalizar_voto_gsm8k('1.000'), normalizar_voto_gsm8k('1000'))
        self.assertEqual(normalizar_voto_gsm8k('12,50'), normalizar_voto_gsm8k('12.5'))
        self.assertNotEqual(normalizar_voto_gsm8k('12'), normalizar_voto_gsm8k('13'))


class TestExtracaoNumerica(unittest.TestCase):
    def test_extrai_resposta_declarada(self):
        casos = [('Passo 1: 3+4=7.\nResposta final: 72', '72'),
                 ('Resposta: 1.250', '1.250'),
                 ('resposta final: R$ 15,50', '15,50'),
                 ('Calculo.\n#### 42', '42'),
                 ('Resposta final: -8', '-8')]
        for texto, esperado in casos:
            with self.subTest(texto=texto):
                self.assertEqual(extrair_resposta_numerica(texto), esperado)

    def test_nao_inventa_resposta(self):
        for texto in ('', None, 'Não sei resolver.', 'Resposta final: depende',
                      'Resposta final: 3 + 4', 'Resposta final: 2 x 5'):
            with self.subTest(texto=texto):
                self.assertEqual(extrair_resposta_numerica(texto), '')

    def test_usa_a_ultima_resposta_declarada(self):
        self.assertEqual(extrair_resposta_numerica('Resposta: 10\nCorrigindo.\nResposta final: 12'), '12')

    def test_gabarito_gsm8k(self):
        self.assertEqual(extrair_gabarito_gsm8k({'answer': 'passos\n#### 1.250'}), '1.250')
        self.assertEqual(extrair_gabarito_gsm8k({'answer': ''}), '')


class TestVotoMajoritario(unittest.TestCase):
    def test_maioria(self):
        r = voto_majoritario(['5', '7', '5', '5', '7'])
        self.assertEqual((r['vencedora'], r['votos'], r['houve_empate']), ('5', 3, False))

    def test_empate_vence_primeira_geracao(self):
        r = voto_majoritario(['7', '5', '5', '7'])
        self.assertEqual(r['vencedora'], '7')
        self.assertTrue(r['houve_empate'])

    def test_ignora_vazias_e_none(self):
        r = voto_majoritario([None, '', '  ', '9', '9'])
        self.assertEqual(r['vencedora'], '9')
        self.assertEqual(r['total_respostas_validas'], 2)

    def test_sem_respostas_validas(self):
        r = voto_majoritario([None, ''])
        self.assertEqual(r['vencedora'], '')
        self.assertEqual(r['votos'], 0)

    def test_normalizacao_junta_formatos(self):
        r = voto_majoritario(['1.000', '1000', '12', '1000', '12'], normalizar_voto_gsm8k)
        self.assertEqual(r['vencedora'], '1000')
        self.assertEqual(r['votos'], 3)

    def test_normalizador_que_falha_nao_derruba(self):
        r = voto_majoritario(['abc', 'abc', '5'], normalizar_voto_gsm8k)
        self.assertEqual(r['vencedora'], 'abc')

    def test_determinismo(self):
        entrada = ['A', 'B', 'C', 'B', 'A']
        self.assertEqual(voto_majoritario(entrada), voto_majoritario(entrada))


if __name__ == '__main__':
    unittest.main()
