from playwright.sync_api import Playwright, sync_playwright, expect
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
    return 0




def wait_for_text_data(element, max_attempts):
    attempts = 0
    while element.all_inner_texts() == []:
        if attempts == max_attempts:
            return 0
        time.sleep(1)
        attempts += 1
    return 1




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
    if not menu_items_list:
        return 0
    
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
    # Generating dataframe from collected data
    data = {"nome_item":names_lst,
            "descricao":details_lst,
            "pessoas_servidas":info_serves_lst,
            "peso_tamanho_porcao":info_weight_lst,
            "preco_com_desconto":discounted_price_lst,
            "preco_original":original_price_lst}
    df_menu = pd.DataFrame(data)
    return df_menu




def fetch_restaurants_url(soup):
    with open("casa_de_sucos.txt", "w+") as f:
        f.write(soup.prettify())
    search_word_restaurants_urls = []
    all_restaurants = soup.find_all("div", attrs={"class":"merchant-list-v2__item-wrapper"})
    for restaurant in all_restaurants:
        description = find_element_text(restaurant, tag="div", attrs={"class":"merchant-v2__info"})
        if search_word in description:
            url = "https://www.ifood.com.br" + restaurant.find("a").get("href")
            search_word_restaurants_urls.append(url)
    return search_word_restaurants_urls




def collect_search_word(playwright: Playwright, address, search_word) -> None:
    browser = playwright.chromium.launch(headless=False)
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    context = browser.new_context(user_agent=user_agent, geolocation={"latitude":-19.860570990751865,"longitude":-43.967757361113414}, locale="pt-BR", permissions=["geolocation"], timezone_id="Brazil/East")
    page = context.new_page()
    # Enter website
    page.goto("https://www.ifood.com.br/")
    # Searching Address
    page.get_by_placeholder("Em qual endereço você está?").click()
    page.get_by_role("button", name="Buscar endereço e número").click()
    page.get_by_role("textbox", name="Buscar endereço e número").fill(address)

    # Clicking first address option
    address_search_list = page.locator("[class=\"address-search-list\"]").get_by_role("button")
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

    # Wait until "Ver Mais" Button Shows up
    page.get_by_text("Ver Mais").is_visible()

    # Waiting for restaurant data to load up
    restaurants_elements_list = page.locator("[class=\"merchant-list-v2\"]")
    wait_for_element(restaurants_elements_list)
    for i in range(0, restaurants_elements_list.count()):
        if not wait_for_text_data(restaurants_elements_list.nth(i), max_attempts=5):
            print(f"No restaurants with search word: {search_word}...")
            print(f"Element: {restaurants_elements_list.nth(i)}")
            return 0
    
    menu_html = ""
    # This ensures we fetch all the HTML from open AND closed restaurants if the page loads differently
    for index in range(0, restaurants_elements_list.count()):
        menu_html += restaurants_elements_list.nth(index).inner_html()

    soup = BeautifulSoup(menu_html, "html.parser")
    # Finding all URLs that have the search word category
    search_word_restaurants_urls = fetch_restaurants_url(soup)
    if not search_word_restaurants_urls:
        print(f"No restaurants with search word: {search_word}...")

    # Starting to collect menus
    df_lst = []
    count_restaurants = 0
    for i, url in enumerate(search_word_restaurants_urls):
        if count_restaurants >= 10:
            break
        # This will always work, as i goes up to number of elements found in search_word_restaurants_urls
        page.goto(url)
        # Waiting for restaurant data to load up
        # Ensuring we wait for text data for at least 5 seconds
        dish_card_wrapper = page.locator("[class=\"dish-card-wrapper\"]")
        wait_for_element(dish_card_wrapper)
        if not wait_for_text_data(dish_card_wrapper, max_attempts=5):
            print(f"Could not fetch menu from {url.split("/")[-2]}...")
            continue

        # Fetching restaurant name after the whole page loaded
        restaurant_name = page.locator("[class=\"merchant-info__title\"]").inner_text()
        print(f"Collecting restaurant {count_restaurants+1}: {restaurant_name}...")

        menu_wrapper = page.locator("[class=\"restaurant__fast-menu\"]")
        menu_html = menu_wrapper.inner_html()
        soup = BeautifulSoup(menu_html, "html.parser")
        df_menu = fetch_restaurant_menu(soup)

        # If the tab is not restaurant like (Supermarket/Beverages, etc)
        if isinstance(df_menu, int):
            print("This is not a restaurant...")
            continue

        # Adding Restaurant Name and Searchword to the DataFrame
        df_menu.insert(loc=0, column='palavra_chave', value=search_word)
        df_menu.insert(loc=0, column='nome_restaurante', value=restaurant_name)
        df_lst.append(df_menu)
        count_restaurants += 1
        # Delay between collecting menus
        time.sleep(20)
    # ---------------------
    context.close()
    browser.close()

    # When no restaurants have been found
    if not df_lst:
        print(f"No restaurants with valid menu found for search word: {search_word}!!")
        return 0
    # If we have found restaurants
    df = pd.concat(df_lst)
    # Checking if some searchword has skipped a restaurant from its list
    if len(df['nome_restaurante'].unique()) != len(search_word_restaurants_urls):
        with open("possible_search_word_problems.txt", "w+") as f:
            f.write(search_word)
    # Outputting file to a folder where we use as backup, so if we get IP blocked, we do not lose all progress
    file_path = f"outputs/coleta-menus-{search_word}-{dt.datetime.today().strftime("%d-%m-%Y")}.xlsx"
    df.to_excel(file_path)
    return df




