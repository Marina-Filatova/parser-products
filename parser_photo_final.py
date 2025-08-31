import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd

# Настройки
BASE_URL = "https://visterma.ru"
CATALOG_URL = "https://visterma.ru/catalog/prochee-Weishaupt/?SHOWALL_1=1"
OUTPUT_FOLDER = "Фото категория N"
CSV_FILE = "visterma_products.csv"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7"
}
MAX_WORKERS = 10

# Словарь для хранения соответствия товаров и их изображений
product_images = {}

def create_folder(folder_name):
    """Создаёт папку для сохранения изображений"""
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)
        print(f"Создана папка: {folder_name}")

def transliterate_to_latin(text):
    """Транслитерирует русский текст в латиницу и преобразует в нижний регистр"""
    translit_dict = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
        'А': 'a', 'Б': 'b', 'В': 'v', 'Г': 'g', 'Д': 'd', 'Е': 'e', 'Ё': 'e',
        'Ж': 'zh', 'З': 'z', 'И': 'i', 'Й': 'y', 'К': 'k', 'Л': 'l', 'М': 'm',
        'Н': 'n', 'О': 'o', 'П': 'p', 'Р': 'r', 'С': 's', 'Т': 't', 'У': 'u',
        'Ф': 'f', 'Х': 'h', 'Ц': 'ts', 'Ч': 'ch', 'Ш': 'sh', 'Щ': 'sch',
        'Ъ': '', 'Ы': 'y', 'Ь': '', 'Э': 'e', 'Ю': 'yu', 'Я': 'ya'
    }
    
    result = []
    for char in text:
        if char in translit_dict:
            result.append(translit_dict[char])
        else:
            result.append(char)
    
    return ''.join(result)

def sanitize_filename(filename):
    """Очищает название от недопустимых символов и преобразует в латиницу нижний регистр"""
    latin_name = transliterate_to_latin(filename)
    latin_name = re.sub(r'[\\/*?:"<>|]', "", latin_name)
    latin_name = re.sub(r'[\s,]+', "_", latin_name)
    latin_name = re.sub(r'_+', "_", latin_name)
    latin_name = latin_name.lower()
    latin_name = latin_name.strip('_')
    return latin_name

def get_all_product_links(catalog_url):
    """Получает все ссылки на товары из каталога"""
    try:
        response = requests.get(catalog_url, headers=HEADERS)
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

def transform_image_url(original_url):
    """Преобразует URL изображения, убирая resize_cache и размеры"""
    if not original_url:
        return None
    
    if 'resize_cache' in original_url:
        parts = original_url.split('/')
        try:
            medialibrary_index = parts.index('medialibrary')
            new_parts = [
                BASE_URL,
                'upload',
                'medialibrary',
                parts[medialibrary_index + 1],
                parts[-1]
            ]
            return '/'.join(new_parts)
        except (ValueError, IndexError):
            print(f"Не удалось преобразовать URL: {original_url}")
            return original_url
    
    return original_url

def extract_image_url_from_style(style_content):
    """Извлекает URL изображения из атрибута style"""
    if not style_content:
        return None
    
    url_match = re.search(r'url\(["\']?(.*?)["\']?\)', style_content)
    if url_match:
        return url_match.group(1)
    return None

def get_product_name_and_image(url):
    """Получает название товара и основное изображение с его страницы"""
    try:
        response = requests.get(url, headers=HEADERS)
        soup = BeautifulSoup(response.text, 'lxml')
        
        name_element = soup.find('h1')
        original_name = name_element.get_text(strip=True) if name_element else url.split('/')[-2]
        
        sanitized_name = sanitize_filename(original_name)
        
        img_container = soup.select_one('div.product-item-detail-slider-image.active')
        img_url = None
        
        if img_container:
            img_tag = img_container.find('img')
            if img_tag and img_tag.get('src'):
                original_img_url = urljoin(BASE_URL, img_tag['src'])
                img_url = transform_image_url(original_img_url)
            
            if not img_url and img_tag and img_tag.get('style'):
                style_url = extract_image_url_from_style(img_tag['style'])
                if style_url:
                    original_img_url = urljoin(BASE_URL, style_url)
                    img_url = transform_image_url(original_img_url)
        
        return sanitized_name, img_url, original_name
    except Exception as e:
        print(f"Ошибка при обработке {url}: {e}")
        original_name = url.split('/')[-2]
        sanitized_name = sanitize_filename(original_name)
        return sanitized_name, None, original_name

def download_image(url, filename, folder):
    """Скачивает и сохраняет изображение"""
    try:
        response = requests.get(url, headers=HEADERS, stream=True)
        if response.status_code == 200:
            ext = os.path.splitext(url.split('?')[0])[1]
            if not ext:
                content_type = response.headers.get('content-type', '')
                if 'jpeg' in content_type or 'jpg' in content_type:
                    ext = '.jpg'
                elif 'png' in content_type:
                    ext = '.png'
                elif 'gif' in content_type:
                    ext = '.gif'
                elif 'webp' in content_type:
                    ext = '.webp'
                else:
                    ext = '.jpg'
            
            full_filename = f"{filename}{ext}"
            path = os.path.join(folder, full_filename)
            with open(path, 'wb') as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            return full_filename
    except Exception as e:
        print(f"Ошибка скачивания {url}: {e}")
    return None

def process_product(product_url):
    """Обрабатывает один товар"""
    sanitized_name, img_url, original_name = get_product_name_and_image(product_url)
    if img_url:
        print(f"Обработка: {original_name}")
        
        image_filename = download_image(img_url, sanitized_name, OUTPUT_FOLDER)
        if image_filename:
            print(f"Скачано: {image_filename}")
            # Сохраняем в словарь для последующего обновления CSV
            product_images[original_name] = image_filename
            return True
        else:
            print(f"Ошибка скачивания для: {original_name}")
    else:
        print(f"Не найдено изображение для: {original_name}")
    return False

def update_csv_final():
    """Обновляет CSV файл один раз после скачивания всех изображений"""
    try:
        if not product_images:
            print("Нет данных для обновления CSV")
            return False
        
        # Читаем CSV
        df = pd.read_csv(CSV_FILE)
        
        # Обновляем изображения
        updated_count = 0
        for product_name, image_filename in product_images.items():
            mask = df['Имя'] == product_name
            if mask.any():
                df.loc[mask, 'Изображения'] = image_filename
                updated_count += 1
                print(f"Обновлено: {product_name} -> {image_filename}")
            else:
                print(f"Не найден в CSV: {product_name}")
        
        # Сохраняем обратно
        df.to_csv(CSV_FILE, index=False, encoding='utf-8')
        print(f"CSV обновлен. Обновлено записей: {updated_count}/{len(product_images)}")
        return True
        
    except Exception as e:
        print(f"Ошибка при обновлении CSV: {e}")
        return False

def main():
    create_folder(OUTPUT_FOLDER)
    product_urls = get_all_product_links(CATALOG_URL)
    
    if not product_urls:
        print("Не удалось найти товары в каталоге")
        return
    
    # Обрабатываем товары
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(process_product, url) for url in product_urls]
        
        success = 0
        for future in as_completed(futures):
            if future.result():
                success += 1
    
    print(f"\nСкачано изображений: {success}/{len(product_urls)}")
    
    # ОДИН РАЗ обновляем CSV
    update_csv_final()

if __name__ == "__main__":
    main()