import json
import os
import sys
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, RAIZ)

from codigo import revisao_humana as rh  # noqa: E402


class TestWilson(unittest.TestCase):
    def test_valores_conhecidos(self):
        lo, hi = rh.intervalo_wilson(20, 50)
        self.assertAlmostEqual(lo, 0.2764, places=3)
        self.assertAlmostEqual(hi, 0.5381, places=3)

    def test_extremos(self):
        self.assertEqual(rh.intervalo_wilson(0, 0), (0.0, 0.0))
        lo, hi = rh.intervalo_wilson(0, 44)
        self.assertAlmostEqual(lo, 0.0)
        self.assertGreater(hi, 0.0)
        lo, hi = rh.intervalo_wilson(44, 44)
        self.assertAlmostEqual(hi, 1.0)

    def test_largura_com_n_pequeno(self):
        lo, hi = rh.intervalo_wilson(25, 50)
        self.assertGreater(hi - lo, 0.25)  # ~±14 pp


class TestMcNemar(unittest.TestCase):
    def test_sem_discordancia(self):
        self.assertEqual(rh.mcnemar_exato(0, 0), 1.0)

    def test_simetrico(self):
        self.assertEqual(rh.mcnemar_exato(3, 9), rh.mcnemar_exato(9, 3))

    def test_valor_conhecido(self):
        self.assertAlmostEqual(rh.mcnemar_exato(2, 10), 0.03857, places=4)

    def test_empate_perfeito(self):
        self.assertEqual(rh.mcnemar_exato(5, 5), 1.0)

    def test_pareado_usa_so_ids_em_comum(self):
        a = {'q1': True, 'q2': False, 'q3': True, 'extra': True}
        b = {'q1': False, 'q2': False, 'q3': True}
        r = rh.comparar_pareado(a, b)
        self.assertEqual((r['n'], r['so_a'], r['so_b']), (3, 1, 0))


class TestKappa(unittest.TestCase):
    def test_concordancia_total(self):
        a = {'1': True, '2': False, '3': True, '4': False}
        self.assertAlmostEqual(rh.kappa_cohen(a, dict(a))['kappa'], 1.0)

    def test_acaso(self):
        a = {'1': True, '2': True, '3': False, '4': False}
        b = {'1': True, '2': False, '3': True, '4': False}
        self.assertAlmostEqual(rh.kappa_cohen(a, b)['kappa'], 0.0)

    def test_discordancia_total_e_negativo(self):
        a = {'1': True, '2': False}
        b = {'1': False, '2': True}
        self.assertLess(rh.kappa_cohen(a, b)['kappa'], 0)

    def test_sem_questoes_em_comum(self):
        self.assertIsNone(rh.kappa_cohen({'a': True}, {'b': True})['kappa'])


QUESTOES = [
    {'id': 'q1', 'acertou': True},
    {'id': 'q2', 'acertou': False},
    {'id': 'q3', 'acertou': None, 'revisao_necessaria': True, 'tipo_resultado': 'avaliacao_pendente'},
    {'id': 'q4', 'acertou': None, 'revisao_necessaria': True, 'tipo_resultado': 'avaliacao_pendente'},
]


class TestResumo(unittest.TestCase):
    def test_limites_antes_da_revisao(self):
        r = rh.resumo(QUESTOES)
        self.assertEqual((r['certos_automaticos'], r['pendentes']), (1, 2))
        self.assertAlmostEqual(r['minimo'], 0.25)
        self.assertAlmostEqual(r['maximo'], 0.75)

    def test_pendentes(self):
        self.assertEqual([q['id'] for q in rh.pendentes(QUESTOES)], ['q3', 'q4'])

    def test_revisao_parcial_nao_fecha_acuracia(self):
        revs = [{'id': 'q3', 'revisor': 'layla', 'acertou': True, 'criterio': 'x'}]
        r = rh.resumo(QUESTOES, revs, 'layla')
        self.assertEqual(r['faltam_revisar'], 1)
        self.assertNotIn('acuracia_final', r)

    def test_revisao_completa(self):
        revs = [{'id': 'q3', 'revisor': 'layla', 'acertou': True, 'criterio': 'x'},
                {'id': 'q4', 'revisor': 'layla', 'acertou': False, 'criterio': 'y'}]
        r = rh.resumo(QUESTOES, revs, 'layla')
        self.assertAlmostEqual(r['acuracia_final'], 0.5)
        self.assertIn('ic95', r)

    def test_revisao_de_outro_revisor_nao_conta(self):
        revs = [{'id': 'q3', 'revisor': 'prof', 'acertou': True, 'criterio': 'x'}]
        self.assertEqual(rh.resumo(QUESTOES, revs, 'layla')['faltam_revisar'], 2)

    def test_arquivo_original_nao_e_alterado(self):
        with tempfile.TemporaryDirectory() as pasta:
            arq = os.path.join(pasta, 'r.json')
            texto = json.dumps({'resultados': QUESTOES})
            with open(arq, 'w') as f:
                f.write(texto)
            rh.caminho_revisoes(arq).write_text('[]')
            self.assertTrue(str(rh.caminho_revisoes(arq)).endswith('r.revisoes.json'))
            with open(arq) as f:
                self.assertEqual(f.read(), texto)


