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


class TestVotoCenso(unittest.TestCase):
    def voto(self, respostas):
        return voto_censo_semantico('pergunta', respostas, None)

    def test_pluralidade_sem_maioria(self):
        r = self.voto(['178.766', '5', '178766', '9', '12'])
        self.assertEqual(r['votos'], 2)
        self.assertEqual(r['vencedora'], '178.766')
        self.assertFalse(r['houve_empate'])

    def test_limitacao_frases_com_formatos_diferentes_nao_se_juntam(self):
        # A equivalência só vale para respostas que são apenas um número.
        # Frases iguais com "178.766" e "178766" contam como votos diferentes.
        # Documentar no TCC: a votação do Censo é conservadora.
        r = self.voto(['Há 178.766 escolas.', 'Há 178766 escolas.', 'Há 5 escolas.'])
        self.assertEqual(r['votos'], 1)
        self.assertTrue(r['houve_empate'])

    def test_maiusculas_acentos_e_ponto_final_sao_ignorados(self):
        r = self.voto(['São Paulo.', 'sao paulo', 'Rio de Janeiro'])
        self.assertEqual(r['votos'], 2)

    def test_empate_primeira_geracao(self):
        r = self.voto(['Total 10', 'Total 20'])
        self.assertTrue(r['houve_empate'])
        self.assertEqual(r['vencedora'], 'Total 10')

    def test_sem_resposta(self):
        r = self.voto([None, '', '  '])
        self.assertEqual(r['metodo_votacao'], 'censo_sem_resposta')
        self.assertEqual(r['vencedora'], '')

    def test_nao_usa_o_modelo(self):
        # consultar_ollama=None: se o código tentasse chamá-lo, levantaria erro.
        self.voto(['a 1', 'b 2', 'c 3'])


class TestProtocolo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(RAIZ, 'dados', 'censo_escolar', 'final', 'censo_escolar_2025.json'),
                  encoding='utf-8') as f:
            d = json.load(f)
        cls.censo = d if isinstance(d, list) else d.get('questoes', d)

    def test_limite_valido_e_invalido(self):
        self.assertEqual(resolver_limite('gsm8k', 500), 500)
        self.assertIsNone(resolver_limite('gsm8k', None))
        for ruim in (0, -1, 1.5, True, '10'):
            with self.subTest(limite=ruim):
                with self.assertRaises(ValueError):
                    resolver_limite('gsm8k', ruim)
        with self.assertRaises(ValueError):
            resolver_limite('outro', 5)

    def test_demonstracoes_do_censo(self):
        ex = selecionar_exemplos_comuns('censo', self.censo, 6)
        numeros = sorted(int(e['id'].rsplit('_', 1)[-1]) for e in ex)
        self.assertEqual(numeros, [4, 12, 21, 30, 39, 47])

    def test_ordem_exemplos_sem_repeticao_e_completa(self):
        ordem = ordem_exemplos_censo(self.censo)
        self.assertEqual(sorted(ordem), list(range(50)))

    def test_exemplos_deterministicos(self):
        a = selecionar_exemplos_comuns('censo', self.censo, 6)
        b = selecionar_exemplos_comuns('censo', self.censo, 6)
        self.assertEqual([e['id'] for e in a], [e['id'] for e in b])

    def test_quantidade_invalida(self):
        for q in (0, -2, 1.5, True):
            with self.subTest(q=q):
                with self.assertRaises(ValueError):
                    selecionar_exemplos_comuns('censo', self.censo, q)
        with self.assertRaises(ValueError):
            selecionar_exemplos_comuns('censo', self.censo, 50)

    def test_demonstracoes_tem_resposta_raciocinio_e_sql(self):
        for e in selecionar_exemplos_comuns('censo', self.censo, 6):
            self.assertTrue(e['resposta_esperada'] and e['raciocinio'] and e['consultas_sql'], e['id'])

    def test_gabarito_censo(self):
        self.assertEqual(extrair_gabarito_censo({'resposta_esperada': 'x'}), 'x')


if __name__ == '__main__':
    unittest.main()
