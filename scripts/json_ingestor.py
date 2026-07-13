import os
import re
import json
import fitz  # PyMuPDF
from pathlib import Path
from font_utils import build_font_char_maps, translate_page_text

# --- CONFIGURAÇÕES DE DIRETÓRIOS ---
PASTA_BASE = Path("../PDF")
PASTA_JSON = Path("../scripts/questoes_json")
PASTA_JSON.mkdir(parents=True, exist_ok=True)

ARQUIVO_CONTROLE = PASTA_JSON / "controle_json.txt"
ARQUIVO_DEBUG = PASTA_JSON / "debug_geral.txt"

def _romano_para_inteiro(romano: str) -> int:
    """Converte um numeral romano (ex.: 'XXXVIII') para inteiro. Retorna 0 se inválido."""
    valores = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}
    total = 0
    anterior = 0
    for ch in reversed(romano.upper()):
        val = valores.get(ch, 0)
        if val == 0:
            return 0
        if val < anterior:
            total -= val
        else:
            total += val
            anterior = val
    return total

def log_debug(mensagem, resetar=False):
    modo = "w" if resetar else "a"
    with open(ARQUIVO_DEBUG, modo, encoding="utf-8") as f:
        f.write(mensagem + "\n")

# --- TABELAS DE MATÉRIAS POR GRUPO DE EXAME ---
# Grupo 2 (IV ao IX Exame, 2011-2012): Ética concentra 12 questões, sem Filosofia do Direito.
_FAIXAS_GRUPO_2 = [
    (1, 12, "Ética Profissional"), (13, 20, "Direito Constitucional"),
    (21, 22, "Direitos Humanos"), (23, 24, "Direito Internacional"),
    (25, 26, "Direito Ambiental"), (27, 28, "Direito do Consumidor"),
    (29, 30, "ECA"), (31, 37, "Direito Civil"), (38, 43, "Processo Civil"),
    (44, 48, "Direito Penal"), (49, 54, "Processo Penal"),
    (55, 60, "Direito do Trabalho"), (61, 65, "Processo do Trabalho"),
    (66, 71, "Direito Administrativo"), (72, 76, "Direito Empresarial"),
    (77, 80, "Direito Tributário"),
]

# Grupo 3 (X ao XXXVII Exame, 2013-2023): "ordem clássica", com Filosofia do Direito.
_FAIXAS_GRUPO_3 = [
    (1, 8, "Ética Profissional"), (9, 10, "Filosofia do Direito"),
    (11, 17, "Direito Constitucional"), (18, 19, "Direitos Humanos"),
    (20, 21, "Direito Internacional"), (22, 26, "Direito Tributário"),
    (27, 32, "Direito Administrativo"), (33, 34, "Direito Ambiental"),
    (35, 41, "Direito Civil"), (42, 43, "ECA"), (44, 45, "Direito do Consumidor"),
    (46, 50, "Direito Empresarial"), (51, 57, "Processo Civil"),
    (58, 63, "Direito Penal"), (64, 69, "Processo Penal"),
    (70, 75, "Direito do Trabalho"), (76, 80, "Processo do Trabalho"),
]

# Grupo 4 (XXXVIII em diante, 2023+): inclui Eleitoral, Financeiro e Previdenciário.
_FAIXAS_GRUPO_4 = [
    (1, 8, "Ética Profissional"), (9, 10, "Filosofia do Direito"),
    (11, 16, "Direito Constitucional"), (17, 18, "Direitos Humanos"),
    (19, 20, "Direito Eleitoral"), (21, 22, "Direito Internacional"),
    (23, 24, "Direito Financeiro"), (25, 29, "Direito Tributário"),
    (30, 34, "Direito Administrativo"), (35, 36, "Direito Ambiental"),
    (37, 42, "Direito Civil"), (43, 44, "ECA"), (45, 46, "Direito do Consumidor"),
    (47, 50, "Direito Empresarial"), (51, 56, "Processo Civil"),
    (57, 62, "Direito Penal"), (63, 68, "Processo Penal"),
    (69, 70, "Direito Previdenciário"), (71, 75, "Direito do Trabalho"),
    (76, 80, "Processo do Trabalho"),
]