class TestParecerDoJuiz(unittest.TestCase):
    def test_usa_o_campo_quando_existe(self):
        self.assertEqual(rh.parecer_do_juiz({'parecer_llm': 'CORRETA', 'motivo': 'x'}), 'CORRETA')

    def test_le_do_motivo_nas_execucoes_antigas(self):
        q = {'motivo': 'Parecer do juiz: INCORRETA. A faixa de 4 a 5 anos é maior.'}
        self.assertEqual(rh.parecer_do_juiz(q), 'INCORRETA')

    def test_sem_parecer_devolve_none(self):
        self.assertIsNone(rh.parecer_do_juiz({'motivo': 'Sem avaliador.'}))
        self.assertIsNone(rh.parecer_do_juiz({}))

    def test_final_json_traz_o_parecer_lido_do_motivo(self):
        with tempfile.TemporaryDirectory() as pasta:
            arq = os.path.join(pasta, 'e.json')
            with open(arq, 'w', encoding='utf-8') as f:
                json.dump({'dataset': 'censo', 'status': 'concluido', 'resultados': [
                    {'id': 'a', 'acertou': None, 'revisao_necessaria': True,
                     'motivo': 'Parecer do juiz: CORRETA. ok'}]}, f)
            final = rh.montar_resultado_final(arq, 'layla', {})
            self.assertEqual(final['resultados'][0]['parecer_llm'], 'CORRETA')


if __name__ == '__main__':
    unittest.main()


class TestPerguntaNaRevisao(unittest.TestCase):
    def test_pergunta_vem_do_dataset_pelo_id(self):
        import json, tempfile
        from pathlib import Path
        from codigo import revisao_humana as rh
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / 'ds.json'
            caminho.write_text(json.dumps([{'id': 'a1', 'pergunta': 'Quantas escolas?'}]), encoding='utf-8')
            enunciados = rh.carregar_enunciados(caminho)
            self.assertEqual(rh.pergunta_da_questao({'id': 'a1'}, enunciados), 'Quantas escolas?')
            self.assertEqual(rh.pergunta_da_questao({'id': 'x', 'pergunta': 'própria'}, enunciados), 'própria')
            self.assertEqual(rh.pergunta_da_questao({'id': 'zz'}, enunciados), '')
            self.assertEqual(rh.carregar_enunciados(Path(pasta) / 'nao_existe.json'), {})


