"""Casos de teste das rubricas objetivas do Censo Escolar 2025.

Cada caso tem: questão (número), tipo, resposta e o veredito esperado da rubrica.
Tipos: correta, incorreta, incompleta, contraditoria.
Veredito esperado: True (certo), False (errado) ou None (a rubrica não decide e a
questão vai para a revisão humana).

As respostas foram escritas à mão a partir dos gabaritos de resposta_esperada.
"""

UFS_27 = ('AC, AL, AP, AM, BA, CE, DF, ES, GO, MA, MT, MS, MG, PA, PB, PR, PE, PI, '
          'RJ, RN, RS, RO, RR, SC, SP, SE, TO')
UFS_26 = UFS_27.replace(', TO', '')  # falta o Tocantins

# Questões em que a rubrica sempre dá um veredito (certo ou errado).
COM_VEREDITO = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19,
                22, 23, 24, 31, 33, 35, 40, 42, 46, 47, 49)
# Questões em que a rubrica só decide parte dos casos; o resto vai para revisão humana.
PARCIAL = (20, 28, 41, 43, 44)
# Questões sem rubrica: sempre vão para revisão humana.
SEM_RUBRICA = (21, 25, 26, 27, 29, 30, 32, 34, 36, 37, 38, 39, 45, 48, 50)

