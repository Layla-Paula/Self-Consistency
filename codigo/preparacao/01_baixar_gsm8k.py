"""
Script para baixar e preparar dataset GSM8K
Autor: Layla Paula
Data: 2025-05-26
"""

from datasets import load_dataset
import json
import random
import os
import pandas as pd

# Configurações
SEED = 42
QUANTIDADE = 100
PASTA_DESTINO = "dados/1_gsm8k/originais/"

def baixar_gsm8k():
    """Baixa o dataset GSM8K do HuggingFace"""
    print("📥 Baixando GSM8K do HuggingFace...")
    dataset = load_dataset("openai/gsm8k", "main")
    print(f"✅ Dataset baixado! Total: {len(dataset['test'])}")
    return dataset['test']

def selecionar_problemas(dataset, quantidade, seed):
    """Seleciona problemas aleatórios"""
    print(f"\n🎲 Selecionando {quantidade} problemas...")
    random.seed(seed)
    indices = random.sample(range(len(dataset)), quantidade)
    
    problemas = []
    for idx in indices:
        item = dataset[int(idx)]
        problemas.append({
            'index_original': idx,
            'question': item['question'],
            'answer': item['answer']
        })
    
    print(f"✅ {len(problemas)} problemas selecionados")
    return problemas

def salvar_json(dados, caminho):
    """Salva dados em JSON"""
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, 'w', encoding='utf-8') as f:
        json.dump(dados, f, indent=2, ensure_ascii=False)
    print(f"💾 Salvo em: {caminho}")

def criar_planilha_traducao(problemas, caminho_excel):
    """Cria planilha Excel para tradução"""
    print(f"\n📊 Criando planilha Excel...")
    
    linhas = []
    for i, prob in enumerate(problemas, 1):
        partes = prob['answer'].split('####')
        raciocinio = partes[0].strip() if len(partes) > 0 else ""
        resposta = partes[1].strip() if len(partes) > 1 else ""
        
        linhas.append({
            'ID': f'gsm8k_{i:03d}',
            'Original (EN)': prob['question'],
            'Tradução (PT-BR)': '',
            'Resposta Original': resposta,
            'Resposta PT': resposta,
            'Raciocínio Original': raciocinio,
            'Raciocínio PT': '',
            'Status': '🔄'
        })
    
    df = pd.DataFrame(linhas)
    os.makedirs(os.path.dirname(caminho_excel), exist_ok=True)
    df.to_excel(caminho_excel, index=False, engine='openpyxl')
    
    print(f"✅ Planilha criada: {caminho_excel}")
    print(f"   Total de linhas: {len(df)}")

def main():
    print("="*60)
    print("PREPARAÇÃO DO DATASET GSM8K")
    print("="*60)
    
    dataset = baixar_gsm8k()
    problemas = selecionar_problemas(dataset, QUANTIDADE, SEED)
    
    caminho_json = os.path.join(PASTA_DESTINO, 'gsm8k_selected_100.json')
    salvar_json(problemas, caminho_json)
    
    caminho_excel = 'dados/1_gsm8k/traducoes/gsm8k_traducoes.xlsx'
    criar_planilha_traducao(problemas, caminho_excel)
    
    print("\n" + "="*60)
    print("📄 EXEMPLO DO PRIMEIRO PROBLEMA:")
    print("="*60)
    print(f"\nPergunta: {problemas[0]['question'][:200]}...")
    
    print("\n✅ PREPARAÇÃO CONCLUÍDA!")
    print("\n📝 PRÓXIMOS PASSOS:")
    print("1. Abra: dados/1_gsm8k/traducoes/gsm8k_traducoes.xlsx")
    print("2. Preencha as traduções")
    print("3. Marque Status como ✅ quando terminar")

if __name__ == "__main__":
    main()
