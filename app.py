import requests
import json
from flask import Flask, request, abort,render_template, jsonify, redirect, url_for,session
from urllib import parse
from linebot import LineBotApi
from linebot.models import *
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import openai
from openai import OpenAI
from pprint import pprint
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import configparser


# Setup
config = configparser.ConfigParser()
config.read('config.ini')

line_login_id = config.get('Line','line_login_id')
line_login_secret = config.get('Line','line_login_secret')
end_point = config.get('end_point','web')
DB_end_point = config.get('end_point','DB')


app = Flask(__name__)
app.secret_key = 'your_secret_key'  # 應該使用安全的隨機字符串


@app.route('/',  methods=['GET','POST'])
def index():

    userId = session.get('userId')
    name = session.get('name')
    dialogList = session.get('dialogList')

    if userId == None:
        print('not in session')
        dialogList = []
        session['dialogList'] = dialogList
        print(f"對話內容:{session['dialogList']}")
    if userId :
        print(name,userId)
        return render_template('index.html',dialogList=dialogList, name=name,userId=userId)
    else:
        print(userId)
        return render_template('index.html',dialogList=dialogList, client_id=line_login_id, end_point=end_point, userId=userId)
    

@app.route('/process_data' , methods=["POST"])
def process_data():
    dialogList = session.get('dialogList')
    userId = session.get('userId')
    Udata = request.form.get("Udata")
    print(Udata)

    # OpenAi API 回傳的答案
    # Rdata = OpenAI_process_data(Udata)

    # DB
    response = requests.post(f'{DB_end_point}/question_answer', 
                        json={"userId":userId, "question": Udata})
    Rdata = response.text
    

    dialog = { "You" : Udata, "LawBot" : Rdata }
    dialogList.append(dialog)
    session['dialogList'] = dialogList
    print(dialogList)
    identity = {"userId":userId ,"dialogList":dialogList}
    return identity


@app.route('/line_login', methods=['GET'])
def login():
    code = request.args.get("code", None)
    state = request.args.get("state", None)
    if code and state:
        HEADERS = {'Content-Type': 'application/x-www-form-urlencoded'}
        url = "https://api.line.me/oauth2/v2.1/token"
        FormData = {"grant_type": 'authorization_code', "code": code, "redirect_uri": F"{end_point}/line_login", "client_id": line_login_id, "client_secret":line_login_secret}
        data = parse.urlencode(FormData)
        content = requests.post(url=url, headers=HEADERS, data=data).text
        content = json.loads(content)
        
        url = "https://api.line.me/v2/profile"
        HEADERS = {'Authorization': content["token_type"]+" "+content["access_token"]}
        content = requests.get(url=url, headers=HEADERS).text
        content = json.loads(content)
        session['userId'] = content["userId"]
        session['name'] = content["displayName"]

        # 資料庫 參考 模擬用戶數據庫
        # session['dialogList'] = users[session['userId']]['dialogList']  
        
        response = requests.get(f'{DB_end_point}/history', params={"userId":session['userId'] })
        pprint(response.text)

        def answerTypeChange(a):
            answer = []
            split_sentence = a.split('\n')
            #print(split_sentence)
            for i in range(0,len(split_sentence),2):
                try:
                    answer.append({'LawBot':split_sentence[i+1][4:].strip(), 'You':split_sentence[i][7:].strip()})
                except:
                    answer.append({'LawBot':'', 'You':split_sentence[i][7:].strip()})
            return answer
        

        session['dialogList'] = answerTypeChange(response.text)

        cont = session['dialogList'][0]["LawBot"]
        if cont == "" : session['dialogList'] = []

        print(f"對話內容:{session['dialogList']}")

        return redirect(url_for('index'))


@app.route('/logout')
def logout():

    # 從 session 中移除用戶信息
    session.pop('userId', None)
    session.pop('name', None)
    session.pop('dialogList',[])
    return redirect(url_for('index'))


def send_email(sender_email, receiver_email, subject, message_body):
    # 設置郵件內容
    message = MIMEMultipart()
    message['From'] = sender_email
    message['To'] = receiver_email
    message['Subject'] = subject

    # 添加郵件正文
    message.attach(MIMEText(message_body, 'plain'))

    # 使用您的郵件服務器信息
    smtp_server = 'smtp.gmail.com'
    port = 587  # 一般是 587 或 465
    username = config.get('email','username') 
    password =  config.get('email','password') 

    # 連接郵件服務器
    server = smtplib.SMTP(smtp_server, port)
    server.starttls()  # 使用 TLS 加密通信
    server.login(username, password)

    # 發送郵件
    text = message.as_string()
    server.sendmail(sender_email, receiver_email, text)

    # 關閉連接
    server.quit()

@app.route('/submit_form', methods=['POST'])
def submit_form():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        message = request.form['message']

        # 在這裡添加您的郵件發送邏輯
        # 例如，您可以使用 Python 的郵件庫來發送電子郵件
        # 調用發送郵件函數
        sender_email =  config.get('email','sender_email') 
        receiver_email =  config.get('email','sender_email') 
        subject = 'New message from your website 法律問答'
        message_body = f"Name: {name}\nEmail: {email}\n\nMessage:\n{message}"
        send_email(sender_email, receiver_email, subject, message_body)

        # 重定向回表單頁面
        return redirect('/')


if __name__ == '__main__':
    app.run(debug=True)