CASOS = [
    # ---- Q01: total de escolas (178.766) ----
    (1, 'correta', 'Há 178.766 escolas de Educação Básica na base.', True),
    (1, 'correta', '178766', True),
    (1, 'correta', 'São 178.766.', True),                      # ponto final de frase
    (1, 'correta', 'O total é de 178.766, conforme a consulta.', True),
    (1, 'incorreta', 'Há 46.018.380 escolas na base.', False),
    (1, 'incorreta', 'Há 5.571 escolas na base.', False),
    (1, 'incompleta', 'Há muitas escolas registradas na base.', False),
    (1, 'incompleta', '', False),
    (1, 'contraditoria', 'Existem 178.766 escolas, ou seja, 0 escolas registradas.', False),
    (1, 'incorreta', 'O total é 1178766 escolas.', False),    # número maior que contém o valor

    # ---- Q02: total de matrículas (46.018.380) ----
    (2, 'correta', 'O total de matrículas é 46.018.380.', True),
    (2, 'correta', '46018380', True),
    (2, 'incorreta', 'O total é 46.018.381 matrículas.', False),
    (2, 'incorreta', 'O total é 4.601.838 matrículas.', False),
    (2, 'incompleta', 'O total de matrículas é de milhões de alunos.', False),

    # ---- Q03: dois tipos de turma excluídos ----
    (3, 'correta', 'Não inclui turmas exclusivas de atividade complementar e de '
                   'Atendimento Educacional Especializado (AEE).', True),
    (3, 'incompleta', 'Não inclui turmas exclusivas de atividade complementar.', False),
    (3, 'incompleta', 'Não inclui turmas de AEE.', False),
    (3, 'incorreta', 'Não inclui turmas de EJA e de Educação Infantil.', False),

    # ---- Q04: 27 UFs ----
    (4, 'correta', f'A base cobre 27 UFs: {UFS_27}.', True),
    (4, 'incompleta', f'A base cobre 27 UFs: {UFS_26}.', False),
    (4, 'incompleta', f'A base cobre as UFs: {UFS_27}.', False),          # sem a contagem
    (4, 'contraditoria', f'A base cobre 26 UFs: {UFS_27}.', False),      # diz 26 e lista 27
    (4, 'incorreta', 'A base cobre 27 UFs.', False),                      # sem identificar

    # ---- Q05: 5.571 municípios ----
    (5, 'correta', 'Há escolas em 5.571 municípios distintos.', True),
    (5, 'incorreta', 'Há escolas em 5.570 municípios distintos.', False),
    (5, 'contraditoria', "Contando df['UF'].value_counts() chego a 5571.", False),

    # ---- Q06: NU_ANO_CENSO / 2025 ----
    (6, 'correta', 'NU_ANO_CENSO é o ano de referência do Censo; o valor é 2025.', True),
    (6, 'incompleta', 'O valor é 2025.', False),
    (6, 'incompleta', 'NU_ANO_CENSO é o ano de referência do Censo Escolar.', False),
    (6, 'incorreta', 'NU_ANO_CENSO é o ano de referência e o valor é 2024.', False),

    # ---- Q07: não há escola com QT_MAT_BAS = 0 ----
    (7, 'correta', 'Não existe nenhuma escola com QT_MAT_BAS igual a zero.', True),
    (7, 'correta', 'Não há escolas com zero matrículas (0 ocorrências).', True),
    (7, 'incorreta', 'Existem escolas com QT_MAT_BAS igual a zero.', False),
    (7, 'incorreta', 'Sim, há uma escola com zero matrículas.', False),
    (7, 'incompleta', 'A verificação mostra que a base é consistente.', False),

    # ---- Q08: CO_REDE x TP_DEPENDENCIA ----
    (8, 'correta', 'TP_DEPENDENCIA tem quatro categorias: Federal, Estadual, Municipal e '
                   'Privada. CO_REDE agrupa em duas: Pública e Privada.', True),
    (8, 'incompleta', 'CO_REDE agrupa as escolas em pública e privada.', False),
    (8, 'incorreta', 'As duas variáveis são a mesma coisa.', False),
    (8, 'contraditoria', 'CO_REDE tem quatro categorias: federal, estadual, municipal e '
                         'privada; já TP_DEPENDENCIA agrupa em pública e privada.', False),

    # ---- Q09: escolas por rede ----
    (9, 'correta', 'Rede pública: 137.020 escolas. Rede privada: 41.746 escolas.', True),
    (9, 'incompleta', 'Rede pública: 137.020 escolas.', False),
    (9, 'incorreta', 'Rede pública: 120.000 escolas. Rede privada: 58.766 escolas.', False),

    # ---- Q10: matrículas por dependência ----
    (10, 'correta', 'Federal: 383.526. Estadual: 13.330.302. Municipal: 23.059.168. '
                    'Privada: 9.245.384. A Municipal concentra o maior número.', True),
    (10, 'incompleta', 'Federal: 383.526. Estadual: 13.330.302. Municipal: 23.059.168.', False),
    (10, 'incorreta', 'Federal: 1.000. Estadual: 2.000. Municipal: 3.000. Privada: 4.000.', False),

    # ---- Q11: dependência com menos escolas ----
    (11, 'correta', 'A Federal tem 716 escolas, o menor número, e 383.526 matrículas.', True),
    (11, 'incompleta', 'A Federal tem o menor número de escolas.', False),
    (11, 'incorreta', 'A Estadual tem 716 escolas e 383.526 matrículas.', False),

    # ---- Q12: médias por dependência (valor exato 535,7 / 448,3 / 221,5 / 216,4) ----
    (12, 'correta', 'Federal: 535. Estadual: 448. Privada: 221. Municipal: 216.', True),   # truncado
    (12, 'incompleta', 'Federal: 535,7. Estadual: 448,3. Municipal: 216,4.', False),       # sem a privada
    (12, 'incorreta', 'Federal: 100. Estadual: 200. Privada: 300. Municipal: 400.', False),

    # ---- Q13: média municipal x estadual ----
    (13, 'correta', 'A municipal, 216, é a metade da estadual, 448; municipal e estadual.', True),
    (13, 'incompleta', 'A municipal tem média 216,4 e a estadual 448,3.', False),  # sem a comparação
    (13, 'incorreta', 'A média municipal é 900 e a estadual é 100; a municipal é menor.', False),

    # ---- Q14: variável das escolas privadas ----
    (14, 'correta', 'A variável é TP_CATEGORIA_ESCOLA_PRIVADA: Particular, Comunitária, '
                    'Confessional e Filantrópica.', True),
    (14, 'incompleta', 'A variável é TP_CATEGORIA_ESCOLA_PRIVADA: Particular e Comunitária.', False),
    (14, 'incorreta', 'A variável é TP_DEPENDENCIA.', False),

    # ---- Q15: particular x filantrópica ----
    (15, 'correta', 'Particular: 7.085.034. Filantrópica: 1.711.268. A Particular concentra mais.', True),
    (15, 'incompleta', 'Particular: 7.085.034. Filantrópica: 1.711.268.', False),    # sem conclusão
    (15, 'incorreta', 'Particular: 1.000. Filantrópica: 2.000. A Particular concentra mais.', False),

    # ---- Q16: IN_PODER_PUBLICO_PARCERIA ----
    (16, 'correta', 'Indica parceria ou convênio com o poder público, para financiamento do '
                    'atendimento.', True),
    (16, 'incompleta', 'Indica que há uma parceria.', False),
    (16, 'incorreta', 'Indica uma escola totalmente privada, sem vínculo com o governo.', False),

    # ---- Q17: escolas urbanas x rurais ----
    (17, 'correta', 'Urbana: 128.037 escolas. Rural: 50.729 escolas.', True),
    (17, 'correta', 'Urbanas: 128.037; rurais: 50.729.', True),
    (17, 'incompleta', 'Urbana: 128.037 escolas.', False),
    (17, 'contraditoria', 'Urbana: 128.037 + 50.729 = 178.766 escolas.', False),         # soma como total

    # ---- Q18: matrículas urbanas x rurais ----
    (18, 'correta', 'Urbana: 40.871.166 matrículas. Rural: 5.147.214 matrículas.', True),
    (18, 'incompleta', 'Urbana: 40.871.166 matrículas.', False),
    (18, 'contraditoria', 'Urbana: 40.871.166. Rural: 5.147.214. Os dois totais são iguais.', False),

    # ---- Q19: médias urbana x rural (319,2 e 101,5) ----
    (19, 'correta', 'Urbana: 319. Rural: 101.', True),
    (19, 'incompleta', 'A média urbana é 319,2.', False),
    (19, 'contraditoria', 'Urbana: 319,2 e também 270. Rural: 101,5.', False),
    (19, 'incorreta', 'Urbana: 50. Rural: 400.', False),

    # ---- Q20: percentual rural por região (uma região por linha) ----
    (20, 'correta', 'Norte: 24,42%\nNordeste: 21,34%\nCentro-Oeste: 5,90%\nSul: 5,77%\n'
                    'Sudeste: 3,30%\nA maior é a região Norte.', True),
    (20, 'incompleta', 'Norte: 24,42%\nNordeste: 21,34%\nSul: 5,77%\nSudeste: 3,30%', False),
    (20, 'incorreta', 'Norte: 10,00%\nNordeste: 20,00%\nCentro-Oeste: 30,00%\nSul: 40,00%\n'
                      'Sudeste: 50,00%\nNorte', False),
    (20, 'incompleta', 'Norte 24,42%, Nordeste 21,34%, Centro-Oeste 5,90%, Sul 5,77%, '
                       'Sudeste 3,30%.', None),   # tudo numa linha: associação ambígua

    # ---- Q22: cinco UFs com mais matrículas ----
    (22, 'correta', 'São Paulo, Minas Gerais, Bahia, Rio de Janeiro e Paraná.', True),
    (22, 'correta', 'SP, MG, BA, RJ e PR.', True),
    (22, 'incompleta', 'São Paulo, Minas Gerais, Bahia e Rio de Janeiro.', False),
    (22, 'incorreta', 'São Paulo, Minas Gerais, Bahia, Rio de Janeiro e Rio Grande do Sul.', False),
    (22, 'contraditoria', 'São Paulo, Minas Gerais, Bahia, Rio de Janeiro, Paraná e Acre.', False),

    # ---- Q23: cinco UFs com menos matrículas ----
    (23, 'correta', 'Roraima, Amapá, Acre, Rondônia e Tocantins.', True),
    (23, 'incorreta', 'Roraima, Amapá, Acre, Rondônia e Sergipe.', False),
    (23, 'incompleta', 'Roraima, Amapá e Acre.', False),

    # ---- Q24: maior município ----
    (24, 'correta', 'São Paulo (SP), com 2.512.355 matrículas.', True),
    (24, 'incorreta', 'Rio de Janeiro, com 1.208.798 matrículas.', False),
    (24, 'incompleta', 'O total é 2.512.355 matrículas.', False),
    (24, 'incompleta', 'São Paulo é o maior município.', False),

    # ---- Q28: Anos Iniciais x Anos Finais (só detecta inversão) ----
    (28, 'contraditoria', 'Os Anos Iniciais têm menos matrículas que os Anos Finais.', False),
    (28, 'correta', 'Anos Iniciais: 14.514.244. Anos Finais: 11.292.523. Os Iniciais têm mais.', None),

    # ---- Q31 ----
    (31, 'correta', 'Técnica: 2.490.145 matrículas, 78,1% da Educação Profissional.', True),
    (31, 'incompleta', 'Técnica: 2.490.145 matrículas.', False),
    (31, 'incorreta', 'Técnica: 2.490.145 matrículas, 12,5% da Educação Profissional.', False),

    # ---- Q33 ----
    (33, 'correta', 'Total EJA: 2.252.069 matrículas, 4,89% do total.', True),
    (33, 'incompleta', 'Total EJA: 2.252.069 matrículas.', False),
    (33, 'incorreta', 'Total EJA: 1.000.000 matrículas, 4,89%.', False),

    # ---- Q35 ----
    (35, 'correta', 'O total é de 3637. Esse número é pequeno.', True),         # ponto final
    (35, 'correta', 'QT_MAT_BAS_LIBRAS: 3.637 matrículas.', True),
    (35, 'incorreta', 'O total é 36.370 matrículas.', False),
    (35, 'incompleta', 'É um número muito pequeno.', False),

    # ---- Q40 ----
    (40, 'correta', '6.275.577 matrículas estão como "Não Declarada".', True),
    (40, 'incompleta', '6.275.577 matrículas.', False),                          # sem a categoria
    (40, 'incorreta', '1.000 matrículas estão como "Não Declarada".', False),

    # ---- Q41: sempre para revisão humana ----
    (41, 'correta', '6 a 10 anos: 14.111.254; 11 a 14 anos: 11.194.106. Anos Iniciais e Finais.', None),
    (41, 'incorreta', 'Não sei.', None),

    # ---- Q42 ----
    (42, 'correta', 'São 3.974.803 com 18 anos ou mais, associados à EJA.', True),
    (42, 'correta', '3.974.803, ligados à Educação Profissional.', True),
    (42, 'incompleta', 'São 3.974.803 com 18 anos ou mais.', False),
    (42, 'incorreta', 'São 100.000 com 18 anos ou mais, associados à EJA.', False),

    # ---- Q43: só detecta número malformado ----
    (43, 'contraditoria', '0 a 3 anos: 3.874.541. 4 a 5 anos: 496.8651.', False),
    (43, 'correta', '0 a 3 anos: 3.874.541. 4 a 5 anos: 4.968.651. A de 4 a 5 anos é maior.', None),

    # ---- Q44: só detecta falta dos três totais ----
    (44, 'incompleta', 'Diurno: 42.131.013. Noturno: 3.240.654.', False),
    (44, 'incompleta', 'O turno diurno concentra a maioria das matrículas.', False),
    (44, 'correta', 'Diurno: 42.131.013. Noturno: 3.240.654. EAD: 646.713. O diurno predomina.', None),

    # ---- Q46 ----
    (46, 'correta', 'Tempo integral: 10.143.262 matrículas, 22,04% do total.', True),
    (46, 'incompleta', 'Tempo integral: 10.143.262 matrículas.', False),
    (46, 'incorreta', 'Tempo integral: 10.143.262 matrículas, 30,00% do total.', False),

    # ---- Q47 ----
    (47, 'correta', 'Educação Especial: 2.458.159 matrículas, 5,34% do total.', True),
    (47, 'incompleta', 'Educação Especial: 2.458.159 matrículas.', False),
    (47, 'incorreta', 'Educação Especial: 2.458.159 matrículas, 9,99% do total.', False),

    # ---- Q49 ----
    (49, 'correta', 'Total: 9.078.809. Estadual: 1.431.234. Municipal: 7.647.575. '
                    'A esfera Municipal predomina.', True),
    (49, 'incompleta', 'Total: 9.078.809. Municipal: 7.647.575. A Municipal predomina.', False),
    (49, 'incorreta', 'Total: 100. Estadual: 200. Municipal: 300. A Municipal predomina.', False),
]

