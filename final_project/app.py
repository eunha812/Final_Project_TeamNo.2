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

#doc_list: 전체 문서 단어리스트
#index: 구할 url 인덱스
def compute_tf_idf(index, doc_list):
    #-----------tf 계산------------#
    bow = set()             #전체 문서 단어 집합
    
    word_d = {}             #단어 출현 수 저장 사전

    for word in doc_list[index]:
        if word not in word_d.keys():
            word_d[word]=0
        word_d[word] += 1
        bow.add(word)
    
    tf_d = {}               #단어별 tf 저장 사전
    for word, cnt in word_d.items():
        tf_d[word] = cnt/float(len(bow))

    #-----------idf 계산-----------#
    Dval = len(doc_list)    #문서 개수
    
    #나머지 문서 단어 집합에 넣기
    for i in range(0, Dval):
        if i == index:
            continue
        for tok in doc_list[i]:
            bow.add(tok)

    idf_d = {}
    tf_idf = {}
    for t in bow:
        if t not in tf_d.keys():
            tf_d[t] = 0
        else:
            cnt = 0
            for s in doc_list:
                if t in s:
                    cnt += 1
        
        idf_d[t] = math.log10(Dval/float(cnt))
        tf_idf[t] = tf_d[t]*idf_d[t]
    
    #-----------top10 계산-----------#
    sortList = sorted(tf_idf.items(), key = lambda x: x[1], reverse = True)

    top = []
    if len(sortList) < 10:
        for t in sortList:
            top.append(t[0])
    else:
        for i in range(10):
            t = sortList[i]
            top.append(t[0])

    return top

def make_vector(index, doc_list):
    bow = set()             #전체 문서 단어 집합
    v = []                  #vector
    doc = doc_list[index]

    #전체 문서 단어들 집합에 넣기
    for d in doc_list:
        for w in d:
            bow.add(w)

    #vector계산
    for w in bow:
        val = 0
        for t in doc:
            if w==t:
                val +=1
        v.append(val)

    return v


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
        es = Elasticsearch([{'host':es_host, 'port':es_port}], timeout=30)

        doc = {}
        try:
            #인덱스가 있으면 불러오고
            doc = es.get(index='final',doc_type='test', id=1)
            doc = doc['_source']
            
            #중복 url 여부 확인
            if url not in doc['url']:
                doc['url'].append(url)
                doc['words'].append(word)
                doc['duration'].append(d['duration'])
                doc['tf'].append([])
                doc['cosine'].append([])
        except:
            #없으면 새로 만들기
            doc = {}
            doc['url'] = [url]
            doc['words'] = [word]
            doc['duration'] = [d['duration']]
            doc['tf'] = [[],]
            doc['cosine'] = [[],]
        
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

    for url in urls:
        d = {}          #결과 리스트에 저장할 각 url별 결과 사전

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
                
                #엘라스틱 서치에 문서 넣기
                es = Elasticsearch([{'host':es_host, 'port':es_port}], timeout=30)
                
                doc = {}
                try:
                    #인덱스가 있으면 불러오고
                    doc = es.get(index='final',doc_type='test', id=1)
                    doc = doc['_source']
                                
                    #중복 url 여부 확인
                    if url not in doc['url']:
                        doc['url'].append(url)
                        doc['words'].append(word)
                        doc['duration'].append(d['duration'])
                        doc['tf'].append([])
                        doc['cosine'].append([])
                except:
                    #없으면 새로 만들기
                    doc = {}
                    doc['url'] = [url]
                    doc['words'] = [word]
                    doc['duration'] = [d['duration']]
                    doc['tf'] = [[],]
                    doc['cosine'] = [[],]
                    
                #엘라스틱 서치에 넣기
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
    #엘라스틱 서치에서 문서 불러오기
    es = Elasticsearch([{'host':es_host, 'port':es_port}], timeout=30)
    
    try:
        doc = es.get(index='final',doc_type='test', id=1)
        doc = doc['_source']
    except:
        doc = None
    
    #url 받아오기
    try:
        url = request.form['url']
    except:
        url = None
    
    #문서내 url 인덱스 찾기
    url_index = -1
    for i, findUrl in enumerate(doc['url']):
        if url == findUrl:
            url_index = i

    top = compute_tf_idf(url_index, doc['words'])
    doc['tf'][url_index] = top

    #엘라스틱 서치에 넣기
    es.index(index='final', doc_type='test', id=1, body=doc)

    return render_template('Top10_page.html', top=top)

#유사도 분석 팝업창
@app.route('/cosine', methods=['POST'])
def pop2():
    #엘라스틱 서치에서 문서 불러오기
    es = Elasticsearch([{'host':es_host, 'port':es_port}], timeout=30)
    
    try:
        doc = es.get(index='final',doc_type='test', id=1)
        doc = doc['_source']
    except:
        doc = None
    
    #url 받아오기
    try:
        url = request.form['url']
    except:
        url = None
    
    #문서내 url 인덱스 찾기
    url_index = -1
    for i, findUrl in enumerate(doc['url']):
        if url == findUrl:
            url_index = i

    top = []
    #찾을 url의 단어 리스트
    findList = doc['words'][url_index]
    for i, otherList in enumerate(doc['url']):
        if url_index == i:
            continue
        v1 = make_vector(url_index, doc['words'])
        v2 = make_vector(i, doc['words'])
        dotpro = numpy.dot(v1,v2)
        norm1 = numpy.linalg.norm(v1)
        norm2 = numpy.linalg.norm(v2)
        cossimil = dotpro/norm1/norm2
        top.append((doc['url'][i], cossimil))
    
    top = sorted(top, key = lambda x : x[1], reverse = True)
    doc['cosine'][url_index] = top
    
    #엘라스틱 서치에 넣기
    es.index(index='final', doc_type='test', id=1, body=doc)

    return render_template('Similarity3_page.html', top=top)

if __name__ == '__main__':
    app.run(debug=False)