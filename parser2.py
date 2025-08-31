import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import time
import csv
import re

BASE_URL = "https://visterma.ru"
CATALOG_URL = "https://visterma.ru/catalog/prochee-Weishaupt/?SHOWALL_1=1"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7"
}

def clean_html_tags(html):
    soup = BeautifulSoup(html, 'lxml')
    for tag in soup.find_all(True):
        tag.attrs = {}
    if soup.html:
        soup.html.unwrap()
    if soup.body:
        soup.body.unwrap()
    return str(soup)

def remove_visterma_text(html_content):
    """Удаляет все начиная с фразы 'Компания «Вистерма»'"""
    if not html_content or html_content == '':
        return ''
    
    try:
        soup = BeautifulSoup(str(html_content), 'html.parser')
        
        # Ищем все элементы с текстом
        for element in soup.find_all(True):
            text = element.get_text()
            if '«Вистерма»' in text:
                # Нашли элемент с фразой - удаляем его и все последующие элементы
                for next_element in element.find_all_next():
                    next_element.decompose()
                element.decompose()
                break
        
        # Ищем все параграфы
        for p_tag in soup.find_all('p'):
            # Ищем все br теги внутри параграфа
            br_tags = p_tag.find_all('br')
            
            for br in br_tags:
                # Получаем весь текст после этого br тега до конца параграфа
                next_elements = []
                current = br.next_sibling
                
                while current and current.name != 'br':
                    next_elements.append(current)
                    current = current.next_sibling if current.next_sibling else None
                
                # Проверяем, есть ли в этом тексте упоминание Вистермы
                text_after_br = ''.join(str(elem) for elem in next_elements)
                if 'ВИСТЕРМА' in text_after_br or '«Вистерма»' in text_after_br:
                    # Удаляем все элементы после br
                    for elem in next_elements:
                        elem.decompose()
                    # Также удаляем сам br
                    br.decompose()
                    break

        return str(soup)
            
    except Exception as e:
        print(f"Ошибка при удалении текста Вистермы: {e}")
        return html_content

def extract_first_paragraph(html_content):
    """Извлекает первый абзац из HTML описания"""
    if not html_content or html_content == '':
        return ''
    
    try:
        soup = BeautifulSoup(str(html_content), 'html.parser')
        
        # Ищем первый тег <p>
        first_p = soup.find('p')
        
        if first_p:
            # Получаем текст из первого абзаца, очищаем от лишних пробелов
            text = first_p.get_text().strip()
            # Удаляем множественные пробелы
            text = re.sub(r'\s+', ' ', text)
            return text
        else:
            # Если тегов <p> нет, пытаемся найти любой текстовый контент
            text = soup.get_text().strip()
            if text:
                text = re.sub(r'\s+', ' ', text)
                # Берем первые 150 символов, если текст слишком длинный
                if len(text) > 150:
                    return text[:147] + '...'
                return text
            return ''
            
    except Exception as e:
        print(f"Ошибка при извлечении первого абзаца: {e}")
        return ''

def extract_description(desc_block):
    if not desc_block:
        return ""
    allowed_tags = ['h2', 'h3', 'h4', 'p', 'ul', 'ol', 'li', 'br']
    for tag in desc_block.find_all(True):
        if tag.name not in allowed_tags:
            tag.unwrap()
    
    # Получаем HTML описание
    description_html = clean_html_tags("".join(str(child) for child in desc_block.children))
    
    # Удаляем текст с фразой "Компания «Вистерма»"
    cleaned_description = remove_visterma_text(description_html)
    
    return cleaned_description

def get_characteristics(soup):
    specs = {}
    specs_block = soup.find('li', id='char')
    if specs_block:
        for item in specs_block.find_all('dl', class_='psk072'):
            name = item.find('dt').get_text(strip=True).replace(':', '')
            value = item.find('dd').get_text(strip=True)
            specs[name] = value
    return specs

def get_all_product_links(catalog_url):
    try:
        response = requests.get(catalog_url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'lxml')
        product_links = []
        
        product_items = soup.select('.catalog-section .product-item-list-col-3 .row .c-4 .product-item-container .psk064')
        
        for item in product_items:
            link = item.find('a', class_='psk024')
            if link and link.get('href'):
                full_url = urljoin(BASE_URL, link['href'])
                product_links.append(full_url)
        print(f"Найдено {len(product_links)} товаров")
        return product_links
    except Exception as e:
        print(f"Ошибка при получении ссылок на товары: {e}")
        return []

