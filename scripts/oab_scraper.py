import os
import re
import time
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import urljoin

# Ignora avisos de SSL em sites governamentais antigos
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- CONFIGURAÇÕES GERAIS E SESSÃO ---
PASTA_BASE = Path("PDF")
ARQUIVO_CONTROLE = PASTA_BASE / "controle.txt"
URL_INICIAL = "https://examedeordem.oab.org.br/EditaisProvas?NumeroExame=0"
URL_BASE = "https://examedeordem.oab.org.br"

sessao = requests.Session()
sessao.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9",
    "Connection": "keep-alive"
})

# --- FUNÇÕES DE ESTADO ---
def setup_ambiente():
    PASTA_BASE.mkdir(exist_ok=True)
    if not ARQUIVO_CONTROLE.exists():
        ARQUIVO_CONTROLE.touch()

def ler_exames_processados() -> set:
    with open(ARQUIVO_CONTROLE, "r", encoding="utf-8") as f:
        return set(linha.strip() for linha in f if linha.strip())

def registrar_exame_processado(nome_pasta: str):
    with open(ARQUIVO_CONTROLE, "a", encoding="utf-8") as f:
        f.write(f"{nome_pasta}\n")

def sanitizar_nome_pasta(texto: str) -> str:
    texto = texto.replace('º', '').replace('ª', '')
    texto_limpo = re.sub(r'[^\w\s]', '', texto) 
    return texto_limpo.strip().replace(" ", "_").upper()

# --- SCRAPER E DOWNLOADER ---
def mapear_exames() -> dict:
    resposta = sessao.get(URL_INICIAL, timeout=10, verify=False)
    soup = BeautifulSoup(resposta.text, 'html.parser')
    select_menu = soup.find('select', id='cmb-edital')
    
    exames = {}
    if select_menu:
        for opt in select_menu.find_all('option'):
            valor_id = opt.get('value')
            if valor_id and valor_id != "0":
                exames[sanitizar_nome_pasta(opt.text)] = valor_id
    return exames

def extrair_links_pdf(id_exame: str) -> dict:
    url_exame = f"{URL_BASE}/EditaisProvas?NumeroExame={id_exame}"
    resposta = sessao.get(url_exame, timeout=10, verify=False)
    soup = BeautifulSoup(resposta.text, 'html.parser')
    links = soup.find_all('a', href=True)

    url_prova, url_gab_definitivo, url_gab_preliminar, url_zip = None, None, None, None

    # A GRANDE CORREÇÃO: Lista de Exclusão (Blacklist)
    # Se qualquer uma dessas palavras estiver no texto do link, ele será sumariamente ignorado.
    palavras_proibidas = [
        'edital', 'local', 'locais', 'resultado', 'recurso', 
        'consulta', 'espelho', 'respostas', 'comunicado', 
        'isenção', 'horário', 'atendimento', 'retificação'
    ]

    regex_prova = re.compile(r'(caderno de prova.*(tipo\s*1|\b0?1\b)|prova objetiva.*1ª)', re.IGNORECASE)
    regex_gab_def = re.compile(r'(gabaritos?\s+definitivos?.*1ª|gabarito.*definitivo.*objetiva)', re.IGNORECASE)
    regex_gab_pre = re.compile(r'(gabaritos?\s+preliminares?.*1ª|gabarito.*preliminar.*objetiva|gabarito.*objetiva|gabarito.*01)', re.IGNORECASE)
    regex_zip = re.compile(r'\.zip$', re.IGNORECASE)

    for link in links:
        texto_link = link.text.strip()
        texto_lower = texto_link.lower()
        href = link['href']
        
        # Filtro Blindado: Tem palavra proibida? Pula pro próximo link na hora.
        if any(palavra in texto_lower for palavra in palavras_proibidas):
            continue
            
        is_gabarito = "gabarito" in texto_lower
        
        if regex_prova.search(texto_lower) and not is_gabarito: 
            url_prova = href
        elif regex_gab_def.search(texto_lower): 
            url_gab_definitivo = href
        elif regex_gab_pre.search(texto_lower): 
            url_gab_preliminar = href
        elif regex_zip.search(href) or "zip" in texto_lower: 
            url_zip = href

    url_gabarito = url_gab_definitivo if url_gab_definitivo else url_gab_preliminar
    
    resultado = {}
    if url_prova: resultado['prova'] = urljoin(URL_BASE, url_prova)
    if url_gabarito: resultado['gabarito'] = urljoin(URL_BASE, url_gabarito)
    
    if not resultado and url_zip:
        resultado['pacote_zip'] = urljoin(URL_BASE, url_zip)

    if resultado:
        resultado['url_origem'] = url_exame

    return resultado

