#!/usr/bin/env python

import re
import os
import sys
import ssl
import uuid
import socket
import subprocess 
import logging

from urllib.parse import urlparse
from bs4 import BeautifulSoup
from lxml import etree

class Logger:

    def __init__(self, log_path):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)

        self.formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

        self.file_handler = logging.FileHandler(f"{log_path}/{uuid.uuid4()}_log.txt")
        self.file_handler.setFormatter(self.formatter)
        self.logger.addHandler(self.file_handler)

        self.stream_handler = logging.StreamHandler()
        self.stream_handler.setFormatter(self.formatter)
        self.logger.addHandler(self.stream_handler)

    def debug(self, message):
        self.logger.debug(message)

    def info(self, message):
        self.logger.info(message)

    def warning(self, message):
        self.logger.warning(message)

    def error(self, message):
        self.logger.error(message)

    def critical(self, message):
        self.logger.critical(message)


class WebHandler:

    def __init__(self):
        self.search_link = "https://www.google.com/search?q={}"
        self.search_path = "/search?q={}"
        self.http_port = 80
        self.https_port = 443

        self.log_path = "logs"
        if not os.path.exists(self.log_path):
            os.mkdir(self.log_path)

        self.logger = Logger(self.log_path) 

    def parse_url(self, url):
        parsed_url = urlparse(url)
        self.logger.info("URL parsed")
        return [
            parsed_url.netloc, 
            parsed_url.path, 
            self.http_port if parsed_url.scheme == "http" else self.https_port,
        ]

    def parse_html_page(self, data):
        self.logger.info("Page parsed")
        return subprocess.run(
            ["lynx", "-stdin", "-dump"],
            input=data,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
        ).stdout
    
    def parse_html_links(self, data):
        soup = BeautifulSoup(data, "html.parser")
        dom = etree.HTML(str(soup))

        links = dom.xpath("//span/a//following-sibling::h3/../@href")
        return links
    
    def request(self, host, port, path):
        self.logger.info(f"Requested {host}:{port}{path}")
        response = "" 
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, port))

        if port == self.https_port:
            ctx = ssl.create_default_context()
            sock = ctx.wrap_socket(sock, server_hostname=host)
        
        sock.sendall(
            (f"GET {path} HTTP/1.1\r\n" +
             f"Host: {host}\r\n" +
             "Connection: close\r\n" +
             "User-Agent: Mozilla/5.0 (X11; Linux x86_64; rv:123.0) Gecko/20100101 Firefox/123.0\r\n" +
             "Accept: */*\r\n" +
             "\r\n").encode()
        )

        while True:
            data = sock.recv(4096)
            if not data: break
            response += data.decode("utf-8")
        
        sock.close()

        headers, body = response.split("\r\n\r\n", 1)

        if re.match(r"HTTP/1.1 3\d{2}", headers) and "Location:" in headers:
            location = re.search(r"Location: (.+)\r\n", headers).group(1)
            host, path, port = self.parse_url(location)
            
            self.logger.info(f"Redirected to {str(location)}")
            return self.request(host, port, path)

        self.logger.info(f"Got response") 
        return [headers, body]
    
    def search(self, queries):
        search_query = '+'.join(queries)

        port = self.https_port 
        path = self.search_path.format(search_query)
        host= urlparse(
            self.search_link.format(search_query)
        ).netloc
        
        _, body = self.request(host, port, path)
        return self.parse_html_links(body)

if __name__=="__main__":
    web_handler = WebHandler()

    if "-u" in sys.argv:
        host, path, port = web_handler.parse_url(sys.argv[-1])
        header, body = web_handler.request(host, port, path)
        print(web_handler.parse_html_page(body))

    elif "-s" in sys.argv:
        links = web_handler.search(sys.argv[2:])
        for idx, link in enumerate(links, 1):
            print(f"{idx}. {link}")
        
        option = input("Select the number of the link you want to access or enter `q` to quit\nOption := ")
        if option == "q":
            sys.exit()
        elif 1 <= int(option) <= len(links):
            host, path, port = web_handler.parse_url(links[int(option)])
            
            header, body = web_handler.request(host, port, path)
            print(web_handler.parse_html_page(body))
        else:
            web_handler.logger.error("The user choose an wrong option.")
            sys.exit()

    else:
        print("go2web -u <URL>         # make an HTTP request to URL and print the response")
        print("go2web -s <search-term> # make an HTTP request to search and print top 10 results")
        print("go2web -h               # show help")
