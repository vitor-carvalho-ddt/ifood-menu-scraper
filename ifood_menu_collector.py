import re
from playwright.sync_api import Playwright, Page, sync_playwright, expect
from bs4 import BeautifulSoup
import time
import pandas as pd
## TEST RUN LINE ON BASH:
## ALL THIS DATA IS REGARDING BELO HORIZONTE - MG
## GEOLOCATION IS REGARDING - Federal University of Minas Gerais (UFMG)
## ONLY USE codegen IF YOU WANT TO GENERATE THE CODE USING PLAYWRIGHT
## PASS THE URL AS LAST ARGUMENT
## playwright codegen --timezone="Brazil/East" --geolocation="-19.870570990751865, -43.967757361113414" --lang="pt-BR" "https://www.ifood.com.br/"

## Function to await for element up to a gicen time
def wait_for_element(element, timer=20):
    for i in range(1, timer):
        time.sleep(1)
        if element.count() > 0:
            return 1
    raise Exception(f"Element {element} not found!")

def fetch_restaurant_menu(soup):
    menu_items_list = soup.find_all("div", attrs={"class":"dish-card-wrapper"})
    names_lst = []
    details_lst = []
    info_serves_lst = []
    info_weight_lst = []
    discounted_price_lst = []
    original_price_lst = []

    for item in menu_items_list:
        name = item.find("h3", attrs={"class":"dish-card__description"}).get_text() if item.find("h3", attrs={"class":"dish-card__description"}) else "-"
        details = item.find("span", attrs={"class":"dish-card__details"}).get_text() if item.find("span", attrs={"class":"dish-card__details"}) else "-"
        info_serves = item.find("span", attrs={"class":"dish-info-serves__title"}).get_text() if item.find("span", attrs={"class":"dish-info-serves__title"}) else "-"
        info_weight = item.find("span", attrs={"class":"dish-info-weight__title"}).get_text() if item.find("span", attrs={"class":"dish-info-weight__title"}) else "-"
        discounted_price = item.find("span", attrs={"class":"dish-card__price--discount"}).get_text() if item.find("span", attrs={"class":"dish-card__price--discount"}) else "-"
        original_price = item.find("span", attrs={"class":"dish-card__price--original"}).get_text() if item.find("span", attrs={"class":"dish-card__price--original"}) else "-"

        names_lst.append(name)
        details_lst.append(details)
        info_serves_lst.append(info_serves)
        info_weight_lst.append(info_weight)
        discounted_price_lst.append(discounted_price)
        original_price_lst.append(original_price)

    
    data = {"Nome":names_lst,
            "Descrição":details_lst,
            "Pessoas Servidas":info_serves_lst,
            "Peso/Tamanho Porção":info_weight_lst,
            "Preço com Desconto":discounted_price_lst,
            "Preço sem Desconto":original_price_lst}
    df_menu = pd.DataFrame(data)
    return df_menu

def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context(geolocation={"latitude":-19.870570990751865,"longitude":-43.967757361113414}, locale="pt-BR", permissions=["geolocation"], timezone_id="Brazil/East")
    page = context.new_page()
    page.goto("https://www.ifood.com.br/")
    page.get_by_placeholder("Em qual endereço você está?").click()
    page.get_by_role("button", name="Buscar endereço e número").click()
    page.get_by_role("textbox", name="Buscar endereço e número").fill("UFMG")
    page.locator("[data-test-id=\"button-address-ChIJfeZrgO6QpgAR3REops6RE7s\"]").get_by_role("button").click()
    page.get_by_role("button", name="Confirmar localização").click()
    page.get_by_role("button", name="Salvar endereço").click()
    page.get_by_role("link", name="Restaurantes").click()

    page.locator("[data-test-id=\"search-input-field\"]").click()
    page.locator("[data-test-id=\"search-input-field\"]").press("CapsLock")
    page.locator("[data-test-id=\"search-input-field\"]").fill("HAMBURGUER")
    page.locator("[data-test-id=\"search-input-field\"]").press("Enter")

    restaurants_outer_containter = page.locator("[data-test-id=\"cardstack-section-container\"]")
    wait_for_element(restaurants_outer_containter)

    restaurants_inner_containter = restaurants_outer_containter.locator("[class=\"merchant-list-v2__wrapper\"]")
    restaurants_elements_list = restaurants_inner_containter.locator("[class=\"merchant-list-v2__item-wrapper\"]")
    saved_search_url = page.url

    print(f"Page URL: {saved_search_url}")
    print(f"restaurants_outer_containter: {restaurants_outer_containter.count()}")
    print(f"restaurants_inner_containter: {restaurants_inner_containter.count()}")
    print(f"restaurants_elements_list:{restaurants_elements_list.count()}")

    for i in range(0, restaurants_elements_list.count()):
        if i>=10:
            break
        ele = restaurants_elements_list.nth(i)
        print(f"Index:{i}")
        print(f"Element link:{ele.get_by_role("link").get_attribute('href')}")
        ele.click()
        # Fetching HTML
        restaurant_menu_wrapper = page.locator("[class=\"restaurant__fast-menu\"]")
        dish_wrapper = restaurant_menu_wrapper.locator("[class=\"dish-card-wrapper\"]")
        wait_for_element(dish_wrapper)
        menu_html = restaurant_menu_wrapper.inner_html()
        # Fetching Menu
        soup = BeautifulSoup(menu_html, "html.parser")
        df_menu = fetch_restaurant_menu(soup)
        df_menu.to_excel(f"restaurante_{i+1}.xlsx")
        page.goto(saved_search_url)    

    # ---------------------
    context.close()
    browser.close()


with sync_playwright() as playwright:
    run(playwright)