class TestExportarResultadoFinal(unittest.TestCase):
    def preparar(self, pasta):
        import json
        from pathlib import Path
        qs = [{'id': 'a', 'acertou': True, 'metodo_avaliacao': 'rubrica_objetiva_censo', 'motivo': 'ok'},
              {'id': 'b', 'acertou': False, 'metodo_avaliacao': 'rubrica_objetiva_censo'},
              {'id': 'c', 'acertou': None, 'revisao_necessaria': True, 'parecer_llm': 'CORRETA'},
              {'id': 'd', 'acertou': None, 'revisao_necessaria': True},
              {'id': 'e', 'acertou': None, 'falha_tecnica': True, 'motivo_falha_tecnica': 'timeout'}]
        arq = Path(pasta) / 'x.json'
        arq.write_text(json.dumps({'tecnica': 'self_consistency', 'dataset': 'censo', 'resultados': qs}),
                       encoding='utf-8')
        return arq

    def test_junta_rubrica_e_revisao_sem_alterar_original(self):
        import json, tempfile
        from pathlib import Path
        from codigo import revisao_humana as rh
        with tempfile.TemporaryDirectory() as pasta:
            arq = self.preparar(pasta)
            antes = arq.read_bytes()
            rh.caminho_revisoes(arq).write_text(json.dumps([
                {'id': 'c', 'revisor': 'layla', 'acertou': True, 'criterio': 'tem os totais'},
                {'id': 'd', 'revisor': 'outro', 'acertou': True, 'criterio': 'x'}]), encoding='utf-8')
            destino, final = rh.exportar(arq, 'layla')
            self.assertEqual(arq.read_bytes(), antes)
            self.assertTrue(destino.name.endswith('.final.json'))
            por_id = {x['id']: x for x in final['resultados']}
            self.assertEqual(por_id['c']['veredito_final'], True)
            self.assertEqual(por_id['c']['origem_veredito'], 'revisao_humana')
            self.assertEqual(por_id['c']['criterio'], 'tem os totais')
            self.assertIsNone(por_id['d']['veredito_final'])      # revisão de outro revisor não conta
            self.assertEqual(por_id['d']['origem_veredito'], 'pendente')
            self.assertEqual(por_id['e']['origem_veredito'], 'falha_tecnica')
            r = final['resumo']
            self.assertEqual((r['total_questoes'], r['falhas_tecnicas'], r['acertos'], r['erros'], r['pendentes']),
                             (5, 1, 2, 1, 1))
            self.assertFalse(r['completo'])
            self.assertIsNone(r['acuracia'])
            self.assertEqual(json.loads(destino.read_text(encoding='utf-8'))['revisor'], 'layla')

    def test_completo_calcula_acuracia(self):
        import json, tempfile
        from codigo import revisao_humana as rh
        with tempfile.TemporaryDirectory() as pasta:
            arq = self.preparar(pasta)
            rh.caminho_revisoes(arq).write_text(json.dumps([
                {'id': 'c', 'revisor': 'layla', 'acertou': True, 'criterio': ''},
                {'id': 'd', 'revisor': 'layla', 'acertou': False, 'criterio': ''}]), encoding='utf-8')
            _, final = rh.exportar(arq, 'layla')
            self.assertTrue(final['resumo']['completo'])
            self.assertAlmostEqual(final['resumo']['acuracia'], 2 / 4)
            self.assertIsNotNone(final['resumo']['ic95_wilson'])