def classificar_materia(id_questao: int, num_exame: int) -> str:
    if num_exame >= 38:
        faixas = _FAIXAS_GRUPO_4
    elif num_exame >= 10:
        faixas = _FAIXAS_GRUPO_3
    elif num_exame >= 4:
        faixas = _FAIXAS_GRUPO_2
    else:
        return "Não Mapeada"  # Grupo 1 (I a III): formato de prova ainda não suportado

    for inicio, fim, nome in faixas:
        if inicio <= id_questao <= fim:
            return nome
    return "Não Mapeada"

def ler_processados() -> set:
    if not ARQUIVO_CONTROLE.exists():
        ARQUIVO_CONTROLE.touch()
    with open(ARQUIVO_CONTROLE, "r", encoding="utf-8") as f:
        return set(linha.strip() for linha in f if linha.strip())

def registrar_processado(exame_id: str):
    with open(ARQUIVO_CONTROLE, "a", encoding="utf-8") as f:
        f.write(f"{exame_id}\n")

def extrair_numero_exame(nome_pasta: str) -> int:
    nome_upper = nome_pasta.upper()
    # Prioriza número arábico explícito na pasta (ex.: "40_EXAME_...")
    match_arabico = re.search(r'(?<!\d)(\d{1,3})(?!\d)', nome_upper)
    if match_arabico:
        return int(match_arabico.group(1))
    # Senão, tenta interpretar um numeral romano em um TOKEN INTEIRO isolado por
    # separadores (ex.: "XXXVIII_EXAME_..." -> "XXXVIII"). Não usar regex solto
    # sobre a string toda, pois palavras como "EXAME"/"ORDEM" contêm letras que
    # também são algarismos romanos (X, M, D, C, I) e gerariam falsos positivos.
    for token in re.split(r'[^A-Z]+', nome_upper):
        if token and re.fullmatch(r'[IVXLCDM]+', token):
            valor = _romano_para_inteiro(token)
            if valor > 0:
                return valor
    return 0

# --- EXTRAÇÃO DE DATA DE APLICAÇÃO (STANDALONE, METADATA-AWARE) ---
def extrair_data_aplicacao(caminho_gabarito: Path) -> str:
    """Extrai a data de aplicação do cabeçalho do gabarito (DD/MM/YYYY) e retorna o ano.
    
    Procura padrões como 'PROVAS DO DIA 03/07/2022' nos primeiros blocos
    de texto do PDF de gabarito.  Retorna apenas o ano (str) ou 'Desconhecido'.
    """
    try:
        doc = fitz.open(caminho_gabarito)
        # Basta examinar as 2 primeiras páginas
        texto = "\n".join(p.get_text("text") for p in doc[:2])
        # Padrão: DD/MM/YYYY
        match = re.search(r'\b(\d{1,2})/(\d{1,2})/(\d{4})\b', texto)
        if match:
            return match.group(3)
    except Exception:
        pass
    return "Desconhecido"


