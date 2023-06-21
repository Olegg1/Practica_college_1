from flask import Flask, jsonify, render_template, request, redirect, url_for,\
                    make_response
import mysql.connector
import os
import re
from datetime import datetime
import pymysql
import pytz
import schedule
import time

app = Flask(__name__, template_folder='../templates')


host = ''
user = ''
password = ''
db_name = ''
log_folder_path = ''
error_log_file_name = ''


@app.route('/app')
def index():
    return render_template('index.html')

@app.route('/get_json')
def get_json():
    conn = mysql.connector.connect(
        host=app.config['HOST'],
        user=app.config['USER'],
        password=app.config['PASSWORD'],
        database=app.config['DB_NAME']
    )
    # Выполнение запроса на чтение данных
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM {app.config['USER']}")
    rows = cursor.fetchall()

    # Преобразование результатов запроса в список словарей (JSON)
    result = []
    for row in rows:
        user = {'ip': row[1], 'date': row[2].replace(tzinfo=pytz.UTC).strftime('%Y-%m-%d %H:%M:%S'), 'request': row[3]}
        result.append(user)

    # Закрытие соединения с базой данных
    cursor.close()
    conn.close()

    # Возврат JSON-данных
    return jsonify(result)


def insert_data(ip, date, request):
    connection = pymysql.connect(
        host=app.config['HOST'],
        user=app.config['USER'],
        password=app.config['PASSWORD'],
        database=app.config['DB_NAME']
    )

    cursor = connection.cursor()
    sql_query = "INSERT INTO logs (ip, data, request_info) VALUES (%s, %s, %s)"

    values = [(ip[i], date[i], request[i]) for i in range(len(ip))]

    cursor.executemany(sql_query, values)
    rows_affected = cursor.rowcount

    if rows_affected > 0:
        print(f"{rows_affected} rows inserted successfully")
    else:
        print("No rows inserted")

    connection.commit()
    cursor.close()
    connection.close()

@app.route('/', methods=['GET', 'POST'])
def form():
    global host
    global user
    global password
    global db_name
    global log_folder_path
    global error_log_file_name

    if request.method == 'POST':
        # Получение данных из формы
        host = request.form['host']
        user = request.form['user']
        password = request.form['password']
        db_name = request.form['db_name']
        log_folder_path = request.form['log_folder_path']
        error_log_file_name = request.form['error_log_file_name']

        # Проверка заполненности всех полей
        if not host or not user or not password or not db_name or not log_folder_path or not error_log_file_name:
            # Вывод красным не заполненных полей
            errors = [field for field in
                      ['host', 'user', 'password', 'db_name', 'log_folder_path', 'error_log_file_name'] if
                      not request.form.get(field)]
            return render_template('form.html', errors=errors)

        # Сохранение данных в конфигурационных переменных Flask
        app.config['HOST'] = host
        app.config['USER'] = user
        app.config['PASSWORD'] = password
        app.config['DB_NAME'] = db_name
        app.config['LOG_FOLDER_PATH'] = log_folder_path
        app.config['ERROR_LOG_FILE_NAME'] = error_log_file_name

        # Переменная success для вывода сообщения об успешной отправке формы
        success = True
        # Перенаправление на страницу /app после успешной отправки формы
        with open('user_info.txt', 'w', encoding='utf-8') as f:
            f.write(f'HOST: {host}, USER: {user}\n'
                    f'PASSWORD: {password}, DB_NAME: {db_name}\n'
                    f'LOG_FOLDER_PATH: {log_folder_path}\n, ERROR_LOG_FILE_NAME: {error_log_file_name}')

        return redirect(url_for('index'))

    else:
        success = False

    # Инициализация переменных
    host = app.config.get('HOST', '')
    user = app.config.get('USER', '')
    password = app.config.get('PASSWORD', '')
    db_name = app.config.get('DB_NAME', '')

    return render_template('form.html', success=success, host=host, user=user, password=password, db_name=db_name)

