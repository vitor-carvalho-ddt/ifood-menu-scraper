from playwright.sync_api import Playwright, sync_playwright
from openpyxl import load_workbook
from bs4 import BeautifulSoup
import datetime as dt
import pandas as pd
import time
import re
import os
## TEST RUN LINE ON BASH:
## ALL THIS DATA IS REGARDING BELO HORIZONTE - MG
## GEOLOCATION IS REGARDING - Federal University of Minas Gerais (UFMG)
## ONLY USE codegen IF YOU WANT TO GENERATE THE CODE USING PLAYWRIGHT
## PASS THE URL AS LAST ARGUMENT
## playwright codegen --timezone="Brazil/East" --geolocation="-19.870570990751865, -43.967757361113414" --lang="pt-BR" "https://www.ifood.com.br/"

## Function to await for element up to a gicen time
def wait_for_element(element, timer=20):
    time.sleep(1)
    for i in range(1, timer):
        time.sleep(1)
        if element.count() > 0:
            return 1
    raise Exception(f"Element {element} not found!")

def parse_prices(price):
    if price != "-":
        prices_list = re.findall(r'[0-9]+[\.\,][0-9]+', price)
        if prices_list:
            price = prices_list[0].strip().replace(",", ".")
            return float(price)
    return price

def find_element_text(item, tag, attrs):
    if item.find(tag, attrs=attrs):
        texts = item.find(tag, attrs=attrs).find_all(string=True, recursive=False)
        if texts:
            return texts[0]
    return "-"

def fetch_restaurant_menu(soup):
    menu_items_list = soup.find_all("div", attrs={"class":"dish-card-wrapper"})
    names_lst = []
    details_lst = []
    info_serves_lst = []
    info_weight_lst = []
    discounted_price_lst = []
    original_price_lst = []

    for item in menu_items_list:
        name = find_element_text(item, tag="h3", attrs={"class":"dish-card__description"})
        details = find_element_text(item, tag="span", attrs={"class":"dish-card__details"})
        info_serves = find_element_text(item, tag="span", attrs={"class":"dish-info-serves__title"})
        info_weight = find_element_text(item, tag="span", attrs={"class":"dish-info-weight__title"})
        discounted_price = find_element_text(item, tag="span", attrs={"class":"dish-card__price--discount"})
        if discounted_price != "-":
            original_price = find_element_text(item, tag="span", attrs={"class":"dish-card__price--original"})
        else:
            original_price = find_element_text(item, tag="span", attrs={"class":"dish-card__price"})

        # Parsing prices
        discounted_price = parse_prices(discounted_price)
        original_price = parse_prices(original_price)

        names_lst.append(name)
        details_lst.append(details)
        info_serves_lst.append(info_serves)
        info_weight_lst.append(info_weight)
        discounted_price_lst.append(discounted_price)
        original_price_lst.append(original_price)

    print(f"Collected {len(menu_items_list)} items...")
    
    data = {"nome_item":names_lst,
            "descricao":details_lst,
            "pessoas_servidas":info_serves_lst,
            "peso_tamanho_porcao":info_weight_lst,
            "preco_com_desconto":discounted_price_lst,
            "preco_original":original_price_lst}
    df_menu = pd.DataFrame(data)
    return df_menu

