"""Recuperação de falhas por pasta, com retomada e várias rodadas (sem Ollama)."""
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
except ImportError:
    sys.modules['tqdm'] = types.SimpleNamespace(tqdm=lambda itens, **_: itens)

from codigo.self_consistency import executar_self_consistency as esc

PARAMS = {'temperatura': 0.7, 'maximo_tokens_resposta': 2400, 'n_amostras': 3,
          'limite': 200, 'quantidade_exemplos': 10}


def escrever(raiz, nome, dataset='gsm8k', falhas=(1,), total=4, status='concluido', params=None,
             recuperacao_de=None, ambiente=None):
    pasta = Path(raiz) / 'resultados' / 'self_consistency' / dataset / 'limite_200_exemplos_10'
    pasta.mkdir(parents=True, exist_ok=True)
    resultados = [{'id': f'q{i}', 'falha_tecnica': i in falhas, 'acertou': None if i in falhas else True,
                   'amostras': [{'amostra': 1, 'falha_tecnica': False, 'resposta_completa': 'x'}]}
                  for i in range(total)]
    dados = {'id_execucao': nome, 'tecnica': 'self_consistency', 'dataset': dataset, 'status': status,
             'parametros': dict(params or PARAMS), 'resultados': resultados}
    if recuperacao_de:
        dados['recuperacao_de'] = recuperacao_de
    if ambiente:
        dados['ambiente'] = ambiente
    caminho = pasta / f'{nome}.json'
    caminho.write_text(json.dumps(dados), encoding='utf-8')
    return caminho


def executar_falso(restantes_por_rodada=None):
    """Imita executar_dataset: lê o progresso e grava o arquivo final da recuperação."""
    chamadas = []
    restantes = list(restantes_por_rodada or [0])

    def falso(dataset, limite, quantidade, retomar=None):
        progresso = Path(retomar)
        dados = json.loads(progresso.read_text(encoding='utf-8'))
        faltam = restantes.pop(0) if len(restantes) > 1 else restantes[0]
        for i, r in enumerate(dados['resultados']):
            r['falha_tecnica'] = i < faltam and r.get('falha_tecnica', False)
            if not r['falha_tecnica']:
                r['acertou'] = True
        dados['status'] = 'concluido'
        final = progresso.with_name(progresso.name.replace('.progresso.json', '.json'))
        final.write_text(json.dumps(dados), encoding='utf-8')
        progresso.unlink()
        chamadas.append((dataset, esc.TEMPERATURE, esc.N_AMOSTRAS, esc.NUM_PREDICT, progresso.name))
        return dados
    return falso, chamadas


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.antigo = os.getcwd()
        os.chdir(self.tmp.name)
        self.addCleanup(os.chdir, self.antigo)
        self.raiz = Path(self.tmp.name)
        self.pasta = Path('resultados') / 'self_consistency'


class TestPlano(Base):
    def test_lista_so_o_que_tem_falha_e_ainda_nao_foi_recuperado(self):
        escrever(self.raiz, 'com_falha_a')
        escrever(self.raiz, 'sem_falha', falhas=())
        orig = escrever(self.raiz, 'ja_recuperada')
        escrever(self.raiz, 'ja_recuperada_recuperacao', falhas=(), recuperacao_de=str(orig))
        escrever(self.raiz, 'em_andamento', status='em_andamento')
        (self.raiz / self.pasta / 'gsm8k' / 'limite_200_exemplos_10' / 'com_falha_a.revisoes.json').write_text('[]')
        plano, ignorados = esc.listar_para_recuperar(self.pasta)
        self.assertEqual([i['arquivo'].stem for i in plano], ['com_falha_a'])
        self.assertEqual(ignorados, [])

    def test_recuperacao_que_ainda_tem_falha_entra_no_plano_e_a_original_sai(self):
        orig = escrever(self.raiz, 'x')
        escrever(self.raiz, 'x_recuperacao', falhas=(2,), recuperacao_de=str(orig))
        plano, _ = esc.listar_para_recuperar(self.pasta)
        self.assertEqual([i['arquivo'].stem for i in plano], ['x_recuperacao'])

    def test_execucao_toda_falha_e_ignorada_a_menos_que_peca(self):
        escrever(self.raiz, 'perdida', falhas=(0, 1, 2, 3))
        plano, ignorados = esc.listar_para_recuperar(self.pasta)
        self.assertEqual((plano, len(ignorados)), ([], 1))
        plano, ignorados = esc.listar_para_recuperar(self.pasta, incluir_totais=True)
        self.assertEqual((len(plano), ignorados), (1, []))

    def test_simular_nao_executa_nada(self):
        escrever(self.raiz, 'a')
        with mock.patch.object(esc, 'executar_dataset') as ex:
            resumo = esc.recuperar_pasta(self.pasta, simular=True)
        ex.assert_not_called()
        self.assertEqual(len(resumo['plano']), 1)
        self.assertEqual([p.name for p in (self.raiz / self.pasta).rglob('*recuperacao*')], [])


