from flask import Flask, jsonify, render_template, request, redirect, url_for,\
                    make_response, Response
from typing import *
import mysql.connector
import os
import re
from datetime import datetime
import pymysql
import pytz

app = Flask(__name__, template_folder='../templates')
host = ''
user = ''
password = ''
db_name = ''
log_folder_path = ''
error_log_file_name = ''


@app.route('/app')
def index() -> str:
    """
    Renders the index.html template when a GET request is made to /app.

    Returns:
        rendered HTML content (str): The HTML content of the index.html template.
    """

    return render_template('index.html')



@app.route('/get_json')
def get_json() -> str:
    """
    Retrieves data from a MySQL database and returns it as JSON.

    Returns:
        JSON (str): A string representation of the retrieved data in JSON format.

    Raises:
        Exception: If there is an error connecting to the database or executing the query.
    """
    try:
        conn = mysql.connector.connect(
            host=app.config['HOST'],
            user=app.config['USER'],
            password=app.config['PASSWORD'],
            database=app.config['DB_NAME']
        )

        # Execute a SELECT query to retrieve all the data from the USER table
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM {app.config['USER']}")
        rows = cursor.fetchall()

        # Convert the retrieved data into a list of dictionaries (JSON)
        result = []
        for row in rows:
            if row[2] is not None:
                date = row[2].replace(tzinfo=pytz.UTC).strftime('%Y-%m-%d %H:%M:%S')
            else:
                date = None

            user = {
                'ip': row[1],
                'date': date,
                'requested_URL': row[3],
                'response_code': row[4],
                'response_size': row[5],
                'user_agent': row[6]
            }
            result.append(user)

        # Close the connection to the database
        cursor.close()
        conn.close()

        # Return the retrieved data as JSON
        return jsonify(result)
    except Exception as e:
        return f'An error occurred: {e}'


def insert_data(ip: list[str], date: list[str], requested_URL: list[str], response_code: list[int],
                response_size: list[int], user_agent: list[str]) -> None:
    """
    Inserts data into a MySQL database.

    Args:
        ip (list): A list of IP addresses as strings.
        date (list): A list of dates in string format.
        requested_URL (list): A list of URLs as strings.
        response_code (list): A list of HTTP response codes as integers.
        response_size (list): A list of response sizes as integers.
        user_agent (list): A list of User-Agent strings.

    Returns:
        None

    Raises:
        Exception: If there is an error inserting data into the database.
    """
    try:
        connection = pymysql.connect(
            host=app.config['HOST'],
            user=app.config['USER'],
            password=app.config['PASSWORD'],
            database=app.config['DB_NAME']
        )

        cursor = connection.cursor()

        sql_query = "INSERT INTO logs (ip, data, requested_URL, response_code, response_size, user_agent) \
                     VALUES (%s, %s, %s, %s, %s, %s)"

        values = [(ip[i], date[i], requested_URL[i], response_code[i], response_size[i], user_agent[i])
                  for i in range(len(ip))]

        cursor.executemany(sql_query, values)
        rows_affected = cursor.rowcount

        if rows_affected > 0:
            print(f"{rows_affected} rows inserted successfully")
        else:
            print("No rows inserted")

        connection.commit()
        cursor.close()
        connection.close()
    except Exception as e:
        return f'An error occurred: {e}'


@app.route('/', methods=['GET', 'POST'])
def form() -> str:
    """
    Renders a form template and processes its data when submitted.

    Returns:
        rendered HTML content (str): The HTML content of the rendered template.
    """
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
        return redirect(url_for('index'))

    else:
        success = False

    # Инициализация переменных
    host = app.config.get('HOST', '')
    user = app.config.get('USER', '')
    password = app.config.get('PASSWORD', '')
    db_name = app.config.get('DB_NAME', '')
    log_folder_path = app.config.get('LOG_FOLDER_PATH', '')
    error_log_file_name = app.config.get('ERROR_LOG_FILE_NAME', '')

    return render_template('form.html', success=success, host=host, user=user, password=password, db_name=db_name,
                           log_folder_path=log_folder_path, error_log_file_name=error_log_file_name)


def parse_access_log() -> list:
    """
    Parses an error log file and returns its contents as a list of strings.

    Returns:
        List[str]: A list of strings representing the contents of the error log file.
        An empty list is returned if the file does not exist.

    Raises:
        Exception: If there is an error reading the error log file.
    """
    try:
        log_folder = app.config['LOG_FOLDER_PATH']
        error_log_filename = app.config['ERROR_LOG_FILE_NAME']
        error_log_file_path = os.path.join(log_folder, error_log_filename)
        if os.path.exists(error_log_file_path):
            with open(error_log_file_path, "r") as f:
                content = f.readlines()
            return content
        else:
            print(f"File {error_log_file_path} not found.")
            return []
    except Exception as e:
        return f'An error occurred: {e}'


