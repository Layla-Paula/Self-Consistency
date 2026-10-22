import unittest
from codigo.utils import extrair_letra_resposta

class TestarAlternativas(unittest.TestCase):
    def test_alternativas_validas(self):
        casos = {'Resposta final: C':'C','Resposta: B':'B', 'Resposta: E':'E', 'Resposta: B\nResposta final: D':'D', 'A resposta correta é D) $45':'D',
                 'A única opção que é igual é C) 12.':'C', 'Alternativa correta: E':'E',
                 'Resposta final: B\n':'B', 'C':'C', 'Ans: A':'A',
                 'Resposta final: A\nResposta final: D':'D'}
        for texto, esperado in casos.items():
            with self.subTest(texto=texto): self.assertEqual(extrair_letra_resposta(texto), esperado)
    def test_sem_alternativa_final(self):
        for texto in ('', 'Vamos tentar novamente. A) 5 B) 10', 'Resposta final: Nenhum valor',
                      'Não sei a resposta', 'A) 10\nB) 20\nC) 30'):
            with self.subTest(texto=texto): self.assertEqual(extrair_letra_resposta(texto), '')

if __name__ == '__main__': unittest.main(verbosity=2)
