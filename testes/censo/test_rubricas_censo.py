"""Testes das rubricas objetivas do Censo Escolar 2025.

Rodar na raiz do projeto:  python -m unittest discover -s testes -v
"""
import json
import os
import sys
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, RAIZ)

from codigo.avaliacao.avaliacao_censo import _criterios_censo, avaliar_censo  # noqa: E402
from testes.censo.casos_rubricas_censo import (  # noqa: E402
    CASOS, DEFEITOS, LIMITACOES, COM_VEREDITO, PARCIAL, SEM_RUBRICA)

CAMINHO = os.path.join(RAIZ, 'dados', 'censo_escolar', 'final', 'censo_escolar_2025.json')


def _carregar():
    with open(CAMINHO, encoding='utf-8') as f:
        d = json.load(f)
    return d if isinstance(d, list) else d.get('questoes', d)


QUESTOES = _carregar()


def questao(n):
    return QUESTOES[n - 1]


def rubrica(n, resposta):
    """Veredito da rubrica: True, False ou None (rubrica não decide)."""
    r = _criterios_censo(questao(n), resposta)
    return None if r is None else r['acertou']


class TestDataset(unittest.TestCase):
    def test_50_questoes_com_ids_em_ordem(self):
        self.assertEqual(len(QUESTOES), 50)
        for i, q in enumerate(QUESTOES, 1):
            self.assertTrue(q['id'].endswith(f'_{i:02d}'), q['id'])

    def test_toda_questao_tem_gabarito(self):
        for q in QUESTOES:
            self.assertTrue(str(q.get('resposta_esperada', '')).strip(), q['id'])

    def test_listas_de_cobertura_sao_completas(self):
        todas = set(COM_VEREDITO) | set(PARCIAL) | set(SEM_RUBRICA)
        self.assertEqual(todas, set(range(1, 51)))


class TestCasosPositivosENegativos(unittest.TestCase):
    """Cada caso: resposta correta, incorreta, incompleta ou contraditória."""

    def test_casos(self):
        for n, tipo, resposta, esperado in CASOS:
            with self.subTest(questao=n, tipo=tipo, resposta=resposta[:60]):
                self.assertIs(rubrica(n, resposta), esperado)

    def test_cada_rubrica_tem_caso_correto_e_caso_errado(self):
        for n in COM_VEREDITO:
            tipos = {t for q, t, _, _ in CASOS if q == n}
            with self.subTest(questao=n):
                self.assertIn('correta', tipos, 'falta caso correto')
                self.assertTrue(tipos - {'correta'}, 'falta caso negativo')


class TestDefeitosConhecidos(unittest.TestCase):
    def test_nao_aceita_defeitos_conhecidos_como_sucesso(self):
        self.assertEqual(DEFEITOS, [], 'Mova cada defeito para CASOS com resultado esperado correto.')


class TestLimitacoes(unittest.TestCase):
    """Erros que rubricas de número e palavra-chave não enxergam."""

    def test_limitacoes_documentadas(self):
        for n, desc, resposta, deveria, hoje in LIMITACOES:
            with self.subTest(questao=n, limitacao=desc):
                self.assertIs(rubrica(n, resposta), hoje)


class TestRubricaAceitaOProprioGabarito(unittest.TestCase):
    """Uma rubrica que rejeita o gabarito oficial está errada."""

    DEFEITUOSAS = set()  # gabaritos devem ser aceitos

    def test_gabarito_passa(self):
        for n in COM_VEREDITO:
            if n in self.DEFEITUOSAS:
                continue
            with self.subTest(questao=n):
                self.assertIsNot(rubrica(n, questao(n)['resposta_esperada']), False,
                                 'a rubrica rejeita o gabarito')

    def test_resposta_vazia_nunca_e_certa(self):
        for n in COM_VEREDITO + PARCIAL:
            with self.subTest(questao=n):
                self.assertIsNot(rubrica(n, ''), True)

    def test_resposta_sem_relacao_nunca_e_certa(self):
        for n in COM_VEREDITO + PARCIAL:
            with self.subTest(questao=n):
                self.assertIsNot(rubrica(n, 'Não consegui responder a esta pergunta.'), True)

    def test_sem_rubrica_retorna_none(self):
        for n in SEM_RUBRICA:
            with self.subTest(questao=n):
                self.assertIsNone(rubrica(n, 'qualquer texto 123'))


class TestFluxoAvaliarCenso(unittest.TestCase):
    def juiz(self, veredito):
        def f(prompt, **kw):
            return {'resposta': json.dumps({'veredito': veredito, 'justificativa': 'ok'}),
                    'tentativas': 1}
        return f

    def test_saida_bruta_de_ferramenta_e_erro(self):
        for texto in ('{"a": 1}', '[1, 2]', 'FERRAMENTA: x', '```sql\nSELECT 1\n```',
                      'DICIONARIO: TP_DEPENDENCIA'):
            with self.subTest(texto=texto):
                r = avaliar_censo(questao(25), texto, self.juiz('CORRETA'))
                self.assertIs(r['acertou'], False)
                self.assertEqual(r['metodo_avaliacao'], 'formato_invalido_censo')

    def test_resposta_vazia_e_erro(self):
        r = avaliar_censo(questao(1), '   ', self.juiz('CORRETA'))
        self.assertIs(r['acertou'], False)

    def test_juiz_nao_vira_acerto_sem_revisao(self):
        r = avaliar_censo(questao(25), 'resposta qualquer', self.juiz('CORRETA'))
        self.assertIsNone(r['acertou'])
        self.assertTrue(r['revisao_necessaria'])
        self.assertEqual(r['parecer_llm'], 'CORRETA')
        self.assertEqual(r['metodo_avaliacao'], 'llm_triagem_revisao_humana')

    def test_rubrica_falsa_prevalece_sobre_juiz(self):
        r = avaliar_censo(questao(1), 'Há 5 escolas.', self.juiz('CORRETA'))
        self.assertIs(r['acertou'], False)
        self.assertEqual(r['metodo_avaliacao'], 'rubrica_objetiva_censo')

    def test_rubrica_verdadeira_nao_chama_juiz(self):
        chamadas = []

        def juiz(prompt, **kw):
            chamadas.append(1)
            return {'resposta': '{}'}
        r = avaliar_censo(questao(1), 'Há 178.766 escolas.', juiz)
        self.assertIs(r['acertou'], True)
        self.assertEqual(chamadas, [])

    def test_sem_juiz_vai_para_revisao(self):
        r = avaliar_censo(questao(25), 'texto', None)
        self.assertIsNone(r['acertou'])
        self.assertTrue(r['revisao_necessaria'])

    def test_juiz_com_json_invalido_vai_para_revisao(self):
        def juiz(prompt, **kw):
            return {'resposta': 'não sei', 'tentativas': 1}
        r = avaliar_censo(questao(25), 'texto', juiz)
        self.assertIsNone(r['acertou'])
        self.assertEqual(r['metodo_avaliacao'], 'avaliador_inconclusivo')

    def test_juiz_que_levanta_erro_vai_para_revisao(self):
        def juiz(prompt, **kw):
            raise RuntimeError('ollama fora do ar')
        r = avaliar_censo(questao(25), 'texto', juiz)
        self.assertIsNone(r['acertou'])

    def test_gabarito_ausente_e_erro_conservador(self):
        q = {'id': 'censo_2025_99', 'pergunta': 'x'}
        r = avaliar_censo(q, 'algo', None)
        self.assertIs(r['acertou'], False)


if __name__ == '__main__':
    unittest.main()
