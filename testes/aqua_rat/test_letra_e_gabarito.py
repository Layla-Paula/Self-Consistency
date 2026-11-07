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


class TestExtracaoLetra(unittest.TestCase):
    def test_letras_validas(self):
        casos = [('Resposta final: C', 'C'), ('Resposta: b', 'B'), ('Alternativa correta: D', 'D'),
                 ('raciocínio...\nE', 'E'), ('**A**', 'A'), ('Resposta final: (B)', 'B')]
        for texto, esperado in casos:
            with self.subTest(texto=texto):
                self.assertEqual(extrair_letra_resposta(texto), esperado)

    def test_nao_confunde_artigo(self):
        for texto in ('A resposta é a mais simples', 'a conta fecha', '', None,
                      'Resposta final: F'):
            with self.subTest(texto=texto):
                self.assertEqual(extrair_letra_resposta(texto), '')

    def test_gabarito_aqua(self):
        self.assertEqual(extrair_gabarito_aqua_rat({'correct': 'c'}), 'C')
        with self.assertRaises(ValueError):
            extrair_gabarito_aqua_rat({'correct': 'Z'})
        with self.assertRaises(ValueError):
            extrair_gabarito_aqua_rat({})


if __name__ == '__main__':
    unittest.main()