def extract_ips(log_lines: List[str]) -> List[str]:
    """
    Extracts IP addresses from a list of log lines.

    Args:
        log_lines (List[str]): A list of log lines as strings.

    Returns:
        List[str]: A list of IP addresses as strings.
    """
    ip_pattern = r'(?:[0-9]{1,3}\.){3}[0-9]{1,3}|x\.x\.x\.90|\:\:1|(?:[a-f0-9]{1,4}:){7}[a-f0-9]{1,4}'
    matches = []
    for log_line in log_lines:
        ips = re.findall(ip_pattern, log_line)
        found_ip = False
        for i in range(len(ips)):
            found_ip = True
        if found_ip:
            matches += ips
        else:
            matches.append('Неизвестно')
    return matches


def extract_date(log_line: str) -> str:
    """
    Extracts a date from a log line string using regular expressions and returns it as a formatted string.

    Args:
        log_line (str): A log line as a string.

    Returns:
        str: A formatted date and time string as '%Y-%m-%d %H:%M:%S'.
        If a valid date cannot be extracted, returns 'Неизвестно'.
    """
    # Извлечь дату из строки лога с помощью регулярного выражения
    pattern1 = r'\b\w{3}\s+\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\s+\d{4}\b'
    pattern2 = r'\d{1,2}/\w{3}/\d{4}:\d{2}:\d{2}:\d{2}'

    match = re.search(pattern1, log_line)
    if not match:
        match = re.search(pattern2, log_line)
        if not match:
            return 'Неизвестно'

    # Преобразовать строку даты в объект datetime
    date_str = match.group(0)
    try:
        if match.re.pattern == pattern1:
            date_obj = datetime.strptime(date_str, '%a %b %d %H:%M:%S %Y')
        else:
            date_obj = datetime.strptime(date_str, '%d/%b/%Y:%H:%M:%S')
    except ValueError:
        return 'Неизвестно'
    # Вернуть отформатированную дату и время как строку
    formatted_date = date_obj.strftime('%Y-%m-%d %H:%M:%S')
    return formatted_date


def extract_request(log_line: str) -> Union[str, List[str]]:
    """
    Extracts a request from a log line string using regular expressions and returns it as a list of strings.

    Args:
        log_line (str): A log line as a string.

    Returns:
        Union[str, List[str]]: A list of requests as strings.
        If a valid request cannot be extracted, returns 'Неизвестно'.
    """
    # Извлечь запрос из строки лога с помощью регулярного выражения
    pattern = re.compile(r'("GET .*?"|"POST .*?"|"PROPFIND .*?")')
    matches = re.findall(pattern, log_line)

    # Удалить кавычки из каждого элемента списка
    requests = [match.strip('"') for match in matches]

    return requests if requests else 'Неизвестно'


def extract_response_code(log_line: str) -> Union[str, None]:
    """
    Extracts a response code from a log line string using regular expressions and returns it as a string.

    Args:
        log_line (str): A log line as a string.

    Returns:
        Union[str, None]: A string representing the response code or None if not found.
        If a valid response code cannot be extracted, returns 'Неизвестно'.
    """
    # Извлечь код ответа HTTP из строки лога с помощью регулярного выражения
    pattern = re.compile(r'\s(\d{3})\s')
    match = re.search(pattern, log_line)

    # Вернуть найденный код ответа или None, если не найдено
    return match.group(1) if match else 'Неизвестно'


def extract_response_size(log_line: str) -> Union[str, None]:
    """
    Extracts a response size from a log line string using regular expressions and returns it as a string.

    Args:
        log_line (str): A log line as a string.

    Returns:
        Union[str, None]: A string representing the response size or None if not found.
        If a valid response size cannot be extracted, returns 'Неизвестно'.
    """
    # Извлечь размер ответа HTTP из строки лога с помощью регулярного выражения
    pattern = re.compile(r'\s\d{3}\s(\d+)')
    match = re.search(pattern, log_line)

    # Вернуть найденный размер ответа или None, если не найдено
    return match.group(1) if match else 'Неизвестно'


def parse_user_agent(user_agent: str) -> str:
    """
    Parses a user agent string to extract browser and operating system information.

    Args:
        user_agent (str): A user agent string.

    Returns:
        str: A string containing the browser name, version, and operating system.
        If any information cannot be extracted, returns 'Неизвестно'.
    """
    # Регулярные выражения для поиска браузера и операционной системы
    browser_regex = r'(Chrome|Firefox|Safari|Edge|MSIE)[/\s](\d+\.\d+)'
    os_regex = r'\((Windows|Mac OS|Linux|iPhone|iPad|iPod|Android)[^)]*\)'

    # Извлечение информации о браузере
    browser_match = re.search(browser_regex, user_agent)
    browser_name = browser_match.group(1) if browser_match else 'Неизвестно'
    browser_version = browser_match.group(2) if browser_match else 'Неизвестно'

    # Извлечение информации об операционной системе
    os_match = re.search(os_regex, user_agent)
    os_name = os_match.group(1) if os_match else 'Неизвестно'

    # Сконкатенирование данных о браузере и операционной системе
    result = f"Браузер: {browser_name} {browser_version}, ОС: {os_name}"

    # Возвращение результата
    return result