# --- MOTOR DE GABARITO (HÍBRIDO: LINEAR + ZIP EXTRACTION) ---
def extrair_gabarito(caminho_pdf: Path) -> tuple[dict, str]:
    respostas = {}
    ano = "Desconhecido"
    try:
        doc = fitz.open(caminho_pdf)
        texto_total = chr(10).join([p.get_text("text") for p in doc])
        
        # Extrai o ano diretamente do cabeçalho do gabarito (DD/MM/YYYY)
        ano = extrair_data_aplicacao(caminho_pdf)
        if ano == "Desconhecido":
            # Fallback: busca qualquer ano 20xx no texto
            match_ano = re.search(r'\b(20[0-9]{2})\b', texto_total)
            if match_ano:
                ano = match_ano.group(1)

        # Isola o quadrante estrito do Caderno Tipo/Prova 1
        match_tipo1 = re.search(r'(?i)(?:Tipo|Prova)\s*1(.*?)(?:Tipo|Prova)\s*2', texto_total, re.DOTALL)
        bloco_texto = match_tipo1.group(1) if (match_tipo1 and len(match_tipo1.group(1).strip()) > 100) else texto_total

        def processar_letra(l):
            l = l.upper().strip()
            if l in ['A', 'B', 'C', 'D']: return l, False
            return "Nula", True

        # Tentativa 1: Leitura Linear
        padrao_linear = re.compile(r'\b0?(\d{1,2})\s*[-|]?\s*([A-D*X]|NULA|ANULADA)\b', re.IGNORECASE)
        encontrados = padrao_linear.findall(bloco_texto)

        if len(encontrados) >= 70:
            for num_str, resp_str in encontrados:
                num = int(num_str)
                if 1 <= num <= 80:
                    resp, anulada = processar_letra(resp_str)
                    respostas[num] = {"resposta": resp, "anulada": anulada}
        else:
            # Tentativa 2: Zip Extraction (Especial para Matrizes e Colunas Fragmentadas)
            numeros = []
            for num_str in re.findall(r'\b0?(\d{1,2})\b', bloco_texto):
                num = int(num_str)
                if 1 <= num <= 80:
                    # Remove repetições sequenciais (sujeira de cabeçalhos)
                    if not numeros or numeros[-1] != num:
                        numeros.append(num)

            respostas_brutas = []
            for linha in bloco_texto.split('\n'):
                linha_limpa = linha.strip().upper()
                if not linha_limpa:
                    continue
                tokens = linha_limpa.split()
                if tokens and all(t in ['A', 'B', 'C', 'D', 'X', '*', 'NULA', 'ANULADA'] for t in tokens):
                    respostas_brutas.extend(tokens)

            # Funde matematicamente a ordem dos números com a ordem das letras
            for n, r in zip(numeros, respostas_brutas):
                resp, anulada = processar_letra(r)
                respostas[n] = {"resposta": resp, "anulada": anulada}

        # Tentativa 3: Correspondence Table (Sliding Window Token Parser)
        if len(respostas) < 70:
            tokens = []
            for word in texto_total.split():
                word_upper = word.strip().upper().strip(".-–")
                if not word_upper:
                    continue
                if word_upper.isdigit():
                    val = int(word_upper)
                    if 1 <= val <= 80:
                        tokens.append(word_upper)
                elif word_upper in ['A', 'B', 'C', 'D', 'X', '*', 'NULA', 'ANULADA']:
                    tokens.append(word_upper)

            i = 0
            respostas_correspondencia = {}
            while i < len(tokens) - 4:
                t1, t2, t3, t4, ans = tokens[i:i+5]
                if (t1.isdigit() and t2.isdigit() and t3.isdigit() and t4.isdigit() and 
                        ans in ['A', 'B', 'C', 'D', 'X', '*', 'NULA', 'ANULADA']):
                    num = int(t1)
                    resp, anulada = processar_letra(ans)
                    respostas_correspondencia[num] = {"resposta": resp, "anulada": anulada}
                    i += 5
                else:
                    i += 1

            if len(respostas_correspondencia) >= 70:
                respostas = respostas_correspondencia

        return respostas, ano
    except Exception:
        return {}, ano

# --- NORMALIZAÇÃO DE TEXTO (NLP): remove quebras de linha literais e espaços duplos ---
def normalizar_texto(texto: str) -> str:
    texto = texto.replace('\n', ' ')
    texto = re.sub(r'\s+', ' ', texto)
    return texto.strip()

# --- FUNÇÃO AUXILIAR: FECHAR QUESTÃO ---
def fechar_questao(q_atual, questoes):
    q_atual["alternativas"] = [
        f"A) {normalizar_texto(q_atual['alts']['A'])}",
        f"B) {normalizar_texto(q_atual['alts']['B'])}",
        f"C) {normalizar_texto(q_atual['alts']['C'])}",
        f"D) {normalizar_texto(q_atual['alts']['D'])}",
    ]
    del q_atual["alts"]
    q_atual["texto_pergunta"] = normalizar_texto(q_atual["texto_pergunta"])
    questoes.append(q_atual)
    log_debug(f"  [OK] Questão {q_atual['id']} formatada com sucesso.")

