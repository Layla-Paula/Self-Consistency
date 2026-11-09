"""consultar_ollama com streaming: os pedaços são juntados e o timeout vale entre pedaços."""
import json
import unittest
from unittest import mock

import requests

from codigo import utils


class RespostaFalsa:
    def __init__(self, linhas=(), erro_http=None, erro_leitura=None):
        self.linhas = [json.dumps(x).encode() if isinstance(x, dict) else x for x in linhas]
        self.erro_http = erro_http
        self.erro_leitura = erro_leitura
        self.text = 'corpo do erro'

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def raise_for_status(self):
        if self.erro_http:
            raise self.erro_http

    def iter_lines(self):
        for linha in self.linhas:
            yield linha
        if self.erro_leitura:
            raise self.erro_leitura


FINAL = {'response': '', 'done': True, 'done_reason': 'stop', 'prompt_eval_count': 100,
         'eval_count': 7, 'eval_duration': 5, 'prompt_eval_duration': 3, 'total_duration': 9}


def pedacos(*textos):
    return [{'response': t, 'done': False} for t in textos] + [FINAL]


class TestStreaming(unittest.TestCase):
    def setUp(self):
        p = mock.patch('codigo.utils.time.sleep')
        p.start()
        self.addCleanup(p.stop)

    def consultar(self, respostas, **kw):
        with mock.patch('codigo.utils.requests.post', side_effect=respostas) as post:
            resultado = utils.consultar_ollama('pergunta', **kw)
        return resultado, post

    def test_junta_os_pedacos_e_devolve_o_texto(self):
        texto, _ = self.consultar([RespostaFalsa(pedacos('Res', 'posta ', 'final'))])
        self.assertEqual(texto, 'Resposta final')

    def test_metricas_vem_do_pedaco_final(self):
        info, _ = self.consultar([RespostaFalsa(pedacos('ab', 'c'))], retornar_metricas=True)
        self.assertEqual(info['resposta'], 'abc')
        self.assertEqual(info['eval_count'], 7)
        self.assertEqual(info['prompt_eval_count'], 100)
        self.assertEqual(info['done_reason'], 'stop')
        self.assertTrue(info['done'])
        self.assertEqual(info['tentativas'], 1)
        self.assertIsNone(info['erro_detalhado'])

    def test_pede_streaming_e_timeout_entre_pedacos(self):
        _, post = self.consultar([RespostaFalsa(pedacos('x'))])
        args = post.call_args
        self.assertTrue(args.kwargs['stream'])
        self.assertTrue(args.kwargs['json']['stream'])
        self.assertEqual(args.kwargs['timeout'],
                         (utils.TIMEOUT_CONEXAO_OLLAMA, utils.TIMEOUT_SEM_DADOS_OLLAMA))

    def test_linhas_vazias_sao_ignoradas(self):
        texto, _ = self.consultar([RespostaFalsa([b'', *pedacos('ok'), b''])])
        self.assertEqual(texto, 'ok')

    def test_limite_de_tokens_e_preservado(self):
        final = dict(FINAL, done_reason='length')
        info, _ = self.consultar([RespostaFalsa([{'response': 'corta', 'done': False}, final])],
                                 retornar_metricas=True)
        self.assertEqual(info['done_reason'], 'length')

    def test_timeout_no_meio_do_stream_tenta_de_novo_e_recupera(self):
        falha = RespostaFalsa([{'response': 'par', 'done': False}],
                              erro_leitura=requests.exceptions.ReadTimeout('sem dados'))
        info, post = self.consultar([falha, RespostaFalsa(pedacos('inteira'))], retornar_metricas=True)
        self.assertEqual(info['resposta'], 'inteira')   # não mistura o pedaço da tentativa anterior
        self.assertEqual(info['tentativas'], 2)
        self.assertEqual(post.call_count, 2)

    def test_tres_timeouts_viram_falha_tecnica_com_metadados(self):
        falhas = [RespostaFalsa(erro_leitura=requests.exceptions.ReadTimeout('x')) for _ in range(3)]
        info, post = self.consultar(falhas, retornar_metricas=True)
        self.assertIsNone(info['resposta'])
        self.assertEqual(info['tentativas'], 3)
        self.assertIn('ReadTimeout', info['erro_detalhado'])
        self.assertEqual(post.call_count, 3)

    def test_sem_metricas_falha_devolve_none(self):
        falhas = [RespostaFalsa(erro_leitura=requests.exceptions.ConnectionError('off')) for _ in range(3)]
        texto, _ = self.consultar(falhas)
        self.assertIsNone(texto)

    def test_erro_informado_pelo_ollama_no_stream(self):
        ruim = RespostaFalsa([{'error': 'modelo não encontrado'}])
        info, _ = self.consultar([ruim] * 3, retornar_metricas=True)
        self.assertIsNone(info['resposta'])
        self.assertIn('modelo não encontrado', info['erro_detalhado'])

    def test_stream_sem_pedaco_final_e_erro(self):
        incompleto = RespostaFalsa([{'response': 'meio', 'done': False}])
        info, _ = self.consultar([incompleto] * 3, retornar_metricas=True)
        self.assertIsNone(info['resposta'])
        self.assertIn('done', info['erro_detalhado'])

    def test_http_500_registra_o_erro(self):
        erro = requests.HTTPError('500 Server Error')
        erro.response = mock.Mock(text='falha interna')
        info, _ = self.consultar([RespostaFalsa(erro_http=erro)] * 3, retornar_metricas=True)
        self.assertIsNone(info['resposta'])
        self.assertIn('HTTPError', info['erro_detalhado'])
        self.assertIn('falha interna', info['erro_detalhado'])

    def test_json_invalido_no_stream(self):
        info, _ = self.consultar([RespostaFalsa([b'nao e json'])] * 3, retornar_metricas=True)
        self.assertIsNone(info['resposta'])

    def test_response_com_tipo_invalido(self):
        ruim = RespostaFalsa([{'response': 123, 'done': True}])
        info, _ = self.consultar([ruim] * 3, retornar_metricas=True)
        self.assertIsNone(info['resposta'])
        self.assertIn('response', info['erro_detalhado'])


if __name__ == '__main__':
    unittest.main()
