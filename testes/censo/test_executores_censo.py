"""Few-shot e CoT: máquina gravada, Censo indeciso fica PENDENTE (não falha técnica), status com falhas.
Roda sem Ollama: o modelo, o agente e o avaliador são trocados por versões falsas."""
import importlib
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

try:
    import tqdm  # noqa: F401
except ImportError:                       # ambiente sem tqdm: um substituto simples
    modulo = types.ModuleType('tqdm')
    modulo.tqdm = lambda it, **kw: it
    sys.modules['tqdm'] = modulo
if not hasattr(sys.modules['tqdm'].tqdm, 'write'):     # o substituto de outro teste pode não ter .write
    sys.modules['tqdm'].tqdm.write = print

MODULOS = (('codigo.few_shot.executar_few_shot', 'prompt_few_shot_censo'),
           ('codigo.chain_of_thought.executar_cot', 'prompt_cot_censo'))


def _registros():
    ex = [{'id': f'e{i}', 'resposta_esperada': 'r', 'raciocinio': 'x', 'split': None} for i in range(2)]
    qs = [{'id': f'q{i}', 'pergunta': 'p', 'resposta_esperada': 'r', 'split': None} for i in range(3)]
    return ex, qs


class TestExecutores(unittest.TestCase):
    def rodar(self, nome_modulo, nome_prompt, veredito, respostas=None):
        modulo = importlib.import_module(nome_modulo)
        ex, qs = _registros()
        fake = types.ModuleType('codigo.consulta_censo')
        fake.SessaoCenso = lambda: types.SimpleNamespace(consultar=lambda q: 'ctx')
        fake.verificar_consultas = lambda x: None
        avaliacoes = iter(veredito)
        respostas = iter(respostas or ['resp'] * 3)
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(sys.modules, {'codigo.consulta_censo': fake}), \
                mock.patch.object(modulo, 'carregar_censo', lambda split=None: ex + qs), \
                mock.patch.object(modulo, 'selecionar_exemplos', lambda d, r, n: ex), \
                mock.patch.object(modulo, 'resumo_protocolo', lambda *a, **k: {}), \
                mock.patch.object(modulo, 'executar_consultas_demonstracao', lambda s, e: {x['id']: 'sql' for x in e}), \
                mock.patch.object(modulo, nome_prompt, lambda *a, **k: 'prompt'), \
                mock.patch.object(modulo, 'extrair_gabarito_censo', lambda q: 'r'), \
                mock.patch.object(modulo, 'consultar_censo_agente', lambda *a, **k: {'resposta': next(respostas)}), \
                mock.patch.object(modulo, 'avaliar_censo', lambda *a, **k: next(avaliacoes)):
            anterior = os.getcwd()
            os.chdir(tmp)
            try:
                modulo.executar_dataset('censo', None, 2)
                arquivos = [p for p in Path(tmp).rglob('*.json') if not p.name.endswith('.progresso.json')]
                self.assertEqual(len(arquivos), 1)
                return json.loads(arquivos[0].read_text(encoding='utf-8'))
            finally:
                os.chdir(anterior)

    def test_censo_indeciso_vira_pendente_e_grava_ambiente(self):
        indeciso = {'acertou': None, 'motivo': 'Parecer do juiz: CORRETA.', 'revisao_necessaria': True,
                    'metodo_avaliacao': 'llm_triagem_revisao_humana'}
        certo = {'acertou': True, 'motivo': 'ok', 'revisao_necessaria': False, 'metodo_avaliacao': 'rubrica'}
        for nome, prompt in MODULOS:
            with self.subTest(nome):
                d = self.rodar(nome, prompt, [certo, indeciso, certo])
                por_id = {r['id']: r for r in d['resultados']}
                self.assertFalse(por_id['q1']['falha_tecnica'])
                self.assertIsNone(por_id['q1']['acertou'])
                self.assertTrue(por_id['q1']['revisao_necessaria'])
                self.assertEqual(d['status'], 'concluido')
                self.assertIn('maquina', d['ambiente'])
                self.assertIn('sistema', d['ambiente'])

    def test_status_com_falhas_quando_o_agente_nao_responde(self):
        certo = {'acertou': True, 'motivo': 'ok', 'revisao_necessaria': False, 'metodo_avaliacao': 'rubrica'}
        for nome, prompt in MODULOS:
            with self.subTest(nome):
                d = self.rodar(nome, prompt, [certo, certo], respostas=['resp', None, 'resp'])
                self.assertEqual(d['status'], 'concluido_com_falhas')
                self.assertEqual(sum(r['falha_tecnica'] for r in d['resultados']), 1)


if __name__ == '__main__':
    unittest.main()
