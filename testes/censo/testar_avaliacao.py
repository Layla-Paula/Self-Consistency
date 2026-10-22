import unittest
from codigo.avaliacao.avaliacao_censo import avaliar_censo

class TestarRubricasCenso(unittest.TestCase):
    def avaliar(self, numero, resposta, gabarito='referência disponível'):
        return avaliar_censo({'id': f'censo_2025_{numero:02}', 'pergunta':'Pergunta de teste',
                              'resposta_esperada':gabarito}, resposta)
    def test_total_escolas(self):
        self.assertTrue(self.avaliar(1, '178.766 escolas')['acertou'])
        self.assertFalse(self.avaliar(1, '178.765 escolas')['acertou'])
    def test_cinco_ufs(self):
        self.assertTrue(self.avaliar(22, 'SP, MG, BA, RJ e PR')['acertou'])
        self.assertFalse(self.avaliar(22, 'SP, MG, BA e RJ')['acertou'])
    def test_percentual_eja(self):
        self.assertTrue(self.avaliar(33, '2.252.069 matrículas, 4,89%')['acertou'])
        self.assertFalse(self.avaliar(33, '2.252.069 matrículas, 0,49%')['acertou'])
    def test_nao_declaradas(self):
        self.assertTrue(self.avaliar(40, '6.275.577 não declaradas')['acertou'])
        self.assertFalse(self.avaliar(40, '6.275.557 não declaradas')['acertou'])
    def test_28_inversao(self):
        self.assertFalse(self.avaliar(28, 'Anos Iniciais têm menos matrículas que os Anos Finais')['acertou'])
    def test_43_numero_malformado(self):
        self.assertFalse(self.avaliar(43, '496.8651 crianças')['acertou'])
    def test_44_incompleta(self):
        self.assertFalse(self.avaliar(44, 'O turno diurno concentra a maioria das matrículas')['acertou'])
    def test_veredito_inconclusivo_conta_erro(self):
        def juiz_inconclusivo(*args, **kwargs): return {'resposta':'{"veredito":"INCERTO"}', 'erro_detalhado':None}
        r=self.avaliar(25, 'Resposta plausível') if False else avaliar_censo(
            {'id':'censo_2025_25','pergunta':'Pergunta','resposta_esperada':'Gabarito'},
            'Resposta plausível', juiz_inconclusivo)
        self.assertIs(r['acertou'], False)
        self.assertFalse(r['revisao_necessaria'])

if __name__ == '__main__': unittest.main(verbosity=2)
