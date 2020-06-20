#!/usr/bin/python
#-*-coding: utf-8 -*-

import sys
import re
import os
import requests
import argparse
import subprocess

import time
import numpy
import math

from bs4 import BeautifulSoup
from elasticsearch import Elasticsearch
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from flask import Flask, jsonify, request, render_template
from werkzeug.utils import secure_filename

es_host="127.0.0.1"
es_port="9200"

#------------------function-------------------#

#html body에서 순수한 text만 뽑아오기
def getText(body):    
    #태그 제거
    tag = re.compile('<.*?>')
    text = re.sub(tag, ' ', body)

    #특수문자 제거하기
    cleanText = re.sub('[^\w\s]', ' ', text)

    return cleanText

#--------------------flask---------------------#

#flask 객체 app 할당
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

#단일 url 분석 페이지
@app.route('/single_result', methods=['POST'])
def single_result():
    try:
        url = request.form['input']
    except:
        url = None
    
    result = []         #html에 보낼 결과리스트
    d ={}               #결과 리스트에 저장할 각 url별 결과
    word = []           #크롤링할 단어리스트
    
    d['count'] = 1
    d['url'] = url
    
    #크롤링으로 단어 뽑아오기
    try:
        #url get 성공
        page = requests.get(url)
        d['success'] = 1
        
        #시간 측정 시작
        start = time.time() 

        #크롤링
        soup = BeautifulSoup(page.content, "html.parser")
        body = str(soup.find('body'))
        text = getText(body).lower()
        text = word_tokenize(text)

        #의미 있는 단어만 뽑기
        for i in text:
            if i not in stopwords.words("english"):
                word.append(i)
        
        #엘라스틱 서치에 문서 넣기
        doc = {}
        try:
            #인덱스가 있으면 불러오고
            doc = es.get(index='final',doc_type='test', id=1)
            doc = doc['_source']
            
            #중복 url 여부 확인
            if url not in doc['url']:
                doc['url'].append(url)
                doc['words'].append(word)
        except:
            #없으면 새로 만들기
            doc = {}
            doc['url'] = [url]
            doc['words'] = [word]

        es = Elasticsearch([{'host':es_host, 'port':es_port}], timeout=100)
        es.index(index='final', doc_type='test', id=1, body=doc)
    except requests.ConnectionError:
        #url get 실패
        d['success'] = 0

    d['word_count'] = len(word)
    d['duration'] = time.time() - start
    result.append(d)

    return render_template('Result_page.html', result=result)

#url파일 분석 페이지
@app.route('/file_result', methods=['POST'])
def file_result():
    try:
        f = request.files['file']   #html에서 name='file'인 값을 받기
        f.save(secure_filename(f.filename)) #업로드된 파일을 특정 폴더에 저장
        with open(f.filename, 'r') as f:
            urls = f.readlines()
        urls = [i.strip() for i in urls]
    except:
        f = None

    result = []         #html에 보낼 결과리스트
    url_check = []      #url 중복 확인용

    for i, url in enumerate(urls):
        d = {}          #결과 리스트에 저장할 각 url별 결과 사전

        d['count'] = i + 1
        d['url'] = url
        
        if url in url_check:
            #중복
            d['success'] = -1
            d['word_count'] = -1
            d['duration'] = -1
        else:
            #중복이 아니면 분석
            url_check.append(url)       #중복 확인용으로 넣기
            word = []                   #크롤링할 단어리스트

            #크롤링으로 단어 뽑아오기
            try:
                #url get 성공
                page = requests.get(url)
                d['success'] = 1

                #시간 측정 시작
                start = time.time() 

                #크롤링
                soup = BeautifulSoup(page.content, "html.parser")
                body = str(soup.find('body'))
                text = getText(body).lower()
                text = word_tokenize(text)

                #의미 있는 단어만 뽑기
                for i in text:
                    if i not in stopwords.words("english"):
                        word.append(i)

                d['word_count'] = len(word)
                d['duration'] = time.time() - start
                
                doc = {}

                #엘라스틱 서치에 넣기
                try:
                    #인덱스가 있으면 불러오고
                    doc = es.get(index='final',doc_type='test', id=1)
                    doc = doc['_source']
                                
                    #중복 url 여부 확인
                    if url not in doc['url']:
                        doc['url'].append(url)
                        doc['words'].append(word)
                except:
                    #없으면 새로 만들기
                    doc = {}
                    doc['url'] = [url]
                    doc['words'] = [word]
                
                #엘라스틱 서치에 넣기
                es = Elasticsearch([{'host':es_host, 'port':es_port}], timeout=100)
                es.index(index='final', doc_type='test', id=1, body=doc)
            except requests.ConnectionError:
                #url get 실패
                d['success'] = 0
                d['word_count'] = 0
                d['duration'] = 0
        
        result.append(d)

    return render_template('Result_page.html', result=result)

#단어 분석 팝업창
@app.route('/tf_idf', methods=['POST'])
def pop():
    return render_template('Top10_page.html')

#유사도 분석 팝업창
@app.route('/cosine', methods=['POST'])
def pop2():
    return render_template('Similarity3_page.html')

if __name__ == '__main__':
    app.run(debug=False)