def parse_access_log():
    log_folder = app.config['LOG_FOLDER_PATH']
    error_log_filename = app.config['ERROR_LOG_FILE_NAME']
    print(log_folder, error_log_filename)
    error_log_file_path = os.path.join(log_folder, error_log_filename)
    if os.path.exists(error_log_file_path):
        with open(error_log_file_path, "r") as f:
            content = f.readlines()
        return content
    else:
        print(f"File {error_log_file_path} not found.")
        return []


def extract_ips(log_lines):
    ip_pattern = r'(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)|\:\:1|(?:[a-f0-9]{1,4}:){7}[a-f0-9]{1,4}'
    matches = []
    for log_line in log_lines:
        ips = re.findall(ip_pattern, log_line)
        for i in range(len(ips)):
            if ips[i] == '::1 - -':
                ips[i] = '127.0.0.1'
        matches += ips
    return matches


def extract_date(log_line):
    # Извлечь дату из строки лога с помощью регулярного выражения
    pattern = r'\[(\d{2})/(\w{3})/(\d{4}):(\d{2}):(\d{2}):(\d{2})'
    match = re.search(pattern, log_line)
    date_str = match.group(0)[1:]

    # Преобразовать строку даты в объект datetime
    date_obj = datetime.strptime(date_str, '%d/%b/%Y:%H:%M:%S')

    # Вернуть отформатированную дату и время как строку
    formatted_date = date_obj.strftime('%Y:%m:%d %H:%M:%S')

    return formatted_date


def extract_request(log_line):
    # Извлечь запрос из строки лога с помощью регулярного выражения
    pattern = re.compile(r'("GET .*?"|"POST .*?")')
    matches = re.findall(pattern, log_line)

    # Удалить кавычки из каждого элемента списка
    requests = [match.strip('"') for match in matches]

    return requests if requests else None


def get_parsed_data(data):
    # Ваши переменные и код для их вычисления
    ips = extract_ips(data)
    date = [extract_date(line) for line in data]
    requests = [extract_request(line) for line in data]

    # Возвращаем значения переменных
    return ips, date, requests


@app.route('/insert_data', methods=['POST'])
def insert_data_route():
    print(host, user, 'www')
    data = parse_access_log()
    ips, dates, requests = get_parsed_data(data)

    # Получение существующих данных из базы данных
    conn = mysql.connector.connect(
        host=app.config['HOST'],
        user=app.config['USER'],
        password=app.config['PASSWORD'],
        database=app.config['DB_NAME']
    )
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM {app.config['USER']}")
    existing_dates = [row[2] for row in cursor.fetchall()]

    out = []
    for existing_date in existing_dates:
        if existing_date is not None:
            out.append(existing_date.replace(tzinfo=pytz.UTC).strftime('%Y:%m:%d %H:%M:%S'))
        else:
            out.append('')
    # print(existing_dates[0], out[-1])
    cursor.close()
    conn.close()

    new_data = []
    for i in range(len(dates)):
        if dates[i] not in out:
            new_data.append((ips[i], dates[i], requests[i]))

    # Если новых данных нет, то не вызываем функцию insert_data()
    if not new_data:
        response = make_response(jsonify({'message': 'Data already exists in database'}))
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Expires'] = 0
        return response

    # Вызов функции insert_data() с новыми данными
    ips, dates, requests = zip(*new_data)
    insert_data(list(ips), list(dates), list(requests))

    # Создание HTTP-ответа с заголовками Cache-Control и Expires
    response = make_response(jsonify({'message': 'Data inserted successfully'}))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Expires'] = 0
    return response

@app.route('/get_config')
def get_config():
    config = {
        'host': app.config['HOST'],
        'user': app.config['USER'],
        'password': app.config['PASSWORD'],
        'db_name': app.config['DB_NAME'],
        'log_folder_path': app.config['LOG_FOLDER_PATH'],
        'error_log_file_name': app.config['ERROR_LOG_FILE_NAME']
    }
    return jsonify(config)


@app.route('/user_data')
def user_data():
    return render_template('user_data.html')


if __name__ == '__main__':
    app.run(port=5000, debug=True)


# При входе на сайт меняем фильтры и получаем отфильтрованные данные
# Сохраняем переменные чтобы не вылетали все время + записываем их
# Обновляем по времени