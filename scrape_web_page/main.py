import argparse
import os
from io import BytesIO
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup
from PyPDF2 import PdfFileReader

default_root_urls = [
    ''
]
default_ignore_urls = []
file_path = os.path.join(os.path.expanduser('~/Desktop'), 'page-content.txt')


class WebCrawlerScraper:
    def __init__(self, root_urls, ignore_urls=None):
        # WebCrawlerの初期化
        self.root_urls = [self.normalize_url(url) for url in (root_urls if isinstance(root_urls, list) else [root_urls])]
        self.ignore_urls = set(ignore_urls) if ignore_urls else set()
        self.found_urls = set()
        self.visited_urls = set()
        self.scraped_data = {}

    def normalize_url(self, url):
        parsed_url = urlparse(url)
        return urlunparse(parsed_url._replace(query="", fragment=""))

    def is_subpath(self, url, root_url):
        return urlparse(url).path.startswith(urlparse(root_url).path)

    def should_ignore(self, url):
        return any(ignore_url in url for ignore_url in self.ignore_urls)

    def explore_and_scrape(self, url, root_url):
        normalized_url = self.normalize_url(url)
        if normalized_url in self.visited_urls or not self.is_subpath(normalized_url, root_url) or self.should_ignore(normalized_url):
            return
        self.visited_urls.add(normalized_url)
        print('Exploring:', len(self.visited_urls), '/', len(self.found_urls))

        if normalized_url.endswith('.pdf') or normalized_url.endswith('.jpg') or normalized_url.endswith('.jpeg'):
            print(f'Skipping file URL: {normalized_url}')
            return  # PDFや画像ファイルのURLはスキップ

        try:
            response = requests.get(normalized_url, stream=True)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                self.scrape_content(soup, normalized_url)
            else:
                print(f"Error: {normalized_url} returned status code {response.status_code}")
                return
        except requests.exceptions.RequestException as e:
            print(f"Error exploring {normalized_url}: {e}")
            return

        # HTMLリンク探索
        for link in soup.find_all('a', href=True):
            href = link['href']
            full_url = self.normalize_url(urljoin(normalized_url, href))
            if not (full_url.endswith('.pdf') or full_url.endswith('.jpg') or full_url.endswith('.jpeg')):
                if urlparse(full_url).netloc == urlparse(root_url).netloc and not self.should_ignore(full_url):
                    if full_url not in self.found_urls and self.is_subpath(full_url, root_url):
                        self.found_urls.add(full_url)

    def scrape_content(self, soup, url):
        for selector in ['header', 'footer', 'nav', 'aside']:
            for element in soup.select(selector):
                element.decompose()
        text = soup.get_text(separator=' ', strip=True).replace('\0', '')  # Null文字を除去
        self.scraped_data[url] = text

    def scrape_pdf(self, response, url):
        try:
            with BytesIO(response.content) as f:
                reader = PdfFileReader(f)
                text = ' '.join(page.extract_text() for page in reader.pages if page and page.extract_text()).replace('\0', '')  # Null文字を除去
            self.scraped_data[url] = text
        except Exception as e:
            print(f"Error scraping PDF {url}: {e}")

    def crawl_and_scrape(self):
        for root_url in self.root_urls:
            self.explore_and_scrape(root_url, root_url)
            while self.found_urls - self.visited_urls:
                next_url = (self.found_urls - self.visited_urls).pop()
                self.explore_and_scrape(next_url, root_url)

    def sort_scraped_data(self):
        """スクレイプデータをURLのアルファベット順にソートする"""
        return dict(sorted(self.scraped_data.items()))

    def convert_to_text(self):
        """スクレイプデータをテキストに変換する"""
        sorted_data = self.sort_scraped_data()
        text_content = ''
        for url, content in sorted_data.items():
            text_content += f"{url}\n\"\"\"\n{content}\n\"\"\"\n\n"
        return text_content

    def save_to_file(self):
        """テキストをファイルに保存する"""
        text_content = self.convert_to_text()
        # デスクトップにpage-content.txtを作成
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(text_content)
        print("\n", "Create File:", file_path, "\n")


# 使用例
if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='指定したURLからサイトマップを作成します。'
    )
    parser.add_argument('root_urls', metavar='root_url', type=str, nargs='+', default=default_root_urls)
    parser.add_argument('-i', '--ignore-urls', metavar='ignore_url', type=str, nargs='*', default=default_ignore_urls)
    args = parser.parse_args()
    crawler_scraper = WebCrawlerScraper(args.root_urls, args.ignore_urls)
    crawler_scraper.crawl_and_scrape()
    crawler_scraper.save_to_file()
