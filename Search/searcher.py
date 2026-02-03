from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    StaleElementReferenceException,
    WebDriverException,
    NoSuchElementException,
)

import warnings

import time
import os
import random
import re
from datetime import datetime
from urllib.parse import quote_plus, urlsplit, parse_qs, urlunsplit

import pandas as pd

from utils import formatar_dados, selecionar_colunas

from db import salvar_dados_no_banco
from tabulate import tabulate  # Para exibir os dados formatados no terminal

# Suprimir avisos de Deprecation
warnings.filterwarnings("ignore", category=DeprecationWarning)

DEBUG = os.getenv("SEARCHMAPS_DEBUG", "").strip().lower() in ("1", "true", "yes", "on")

DEFAULT_MAX_LIMIT = int(os.getenv("SEARCHMAPS_MAX_LIMIT", "200"))
SCROLL_MAX_TRIES = int(os.getenv("SEARCHMAPS_SCROLL_MAX_TRIES", "60"))
SCROLL_STALL_TRIES = int(os.getenv("SEARCHMAPS_SCROLL_STALL_TRIES", "8"))
BACKOFF_SECONDS = float(os.getenv("SEARCHMAPS_BACKOFF_SECONDS", "6"))
DEFAULT_TIMEOUT = int(os.getenv("SEARCHMAPS_TIMEOUT", "40"))

_DRIVER = None
_DRIVER_HEADLESS = None


def _create_driver(headless: bool) -> webdriver.Chrome:
    options = webdriver.ChromeOptions()
    effective_headless = headless and not DEBUG
    if effective_headless:
        options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--lang=pt-BR")
    options.add_argument("--no-sandbox")
    if not DEBUG:
        options.add_argument("--log-level=3")  # Apenas erros
        options.add_experimental_option("excludeSwitches", ["enable-logging"])  # Remove logs de warning
    return webdriver.Chrome(options=options)


def _get_driver(headless: bool = True) -> webdriver.Chrome:
    global _DRIVER
    global _DRIVER_HEADLESS

    effective_headless = headless and not DEBUG

    if _DRIVER is None or _DRIVER_HEADLESS != effective_headless:
        if _DRIVER is not None:
            try:
                _DRIVER.quit()
            except Exception:
                pass
        _DRIVER = _create_driver(headless=effective_headless)
        _DRIVER_HEADLESS = effective_headless
    return _DRIVER


def _human_delay(min_seconds: float = 0.8, max_seconds: float = 2.2) -> None:
    time.sleep(random.uniform(min_seconds, max_seconds))


def _debug_capture(driver: webdriver.Chrome, label: str) -> None:
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


def _normalize_limit(limit):
    if limit is None:
        return DEFAULT_MAX_LIMIT
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        return DEFAULT_MAX_LIMIT
    if limit <= 0:
        return DEFAULT_MAX_LIMIT
    return min(limit, DEFAULT_MAX_LIMIT)


def _normalize_text(value: str) -> str:
    if not value:
        return ""
    value = value.strip().lower()
    value = re.sub(r"\s+", " ", value)
    return value


def _normalize_place_url(url: str) -> str:
    if not url:
        return ""
    parts = urlsplit(url)
    query = parse_qs(parts.query)
    if "place_id" in query and query["place_id"]:
        return f"place_id:{query['place_id'][0]}"
    if "cid" in query and query["cid"]:
        return f"cid:{query['cid'][0]}"
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def _extract_place_id_from_url(url: str) -> str:
    if not url:
        return ""
    parts = urlsplit(url)
    query = parse_qs(parts.query)
    if "place_id" in query and query["place_id"]:
        return query["place_id"][0]
    if "cid" in query and query["cid"]:
        return query["cid"][0]
    match = re.search(r"!1s([^!]+)", url)
    if match:
        return match.group(1)
    return ""


def _build_listing_key(item: dict) -> str:
    place_id = (item or {}).get("place_id") or ""
    if place_id:
        return f"place_id:{place_id}"
    cid = (item or {}).get("cid") or ""
    if cid:
        return f"cid:{cid}"
    url_key = _normalize_place_url((item or {}).get("place_url"))
    if url_key:
        return f"url:{url_key}"
    name = _normalize_text((item or {}).get("title"))
    address = _normalize_text((item or {}).get("address"))
    if name and address:
        return f"name_addr:{name}|{address}"
    return ""