def run(playwright: Playwright, address, search_word) -> None:
    browser = playwright.chromium.launch(headless=False)
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    context = browser.new_context(user_agent=user_agent, geolocation={"latitude":-19.890570990751865,"longitude":-43.997757361113414}, locale="pt-BR", permissions=["geolocation"], timezone_id="Brazil/East")
    page = context.new_page()
    # Enter website
    page.goto("https://www.ifood.com.br/")
    # Searching Address
    page.get_by_placeholder("Em qual endereço você está?").click()
    page.get_by_role("button", name="Buscar endereço e número").click()
    page.get_by_role("textbox", name="Buscar endereço e número").fill(address)

    # Clicking first address option
    address_search_list = page.locator("[class=\"address-search-list\"]").get_by_role("button")
    wait_for_element(address_search_list)
    address_search_list.nth(0).click()

    # Confirming address
    page.get_by_role("button", name="Confirmar localização").click()
    page.get_by_role("button", name="Salvar endereço").click()

    # Entering Restaurants tab
    page.get_by_role("link", name="Restaurantes").click()

    # Filling Search Word
    page.locator("[data-test-id=\"search-input-field\"]").click()
    page.locator("[data-test-id=\"search-input-field\"]").fill(search_word)
    page.locator("[data-test-id=\"search-input-field\"]").press("Enter")

    # Waiting for restaurants to load up
    restaurants_elements_list = page.locator("[class=\"merchant-list-v2__item-wrapper\"]")
    wait_for_element(restaurants_elements_list)

    # Saving search URL
    saved_search_url = page.url

    # Starting to collect menus
    df_lst = []
    for i in range(0, restaurants_elements_list.count()):
        print(f"Collecting restaurant {i+1}...")
        # Only collecting first 10 restaurants
        if i>=10:
            break

        elements = page.locator("[class=\"merchant-list-v2__item-wrapper\"]")
        wait_for_element(elements)
        ele = elements.nth(i)

        restaurant_name = ele.locator("[class=\"merchant-v2__name\"]").inner_text() if ele.locator("[class=\"merchant-v2__name\"]").count() > 0 else "-"
        ele.click()
        # Fetching HTML
        restaurant_menu_wrapper = page.locator("[class=\"restaurant__fast-menu\"]")
        dish_wrapper = restaurant_menu_wrapper.locator("[class=\"dish-card-wrapper\"]")
        wait_for_element(dish_wrapper)
        menu_html = restaurant_menu_wrapper.inner_html()
        # Fetching Menu
        soup = BeautifulSoup(menu_html, "html.parser")
        df_menu = fetch_restaurant_menu(soup)
        # Adding Restaurant Name and Searchword to the DataFrame
        df_menu.insert(loc=0, column='nome_restaurante', value=restaurant_name)
        df_menu.insert(loc=1, column='palavra_chave', value=search_word)
        df_lst.append(df_menu)
        # Returning to the Search Page (Restaurants)
        page.goto(saved_search_url)    

    # ---------------------
    context.close()
    browser.close()

    df = pd.concat(df_lst)
    # Outputting file to a folder where we use as backup, so if we get IP blocked, we do not lose all progress
    file_path = f"outputs/coleta-menus-{search_word}-{dt.datetime.today().strftime("%d-%m-%Y")}.xlsx"
    df.to_excel(file_path)
    return df


with sync_playwright() as playwright:
    max_restaurants = 10
    address = "Avenida João Pinheiro, 100. Centro - Belo Horizonte"

    with open("search_words.txt", "r", encoding="utf-8") as f:
        search_words = f.read().splitlines()

    for index, search_word in enumerate(search_words):
        # Skipping those already collected
        if ":d" in search_word:
            continue
        # Only collecting first 10 restaurants
        search_word = search_word[:-2] # Ignoring the "collected tag" (which shows wether we should collect this keyword or not), it helps with backup
        if index < max_restaurants:
            print(f"Collecting search word: {search_word}")
            df_search_word = run(playwright, address, search_word)
            if isinstance(df_search_word, pd.DataFrame):
                search_words[index] = search_word + ":d" # Setting "collected tag" as "d" for Done (to not collect after it something goes wrong)
                # Writing back to the text file so we can save the collect progress
                with open("search_words.txt", "w+", encoding="utf-8") as f:
                    f.write("\n".join(search_words))
                print(f"Finished collecting search word: {search_word}")
    
    # Fetching all backups into a file
    df_lst = []
    directory = "outputs"
    for file in os.listdir():
        f = os.path.join(directory, file)
        # checking if it is a file
        if os.path.isfile(f):
            df_lst.append(pd.read_excel(f))

    if not df_lst:
        raise Exception("No backup collected files!")
    
    file_path = f"coleta-menus-{dt.datetime.today().strftime("%d-%m-%Y")}.xlsx"
    df_complete = pd.concat(df_lst)
    df_complete.to_excel(file_path, sheet_name="dados-menu-restaurantes", index=False)

    # Parsing workbook with Fiter on Header
    wb = load_workbook(file_path)
    ws = wb.active
    # Setting Filters
    ws.auto_filter.ref = ws.dimensions
    wb.save(file_path)
    wb.close()
    print("Scraping has been successful!")