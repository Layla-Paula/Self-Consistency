"""Testes do agente SQL do Censo com um "modelo" de mentira (respostas roteirizadas).

Não usa Ollama nem internet.
"""
import os
import sys
import unittest
from unittest import mock

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, RAIZ)

from codigo import agente_censo  # noqa: E402
from codigo.agente_censo import (_extrair_resposta_final, _resposta_final_valida,  # noqa: E402
                                 consultar_censo_agente)

SQL1 = '```sql\nSELECT COUNT(*) AS total FROM matriculas\n```'
SQL2 = '```sql\nSELECT SUM(QT_MAT_BAS) FROM matriculas\n```'


class SessaoFalsa:
    def __init__(self, falhar_sql=False):
        self.sqls, self.dics, self.falhar_sql = [], [], falhar_sql

    def executar_sql(self, comando):
        self.sqls.append(comando)
        if self.falhar_sql:
            raise RuntimeError('sql inválido')
        return {'colunas': ['total'], 'linhas': [[178766]]}

    def consultar_dicionario(self, nome):
        self.dics.append(nome)
        return {'variavel': nome, 'descricao': 'texto'}


def rodar(respostas, sessao=None, **kw):
    """Executa o agente com o modelo respondendo, em ordem, a lista `respostas`."""
    sessao = sessao or SessaoFalsa()
    fila = list(respostas)

    def falso(prompt, **opcoes):
        if not fila:
            return {'resposta': None, 'erro_detalhado': 'fila vazia no teste'}
        return {'resposta': fila.pop(0), 'prompt_eval_count': 10, 'eval_count': 5,
                'tempo_total_segundos': 1.0}

    with mock.patch.object(agente_censo, 'consultar_ollama', falso):
        return consultar_censo_agente('Quantas escolas?', sessao, **kw), sessao


class TestExtracaoDaRespostaFinal(unittest.TestCase):
    def test_pega_texto_depois_do_rotulo(self):
        self.assertEqual(_extrair_resposta_final('x\nResposta final: Há 5 escolas.'), 'Há 5 escolas.')

    def test_usa_o_ultimo_rotulo(self):
        self.assertEqual(_extrair_resposta_final('Resposta final: 1\nResposta final: 2'), '2')

    def test_sem_rotulo(self):
        self.assertIsNone(_extrair_resposta_final('Há 5 escolas.'))

    def test_remove_sql_e_ferramenta(self):
        r = _extrair_resposta_final('Resposta final: Há 5.\nFERRAMENTA: {"a":1}')
        self.assertEqual(r, 'Há 5.')
        self.assertIsNone(_extrair_resposta_final('Resposta final: ```sql\nSELECT 1 FROM t\n```'))


class TestRespostaFinalValida(unittest.TestCase):
    def test_invalidas(self):
        for t in ('', None, '{"a": 1}', '[1]', 'ASSISTENTE: oi', 'FERRAMENTA: x',
                  'DICIONARIO: X', '```sql', 'SELECT a FROM b', 'WITH x AS (select 1) SELECT 1 FROM x'):
            with self.subTest(t=t):
                self.assertFalse(_resposta_final_valida(t))

    def test_validas(self):
        for t in ('Há 178.766 escolas.', 'A Federal tem 716 escolas.', '42'):
            with self.subTest(t=t):
                self.assertTrue(_resposta_final_valida(t))