def generate_final_spreadsheet():
    # Fetching all backups into a file
    df_lst = []
    directory = "outputs"
    for file in os.listdir(directory):
        f = os.path.join(directory, file)
        # checking if it is a file
        if os.path.isfile(f):
            df_lst.append(pd.read_excel(f))

    if not df_lst:
        raise Exception("No backup collected files!")
    
    file_path = f"coleta-menus-{dt.datetime.today().strftime("%d-%m-%Y")}.xlsx"
    # Concatenating all data and deleting "Unnamed: 0" column
    df_complete = pd.concat(df_lst).iloc[:,1:]
    df_complete.to_excel(file_path, sheet_name="dados-menu-restaurantes", index=False)

    # Parsing workbook with Fiter on Header
    wb = load_workbook(file_path)
    ws = wb.active
    # Setting Filters
    ws.auto_filter.ref = ws.dimensions
    wb.save(file_path)
    wb.close()
    print("Scraping has been successful!")


# search_words.txt subtitles
# n -> not collected
# d -> done
# f -> yields no restaurants
with sync_playwright() as playwright:
    address = "Avenida João Pinheiro, 100. Centro - Belo Horizonte"
    with open("search_words.txt", "r", encoding="utf-8") as f:
        search_words = f.read().splitlines()
    # Skipping those already collected
    search_word = [word for word in search_words if ":n" in word]
    for index, search_word in enumerate(search_words):
        search_word = search_word[:-2] # Ignoring the "collected tag" (which shows wether we should collect this keyword or not), it helps with backup
        print(f"Collecting search word: {search_word}")
        df_search_word = collect_search_word(playwright, address, search_word)
        if isinstance(df_search_word, pd.DataFrame):
            search_words[index] = search_word + ":d" # Setting "collected tag" as "d" for Done (to not collect after it something goes wrong)
            # Writing back to the text file so we can save the collect progress
            with open("search_words.txt", "w+", encoding="utf-8") as f:
                f.write("\n".join(search_words))
            print(f"Finished collecting search word: {search_word}")
        elif isinstance(df_search_word, int):
            search_words[index] = search_word + ":f" # Setting "collected tag" as "d" for Done (to not collect after it something goes wrong)
            # Writing back to the text file so we can tag "no restaurants" search words
            with open("search_words.txt", "w+", encoding="utf-8") as f:
                f.write("\n".join(search_words))
            print("Moving to the next search word, as the current search word yields no restaurants...")
        # Sleeping for 2 minutes in order to avoid IP block (This feature is optional, but makes things more consistent)
        if index != (len(search_words) - 1):
            time.sleep(120)
    
    # When all scraping part has finished
    generate_final_spreadsheet()