# DEFEITOS CONHECIDOS: a rubrica, como está escrita hoje, dá o veredito ERRADO.
# (questão, descrição, resposta, veredito que DEVERIA sair, veredito que sai hoje)
# Quando a rubrica for corrigida, o teste avisa para tirar o caso desta lista.
# Defeitos anteriores convertidos em regressões obrigatórias.
DEFEITOS = []

CASOS.extend([
    (12, 'correta', 'Federal: 535,7. Estadual: 448,3. Privada: 221,5. Municipal: 216,4. A Federal tem a maior média.', True),
    (12, 'correta', 'Federal: 536. Estadual: 448. Privada: 222. Municipal: 216.', True),
    (13, 'correta', 'A média municipal (216,4) é praticamente metade da estadual (448,3).', True),
    (19, 'correta', 'Urbana: 319,2. Rural: 101,5. A média urbana é mais de três vezes a rural.', True),
    (17, 'contraditoria', 'Urbana: 50.729 escolas. Rural: 128.037 escolas.', False),
    (18, 'contraditoria', 'Urbana: 5.147.214 matrículas. Rural: 40.871.166 matrículas.', False),
    (7, 'contraditoria', 'Não existe nenhuma escola com zero matrículas, mas há escolas com QT_MAT_BAS igual a zero.', False),
    (9, 'contraditoria', 'Rede pública: 41.746 escolas. Rede privada: 137.020 escolas.', False),
    (10, 'contraditoria', 'Federal: 383.526. Estadual: 13.330.302. Municipal: 23.059.168. Privada: 9.245.384. A Estadual concentra o maior número.', False),
    (15, 'contraditoria', 'Particular: 7.085.034. Filantrópica: 1.711.268. A Filantrópica concentra mais.', False),
    (2, 'contraditoria', 'São 46.018.380, mas o total verdadeiro é 50 milhões.', False),
])