class TestPastaInteira(unittest.TestCase):
    """Comandos revisar-pasta e exportar-pasta e o progresso da pasta."""

    def montar(self, pasta):
        from pathlib import Path
        base = Path(pasta)
        (base / 'sub').mkdir()

        def gravar(caminho, dados):
            caminho.write_text(json.dumps(dados), encoding='utf-8')

        def censo(ids, status='concluido'):
            return {'dataset': 'censo', 'tecnica': 'self_consistency', 'status': status,
                    'resultados': [{'id': i, 'acertou': None, 'revisao_necessaria': True,
                                    'gabarito': 'g', 'resposta': 'r'} for i in ids]}
        gravar(base / 'um.json', censo(['a', 'b']))
        gravar(base / 'sub' / 'dois.json', censo(['c']))
        gravar(base / 'andamento.json', censo(['d'], status='em_andamento'))
        gravar(base / 'x.progresso.json', censo(['e']))
        gravar(base / 'gsm.json', {'dataset': 'gsm8k', 'status': 'concluido', 'resultados': []})
        gravar(base / 'um.revisoes.json', [])
        gravar(base / 'um.final.json', {'dataset': 'censo', 'status': 'concluido', 'resultados': []})
        gravar(base / 'quebrado.json', ['x'])
        return base

    def rodar(self, argv, entradas):
        import io
        from unittest import mock
        it = iter(entradas)
        with mock.patch('builtins.input', lambda *_: next(it)), \
             mock.patch('sys.stdout', new=io.StringIO()) as saida:
            rh.main(argv)
        return saida.getvalue()

    def test_arquivos_da_pasta_ignora_derivados_outros_datasets_e_incompletos(self):
        with tempfile.TemporaryDirectory() as pasta:
            base = self.montar(pasta)
            import io
            from unittest import mock
            with mock.patch('sys.stdout', new=io.StringIO()):
                nomes = sorted(p.name for p in rh.arquivos_da_pasta(base))
            self.assertEqual(nomes, ['dois.json', 'um.json'])

    def test_pasta_inexistente_da_erro_claro(self):
        with self.assertRaises(NotADirectoryError):
            rh.arquivos_da_pasta('/pasta/que/nao/existe')

    def test_revisar_pasta_revisa_todos_e_cada_um_ganha_seu_arquivo(self):
        with tempfile.TemporaryDirectory() as pasta:
            base = self.montar(pasta)
            # ordem alfabética dos caminhos: sub/dois.json (c), depois um.json (a, b)
            self.rodar(['revisar-pasta', str(base), '--revisor', 'layla',
                        '--questoes', str(base / 'nao.json')],
                       ['c', 'ok', 'c', 'ok2', 'e', 'ok3'])
            um = rh.veredito_revisor(rh.carregar_revisoes(base / 'um.json'), 'layla')
            dois = rh.veredito_revisor(rh.carregar_revisoes(base / 'sub' / 'dois.json'), 'layla')
            self.assertEqual(um, {'a': True, 'b': False})
            self.assertEqual(dois, {'c': True})
            self.assertFalse((base / 'gsm.revisoes.json').exists())
            self.assertFalse((base / 'andamento.revisoes.json').exists())

    def test_sair_com_s_preserva_o_que_foi_feito_e_para_a_pasta(self):
        with tempfile.TemporaryDirectory() as pasta:
            base = self.montar(pasta)
            texto = self.rodar(['revisar-pasta', str(base), '--revisor', 'layla',
                                '--questoes', str(base / 'nao.json')],
                               ['c', 'ok', 's'])
            self.assertIn('interrompida', texto)
            self.assertEqual(rh.veredito_revisor(
                rh.carregar_revisoes(base / 'sub' / 'dois.json'), 'layla'), {'c': True})
            self.assertEqual(rh.carregar_revisoes(base / 'um.json'), [])

    def test_segunda_rodada_continua_de_onde_parou_sem_repetir(self):
        with tempfile.TemporaryDirectory() as pasta:
            base = self.montar(pasta)
            args = ['revisar-pasta', str(base), '--revisor', 'layla',
                    '--questoes', str(base / 'nao.json')]
            self.rodar(args, ['c', 'ok', 's'])
            # só 2 perguntas restam: a e b (a de 'c' já foi feita)
            self.rodar(args, ['e', 'ok2', 'c', 'ok3'])
            self.assertEqual(len(rh.carregar_revisoes(base / 'sub' / 'dois.json')), 1)
            self.assertEqual(len(rh.carregar_revisoes(base / 'um.json')), 2)
            # terceira rodada: nada a revisar, não pede nenhuma entrada
            texto = self.rodar(args, [])
            self.assertIn('concluída: 3/3', texto)

    def test_progresso_da_pasta_soma_os_arquivos_e_avanca(self):
        with tempfile.TemporaryDirectory() as pasta:
            base = self.montar(pasta)
            texto = self.rodar(['revisar-pasta', str(base), '--revisor', 'layla',
                                '--questoes', str(base / 'nao.json')],
                               ['c', 'ok', 'c', 'ok', 's'])
            self.assertIn('3 questões para revisão | 0 revisadas | 3 faltando', texto)
            self.assertIn('Pasta: 1/3 | Faltam: 2', texto)
            self.assertIn('Pasta: 2/3 | Faltam: 1', texto)

    def test_revisor_diferente_comeca_do_zero(self):
        with tempfile.TemporaryDirectory() as pasta:
            base = self.montar(pasta)
            args = ['revisar-pasta', str(base), '--questoes', str(base / 'nao.json')]
            self.rodar(args + ['--revisor', 'layla'], ['c', 'ok', 'c', 'ok', 'c', 'ok'])
            texto = self.rodar(args + ['--revisor', 'prof'], ['s'])
            self.assertIn('0 revisadas | 3 faltando', texto)

    def test_contar_pendentes_arquivo(self):
        with tempfile.TemporaryDirectory() as pasta:
            base = self.montar(pasta)
            self.assertEqual(rh.contar_pendentes_arquivo(base / 'um.json', 'layla'), (2, 0))
            self.rodar(['revisar', str(base / 'um.json'), '--revisor', 'layla',
                        '--questoes', str(base / 'nao.json')], ['c', 'ok', 's'])
            self.assertEqual(rh.contar_pendentes_arquivo(base / 'um.json', 'layla'), (2, 1))

    def test_exportar_pasta_cria_um_final_por_execucao_sem_tocar_no_original(self):
        with tempfile.TemporaryDirectory() as pasta:
            base = self.montar(pasta)
            original = (base / 'um.json').read_bytes()
            self.rodar(['revisar-pasta', str(base), '--revisor', 'layla',
                        '--questoes', str(base / 'nao.json')],
                       ['c', 'ok', 'e', 'ok', 'c', 'ok'])
            self.rodar(['exportar-pasta', str(base), '--revisor', 'layla',
                        '--questoes', str(base / 'nao.json')], [])
            final_um = json.loads((base / 'um.final.json').read_text(encoding='utf-8'))
            final_dois = json.loads((base / 'sub' / 'dois.final.json').read_text(encoding='utf-8'))
            self.assertEqual(final_um['resumo']['acuracia'], 0.5)
            self.assertEqual(final_um['resumo']['pendentes'], 0)
            self.assertEqual(final_dois['resumo']['acuracia'], 1.0)
            self.assertFalse((base / 'gsm.final.json').exists())
            self.assertEqual((base / 'um.json').read_bytes(), original)

    def test_revisar_pasta_gera_os_finais_ao_concluir(self):
        with tempfile.TemporaryDirectory() as pasta:
            base = self.montar(pasta)
            self.rodar(['revisar-pasta', str(base), '--revisor', 'layla',
                        '--questoes', str(base / 'nao.json')],
                       ['c', 'ok', 'e', 'ok', 'c', 'ok'])
            self.assertTrue((base / 'um.final.json').exists())
            self.assertTrue((base / 'sub' / 'dois.final.json').exists())
            final = json.loads((base / 'um.final.json').read_text(encoding='utf-8'))
            self.assertEqual(final['resumo']['acuracia'], 0.5)

    def test_revisar_pasta_interrompida_gera_final_parcial_sem_acuracia(self):
        with tempfile.TemporaryDirectory() as pasta:
            base = self.montar(pasta)
            (base / 'um.final.json').unlink()
            self.rodar(['revisar-pasta', str(base), '--revisor', 'layla',
                        '--questoes', str(base / 'nao.json')], ['c', 'ok', 's'])
            parcial = json.loads((base / 'sub' / 'dois.final.json').read_text(encoding='utf-8'))
            self.assertTrue(parcial['resumo']['completo'])      # a única questão de dois.json foi revisada
            parcial_um = json.loads((base / 'um.final.json').read_text(encoding='utf-8'))
            self.assertEqual(parcial_um['resumo']['pendentes'], 2)   # um.json: nada revisado ainda
            self.assertFalse(parcial_um['resumo']['completo'])
            self.assertIsNone(parcial_um['resumo']['acuracia'])      # nunca declara acurácia incompleta

    def test_final_parcial_nao_declara_acuracia(self):
        with tempfile.TemporaryDirectory() as pasta:
            base = self.montar(pasta)
            self.rodar(['revisar', str(base / 'um.json'), '--revisor', 'layla',
                        '--questoes', str(base / 'nao.json')], ['c', 'ok', 's'])
            final = json.loads((base / 'um.final.json').read_text(encoding='utf-8'))
            self.assertEqual(final['resumo']['pendentes'], 1)
            self.assertFalse(final['resumo']['completo'])
            self.assertIsNone(final['resumo']['acuracia'])

    def test_exportar_pasta_sem_revisao_deixa_acuracia_vazia(self):
        with tempfile.TemporaryDirectory() as pasta:
            base = self.montar(pasta)
            self.rodar(['exportar-pasta', str(base), '--revisor', 'layla',
                        '--questoes', str(base / 'nao.json')], [])
            final = json.loads((base / 'um.final.json').read_text(encoding='utf-8'))
            self.assertIsNone(final['resumo']['acuracia'])
            self.assertEqual(final['resumo']['pendentes'], 2)


if __name__ == '__main__':
    unittest.main()
