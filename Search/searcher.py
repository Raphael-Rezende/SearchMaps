
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import warnings

import time
import os
#Manipulação de dados
import pandas as pd
import shutil

from utils import  formatar_dados, selecionar_colunas

from db import salvar_dados_no_banco, listar_dados
from tabulate import tabulate  # Para exibir os dados formatados no terminal

# Suprimir avisos de Deprecation
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Configuração do driver do Selenium
options = webdriver.ChromeOptions()
options.add_argument("--headless")  # Executa em modo headless (sem interface gráfica)
options.add_argument("--disable-gpu")
options.add_argument("--log-level=3")  # Apenas erros
options.add_argument("--no-sandbox")
options.add_experimental_option("excludeSwitches", ["enable-logging"])  # Remove logs de warning
driver = webdriver.Chrome(options=options) # Suprime logs do driver

# Função para buscar estabelecimentos em uma cidade
def buscar_estabelecimentos(cidade, tipo_estabelecimento, limit=None, progress_cb=None, should_cancel=None, return_dicts=False):
    """
    Busca estabelecimentos no Google Maps.
    :param cidade: Cidade para busca.
    :param tipo_estabelecimento: Tipo de estabelecimento.
    :param limit: Limite máximo de resultados (None para ilimitado).
    :param progress_cb: Callback opcional para progresso (recebe contagem atual e limite).
    :param should_cancel: Callback opcional para cancelamento (retorna True para cancelar).
    :param return_dicts: Se True, retorna lista de dicts; caso contrário, lista de listas compatível com SQLite.
    """
    url_base = "https://www.google.com/maps"
    driver.get(url_base)

    # Aguarda o campo de busca aparecer e faz a busca pela cidade e o tipo de estabelecimento
    search_box = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, "//input[@id='searchboxinput']"))
    )
    search_box.clear()
    search_box.send_keys(f"{tipo_estabelecimento} em {cidade}")
    search_box.send_keys(Keys.RETURN)

    time.sleep(3)  # Aguarda a página carregar os resultados

    estabelecimentos = []
    collected_count = 0
    if isinstance(limit, int) and limit <= 0:
        limit = None
    scroll_pause_time = 2  # Tempo de pausa para carregamento dos resultados
    prev_height = 0

    while True:
        try:
            if should_cancel and should_cancel():
                return estabelecimentos
            # Encontra os resultados listados na página
            elementos = driver.find_elements(By.CLASS_NAME, "Nv2PK")
            if not elementos:
                break
            for elem in elementos[prev_height:]:
                try:
                    if should_cancel and should_cancel():
                        return estabelecimentos
                    elem.click()
                    time.sleep(1)
                    endereco = ''
                    phone = ''
                    website = ''
                    ifood = ''
                    menu = ''
                    nome = driver.find_element(By.CLASS_NAME, "DUwDvf").text
                    maps_url = driver.current_url
                    infos = driver.find_elements(By.CLASS_NAME, "AeaXub")
                    for info in infos:
                        span = info.find_element(By.TAG_NAME, "span").text
                        if span == '\ue0c8':
                            endereco = info.text
                        elif span == '\ue558':
                            ifood = info.text
                        elif span == '\ue0b0':
                            phone = info.text
                        elif span == '\ue561':
                            menu = info.text
                        elif span == '\ue80b':
                            website = info.text

                    if return_dicts:
                        estabelecimentos.append({
                            "city": cidade,
                            "query": tipo_estabelecimento,
                            "name": nome,
                            "address": endereco,
                            "delivery": ifood,
                            "phone": phone,
                            "menu": menu,
                            "website": website,
                            "maps_url": maps_url,
                        })
                    else:
                        estabelecimentos.append([cidade, tipo_estabelecimento, nome, endereco, ifood, phone, menu, website])

                    collected_count += 1
                    if progress_cb:
                        progress_cb(collected_count, limit)
                    if limit and collected_count >= limit:
                        return estabelecimentos
                except Exception as e:
                    print(f"Erro ao extrair dados: {e}")
            
            # Simula a rolagem até o final da página
            driver.execute_script("arguments[0].scrollIntoView();", elementos[-1])
            time.sleep(scroll_pause_time)

            # Verifica se a rolagem parou (ou seja, todos os resultados foram carregados)
            if len(elementos) == prev_height:
                break
            prev_height = len(elementos)
        except Exception as e:
            print(f"Erro ao carregar resultados adicionais: {e}")
            break

    return estabelecimentos




def visualizar_dados():
    arquivo_excel = "estabelecimentos.xlsx"
    if os.path.exists(arquivo_excel):
        try:
            df = pd.read_excel(arquivo_excel)

            # Formatar os dados
            df = formatar_dados(df)
            
            # Permitir que o usuário selecione colunas
            colunas_selecionadas = selecionar_colunas(df)
            
            # Exibir os dados com tabulate
            print("\n=== Dados Salvos ===")
            print(tabulate(df[colunas_selecionadas], headers="keys", tablefmt="fancy_grid", showindex=False))
        except Exception as e:
            print(f"Erro ao ler o arquivo: {e}")
    else:
        print("\nNenhum arquivo de dados encontrado. Realize uma pesquisa primeiro.")
    input("\nPressione Enter para voltar ao menu.")
    


def search():
    
    # Perguntar ao usuário as cidades e o tipo de estabelecimento
    cidades = input("Digite as cidades que deseja pesquisar, separadas por vírgula: ").split(",")
    tipo_estabelecimento = input("Digite o tipo de estabelecimento que deseja pesquisar (ex: pizzarias, restaurantes, etc.): ").strip()

    # Coleta os dados de cada cidade
    dados_completos = []
    for cidade in cidades:
        cidade = cidade.strip()  # Remove espaços extras
        dados_cidade = buscar_estabelecimentos(cidade, tipo_estabelecimento)
        dados_completos.extend(dados_cidade)

  

    # Salvar no banco
    salvar_dados_no_banco(dados_completos)
    
    print("\nDados coletados e salvos com sucesso.")
    input("\nPressione Enter para voltar ao menu.")