def _build_final_key(item: dict) -> str:
    place_id = (item or {}).get("place_id") or ""
    if place_id:
        return f"place_id:{place_id}"
    url_key = _normalize_place_url((item or {}).get("maps_url") or (item or {}).get("place_url"))
    if url_key:
        return f"url:{url_key}"
    name = _normalize_text((item or {}).get("name"))
    address = _normalize_text((item or {}).get("address"))
    if name and address:
        return f"name_addr:{name}|{address}"
    return ""


def _try_click_buttons(driver: webdriver.Chrome, label_options) -> bool:
    buttons = driver.find_elements(By.CSS_SELECTOR, "button, div[role='button']")
    for button in buttons:
        label = f"{button.text} {button.get_attribute('aria-label') or ''}".strip()
        if not label:
            continue
        lower_label = label.lower()
        if any(text in lower_label for text in label_options):
            try:
                button.click()
                time.sleep(0.5)
                return True
            except Exception:
                try:
                    driver.execute_script("arguments[0].click();", button)
                    time.sleep(0.5)
                    return True
                except Exception:
                    continue
    return False


def _accept_consent_if_present(driver: webdriver.Chrome) -> bool:
    accept_texts = [
        "aceitar tudo",
        "aceitar",
        "concordo",
        "i agree",
        "accept all",
        "agree",
        "yes, i agree",
    ]
    reject_texts = [
        "rejeitar tudo",
        "rejeitar",
        "recusar",
        "reject all",
        "reject",
        "disagree",
    ]

    if _try_click_buttons(driver, accept_texts):
        return True
    if _try_click_buttons(driver, reject_texts):
        return True

    iframes = driver.find_elements(By.TAG_NAME, "iframe")
    for iframe in iframes:
        try:
            driver.switch_to.frame(iframe)
            if _try_click_buttons(driver, accept_texts) or _try_click_buttons(driver, reject_texts):
                driver.switch_to.default_content()
                return True
            driver.switch_to.default_content()
        except Exception:
            driver.switch_to.default_content()
            continue

    return False


def _dismiss_popups(driver: webdriver.Chrome) -> bool:
    if _accept_consent_if_present(driver):
        return True

    close_texts = [
        "fechar",
        "close",
        "not now",
        "agora nao",
        "dismiss",
    ]
    return _try_click_buttons(driver, close_texts)


def _wait_for_results(driver: webdriver.Chrome, timeout: int = DEFAULT_TIMEOUT) -> bool:
    def _ready(drv):
        if drv.find_elements(By.CSS_SELECTOR, "div.Nv2PK"):
            return True
        if drv.find_elements(By.CSS_SELECTOR, "h1.DUwDvf, h1.fontHeadlineLarge"):
            return True
        return False

    return WebDriverWait(driver, timeout).until(_ready)


def _fallback_search_box(driver: webdriver.Chrome, search_term: str) -> None:
    try:
        search_box = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.XPATH, "//input[@id='searchboxinput']"))
        )
        search_box.clear()
        search_box.send_keys(search_term)
        search_box.send_keys(Keys.RETURN)
        _human_delay(1.0, 2.0)
    except TimeoutException:
        _debug_capture(driver, "timeout_search")
        raise


def _find_results_container(driver: webdriver.Chrome, timeout: int = DEFAULT_TIMEOUT):
    # DOM sensível: o painel de resultados varia, mas normalmente tem role='feed'.
    selectors = [
        "div[role='feed']",
        "div[aria-label*='Resultados'] div[role='feed']",
        "div[aria-label*='Results'] div[role='feed']",
        "div[aria-label*='Search results'] div[role='feed']",
        "div.m6QErb.DxyBCb.kA9KIf.dS8AEf",
    ]

    end_time = time.time() + timeout
    while time.time() < end_time:
        for selector in selectors:
            containers = driver.find_elements(By.CSS_SELECTOR, selector)
            for container in containers:
                try:
                    if container.is_displayed() and container.find_elements(By.CSS_SELECTOR, "div.Nv2PK"):
                        return container
                except StaleElementReferenceException:
                    continue
        time.sleep(0.5)

    return None


def _find_result_cards(driver: webdriver.Chrome):
    return driver.find_elements(By.CSS_SELECTOR, "div.Nv2PK")