class TestExecucao(Base):
    def test_recupera_todas_com_os_parametros_de_cada_arquivo(self):
        escrever(self.raiz, 'a', params=dict(PARAMS, temperatura=0.3, n_amostras=5))
        escrever(self.raiz, 'b', dataset='aqua_rat')
        falso, chamadas = executar_falso()
        with mock.patch.object(esc, 'executar_dataset', falso):
            resumo = esc.recuperar_pasta(self.pasta)
        self.assertEqual({(c[0], c[1], c[2], c[3]) for c in chamadas},
                         {('gsm8k', 0.3, 5, 2400), ('aqua_rat', 0.7, 3, 2400)})
        self.assertTrue(all(r['falhas_restantes'] == 0 and r['erro'] is None for r in resumo['resultado']))
        self.assertEqual(esc.listar_para_recuperar(self.pasta), ([], []))      # nada mais a fazer

    def test_repete_ate_zerar_as_falhas(self):
        escrever(self.raiz, 'a', falhas=(0, 1))
        falso, chamadas = executar_falso([1, 0])          # 1ª rodada deixa 1 falha, 2ª zera
        with mock.patch.object(esc, 'executar_dataset', falso):
            resumo = esc.recuperar_pasta(self.pasta, rodadas=3)
        self.assertEqual([c[4] for c in chamadas],
                         ['a_recuperacao.progresso.json', 'a_recuperacao_recuperacao.progresso.json'])
        self.assertEqual(resumo['resultado'][0]['falhas_restantes'], 0)

    def test_respeita_o_maximo_de_rodadas(self):
        escrever(self.raiz, 'a', falhas=(0,))
        falso, chamadas = executar_falso([1])              # nunca resolve
        with mock.patch.object(esc, 'executar_dataset', falso):
            resumo = esc.recuperar_pasta(self.pasta, rodadas=2)
        self.assertEqual(len(chamadas), 2)
        self.assertEqual(resumo['resultado'][0]['falhas_restantes'], 1)

    def test_erro_em_uma_nao_impede_as_outras(self):
        escrever(self.raiz, 'a')
        escrever(self.raiz, 'b', dataset='aqua_rat')
        falso, chamadas = executar_falso()

        def quebra_na_primeira(dataset, limite, quantidade, retomar=None):
            if dataset == 'gsm8k':
                raise RuntimeError('boom')
            return falso(dataset, limite, quantidade, retomar)
        with mock.patch.object(esc, 'executar_dataset', quebra_na_primeira):
            resumo = esc.recuperar_pasta(self.pasta)
        por_nome = {r['arquivo']: r for r in resumo['resultado']}
        self.assertIn('boom', por_nome['a.json']['erro'])
        self.assertIsNone(por_nome['b.json']['erro'])
        self.assertEqual(len(chamadas), 1)

    def test_progresso_interrompido_e_retomado_sem_recomecar(self):
        orig = escrever(self.raiz, 'a')
        prog = orig.with_name('a_recuperacao.progresso.json')
        prog.write_text(json.dumps({'marca': 'meio do caminho', 'resultados': [{'id': 'q1', 'falha_tecnica': True}]}))
        falso, chamadas = executar_falso()
        with mock.patch.object(esc, 'executar_dataset', falso):
            esc.recuperar_falhas(orig)
        self.assertEqual(len(chamadas), 1)
        self.assertTrue(orig.with_name('a_recuperacao.json').exists())

    def test_recuperacao_ja_concluida_nao_executa_de_novo(self):
        orig = escrever(self.raiz, 'a')
        escrever(self.raiz, 'a_recuperacao', falhas=(), recuperacao_de=str(orig))
        with mock.patch.object(esc, 'executar_dataset') as ex:
            dados = esc.recuperar_falhas(orig)
        ex.assert_not_called()
        self.assertEqual(dados['id_execucao'], 'a_recuperacao')

    def test_registra_ambiente_da_recuperacao_sem_trocar_o_da_original(self):
        orig = escrever(self.raiz, 'a', ambiente={'sistema': 'Linux', 'maquina': 'pc2'})
        vistos = {}

        def falso(dataset, limite, quantidade, retomar=None):
            vistos.update(json.loads(Path(retomar).read_text(encoding='utf-8')))
            raise KeyboardInterrupt
        with mock.patch.object(esc, 'executar_dataset', falso):
            with self.assertRaises(KeyboardInterrupt):
                esc.recuperar_falhas(orig)
        self.assertEqual(vistos['ambiente']['maquina'], 'pc2')
        self.assertIn('sistema', vistos['ambiente_recuperacao'])
        self.assertEqual(vistos['recuperacao_de'], str(orig))

    def test_recuperar_aceita_arquivo_ou_pasta(self):
        arq = escrever(self.raiz, 'a')
        with mock.patch.object(esc, 'recuperar_falhas', return_value='arquivo') as rf, \
                mock.patch.object(esc, 'recuperar_pasta', return_value='pasta') as rp:
            self.assertEqual(esc.recuperar(arq), 'arquivo')
            self.assertEqual(esc.recuperar(self.pasta, simular=True), 'pasta')
        rf.assert_called_once()
        rp.assert_called_once_with(self.pasta, simular=True)


if __name__ == '__main__':
    unittest.main()
