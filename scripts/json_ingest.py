from pathlib import Path
import json
from supabase import create_client
from dotenv import load_dotenv
import os

supabase_key = os.getenv('SUPABASE_API_KEY')
supabase_url = os.getenv('SUPABASE_URL')

client = create_client(supabase_key, supabase_url)

BASE_DIR = Path(__file__).resolve().parent.parent
DADOS = BASE_DIR / "dados_brutos"

arquivos = [
    p for p in DADOS.iterdir() if p.is_file()
]

for arquivo in arquivos:
    with open(arquivo, "r", encoding='utf-8') as f:
        questoes = json.load(f)

    for questao in questoes:
        questao['alternativa_a'] = questao['alternativas'][0]
        questao['alternativa_b'] = questao['alternativas'][1]
        questao['alternativa_c'] = questao['alternativas'][2]
        questao['alternativa_d'] = questao['alternativas'][3]
        
        questao.remove('alternativas')
    