def _extract_listing_from_card(card):
    try:
        title = ""
        raw_text = card.text.strip()
        if raw_text:
            title = raw_text.split("\n")[0].strip()

        place_url = ""
        link = None
        for selector in [
            "a.hfpxzc",
            "a[href*='/maps/place/']",
            "a[href*='google.com/maps/place']",
        ]:
            links = card.find_elements(By.CSS_SELECTOR, selector)
            if links:
                link = links[0]
                break
        if link is not None:
            place_url = link.get_attribute("href") or ""

        place_id = card.get_attribute("data-place-id") or ""
        cid = card.get_attribute("data-cid") or ""
        if not place_id and place_url:
            place_id = _extract_place_id_from_url(place_url)

        return {
            "title": title,
            "place_url": place_url,
            "place_id": place_id,
            "cid": cid,
        }
    except StaleElementReferenceException:
        return None


def _get_last_card_key(cards) -> str:
    if not cards:
        return ""
    item = _extract_listing_from_card(cards[-1])
    if not item:
        return ""
    return _build_listing_key(item) or _normalize_text(item.get("title"))


def _scroll_results_panel(driver: webdriver.Chrome, container) -> bool:
    if container is None:
        return False
    try:
        driver.execute_script(
            "const c = arguments[0]; c.scrollTop = c.scrollTop + (c.clientHeight * 0.8); return c.scrollTop;",
            container,
        )
        return True
    except StaleElementReferenceException:
        return False


def _wait_for_results_update(
    driver: webdriver.Chrome,
    previous_count: int,
    previous_last_key: str,
    timeout: int = 8,
) -> bool:
    end_time = time.time() + timeout
    while time.time() < end_time:
        cards = _find_result_cards(driver)
        if len(cards) > previous_count:
            return True
        current_last = _get_last_card_key(cards)
        if previous_last_key and current_last and current_last != previous_last_key:
            return True
        time.sleep(0.4)
    return False


def _has_end_of_list_marker(driver: webdriver.Chrome) -> bool:
    # DOM sensível: o texto varia por idioma e por layout.
    end_texts = [
        "Você chegou ao fim da lista",
        "Fim dos resultados",
        "Não há mais resultados",
        "You've reached the end of the list",
        "End of list",
        "No more results",
    ]
    for text in end_texts:
        try:
            if driver.find_elements(By.XPATH, f"//*[contains(text(), '{text}')]"):
                return True
        except Exception:
            continue
    return False


def _is_place_details_view(driver: webdriver.Chrome) -> bool:
    return bool(driver.find_elements(By.CSS_SELECTOR, "h1.DUwDvf, h1.fontHeadlineLarge"))


def _get_place_title(driver: webdriver.Chrome, timeout: int = DEFAULT_TIMEOUT) -> str:
    # DOM sensível: o seletor do título muda com frequência.
    try:
        elem = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "h1.DUwDvf, h1.fontHeadlineLarge"))
        )
        return elem.text.strip()
    except TimeoutException:
        return ""


def _get_item_text(driver: webdriver.Chrome, selectors, prefer_href: bool = False) -> str:
    for selector in selectors:
        try:
            element = driver.find_element(By.CSS_SELECTOR, selector)
        except NoSuchElementException:
            continue
        except StaleElementReferenceException:
            continue

        try:
            if prefer_href:
                href = element.get_attribute("href")
                if href:
                    return href.strip()
            text = element.text.strip()
            if text:
                return text
            aria = element.get_attribute("aria-label")
            if aria:
                return aria.strip()
        except StaleElementReferenceException:
            continue
    return ""


def _extract_legacy_info(driver: webdriver.Chrome):
    address = ""
    phone = ""
    website = ""
    menu = ""
    delivery = ""

    # DOM sensível: ícones de mapas usam glifos internos.
    infos = driver.find_elements(By.CLASS_NAME, "AeaXub")
    for info in infos:
        try:
            span = info.find_element(By.TAG_NAME, "span").text
        except NoSuchElementException:
            continue
        if span == "\ue0c8":
            address = info.text
        elif span == "\ue558":
            delivery = info.text
        elif span == "\ue0b0":
            phone = info.text
        elif span == "\ue561":
            menu = info.text
        elif span == "\ue80b":
            website = info.text

    return address, phone, website, menu, delivery


