import unittest
from codigo.utils import extrair_resposta_numerica, comparar_numeros

class TestarNumeros(unittest.TestCase):
    def test_extracao(self):
        casos = {'Resposta final: 72':'72','Resposta: 72':'72', 'Resposta: 60':'60', 'Resposta: 9,96':'9,96', 'Resposta: 3x/4':'', 'Resposta final: 9,96':'9,96',
                 'Resposta final: -3':'-3', 'Resposta final: 178.766':'178.766',
                 '#### 42':'42', 'Resposta final: 3x/4':'', 'Resposta final: 12/5':'',
                 'Resposta final: x = 3':'', '12+5=17':'', 'Resposta final: 5*2':'',
                 'Resposta final:':'', 'Resposta final: 5\nResposta final: 6':'6'}
        for texto, esperado in casos.items():
            with self.subTest(texto=texto): self.assertEqual(extrair_resposta_numerica(texto), esperado)
    def test_comparacao(self):
        self.assertTrue(comparar_numeros('9,96','9.96'))
        self.assertFalse(comparar_numeros('3','4'))

if __name__ == '__main__': unittest.main(verbosity=2)
