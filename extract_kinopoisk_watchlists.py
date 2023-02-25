import math
import os
import re
import json

from datetime import datetime

import requests
from bs4 import BeautifulSoup

# set your cookie (you can get from curl request) and list name to id mapping
COOKIE = ''
LIST_NAME_TO_ID = {
    'Буду смотреть': 3575,
    'Любимые фильмы': 6,
    'Примечания': 142498,
    'Смотрю': 1907,
    'Попробовать': 27240,
    'Просмотренные': 112,
    'Отложено': 61981,
    'Избранное': 1,
    'Брошено': 132536,
    'Детям': 15161,
    'Новогодние': 1102,
    'Смотреть в кино': 2
}

HEADERS = {
    'authority': 'www.kinopoisk.ru',
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'accept-language': 'en-US,en;q=0.9,ru-RU;q=0.8,ru;q=0.7',
    'cache-control': 'max-age=0',
    'cookie': COOKIE,
    'dnt': '1',
    'sec-ch-ua': '"Chromium";v="110", "Not A(Brand";v="24", "Google Chrome";v="110"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"macOS"',
    'sec-fetch-dest': 'document',
    'sec-fetch-mode': 'navigate',
    'sec-fetch-site': 'none',
    'sec-fetch-user': '?1',
    'upgrade-insecure-requests': '1',
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36'
}
DEFAULT_PER_PAGE = 50
BASE_URL = 'https://www.kinopoisk.ru/mykp/movies'
INPUT_DIR_PATH = r'responses_input'
OUTPUT_DIR_PATH = r'responses_output'


def mkdir_if_not_exist(dir_path):
    if not os.path.exists(dir_path):
        os.mkdir(dir_path)


def get_url(list_name, page):
    return f'{BASE_URL}' \
           f'/list/type/{LIST_NAME_TO_ID[list_name]}' \
           f'/sort/default/vector/desc/vt/all/perpage/{DEFAULT_PER_PAGE}' \
           f'{f"/page/{page + 1}/" if page > 0 else "/"}'


def get_page(list_name, page):
    return requests.get(get_url(list_name, page), headers=HEADERS).text


def save_page(relative_dir_path, list_name, page, page_data):
    ffrom = page * DEFAULT_PER_PAGE + 1
    to = (page + 1) * DEFAULT_PER_PAGE
    relative_path = f"{relative_dir_path}/{list_name}_{ffrom}-{to}.html"
    with open(relative_path, mode="w", encoding='utf8') as write_file:
        write_file.write(page_data)
    print(f"Writing completed '{relative_path}'")


def get_list(list_name):
    relative_dir_path = f"{INPUT_DIR_PATH}/{list_name}"
    mkdir_if_not_exist(relative_dir_path)

    first_page = get_page(list_name, 0)
    save_page(relative_dir_path, list_name, 0, first_page)

    html = BeautifulSoup(first_page, features='html.parser')
    if html.find('p', attrs={'class': 'emptyMessage'}) is not None:
        print(f"List '{list_name}' is empty")
    else:
        pagesFromTo = html.find('div', attrs={'class': 'pagesFromTo'}).text
        count_of_films = int(pagesFromTo.split(' из ')[-1])
        pages = math.ceil(count_of_films / DEFAULT_PER_PAGE)

        for page in range(1, pages):
            save_page(relative_dir_path, list_name, page, get_page(list_name, page))


def get_all_lists():
    for list_name in LIST_NAME_TO_ID.keys():
        get_list(list_name)


def split(text, delim=None):
    splited = [token.strip() for token in text.split(delim)]
    return [token for token in splited if token]


def extract_genres(text):
    return split(text.replace('...', '')[1:-1], ',')