def collect_listing_urls(
    limit,
    timeout: int = DEFAULT_TIMEOUT,
    headless: bool = True,
    return_metrics: bool = False,
    should_cancel=None,
):
    driver = _get_driver(headless=headless)
    limit = _normalize_limit(limit)

    metrics = {
        "scroll_attempts": 0,
        "stall_attempts": 0,
        "backoff_count": 0,
        "stop_reason": "",
    }

    container = _find_results_container(driver, timeout=timeout)
    if container is None:
        if _is_place_details_view(driver):
            title = _get_place_title(driver, timeout=timeout)
            single = {
                "title": title,
                "place_url": driver.current_url,
                "place_id": _extract_place_id_from_url(driver.current_url),
                "cid": "",
            }
            metrics["stop_reason"] = "single_place"
            return ( [single], metrics ) if return_metrics else [single]
        metrics["stop_reason"] = "no_results_container"
        return ( [], metrics ) if return_metrics else []

    items = []
    seen = set()

    while len(items) < limit and metrics["scroll_attempts"] < SCROLL_MAX_TRIES:
        if should_cancel and should_cancel():
            metrics["stop_reason"] = "canceled"
            break

        _dismiss_popups(driver)
        cards = _find_result_cards(driver)
        if not cards:
            metrics["stop_reason"] = "no_cards"
            break

        for card in cards:
            if should_cancel and should_cancel():
                metrics["stop_reason"] = "canceled"
                break

            item = _extract_listing_from_card(card)
            if not item:
                continue
            if not item.get("place_url"):
                continue

            key = _build_listing_key(item)
            if key and key in seen:
                continue
            if key:
                seen.add(key)

            items.append(item)
            if len(items) >= limit:
                break

        if len(items) >= limit:
            metrics["stop_reason"] = "limit"
            break

        previous_count = len(cards)
        previous_last_key = _get_last_card_key(cards)

        if not _scroll_results_panel(driver, container):
            container = _find_results_container(driver, timeout=5)
            if container is None:
                metrics["stop_reason"] = "container_lost"
                break

        metrics["scroll_attempts"] += 1
        _human_delay()

        changed = _wait_for_results_update(driver, previous_count, previous_last_key)
        if not changed:
            metrics["stall_attempts"] += 1
        else:
            metrics["stall_attempts"] = 0

        if metrics["stall_attempts"] >= SCROLL_STALL_TRIES:
            if _has_end_of_list_marker(driver):
                metrics["stop_reason"] = "end_marker"
                break
            metrics["backoff_count"] += 1
            time.sleep(BACKOFF_SECONDS)
            metrics["stall_attempts"] = 0

    if not metrics["stop_reason"]:
        metrics["stop_reason"] = "max_scroll_tries"

    return ( items, metrics ) if return_metrics else items


def extract_place_details(
    place_url: str,
    timeout: int = DEFAULT_TIMEOUT,
    headless: bool = True,
) -> dict:
    driver = _get_driver(headless=headless)
    try:
        driver.get(place_url)
    except WebDriverException:
        return {}

    _accept_consent_if_present(driver)
    _dismiss_popups(driver)

    name = _get_place_title(driver, timeout=timeout)
    maps_url = driver.current_url

    # DOM sensível: dados de contato mudam com frequência.
    address = _get_item_text(
        driver,
        [
            "button[data-item-id='address']",
            "div[data-item-id='address']",
            "button[data-item-id='address'] span",
            "div[data-item-id='address'] span",
        ],
    )
    phone = _get_item_text(
        driver,
        [
            "button[data-item-id='phone']",
            "div[data-item-id='phone']",
            "button[aria-label*='Telefone']",
            "button[aria-label*='Phone']",
        ],
    )
    website = _get_item_text(
        driver,
        [
            "a[data-item-id='authority']",
            "button[data-item-id='authority']",
            "div[data-item-id='authority']",
        ],
        prefer_href=True,
    )
    menu = _get_item_text(
        driver,
        [
            "a[data-item-id='menu']",
            "a[data-item-id='action:menu']",
            "button[data-item-id='menu']",
        ],
        prefer_href=True,
    )
    delivery = _get_item_text(
        driver,
        [
            "a[data-item-id='action:order']",
            "a[data-item-id='action:delivery']",
            "a[data-item-id='action:order-online']",
            "button[data-item-id='action:order']",
        ],
        prefer_href=True,
    )

    legacy_address, legacy_phone, legacy_website, legacy_menu, legacy_delivery = _extract_legacy_info(driver)
    if not address:
        address = legacy_address
    if not phone:
        phone = legacy_phone
    if not website:
        website = legacy_website
    if not menu:
        menu = legacy_menu
    if not delivery:
        delivery = legacy_delivery

    return {
        "name": name,
        "address": address,
        "delivery": delivery,
        "phone": phone,
        "menu": menu,
        "website": website,
        "maps_url": maps_url,
        "place_id": _extract_place_id_from_url(maps_url),
    }