def baixar_arquivo(url: str, caminho_destino: Path, url_origem: str) -> bool:
    # A MÁGICA: Força o HTTPS imediatamente para não perder tempo com Erro 502
    url_segura = url.replace("http://", "https://")
    
    tentativas = 3
    headers_download = {
        "Referer": url_origem,
        "Accept": "application/pdf,application/octet-stream,*/*",
        "Accept-Encoding": "identity" 
    }
    
    for tentativa in range(1, tentativas + 1):
        try:
            resposta = sessao.get(url_segura, headers=headers_download, stream=True, timeout=(10, 30), verify=False)
            resposta.raise_for_status() 
            
            with open(caminho_destino, 'wb') as f:
                for chunk in resposta.iter_content(chunk_size=8192):
                    if chunk: f.write(chunk)
            return True
            
        except Exception as e:
            erro_http = getattr(getattr(e, 'response', None), 'status_code', None)
            erro_msg = erro_http if erro_http else str(e)[:50].strip()
            
            nome_arq = url_segura.split('/')[-1][:20]
            print(f"\033[91m    [FALHA {tentativa}/{tentativas}] Erro: {erro_msg} | Arquivo: {nome_arq}...\033[0m")
            
            if tentativa < tentativas:
                time.sleep(3)
            else:
                if caminho_destino.exists(): caminho_destino.unlink()
                return False
    return False

def main():
    print("-" * 50)
    print("🚀 INICIANDO SCRAPER OAB (MODO EXPRESSO)")
    print("-" * 50)
    
    setup_ambiente()
    processados = ler_exames_processados()
    todos_exames = mapear_exames()
    exames_pendentes = {nome: uid for nome, uid in todos_exames.items() if nome not in processados}
    
    if not exames_pendentes:
        print("🎉 Todos os exames já estão baixados. Nada a fazer!")
        return

    for nome_exame, id_exame in exames_pendentes.items():
        print(f"\n⚙️ Processando: {nome_exame} (ID: {id_exame})")
        
        links = extrair_links_pdf(id_exame)
        
        if not links:
            print("\033[93m  -> [AVISO] Nenhum PDF de 1ª Fase ou ZIP encontrado nesta página.\033[0m")
            continue
            
        url_origem = links.pop('url_origem', URL_INICIAL)
        pasta_exame = PASTA_BASE / nome_exame
        pasta_exame.mkdir(exist_ok=True)
        sucesso_total = True
        
        if 'pacote_zip' in links:
            print("  -> Baixando Pacote ZIP completo...")
            if not baixar_arquivo(links['pacote_zip'], pasta_exame / f"Pacote_{nome_exame}.zip", url_origem):
                sucesso_total = False
        else:
            if 'prova' in links:
                print("  -> Baixando Prova...")
                if not baixar_arquivo(links['prova'], pasta_exame / f"Prova_{nome_exame}.pdf", url_origem):
                    sucesso_total = False
            else:
                print("\033[93m  -> [AVISO] Link da Prova não extraído do site.\033[0m")
                sucesso_total = False
                
            if 'gabarito' in links:
                print("  -> Baixando Gabarito...")
                if not baixar_arquivo(links['gabarito'], pasta_exame / f"Gabarito_{nome_exame}.pdf", url_origem):
                    sucesso_total = False
            else:
                print("\033[93m  -> [AVISO] Link do Gabarito não extraído do site.\033[0m")
                sucesso_total = False

        if sucesso_total:
            registrar_exame_processado(nome_exame)
            print(f"\033[92m  ✅ {nome_exame} concluído e salvo no controle!\033[0m")
        else:
            print(f"\033[93m  ⚠️ {nome_exame} finalizado com pendências.\033[0m")
            
        time.sleep(1.5)

if __name__ == "__main__":
    main()