LIMITACOES = [
    # Aqui a rubrica não decide e manda para revisão humana (resultado seguro).
    (28, 'inversão escrita de outro jeito',
     'Os Anos Finais têm mais matrículas do que os Anos Iniciais.', False, None),
]


# Regressões: frases naturais (número antes ou depois do rótulo, tabelas, arredondamento)
# e valores trocados entre rótulos. (questão, resposta, veredito esperado)
T, F = True, False
_FRASES_NATURAIS = [
(12,'A rede Federal possui média de 535,7 matrículas por escola; a Estadual, 448,3; a Privada, 221,5; e a Municipal, 216,4.',T),
(12,'A média da rede federal é de 535,7, da estadual 448,3, da privada 221,5 e da municipal 216,4. A Federal tem a maior.',T),
(12,'Federal 716 escolas, média 535,7. Estadual 29.732 escolas, média 448,3. Privada: 221,5. Municipal: 216,4.',T),
(12,'Federal | 716 | 383.526 | 535,7\nEstadual | 29.732 | 13.330.302 | 448,3\nPrivada | 41.746 | 9.245.384 | 221,5\nMunicipal | 106.572 | 23.059.168 | 216,4',T),
(12,'Federal: 448,3. Estadual: 535,7. Privada: 221,5. Municipal: 216,4.',F),
(12,'Federal: 535,7. Estadual: 448,3. Privada: 216,4. Municipal: 221,5.',F),
(19,'A média urbana é de 319,2 matrículas por escola e a rural é de 101,5; a urbana é mais de três vezes a rural.',T),
(19,'Urbana: 319,2. Rural: 101,5.',T),
(19,'Em escolas urbanas a média é 319,2 e nas rurais 101,5.',T),
(19,'Urbana: 101,5. Rural: 319,2.',F),
(19,'A média rural é 101,5 e a urbana é 319,2.',T),
(13,'A média municipal (216,4) é praticamente metade da estadual (448,3).',T),
(13,'A rede municipal tem média de 216,4 e a estadual 448,3, ou seja, a municipal é menor, cerca de metade.',T),
(13,'A média estadual (216,4) é metade da municipal (448,3).',F),
(17,'Há 128.037 escolas urbanas e 50.729 escolas rurais.',T),
(17,'São 128.037 escolas na zona urbana e 50.729 na zona rural.',T),
(17,'Das 178.766 escolas, 128.037 são urbanas e 50.729 são rurais.',T),
(17,'Há 50.729 escolas urbanas e 128.037 escolas rurais.',F),
(17,'Urbana: 50.729 escolas. Rural: 128.037 escolas.',F),
(18,'As escolas urbanas somam 40.871.166 matrículas e as rurais 5.147.214.',T),
(18,'As escolas rurais somam 40.871.166 matrículas e as urbanas 5.147.214.',F),
(9,'A rede pública tem 137.020 escolas e a rede privada 41.746.',T),
(9,'Existem 137.020 escolas públicas e 41.746 escolas privadas.',T),
(9,'Pública: 137.020. Privada: 41.746.',T),
(9,'Pública: 41.746. Privada: 137.020.',F),
(9,'Existem 41.746 escolas públicas e 137.020 escolas privadas.',F),
(10,'Federal tem 383.526, Estadual 13.330.302, Municipal 23.059.168 e Privada 9.245.384 matrículas; a Municipal concentra mais.',T),
(10,'A dependência municipal possui o maior número de matrículas (23.059.168), seguida da estadual (13.330.302), privada (9.245.384) e federal (383.526).',T),
(10,'Federal: 383.526. Estadual: 13.330.302. Municipal: 9.245.384. Privada: 23.059.168.',F),
(15,'A Particular concentra 7.085.034 matrículas e a Filantrópica 1.711.268; a Particular é maior.',T),
(15,'A categoria Filantrópica tem 1.711.268 matrículas e a Particular tem 7.085.034, sendo a Particular a maior.',T),
(15,'Particular: 1.711.268. Filantrópica: 7.085.034. A Particular é maior.',F),
(9,'As redes pública e privada somam 178.766 escolas.',None),
]

CASOS.extend([(n, 'contraditoria' if esperado is False else 'correta', texto, esperado)
              for n, texto, esperado in _FRASES_NATURAIS])
