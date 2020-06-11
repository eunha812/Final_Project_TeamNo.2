#!/usr/bin/python
#-*-coding: utf-8 -*-

import sys
import re
import requests

from bs4 import BeautifulSoup
from elasticsearch import Elasticsearch

from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize

def cleanText(body):    
    #태그 제거
    tag = re.compile('<.*?>')
    text = re.sub(tag, ' ', body)

    #특수문자 제거하기
    cleanText = re.sub('[^\w\s]', ' ', text)

    return cleanText

if __name__ == '__main__':

    #crawling
    word_list = []

    url = u'http://buildr.apache.org/'
    page = requests.get(url)
    soup = BeautifulSoup(page.content, "html.parser")
    body = str(soup.find('body'))
    text = cleanText(body).lower()
    text = word_tokenize(text)

    print(text)