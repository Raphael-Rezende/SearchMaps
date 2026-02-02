
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

import warnings

import time
import os
from datetime import datetime
from urllib.parse import quote_plus
#Manipulação de dados
import pandas as pd
import shutil

from utils import  formatar_dados, selecionar_colunas

from db import salvar_dados_no_banco, listar_dados
from tabulate import tabulate  # Para exibir os dados formatados no terminal

# Suprimir avisos de Deprecation
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Configuração do driver do Selenium
DEBUG = os.getenv("SEARCHMAPS_DEBUG", "").strip().lower() in ("1", "true", "yes", "on")

options = webdriver.ChromeOptions()
if not DEBUG:
    options.add_argument("--headless")  # Executa em modo headless (sem interface gráfica)
options.add_argument("--disable-gpu")
options.add_argument("--window-size=1920,1080")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--lang=pt-BR")
if not DEBUG:
    options.add_argument("--log-level=3")  # Apenas erros
options.add_argument("--no-sandbox")
if not DEBUG:
    options.add_experimental_option("excludeSwitches", ["enable-logging"])  # Remove logs de warning
driver = webdriver.Chrome(options=options) # Suprime logs do driver

def _debug_capture(label):
    if not DEBUG:
        return
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot = f"debug_{label}_{timestamp}.png"
        html = f"debug_{label}_{timestamp}.html"
        driver.save_screenshot(screenshot)
        with open(html, "w", encoding="utf-8") as file:
            file.write(driver.page_source)
        print(f"[DEBUG] Capturado: {screenshot} | {html}")
        print(f"[DEBUG] URL: {driver.current_url}")
    except Exception as exc:
        print(f"[DEBUG] Falha ao capturar debug: {exc}")

def _accept_consent_if_present():
    consent_texts = [
        "Aceitar tudo",
        "Aceitar",
        "Concordo",
        "I agree",
        "Accept all",
        "Agree",
        "Yes, I agree",
    ]

    def try_click_buttons():
        buttons = driver.find_elements(By.TAG_NAME, "button")
        for button in buttons:
            label = f"{button.text} {button.get_attribute('aria-label') or ''}".strip()
            if not label:
                continue
            lower_label = label.lower()
            if any(text.lower() in lower_label for text in consent_texts):
                try:
                    button.click()
                    time.sleep(1)
                    return True
                except Exception:
                    try:
                        driver.execute_script("arguments[0].click();", button)
                        time.sleep(1)
                        return True
                    except Exception:
                        continue
        return False

    if try_click_buttons():
        return True

    iframes = driver.find_elements(By.TAG_NAME, "iframe")
    for iframe in iframes:
        try:
            driver.switch_to.frame(iframe)
            if try_click_buttons():
                driver.switch_to.default_content()
                return True
            driver.switch_to.default_content()
        except Exception:
            driver.switch_to.default_content()
            continue

    return False


def _wait_for_results(timeout=20):
    return WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.CLASS_NAME, "Nv2PK"))
    )

# Função para buscar estabelecimentos em uma cidade
def buscar_estabelecimentos(
    cidade,
    tipo_estabelecimento,
    state=None,
    limit=None,
    progress_cb=None,
    should_cancel=None,
    return_dicts=False,
):
    """
    Busca estabelecimentos no Google Maps.
    :param cidade: Cidade para busca.
    :param tipo_estabelecimento: Tipo de estabelecimento.
    :param state: Estado/UF opcional para refinar a busca.
    :param limit: Limite máximo de resultados (None para ilimitado).
    :param progress_cb: Callback opcional para progresso (recebe contagem atual e limite).
    :param should_cancel: Callback opcional para cancelamento (retorna True para cancelar).
    :param return_dicts: Se True, retorna lista de dicts; caso contrário, lista de listas compatível com SQLite.
    """
    location = cidade
    if state:
        location = f"{cidade}, {state}"

    search_term = f"{tipo_estabelecimento} em {location}"
    search_url = f"https://www.google.com/maps/search/{quote_plus(search_term)}"
    driver.get(search_url)

    _accept_consent_if_present()

    try:
        _wait_for_results(timeout=20)
    except TimeoutException:
        # Fallback: tenta usar o campo de busca manualmente
        try:
            search_box = WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.XPATH, "//input[@id='searchboxinput']"))
            )
            search_box.clear()
            search_box.send_keys(search_term)
            search_box.send_keys(Keys.RETURN)
            time.sleep(3)
        except TimeoutException:
            _debug_capture("timeout_search")
            raise

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
            _debug_capture("loop_error")
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
