"""Testes do comparador de configurações e da recuperação de falhas (sem Ollama)."""
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

try:                      # o executor importa tqdm só para a barra de progresso
    import tqdm  # noqa: F401
except ImportError:
    sys.modules['tqdm'] = types.SimpleNamespace(tqdm=lambda itens, **_: itens)

from codigo.avaliacao import comparar_configuracoes as cc
from codigo.avaliacao import comparacao_tecnicas as ct
from codigo.self_consistency import executar_self_consistency as esc


def escrever(pasta, tecnica, dataset, nome, acertos, temp=0.0, tokens=1200, amostras=None,
             exemplos=10, limite=10, status='concluido', falhas=(), sem_extracao=False,
             recuperacao_de=None, ambiente=None, sub='x'):
    """Cria uma execução sintética em pasta/tecnica/dataset/sub/nome.json."""
    qs = []
    for i, a in enumerate(acertos):
        q = {'id': f'q{i}', 'acertou': a, 'tempo_segundos': 10.0, 'tokens_entrada': 100,
             'tokens_saida': 20, 'falha_tecnica': i in falhas}
        if i in falhas:
            q['acertou'] = None
        if amostras:
            q['amostras'] = [{'resposta_extraida': '' if sem_extracao else '1'} for _ in range(amostras)]
        qs.append(q)
    dados = {'id_execucao': nome, 'tecnica': tecnica, 'dataset': dataset, 'status': status,
             'data_inicio': '2026-11-01T10:00:00',
             'parametros': {'modelo': 'm', 'temperatura': temp, 'maximo_tokens_resposta': tokens,
                            'n_amostras': amostras, 'quantidade_exemplos': exemplos, 'limite': limite},
             'resultados': qs}
    if recuperacao_de:
        dados['recuperacao_de'] = recuperacao_de
    if ambiente:
        dados['ambiente'] = ambiente
    caminho = Path(pasta) / tecnica / dataset / sub / f'{nome}.json'
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(dados), encoding='utf-8')
    return caminho