def get_parsed_data(data: List[str]) -> Tuple[List[str], List[str], List[Union[str, List[str]]],
                                               List[Union[str, None]], List[Union[str, None]], List[str]]:
    """
    Parses a list of log lines to extract IP addresses, dates, requested URLs, response codes, response sizes,
    and user agents.

    Args:
        data (List[str]): A list of log lines as strings.

    Returns:
        Tuple[List[str], List[str], List[Union[str, List[str]]], List[Union[str, None]], List[Union[str, None]], List[str]]:
            A tuple containing the parsed data as lists in the following order:
            - A list of IP addresses as strings.
            - A list of dates as strings.
            - A list of requested URLs as strings or lists of strings.
            - A list of response codes as strings or None.
            - A list of response sizes as strings or None.
            - A list of user agents as strings.
            If any information cannot be extracted, returns 'Неизвестно'.
    """
    # Ваши переменные и код для их вычисления
    ips = extract_ips(data)
    date = [extract_date(line) for line in data]
    requested_URL = [extract_request(line) for line in data]
    response_codes = [extract_response_code(line) for line in data]
    response_sizes = [extract_response_size(line) for line in data]
    user_agents = [parse_user_agent(line) for line in data]

    # Возвращаем значения переменных в виде кортежа
    return ips, date, requested_URL, response_codes, response_sizes, user_agents


@app.route('/insert_data', methods=['POST'])
def insert_data_route() -> str:
    """
    Inserts parsed log data into a MySQL database table via HTTP POST request.

    Returns:
        str: A string containing a success or error message.
    """
    data = parse_access_log()
    ips, dates, requested_URL, response_codes, response_sizes, user_agents = get_parsed_data(data)

    # Получение существующих данных из базы данных
    try:
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
                out.append(existing_date.replace(tzinfo=pytz.UTC).strftime('%Y-%m-%d %H:%M:%S'))
            else:
                out.append('')
        cursor.close()
        conn.close()

        new_data = []
        for i in range(len(dates)):
            if dates[i] not in out:
                new_data.append(
                    (ips[i], dates[i], requested_URL[i], response_codes[i], response_sizes[i], user_agents[i]))

        # Если новых данных нет, то не вызываем функцию insert_data()
        if not new_data:
            response = make_response(jsonify({'message': 'Data already exists in database'}))
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Expires'] = 0
            return response

        # Вызов функции insert_data() с новыми данными
        ips, dates, requested_URL, response_codes, response_sizes, user_agents = zip(*new_data)
        insert_data(list(ips), list(dates), list(requested_URL), list(response_codes), list(response_sizes),
                    list(user_agents))

        # Создание HTTP-ответа с заголовками Cache-Control и Expires
        response = make_response(jsonify({'message': 'Data inserted successfully'}))
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Expires'] = 0
        return response
    except Exception as e:
        return f'Вы не ввели данные, {e}'


@app.route('/get_config')
def get_config() -> Union[str, Response]:
    """
    Returns a JSON object containing the configuration data for the Flask application.

    Returns:
        Union[str, Response]: If successful, returns a Flask Response object containing a JSON representation
        of the configuration data. Otherwise, returns a string with an error message.
    """
    try:
        config = {
            'host': app.config['HOST'],
            'user': app.config['USER'],
            'password': app.config['PASSWORD'],
            'db_name': app.config['DB_NAME'],
            'log_folder_path': app.config['LOG_FOLDER_PATH'],
            'error_log_file_name': app.config['ERROR_LOG_FILE_NAME']
        }
        return jsonify(config)
    except Exception as e:
        return f'Вы не ввели данные, {e}'

@app.route('/user_data')
def user_data() -> str:
    """
    Renders the 'user_data.html' template.

    Returns:
        str: A string containing the rendered HTML template.
    """
    return render_template('user_data.html')


def filter_json() -> Response:
    """
    Filters data from a MySQL database table based on start and end datetime values provided in an HTTP POST request.

    Returns:
        Response: A Flask Response object containing the filtered data as a JSON array.
    """
    # Получение данных фильтров из запроса
    start_datetime = request.json.get('start-datetime')
    end_datetime = request.json.get('end-datetime')

    # Подключение к базе данных
    conn = mysql.connector.connect(
        host=app.config['HOST'],
        user=app.config['USER'],
        password=app.config['PASSWORD'],
        database=app.config['DB_NAME']
    )

    # Выполнение SQL-запроса с использованием фильтров
    cursor = conn.cursor()
    query = f"SELECT * FROM your_table WHERE date >= '{start_datetime}' AND date <= '{end_datetime}'"
    cursor.execute(query)
    result = cursor.fetchall()

    # Закрытие соединения с базой данных
    conn.close()

    # Формирование результата в формате JSON
    filtered_data = []
    for row in result:
        item = {
            'ip': row[0],
            'date': row[1],
            'requested_URL': row[2],
            'response_code': row[3],
            'response_size': row[4],
            'user_agent': row[5]
        }
        filtered_data.append(item)

    return jsonify(filtered_data)


# Execute
if __name__ == '__main__':
    app.run(port=5000, debug=True)