# --- MÁQUINA DE ESTADOS (GEOMÉTRICA & LOOKAHEAD) ---
def extrair_prova(caminho_pdf: Path, gabarito: dict, ano: str, id_exame: str, num_exame: int) -> list:
    doc = fitz.open(caminho_pdf)
    linhas_totais = []
    
    log_debug(f"\n[{id_exame}] Iniciando extração geométrica do PDF...")
    
    # 0. CONSTRUIR MAPA DE FONTES CORROMPIDAS (se houver)
    font_char_maps = build_font_char_maps(doc)
    has_corruption = len(font_char_maps) > 0
    if has_corruption:
        log_debug(f"  [FONT DECODER] Detectadas {len(font_char_maps)} fontes corrompidas; ativando tradução geométrica.")
    
    # 1. ACHATAMENTO GEOMÉTRICO (CROP BOX E COLUNAS)
    for pagina in doc:
        # Ignora APENAS a capa do caderno (index 0)
        if pagina.number == 0:
            continue
            
        meio = pagina.rect.width / 2
        page_num = pagina.number + 1
        
        # Usa rawdict+tradução se há corrupção, senão dict padrão (mais rápido)
        if has_corruption:
            linhas_com_pos = translate_page_text(pagina, font_char_maps, page_num)
        else:
            dados_pagina = pagina.get_text("dict")
            linhas_com_pos = []  # (y0, x_center, texto)
            for bloco in dados_pagina.get("blocks", []):
                for linha_obj in bloco.get("lines", []):
                    texto_linha = "".join(s.get("text", "") for s in linha_obj.get("spans", []))
                    if not texto_linha.strip():
                        continue
                    bbox = linha_obj["bbox"]
                    linhas_com_pos.append((bbox[1], (bbox[0] + bbox[2]) / 2, texto_linha))

        linhas_esquerda = sorted(
            [(y0, t) for (y0, xc, t) in linhas_com_pos if xc < meio], key=lambda p: p[0]
        )
        linhas_direita = sorted(
            [(y0, t) for (y0, xc, t) in linhas_com_pos if xc >= meio], key=lambda p: p[0]
        )
        texto_esquerda = "\n".join(t for _, t in linhas_esquerda)
        texto_direita = "\n".join(t for _, t in linhas_direita)

        # Salvaguarda: se a coluna "direita" vier quase vazia enquanto a
        # esquerda tem bastante conteúdo, é provável que esta página NÃO seja
        # de duas colunas de verdade (formato de coluna única).
        if len(texto_direita.strip()) < 40 and len(texto_esquerda.strip()) > 200:
            linhas_pagina_inteira = sorted(
                [(y0, t) for (y0, xc, t) in linhas_com_pos], key=lambda p: p[0]
            )
            colunas = [("única", linhas_pagina_inteira)]
        else:
            colunas = [("esquerda", linhas_esquerda), ("direita", linhas_direita)]

        numero_pagina_impresso = str(pagina.number + 1)

        padrao_cabecalho_rodape = re.compile(
            r'\b[IVXLCDM]+\s*EXAME\s*(?:DE|DO)?\s*ORDEM\s*UNIFICADO\s*[–\-]?\s*TIPO\s*\d+\s*[–\-]?\s*'
            r'(?:BRANCA|VERDE|AMARELA|AZUL)?',
            re.IGNORECASE
        )

        for nome_coluna, linhas_coluna in colunas:
            for y0, linha in linhas_coluna:
                linha_limpa = linha.strip()
                if not linha_limpa:
                    continue
                linha_compacta = re.sub(r'\s+', ' ', linha_limpa).strip()

                m_header = padrao_cabecalho_rodape.search(linha_compacta)
                if m_header:
                    resto = (linha_compacta[:m_header.start()] + linha_compacta[m_header.end():]).strip(" .–-")
                    if len(resto) < 15:
                        continue
                    else:
                        linha_limpa = resto
                        linha_compacta = resto

                # Filtro de número de página isolado: apenas se estiver na margem inferior (rodapé)
                if linha_compacta == numero_pagina_impresso:
                    is_bottom = y0 > pagina.rect.height * 0.90
                    if is_bottom:
                        continue

                linhas_totais.append(linha_limpa)

    # 1.5 GUILHOTINA DE FIM DE PROVA (HARD STOP)
    # Localiza o ponto EXATO de corte concatenando todas as linhas em um único texto
    # normalizado (a frase-gatilho pode estar fragmentada entre blocos/linhas do PDF)
    # e mapeando o offset do match de volta para o índice de linha correspondente.
    # Isso evita cortar linhas legítimas que antecedem a frase-gatilho (bug anterior:
    # parar assim que a frase aparecesse dentro de uma janela de N linhas à frente,
    # o que descartava o fim de Alternativas reais, como a D da Questão 80).
    GATILHOS_HARD_STOP = [
        "facultativo pelo examinando",
        "questionario de percepcao",
        "questionário de percepção",
    ]

    def _normalizar_para_busca(txt: str) -> str:
        return re.sub(r'\s+', ' ', txt).strip().lower()

    offsets = []  # (offset_inicial_no_texto_concatenado, indice_da_linha)
    partes_normalizadas = []
    cursor = 0
    for idx, linha in enumerate(linhas_totais):
        norm = _normalizar_para_busca(linha)
        offsets.append((cursor, idx))
        partes_normalizadas.append(norm)
        cursor += len(norm) + 1  # +1 pelo espaço separador usado no join abaixo

    texto_concatenado = " ".join(partes_normalizadas)

    indice_corte = len(linhas_totais)  # padrão: não corta nada
    for gatilho in GATILHOS_HARD_STOP:
        pos = texto_concatenado.find(gatilho)
        if pos != -1:
            # Encontra a última linha cujo offset inicial é <= pos (linha onde o gatilho começa)
            linha_do_gatilho = 0
            for offset_inicial, idx in offsets:
                if offset_inicial <= pos:
                    linha_do_gatilho = idx
                else:
                    break
            if linha_do_gatilho < indice_corte:
                indice_corte = linha_do_gatilho
                log_debug(f"  [HARD STOP] Gatilho '{gatilho}' localizado; corte preciso na linha {indice_corte}.")

    if indice_corte < len(linhas_totais):
        linhas_totais = linhas_totais[:indice_corte]

    # 2. MÁQUINA DE ESTADOS
    questoes = []
    padrao_q = re.compile(r'^\s*(?:Quest[aã]o\s*)?0?(\d+)\s*(?:[\*\s\-\.)]+(.*))?$', re.IGNORECASE)
    padrao_alt = re.compile(r'^\s*[\(]?([A-D])[)\.]\s*(.*)', re.IGNORECASE)
    
    q_atual = None
    estado = "BUSCANDO"
    letra_atual = None
    questao_esperada = 1

    for i, linha in enumerate(linhas_totais):
        m_q = padrao_q.match(linha)
        if m_q:
            num = int(m_q.group(1))
            if num == questao_esperada:
                # VALIDAÇÃO LOOKAHEAD: Há uma alternativa "A" nas próximas linhas?
                is_valid_lookahead = False
                for j in range(i + 1, min(i + 150, len(linhas_totais))):
                    if padrao_alt.match(linhas_totais[j]):
                        if padrao_alt.match(linhas_totais[j]).group(1).upper() == 'A':
                            is_valid_lookahead = True
                            break
                
                if is_valid_lookahead:
                    if q_atual:
                        fechar_questao(q_atual, questoes)

                    if questao_esperada > 80:
                        break 

                    q_atual = {
                        "exame": id_exame, "ano": ano, "id": questao_esperada,
                        "materia": classificar_materia(questao_esperada, num_exame),
                        "texto_pergunta": "",
                        "alts": {'A': '', 'B': '', 'C': '', 'D': ''},
                        "resposta_correta": gabarito.get(questao_esperada, {}).get("resposta", "N/A"),
                        "anulada": gabarito.get(questao_esperada, {}).get("anulada", False)
                    }
                    if m_q.group(2):
                        q_atual["texto_pergunta"] += m_q.group(2).strip() + "\n"
                        
                    estado = "ENUNCIADO"
                    letra_atual = None
                    questao_esperada += 1
                    continue
                else:
                    log_debug(f"  [LOOKAHEAD] Falso positivo ignorado para o número {num}")

        if not q_atual:
            continue

        m_alt = padrao_alt.match(linha)
        if m_alt:
            letra = m_alt.group(1).upper()
            if letra in ['A', 'B', 'C', 'D']:
                esperada = 'A' if not letra_atual else chr(ord(letra_atual) + 1)
                if letra == esperada:
                    estado = "ALTERNATIVA"
                    letra_atual = letra
                    q_atual["alts"][letra_atual] += m_alt.group(2).strip() + "\n"
                    continue

        if estado == "ENUNCIADO":
            q_atual["texto_pergunta"] += linha + "\n"
        elif estado == "ALTERNATIVA" and letra_atual:
            q_atual["alts"][letra_atual] += linha + "\n"

    # Salva a última questão no EOF
    if q_atual and len(questoes) < 80:
        fechar_questao(q_atual, questoes)

    if len(questoes) < 80:
        log_debug(f"  [ERRO CRÍTICO] A extração travou e extraiu apenas {len(questoes)} questões.")
        
    return questoes