class TestColeta(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pasta = Path(self.tmp.name)

    def test_le_todas_as_configuracoes_e_agrupa(self):
        escrever(self.pasta, 'few_shot', 'gsm8k', 'f1', [True, False, True, True], tokens=1200)
        escrever(self.pasta, 'few_shot', 'gsm8k', 'f2', [True, True, True, True], tokens=2400)
        escrever(self.pasta, 'self_consistency', 'gsm8k', 's1', [True, False], temp=0.3, amostras=3)
        escrever(self.pasta, 'self_consistency', 'gsm8k', 's2', [True, True], temp=0.5, amostras=5)
        linhas = cc.coletar(self.pasta)
        self.assertEqual(len(linhas), 4)
        ags = cc.agregar(linhas)
        self.assertEqual(len(ags), 4)
        self.assertEqual({(a['tecnica'], a['temperatura'], a['tokens'], a['n_amostras']) for a in ags},
                         {('few_shot', 0.0, 1200, None), ('few_shot', 0.0, 2400, None),
                          ('self_consistency', 0.3, 1200, 3), ('self_consistency', 0.5, 1200, 5)})

    def test_repeticoes_da_mesma_configuracao_viram_media(self):
        escrever(self.pasta, 'few_shot', 'gsm8k', 'a', [True, True, False, False])
        escrever(self.pasta, 'few_shot', 'gsm8k', 'b', [True, True, True, False])
        ag = cc.agregar(cc.coletar(self.pasta))[0]
        self.assertEqual(ag['execucoes'], 2)
        self.assertAlmostEqual(ag['acuracia_media'], 0.625)
        self.assertEqual((ag['acuracia_min'], ag['acuracia_max']), (0.5, 0.75))

    def test_conjuntos_de_questoes_diferentes_nao_se_misturam(self):
        escrever(self.pasta, 'few_shot', 'gsm8k', 'a', [True], exemplos=10, limite=10)
        escrever(self.pasta, 'few_shot', 'gsm8k', 'b', [True], exemplos=5, limite=40)
        self.assertEqual(len(cc.agregar(cc.coletar(self.pasta))), 2)
        self.assertEqual(len(cc.coletar(self.pasta, limite=40)), 1)
        self.assertEqual(len(cc.coletar(self.pasta, exemplos=10)), 1)

    def test_ignora_progresso_revisoes_e_em_andamento(self):
        escrever(self.pasta, 'few_shot', 'gsm8k', 'ok', [True])
        escrever(self.pasta, 'few_shot', 'gsm8k', 'parcial', [True], status='em_andamento')
        (self.pasta / 'few_shot' / 'gsm8k' / 'x' / 'ok.progresso.json').write_text('{}', encoding='utf-8')
        (self.pasta / 'few_shot' / 'gsm8k' / 'x' / 'ok.revisoes.json').write_text('[]', encoding='utf-8')
        self.assertEqual([l['id_execucao'] for l in cc.coletar(self.pasta)], ['ok'])

    def test_arquivo_ilegivel_nao_derruba(self):
        escrever(self.pasta, 'few_shot', 'gsm8k', 'ok', [True])
        (self.pasta / 'few_shot' / 'gsm8k' / 'x' / 'quebrado.json').write_text('{nao e json', encoding='utf-8')
        self.assertEqual(len(cc.coletar(self.pasta)), 1)


class TestFalhasERecuperacao(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pasta = Path(self.tmp.name)

    def test_execucao_com_falha_entra_e_mostra_as_falhas(self):
        escrever(self.pasta, 'self_consistency', 'gsm8k', 's', [True, False, None, True], amostras=3,
                 falhas=(2,), status='concluido_com_falhas')
        [l] = cc.coletar(self.pasta)
        self.assertEqual((l['falhas_tecnicas'], l['avaliadas']), (1, 3))
        self.assertAlmostEqual(l['acuracia'], 2 / 3)
        self.assertIn('1 falha', cc._obs(l))

    def test_recuperacao_substitui_a_original_nas_duas_ferramentas(self):
        orig = escrever(self.pasta, 'self_consistency', 'censo', 'self_consistency_censo_08112026_1',
                        [True, None, False], amostras=3, falhas=(1,))
        rec = escrever(self.pasta, 'self_consistency', 'censo', 'self_consistency_censo_08112026_1_recuperacao',
                       [True, False, False], amostras=3, recuperacao_de=f'C:\\\\proj\\\\resultados\\\\{orig.name}')
        linhas = cc.coletar(self.pasta)
        self.assertEqual([l['id_execucao'] for l in linhas], ['self_consistency_censo_08112026_1_recuperacao'])
        self.assertEqual(linhas[0]['falhas_tecnicas'], 0)
        # a comparação das técnicas também escolhe a recuperação, mesmo com a mesma data no nome
        escolhidas, avisos = ct.escolher_execucoes('censo', pasta=self.pasta)
        self.assertEqual(escolhidas['self_consistency'].name, rec.name)
        self.assertTrue(any('recuperação' in a for a in avisos))

    def test_recuperacao_com_barra_normal(self):
        orig = escrever(self.pasta, 'few_shot', 'gsm8k', 'a', [True])
        escrever(self.pasta, 'few_shot', 'gsm8k', 'a_recuperacao', [True], recuperacao_de=f'resultados/x/{orig.name}')
        self.assertEqual([Path(a).stem for a in cc.listar_arquivos(self.pasta)], ['a_recuperacao'])

    def test_execucao_sem_nenhuma_resposta_e_suspeita_e_fica_fora_da_media(self):
        escrever(self.pasta, 'self_consistency', 'gsm8k', 'ruim', [False, False], amostras=3, sem_extracao=True)
        escrever(self.pasta, 'self_consistency', 'gsm8k', 'boa', [True, False], amostras=3)
        ag = cc.agregar(cc.coletar(self.pasta))[0]
        self.assertEqual(ag['execucoes_suspeitas'], 1)
        self.assertAlmostEqual(ag['acuracia_media'], 0.5)   # só a boa
        self.assertEqual(ag['com_acuracia'], 1)

    def test_censo_sem_revisao_fica_pendente_e_com_revisao_fecha(self):
        arq = escrever(self.pasta, 'self_consistency', 'censo', 'c', [True, None, False], amostras=3)
        [l] = cc.coletar(self.pasta, revisor='layla')
        self.assertIsNone(l['acuracia'])
        self.assertEqual(l['pendentes'], 1)
        arq.with_name('c.revisoes.json').write_text(json.dumps(
            [{'id': 'q1', 'revisor': 'layla', 'acertou': True}]), encoding='utf-8')
        [l] = cc.coletar(self.pasta, revisor='layla')
        self.assertAlmostEqual(l['acuracia'], 2 / 3)


class TestMaquinasERelatorio(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pasta = Path(self.tmp.name)

    def test_maquina_por_prefixo_e_campo_gravado(self):
        escrever(self.pasta, 'few_shot', 'gsm8k', 'few_shot_gsm8k_01112026_a', [True])
        escrever(self.pasta, 'few_shot', 'gsm8k', 'few_shot_gsm8k_02112026_b', [True])
        escrever(self.pasta, 'few_shot', 'gsm8k', 'few_shot_gsm8k_03112026_c', [True], ambiente={'maquina': 'pc9'})
        mapa = {'few_shot_gsm8k_01112026': 'pc1', 'few_shot_gsm8k_0': 'pcX', 'few_shot_gsm8k_03112026_c': 'pc2'}
        por_id = {l['id_execucao']: l['maquina'] for l in cc.coletar(self.pasta, mapa=mapa)}
        self.assertEqual(por_id['few_shot_gsm8k_01112026_a'], 'pc1')        # maior prefixo vence
        self.assertEqual(por_id['few_shot_gsm8k_02112026_b'], 'pcX')
        self.assertEqual(por_id['few_shot_gsm8k_03112026_c'], 'pc9')        # campo gravado vence o mapa

    def test_sem_mapa_diz_nao_informada(self):
        escrever(self.pasta, 'few_shot', 'gsm8k', 'a', [True])
        self.assertEqual(cc.coletar(self.pasta)[0]['maquina'], cc.SEM_MAQUINA)

    def test_modelo_de_maquinas_lista_as_execucoes(self):
        escrever(self.pasta, 'few_shot', 'gsm8k', 'a', [True])
        escrever(self.pasta, 'few_shot', 'gsm8k', 'b', [True])
        modelo = cc.modelo_de_maquinas(cc.listar_arquivos(self.pasta))
        self.assertEqual(modelo['execucoes'], {'a': '', 'b': ''})
        self.assertIn('periodos', modelo)

    def test_main_nao_sobrescreve_arquivo_de_maquinas(self):
        escrever(self.pasta, 'few_shot', 'gsm8k', 'a', [True])
        self.assertEqual(cc.main(['--pasta', str(self.pasta), '--modelo-maquinas']), 0)
        destino = self.pasta / 'metricas' / 'maquinas.json'
        destino.write_text('{"a": "pc1"}', encoding='utf-8')
        self.assertEqual(cc.main(['--pasta', str(self.pasta), '--modelo-maquinas']), 1)
        self.assertEqual(json.loads(destino.read_text(encoding='utf-8')), {'a': 'pc1'})

    def test_relatorio_completo_tokens_e_maquinas(self):
        for tecnica, kw in (('few_shot', {}), ('chain_of_thought', {}),
                            ('self_consistency', {'temp': 0.5, 'amostras': 3})):
            escrever(self.pasta, tecnica, 'gsm8k', f'{tecnica}_1200', [True, False, True, True], tokens=1200, **kw)
            escrever(self.pasta, tecnica, 'gsm8k', f'{tecnica}_2400', [True, True, True, True], tokens=2400, **kw)
        mapa = self.pasta / 'maq.json'
        mapa.write_text(json.dumps({'few_shot_1200': 'pc1', 'few_shot_2400': 'pc2'}), encoding='utf-8')
        saida = self.pasta / 'saida'
        linhas, ags, texto = cc.gerar(self.pasta, saida, maquinas=mapa, detalhado=True)
        self.assertEqual(len(linhas), 6)
        self.assertIn('Técnica × tokens', texto)
        self.assertIn('1200 tokens', texto)
        self.assertIn('2400 tokens', texto)
        self.assertIn('Todas as execuções', texto)
        self.assertIn('4 execuções sem máquina informada', texto)
        for nome in ('configuracoes.md', 'configuracoes.json', 'execucoes.csv'):
            self.assertTrue((saida / nome).exists(), nome)
        matriz = cc.matriz_tokens(ags)
        self.assertAlmostEqual(matriz[('few_shot', 0.0, None)][1200][0], 0.75)
        self.assertAlmostEqual(matriz[('few_shot', 0.0, None)][2400][0], 1.0)
        self.assertIn('Acurácia', (saida / 'execucoes.csv').read_text(encoding='utf-8-sig').replace('acuracia', 'Acurácia'))

    def test_mesma_configuracao_em_duas_maquinas(self):
        escrever(self.pasta, 'self_consistency', 'gsm8k', 'em_pc1', [True, False], amostras=3, temp=0.3)
        escrever(self.pasta, 'self_consistency', 'gsm8k', 'em_pc2', [True, True], amostras=3, temp=0.3)
        mapa = {'em_pc1': 'pc1', 'em_pc2': 'pc2'}
        ags = cc.agregar(cc.coletar(self.pasta, mapa=mapa))
        grupos = cc.entre_maquinas(ags)
        self.assertEqual(len(grupos), 1)
        texto = cc.para_markdown(cc.coletar(self.pasta, mapa=mapa), ags)
        self.assertIn('Mesma configuração em máquinas diferentes', texto)
        self.assertIn('pc1: acurácia / tempo (s)', texto)

    def test_originais_nao_sao_alterados(self):
        arq = escrever(self.pasta, 'few_shot', 'gsm8k', 'a', [True, False])
        antes = arq.read_bytes()
        cc.gerar(self.pasta, self.pasta / 'saida')
        self.assertEqual(arq.read_bytes(), antes)


class TestRecuperarFalhasUsaOsParametrosDoArquivo(unittest.TestCase):
    """A 08/11 foi rodada com 0,7 / 2400 / 3 amostras; o código pode estar com outros valores."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.antigo = os.getcwd()
        os.chdir(self.tmp.name)
        self.addCleanup(os.chdir, self.antigo)

    def arquivo(self, **params):
        base = {'temperatura': 0.7, 'maximo_tokens_resposta': 2400, 'n_amostras': 3,
                'limite': None, 'quantidade_exemplos': 6}
        base.update(params)
        dados = {'id_execucao': 'self_consistency_censo_08112026_1', 'tecnica': 'self_consistency',
                 'dataset': 'censo', 'status': 'concluido', 'parametros': base,
                 'resultados': [{'id': 'q1', 'falha_tecnica': True, 'amostras': [
                     {'amostra': 1, 'falha_tecnica': False, 'resposta_completa': 'x'}]},
                     {'id': 'q2', 'falha_tecnica': False}]}
        caminho = Path('original.json')
        caminho.write_text(json.dumps(dados), encoding='utf-8')
        return caminho

    def test_aplica_os_parametros_do_arquivo_e_restaura_depois(self):
        vistos = {}

        def falso(dataset, limite, quantidade, retomar=None):
            vistos.update(t=esc.TEMPERATURE, n=esc.N_AMOSTRAS, tokens=esc.NUM_PREDICT, retomar=retomar)
            return 'ok'
        guardados = (esc.TEMPERATURE, esc.N_AMOSTRAS, esc.NUM_PREDICT)
        with mock.patch.object(esc, 'executar_dataset', falso):
            self.assertEqual(esc.recuperar_falhas(self.arquivo()), 'ok')
        self.assertEqual((vistos['t'], vistos['n'], vistos['tokens']), (0.7, 3, 2400))
        self.assertEqual((esc.TEMPERATURE, esc.N_AMOSTRAS, esc.NUM_PREDICT), guardados)   # restaurado
        progresso = json.loads(Path(vistos['retomar']).read_text(encoding='utf-8'))
        self.assertEqual(list(progresso['amostras_em_andamento']), ['q1'])
        self.assertEqual(progresso['recuperacao_de'], 'original.json')

    def test_restaura_mesmo_se_a_execucao_falhar(self):
        guardados = (esc.TEMPERATURE, esc.N_AMOSTRAS, esc.NUM_PREDICT)
        with mock.patch.object(esc, 'executar_dataset', side_effect=RuntimeError('boom')):
            with self.assertRaises(RuntimeError):
                esc.recuperar_falhas(self.arquivo())
        self.assertEqual((esc.TEMPERATURE, esc.N_AMOSTRAS, esc.NUM_PREDICT), guardados)

    def test_arquivo_sem_parametro_obrigatorio_e_recusado(self):
        with self.assertRaises(ValueError):
            esc.recuperar_falhas(self.arquivo(temperatura=None))

    def test_mensagem_de_parametros_diferentes_lista_o_que_mudou(self):
        d = esc.diferencas_parametros({'igual': 1, 'temperatura': 0.7, 'protocolo': {'v': 1}},
                                      {'igual': 1, 'temperatura': 0.3, 'protocolo': {'v': 2}})
        texto = ' | '.join(d)
        self.assertIn('temperatura', texto)
        self.assertIn('protocolo', texto)
        self.assertNotIn('igual', texto)
        self.assertEqual(esc.diferencas_parametros({'a': 1}, {'a': 1}), [])


if __name__ == '__main__':
    unittest.main()