def convert_to_json(list_name):
    input_relative_dir_path = f"{INPUT_DIR_PATH}/{list_name}"
    result = []
    i = 0
    for path in os.scandir(input_relative_dir_path):
        if path.is_file():
            input_relative_path = f"{input_relative_dir_path}/{path.name}"
            with open(input_relative_path, 'r') as f:
                content = f.read()
                html = BeautifulSoup(content, features='html.parser')
                itemList = html.find('ul', attrs={'id': "itemList"})
                for item in itemList.findAll('li'):
                    addTime = datetime.strptime(item.span.text, '%d.%m.%Y, %H:%M')
                    film_id = item.attrs['data-id']

                    item_data = item.find('div', attrs={'class': 'info'})
                    title_ru = item_data.find('a', attrs={'class': 'name'}).text

                    spans = item_data.findAll('span')
                    item_title_en_and_year_and_duration = spans[0].text
                    pattern = r'\(([0-9]{4} – [0-9]{4}|[0-9]{4} – \.{3}|[0-9]{4})\)'
                    item_title_en_and_duration = re.split(pattern, item_title_en_and_year_and_duration)
                    title_en = item_title_en_and_duration[0].strip() or None
                    duration = item_title_en_and_duration[-1].strip()
                    years = re.findall(pattern, item_title_en_and_year_and_duration)
                    year = years[-1]
                    genres = extract_genres(spans[2].text)
                    result.append({
                        'add_time': addTime,
                        'film_id': film_id,
                        'year': year,
                        'title_en': title_en,
                        'title_ru': title_ru,
                        'genres': genres,
                        'duration': duration
                    })
                    # print(f"Film {i} - AddTime:{addTime}; kinopoiskFilmId: {film_id}; Year:{year}; EN:{title_en}; EN:{title_ru}; Genres: {genres}; Duration: {duration}")
                    i += 1
            print(f"Reading completed '{input_relative_path}'")
    result = sorted(result, key=lambda x: x['add_time'], reverse=True)
    for item in result:
        item['add_time'] = item['add_time'].strftime('%Y-%m-%d_%H:%M')
    output_relative_path = f"{OUTPUT_DIR_PATH}/{list_name}.json"
    with open(output_relative_path, mode="w", encoding='utf8') as write_file:
        json.dump(result, write_file, indent=4, ensure_ascii=False)
    print(f"Converting completed '{input_relative_dir_path}' to '{output_relative_path}'")


def convert_all_lists():
    for list_name in LIST_NAME_TO_ID.keys():
        convert_to_json(list_name)


def test_split_by_pattern(pattern, test_str, expected):
    assert re.split(pattern, test_str) == expected


def test_split_span_with_title_en_and_year_and_duration_by_pattern():
    pattern = r'\(([0-9]{4} – [0-9]{4}|[0-9]{4} – \.{3}|[0-9]{4})\)'
    test_split_by_pattern(
        pattern,
        "Bakuman. (2010 – 2013) 25 мин.",
        ['Bakuman. ', '2010 – 2013', ' 25 мин.']
    )
    test_split_by_pattern(
        pattern,
        "Bakuman. (2010 – ...) 25 мин.",
        ['Bakuman. ', '2010 – ...', ' 25 мин.']
    )
    test_split_by_pattern(
        pattern,
        "Bakuman. (2010) 25 мин.",
        ['Bakuman. ', '2010', ' 25 мин.']
    )
    test_split_by_pattern(
        pattern,
        "Evangelion: 3.0 You Can (Not) Redo (2012) 106 мин.",
        ['Evangelion: 3.0 You Can (Not) Redo ', '2012', ' 106 мин.']
    )


def test_extract_genres(test_str, expected):
    assert extract_genres(test_str) == expected


def test_split_span_with_genres():
    test_extract_genres(
        "(документальный)",
        ['документальный']
    )
    test_extract_genres(
        "(документальный, биография)",
        ['документальный', 'биография']
    )
    test_extract_genres(
        "(документальный, биография, ...)",
        ['документальный', 'биография']
    )
    test_extract_genres(
        "(документальный , биография, ... , ...)",
        ['документальный', 'биография']
    )


def tests():
    test_split_span_with_title_en_and_year_and_duration_by_pattern()
    test_split_span_with_genres()
    print("Complete all tests")


def prepare():
    mkdir_if_not_exist(INPUT_DIR_PATH)
    mkdir_if_not_exist(OUTPUT_DIR_PATH)
    tests()


prepare()
get_all_lists()
convert_all_lists()