def search_places(
    city: str,
    query: str,
    limit: int = DEFAULT_MAX_LIMIT,
    timeout: int = DEFAULT_TIMEOUT,
    headless: bool = True,
    progress_cb=None,
    should_cancel=None,
) -> list:
    driver = _get_driver(headless=headless)
    limit = _normalize_limit(limit)

    start_time = time.perf_counter()
    search_term = f"{query} em {city}"
    search_url = f"https://www.google.com/maps/search/{quote_plus(search_term)}"
    driver.get(search_url)

    _accept_consent_if_present(driver)

    try:
        _wait_for_results(driver, timeout=timeout)
    except TimeoutException:
        _fallback_search_box(driver, search_term)
        _wait_for_results(driver, timeout=timeout)

    _human_delay()

    listings, metrics = collect_listing_urls(
        limit=limit,
        timeout=timeout,
        headless=headless,
        return_metrics=True,
        should_cancel=should_cancel,
    )

    print(
        "[SearchMaps] Fase A (lista) concluída | "
        f"itens={len(listings)} | scrolls={metrics['scroll_attempts']} | "
        f"backoffs={metrics['backoff_count']} | motivo={metrics['stop_reason']}"
    )

    results = []
    seen = set()

    for item in listings:
        if should_cancel and should_cancel():
            print("[SearchMaps] Cancelado pelo usuário durante Fase B.")
            break

        place_url = item.get("place_url")
        if not place_url:
            continue

        details = extract_place_details(place_url, timeout=timeout, headless=headless)
        merged = {
            "city": city,
            "query": query,
            "name": details.get("name") or item.get("title") or "",
            "address": details.get("address") or "",
            "delivery": details.get("delivery") or "",
            "phone": details.get("phone") or "",
            "menu": details.get("menu") or "",
            "website": details.get("website") or "",
            "maps_url": details.get("maps_url") or place_url,
            "place_id": details.get("place_id") or item.get("place_id") or item.get("cid") or "",
            "place_url": place_url,
        }

        key = _build_final_key(merged)
        if key and key in seen:
            continue
        if key:
            seen.add(key)

        results.append(merged)
        if progress_cb:
            progress_cb(len(results), limit)

        _human_delay()

        if limit and len(results) >= limit:
            break

    elapsed = time.perf_counter() - start_time
    print(
        "[SearchMaps] Fase B (detalhes) concluída | "
        f"detalhados={len(results)}/{len(listings)} | tempo_total={elapsed:.1f}s"
    )

    return results


# Função para buscar estabelecimentos em uma cidade
def buscar_estabelecimentos(
    cidade,
    tipo_estabelecimento,
    state=None,
    limit=None,
    progress_cb=None,
    should_cancel=None,
    return_dicts=False,
    headless=True,
):
    """
    Busca estabelecimentos no Google Maps.
    :param cidade: Cidade para busca.
    :param tipo_estabelecimento: Tipo de estabelecimento.
    :param state: Estado/UF opcional para refinar a busca.
    :param limit: Limite máximo de resultados.
    :param progress_cb: Callback opcional para progresso (recebe contagem atual e limite).
    :param should_cancel: Callback opcional para cancelamento (retorna True para cancelar).
    :param return_dicts: Se True, retorna lista de dicts; caso contrário, lista de listas compatível com SQLite.
    :param headless: Se False, abre o Chrome visível (ignorado quando SEARCHMAPS_DEBUG está ativo).
    """
    location = cidade
    if state:
        location = f"{cidade}, {state}"

    results = search_places(
        city=location,
        query=tipo_estabelecimento,
        limit=limit,
        timeout=DEFAULT_TIMEOUT,
        headless=headless,
        progress_cb=progress_cb,
        should_cancel=should_cancel,
    )

    if return_dicts:
        for item in results:
            item["city"] = cidade
            item["query"] = tipo_estabelecimento
        return results

    estabelecimentos = []
    for item in results:
        estabelecimentos.append(
            [
                cidade,
                tipo_estabelecimento,
                item.get("name", ""),
                item.get("address", ""),
                item.get("delivery", ""),
                item.get("phone", ""),
                item.get("menu", ""),
                item.get("website", ""),
            ]
        )

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
    tipo_estabelecimento = input(
        "Digite o tipo de estabelecimento que deseja pesquisar (ex: pizzarias, restaurantes, etc.): "
    ).strip()

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
