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

#------------------flask-------------------#

app = Flask(__name__)

#main 페이지
@app.route('/')
def home_page():
    return render_template("Home_page.html")

#단일 url 입력 페이지
@app.route('/single', methods=['POST'])
def single_page():
    return render_template("Single_page.html")

#url file 입력 페이지
@app.route('/file', methods=['POST'])
def file_page():
    return render_template("File_page.html")

#웹사이트 분석 결과표 페이지
@app.route('/single_result', methods=['POST'])
def single_result():
    try:
        url = request.form['input']
    except:
        url = None
    
    page = requests.get(url)
    #크롤링
    soup = BeautifulSoup(page.content, "html.parser")
    body = str(soup.find('body'))
    text = getText(body).lower()
    text = word_tokenize(text)

    return render_template("Result_page.html")

#단어 분석 팝업창

#유사도 분석 팝업창

if __name__ == '__main__':
    app.run(debug=False)