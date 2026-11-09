"""Testes sem Ollama para preservar e retomar amostras."""
import unittest
from codigo.self_consistency.experimentos import executar_experimento_self_consistency


class TestRetomada(unittest.TestCase):
    def test_reaproveita_primeira_amostra_sem_gerar_novamente(self):
        chamadas = []
        snapshots = []
        def modelo(**kwargs):
            chamadas.append(kwargs['seed'])
            return {'resposta': f"Resposta final: {kwargs['seed']}", 'tentativas': 1,
                    'done_reason': 'stop', 'eval_count': 10, 'prompt_eval_count': 10}
        primeira = executar_experimento_self_consistency(
            'p', lambda s: s.split(': ')[-1], n_amostras=2,
            consultar_modelo=modelo, ao_concluir_amostra=lambda a: snapshots.append(a))
        self.assertEqual(chamadas, [43, 44])
        chamadas.clear()
        segunda = executar_experimento_self_consistency(
            'p', lambda s: s.split(': ')[-1], n_amostras=2,
            consultar_modelo=modelo, amostras_anteriores=snapshots[0])
        self.assertEqual(chamadas, [44])
        self.assertEqual(primeira['respostas_extraidas'], segunda['respostas_extraidas'])

    def test_amostra_falha_nao_e_reutilizada(self):
        chamadas = []
        def modelo(**kwargs):
            chamadas.append(kwargs['seed'])
            return {'resposta': 'Resposta final: 10', 'done_reason': 'stop'}
        anterior = [{'amostra': 1, 'semente': 43, 'resposta_completa': None,
                     'falha_tecnica': True, 'resposta_extraida': ''}]
        saida = executar_experimento_self_consistency(
            'p', lambda s: '10', n_amostras=1,
            consultar_modelo=modelo, amostras_anteriores=anterior)
        self.assertEqual(chamadas, [43])
        self.assertFalse(saida['falha_tecnica'])

if __name__ == '__main__':
    unittest.main()
