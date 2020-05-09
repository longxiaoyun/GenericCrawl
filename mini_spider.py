# -*-coding:utf-8 -*-

from retrying import retry
from configparser import ConfigParser
import re
import os
import time
from datetime import datetime
from collections import deque
import random
import logging
import threading
import requests
import argparse
from urllib.parse import urldefrag, urljoin, urlparse
from urllib.parse import quote
logger = logging.getLogger(__name__)


# 命令行参数
def parse_argument():
    parser = argparse.ArgumentParser("mini_spider", add_help=False)
    parser.add_argument("-c", "--config", type=str, required=True,help="config file path")
    parser.add_argument("-v", "--version",  action="version", version='%(prog)s 1.0', help='show version message.')
    parser.add_argument("-h", "--help", action="help", default=argparse.SUPPRESS, help='show help message.')
    options = parser.parse_args()
    return options


# 初始化配置文件
class InitConf(object):
    conf = ConfigParser()
    options = parse_argument()

    @classmethod
    def getter_settings(cls):
        config = cls.conf
        options = cls.options
        config_path = options.config

        if not config_path:
            logger.error('未指定配置文件.')
            return
        file_path = get_file_path(config_path)
        config.read(file_path, encoding='utf-8')
        return config['spider']


# 文件路径处理
def get_file_path(_path):
    current_file = os.path.abspath(__file__)
    parent_path = os.path.abspath(os.path.dirname(current_file) + os.path.sep + ".")
    file_path = os.path.join(parent_path, _path)
    return file_path


# 链接补全
def link_handler(seed_url, url):
    real_url, _ = urldefrag(url)  # 网站内的相对网址(没有域名)
    return urljoin(seed_url, real_url)


# 保存结果
def save_result(html, url, encode):
    if not html or not url:
        logger.error('待保存数据不能为空')
        return
    try:
        output_directory = settings.get('output_directory')
        _url = quote(url, safe='')
        current_file = os.path.abspath(__file__)
        parent_path = os.path.abspath(os.path.dirname(current_file) + os.path.sep + ".")
        file_path = os.path.join(parent_path, output_directory, _url)

        with open(file_path, 'w', encoding=encode) as f:
            f.write(html)
    except OSError as e:
        logger.error(e)


# 参数处理
def params_handler(param, default_param):
    if param:
        param = param.strip()
    else:
        param = default_param
    return param


# 主要爬取类
class DefaultCrawl(threading.Thread):
    def __init__(self, seed_url, settings, visited, q):
        # 调用父类的构造方法
        super(DefaultCrawl, self).__init__()

        self.will_crawl_queue = q
        self.visited = visited
        if isinstance(seed_url, str):
            self.will_crawl_queue.appendleft(seed_url)
            self.visited[seed_url] = 0
        if isinstance(seed_url, list):
            for _s in seed_url:
                self.will_crawl_queue.appendleft(_s)
                self.visited[_s] = 0

        self.settings = settings
        self.download_delay = int(params_handler(self.settings.get('crawl_interval'), 3))
        self.timeout = int(params_handler(self.settings.get('crawl_timeout'), 10))
        self.headers = {'User-Agent': 'Mozilla/5.0 (compatible; Baiduspider/2.0; +http://www.baidu.com/search/spider.html)'}
        self.max_depth = int(params_handler(self.settings.get('max_depth'), 1))
        self.regex_str = '<a[^>]+href=["\'](.*?)["\']'
        self.enc = 'utf-8'
        self.throttle = Throttle(self.download_delay)

    @retry(stop_max_attempt_number=3)
    def request(self, url, method, data):
        if method == "POST":
            result = requests.post(url, data=data, headers=self.headers, timeout=self.timeout)
        else:
            result = requests.get(url, headers=self.headers, timeout=self.timeout)
        assert result.status_code == 200
        self.enc = result.encoding
        return result.content, result.url

    def downloader(self, url, method='GET', data=None):
        try:
            result, page_url = self.request(url, method, data)
        except Exception as e:
            logger.error(e)
            result = None
            page_url = None
        return result, page_url

    def extractor_urls(self, html):
        url_regex = re.compile(self.regex_str, re.IGNORECASE)
        return url_regex.findall(html)

    def run(self):
        while self.will_crawl_queue:
            url = self.will_crawl_queue.pop()
            self.throttle.wait_url(url)
            depth = self.visited[url]
            if depth <= self.max_depth:
                # 下载链接
                html,page_url = self.downloader(url)
                if html:
                    if isinstance(html, bytes):
                        html = html.decode(self.enc)
                    # 筛选出页面的链接
                    url_list = self.extractor_urls(html)
                    # 筛选需要爬取的链接(包含了htm,html的链接)
                    filter_urls = [link for link in url_list if link.endswith(('.html', '.htm', '.shtml'))]
                    for url in filter_urls:
                        # 补全链接
                        real_url = link_handler(page_url, url)  # 将每一个抽取到的相对网址补全为http:// + 域名 + 相对网址的格式
                        # 判断链接是否访问过
                        if real_url not in self.visited:
                            save_result(html, real_url, encode=self.enc)
                            # 将每一个页面中的下一层url链接的depth都加一，这样每一层都会对应一个depth
                            self.visited[real_url] = depth + 1
                            # 将所有抽取出来的链接添加到队列中待爬取
                            if real_url not in self.will_crawl_queue:
                                self.will_crawl_queue.appendleft(real_url)


# 下载延迟
class Throttle:
    def __init__(self, delay):
        # 保存每个爬取过的链接与对应爬取时间的时间戳
        self.domains = {}
        self.delay = delay

    def wait_url(self, url_str):
        # 以netloc为基础进行休眠
        domain_url = urlparse(url_str).netloc  # 获取到爬取的链接的域名
        last_accessed = self.domains.get(domain_url)  # 获取上次爬取链接的时间戳(时间戳与域名对应，爬取该域名的网站之后更新为最新的时间戳)

        # 爬取的条件为上次爬取的时间戳不为空(上次爬取过，如果没有爬取则把这个域名和当前时间戳保存到字典)
        if self.delay > 0 and last_accessed is not None:
            # 计算当前时间和上次访问时间间隔
            # sleep_interval加上随机偏移量
            sleep_interval = self.delay - (datetime.now() - last_accessed).seconds  # 记录上次爬取到这次的时间间隔
            # 如果时间间隔尚未达到规定的时间间隔，则需要等待
            if sleep_interval > 0:
                time.sleep(sleep_interval + round(random.uniform(1, 3), 1))  # 设置一个随机的偏移量


# 启动方法
def main():
    settings = InitConf.getter_settings()
    thread_num = params_handler(settings.get('thread_count'), 8)
    thread_num = int(thread_num)

    url_list_file = settings.get('url_list_file')
    seed_file_path = get_file_path(url_list_file)

    with open(seed_file_path, 'r', encoding='utf-8') as f:
        seed_list = [line.strip() for line in f]

    visited = dict()
    # 使用deque队列，方便做去重
    q = deque()

    threads = []
    for i in range(thread_num):
        t = DefaultCrawl(seed_list, settings, visited, q)
        t.start()
        threads.append(t)
    # 等待所有队列完成
    for _ in threads:
        _.join()
    # 阻塞，直到队列里的所有元素都被处理完
    # q.join()


if __name__=='__main__':
    main()