class TestFluxoDoAgente(unittest.TestCase):
    def test_consulta_e_responde(self):
        r, s = rodar([SQL1, 'Resposta final: Há 178.766 escolas.'])
        self.assertEqual(r['resposta'], 'Há 178.766 escolas.')
        self.assertEqual(r['motivo_encerramento_censo'], 'resposta_com_evidencia')
        self.assertTrue(r['evidencia_consultada'])
        self.assertEqual(r['sql_executadas'], 1)
        self.assertEqual(len(s.sqls), 1)
        self.assertEqual(r['rodadas_censo'], 2)

    def test_dicionario(self):
        r, s = rodar(['DICIONARIO: TP_DEPENDENCIA', 'Resposta final: É a dependência administrativa.'])
        self.assertEqual(s.dics, ['TP_DEPENDENCIA'])
        self.assertEqual(r['dicionario_consultado'], 1)
        self.assertEqual(r['motivo_encerramento_censo'], 'resposta_com_evidencia')

    def test_resposta_sem_consulta_nao_vale(self):
        r, _ = rodar(['Resposta final: Há 178.766 escolas.'])
        self.assertEqual(r['motivo_encerramento_censo'], 'resposta_sem_consulta')
        self.assertFalse(r['evidencia_consultada'])
        self.assertEqual(r['resposta'], '')

    def test_resposta_escrita_junto_de_comando_novo_e_ignorada(self):
        r, s = rodar([SQL1 + '\nResposta final: 999', 'Resposta final: Há 178.766 escolas.'])
        self.assertEqual(r['resposta'], 'Há 178.766 escolas.')
        self.assertEqual(len(s.sqls), 1)

    def test_consulta_repetida_com_resposta_apoiada_em_evidencia(self):
        r, s = rodar([SQL1, SQL1 + '\nResposta final: Há 178.766 escolas.'])
        self.assertEqual(r['motivo_encerramento_censo'], 'resposta_apos_consulta_repetida')
        self.assertEqual(r['resposta'], 'Há 178.766 escolas.')
        self.assertEqual(len(s.sqls), 1, 'não executa de novo')

    def test_consulta_repetida_sem_resposta_pede_finalizacao(self):
        r, s = rodar([SQL1, SQL1, 'Resposta final: Há 178.766 escolas.'])
        self.assertEqual(r['motivo_encerramento_censo'], 'resposta_apos_finalizacao')
        self.assertEqual(r['consultas_repetidas_bloqueadas'], 1)
        self.assertEqual(len(s.sqls), 1)

    def test_finalizacao_sem_resposta(self):
        r, _ = rodar([SQL1, SQL1, 'não sei', 'ainda não sei'])
        self.assertEqual(r['motivo_encerramento_censo'], 'finalizacao_sem_resposta')
        self.assertEqual(r['resposta'], '')

    def test_limite_de_cinco_consultas(self):
        sqls = [f'```sql\nSELECT {i} FROM matriculas\n```' for i in range(8)]
        r, s = rodar(sqls + ['Resposta final: 1'])
        self.assertLessEqual(len(s.sqls), agente_censo.MAX_CONSULTAS)
        self.assertEqual(len(r['consultas_censo']), agente_censo.MAX_CONSULTAS)

    def test_sql_com_erro_nao_conta_como_evidencia(self):
        r, _ = rodar([SQL1, 'Resposta final: Há 5.'], SessaoFalsa(falhar_sql=True))
        self.assertFalse(r['evidencia_consultada'])
        self.assertEqual(r['sql_executadas'], 0)
        self.assertNotEqual(r['motivo_encerramento_censo'], 'resposta_com_evidencia')

    def test_falha_do_ollama(self):
        r, _ = rodar([])
        self.assertEqual(r['motivo_encerramento_censo'], 'falha_ollama')
        self.assertIsNone(r['resposta'])

    def test_resposta_vazia_nao_e_aceita(self):
        r, _ = rodar([SQL1, '', '', ''])
        self.assertEqual(r['resposta'], '')
        self.assertIn(r['motivo_encerramento_censo'],
                      ('finalizacao_sem_resposta', 'resposta_vazia'))

    def test_resposta_final_com_sql_novo_e_rejeitada(self):
        r, s = rodar([SQL1, 'Resposta final: ' + SQL2, 'Resposta final: Há 178.766 escolas.'])
        self.assertEqual(r['resposta'], 'Há 178.766 escolas.')

    def test_tudo_fica_registrado(self):
        r, _ = rodar([SQL1, 'Resposta final: Há 178.766 escolas.'])
        self.assertEqual(len(r['transcricoes_censo']), 2)
        self.assertEqual(r['tokens_entrada'], 20)
        self.assertEqual(r['tokens_saida'], 10)

    def test_seed_e_repassada_ao_ollama(self):
        vistos = []

        def falso(prompt, **opcoes):
            vistos.append(opcoes)
            return {'resposta': 'x'}
        with mock.patch.object(agente_censo, 'consultar_ollama', falso):
            consultar_censo_agente('p', SessaoFalsa(), seed=44)
        self.assertEqual(vistos[0].get('seed'), 44)

    def test_determinismo_com_mesmo_roteiro(self):
        a, _ = rodar([SQL1, 'Resposta final: Há 178.766 escolas.'])
        b, _ = rodar([SQL1, 'Resposta final: Há 178.766 escolas.'])
        for chave in ('resposta', 'motivo_encerramento_censo', 'rodadas_censo'):
            self.assertEqual(a[chave], b[chave])


if __name__ == '__main__':
    unittest.main()