def get_manufacturer_info(first_product_url):
    try:
        response = requests.get(first_product_url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'lxml')
        return extract_description(soup.find('li', id='brand'))
    except Exception as e:
        print(f"Ошибка при получении информации о производителе: {e}")
        return "Нет информации"

def parse_product_page(url, manufacturer_info):
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'lxml')

        title = soup.find('h1').get_text(strip=True) if soup.find('h1') else 'Нет названия'
        description = extract_description(soup.find('li', id='desc'))
        characteristics = get_characteristics(soup)
        
        # Извлекаем артикул из характеристик
        article = characteristics.get('Артикул', '')
        
        # Извлекаем первый абзац из описания для краткого описания
        short_description = extract_first_paragraph(description)

        # Формируем список атрибутов (максимум 7)
        attributes = []
        for i, (name, value) in enumerate(list(characteristics.items())[:7]):
            if name.lower() != 'артикул' and name.lower() != 'название':
                attributes.append({
                    'name': name,
                    'value': value,
                    'visible': 1,
                    'global': 0
                })

        product_data = {
            'ID': 5000,
            'Тип': 'simple',
            'Артикул': article,
            'Имя': title,
            'Опубликован': 1,
            'Видимость в каталоге': 'visible',
            'Краткое описание': short_description,
            'Описание': description,
            'Наличие': 1,
            'Базовая цена': 0,
            'Категории': '',
            'Изображения': '',
            'manufacturer': manufacturer_info,
            'characteristics': characteristics,
            'attributes': attributes
        }
        
        return product_data
        
    except Exception as e:
        print(f"Ошибка при парсинге {url}: {e}")
        return None

def prepare_csv_row(product):
    """Подготавливает строку для CSV файла"""
    row = {
        'ID': product['ID'],
        'Тип': product['Тип'],
        'Артикул': product['Артикул'],
        'Имя': product['Имя'],
        'Опубликован': product['Опубликован'],
        'Видимость в каталоге': product['Видимость в каталоге'],
        'Краткое описание': product['Краткое описание'],
        'Описание': product['Описание'],
        'Наличие': product['Наличие'],
        'Базовая цена': product['Базовая цена'],
        'Категории': product['Категории'],
        'Изображения': product['Изображения']
    }
    
    # Добавляем атрибуты (до 7 возможных)
    for i, attr in enumerate(product['attributes'][:7], 1):
        row[f'Название атрибута {i}'] = attr['name']
        row[f'Значения атрибутов {i}'] = attr['value']
        row[f'Видимость атрибута {i}'] = attr['visible']
        row[f'Глобальный атрибут {i}'] = attr['global']
    
    # Заполняем оставшиеся атрибуты пустыми значениями
    for i in range(len(product['attributes']) + 1, 8):
        row[f'Название атрибута {i}'] = ''
        row[f'Значения атрибутов {i}'] = ''
        row[f'Видимость атрибута {i}'] = ''
        row[f'Глобальный атрибут {i}'] = ''
    
    return row

def main():
    print("Сбор ссылок на все товары...")
    product_urls = get_all_product_links(CATALOG_URL)
    
    if not product_urls:
        print("Не удалось найти товары в каталоге")
        return
    
    print("\nПолучение информации о производителе...")
    manufacturer_info = get_manufacturer_info(product_urls[0])
    print("Информация о производителе получена")
    
    print("\nНачало парсинга товаров...")
    all_products = []
    
    for i, url in enumerate(product_urls, 1):
        print(f"Обработка товара {i}/{len(product_urls)}...")
        product_data = parse_product_page(url, manufacturer_info)
        if product_data:
            all_products.append(product_data)
        # time.sleep(1)
    
    # Определяем заголовки CSV файла
    fieldnames = [
        'ID', 'Тип', 'Артикул', 'Имя', 'Опубликован', 'Видимость в каталоге',
        'Краткое описание', 'Описание', 'Наличие', 'Базовая цена', 'Категории', 'Изображения'
    ]
    
    # Добавляем колонки для атрибутов
    for i in range(1, 8):
        fieldnames.extend([
            f'Название атрибута {i}',
            f'Значения атрибутов {i}',
            f'Видимость атрибута {i}',
            f'Глобальный атрибут {i}'
        ])
    
    # Сохраняем в CSV
    with open('visterma_products.csv', 'w', newline='', encoding='utf-8-sig') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for product in all_products:
            writer.writerow(prepare_csv_row(product))
    
    print("\nДанные успешно сохранены в visterma_products.csv")

if __name__ == "__main__":
    main()