def main():
    print("-" * 60)
    print("🚀 INICIANDO INGESTÃO (COM GATEKEEPER DE GABARITO)")
    print("-" * 60)
    
    log_debug("=== INÍCIO DO RELATÓRIO DE DEBUG DA OAB ===", resetar=True)
    
    if not PASTA_BASE.exists():
        print(f"❌ ERRO: A pasta '{PASTA_BASE}' não foi encontrada.")
        return
        
    processados = ler_processados()
    
    for pasta_exame in sorted(PASTA_BASE.iterdir()):
        if not pasta_exame.is_dir(): continue
            
        nome_pasta = pasta_exame.name
        num_exame = extrair_numero_exame(nome_pasta)
        
        if num_exame < 4:
            # Exames I a III têm formato de prova ainda não mapeado (fora do
            # padrão de 80 questões dos Grupos 2/3/4) e são propositalmente
            # ignorados aqui.
            continue
            
        if nome_pasta in processados:
            continue
            
        print(f"\n⚙️ Processando {nome_pasta} (Exame {num_exame})...")
        
        pdf_prova = list(pasta_exame.glob("Prova_*.pdf"))
        pdf_gabarito = list(pasta_exame.glob("Gabarito_*.pdf"))
        
        if not pdf_prova or not pdf_gabarito:
            print(f"    \033[93m[AVISO] Faltam PDFs na pasta. Pulando...\033[0m")
            continue
            
        gabarito_extraido, ano_exame = extrair_gabarito(pdf_gabarito[0])
        questoes = extrair_prova(pdf_prova[0], gabarito_extraido, ano_exame, nome_pasta, num_exame)
        
        if questoes:
            # GATEKEEPER: Validação de Integridade do Gabarito
            na_count = sum(1 for q in questoes if q["resposta_correta"] == "N/A")
            if (na_count / len(questoes)) > 0.05:
                mensagem_erro = f"Gabarito corrompido ou falha de pareamento ({na_count} respostas 'N/A'). JSON rejeitado."
                log_debug(f"  [GATEKEEPER] FATAL: {mensagem_erro}")
                print(f"  \033[91m❌ {mensagem_erro}\033[0m")
                continue # Aborta a criação deste JSON
            
            # Se passou no Gatekeeper, guarda no disco
            caminho_json = PASTA_JSON / f"questoes{num_exame}.json"
            with open(caminho_json, "w", encoding="utf-8") as f:
                json.dump(questoes, f, ensure_ascii=False, indent=2)
            
            if len(questoes) == 80:
                print(f"  \033[92m✅ SUCESSO! 80/80 questões e gabarito mapeados.\033[0m")
                registrar_processado(nome_pasta)
            else:
                print(f"  \033[93m⚠️ ATENÇÃO: Apenas {len(questoes)}/80 extraídas. Verifique o debug.\033[0m")
        else:
            print(f"  \033[91m❌ FALHA CRÍTICA. Zero questões detectadas.\033[0m")

if __name__ == "__main__":
    main()