import requests
from bs4 import BeautifulSoup
import fake_useragent
import threading
import re
from googletrans import Translator
import pandas


url_main = 'https://www.dream-singles.com/'
url_login = url_main + 'dating-login.php?loc='
url_inbox_Page = url_main + 'messaging/inbox.php?mode=inbox&page={}&folder=-1'
url_sent_Page_Id = url_main + \
                     'messaging/inbox.php?mode=sent&page={}&folder=-1&q={}'
url_inbox_Page_Id = url_main + \
                    'messaging/inbox.php?mode=inbox&page={}&folder=-1&q={}'

payload = {
    'login': input('Enter login: '),
    'password':  input('Enter password: '),
    'remember_me': '1',
    '__tcAction': 'loginMember',
    'submit': ''
}

headers = {
    'User-Agent': fake_useragent.UserAgent().random
}


translator = Translator()
threadLock = threading.Lock()
threads = list()
messages = list()

client = requests.Session()
cookies = client.post(
    url_login,
    data=payload,
    headers=headers,
).cookies


def get_list_id_of_men():
    list_id_of_men = list()
    page = 0
    previous_text, current_text = 'HTML0', 'HTML1'
    while previous_text != current_text:
        page += 1

        html = client.get(
            url_inbox_Page.format(page),
            headers=headers,
            cookies=cookies,
        )

        soup = BeautifulSoup(html.text, "lxml")

        for n in soup.findAll('u', style=''):
            man_id = re.search(r'(\d+)<', str(n)).group(1)
            if man_id not in list_id_of_men:
                list_id_of_men.append(man_id)

        previous_text = current_text
        current_text = re.sub(
            r'page=\d+', '', str(soup.find('div', class_='message-list p0'))
        )
    return list_id_of_men


def get_list_url_messages(man_id, inbox=False, send=False):
    url = ''
    if inbox and not send:
        url = url_inbox_Page_Id
    elif send and not inbox:
        url = url_sent_Page_Id
    else:
        get_list_url_messages(man_id, inbox=True)
        get_list_url_messages(man_id, send=True)

    msg_url_list = list()
    page = 0
    previous_text, current_text = 'HTML0', 'HTML1'

    while previous_text != current_text:
        page += 1
        url_msgs = url.format(page, man_id)
        html = client.get(
                url_msgs,
                headers=headers,
                cookies=cookies,
            )

        soup = BeautifulSoup(html.text, "lxml")
        tags = soup.find_all('div', class_='visible-xs date-mob-blk')
        for tag in tags:
            url_m = url_main[:-1:] + tag.a['href']
            if url_m not in msg_url_list:
                msg_url_list.append(url_m)

        previous_text = current_text
        current_text = re.sub(
            r'page=\d+', '', str(soup.find('div', class_='message-list p0'))
        )

    return msg_url_list


def get_message_data(url):
    html = client.get(
            url,
            headers=headers,
            cookies=cookies
    )

    soup = BeautifulSoup(html.text, 'lxml')
    f_html = soup.find('div', class_="col-sm-12 bordered")
    if not f_html:
        return "Message not found. URL:\n" + url
    date = f_html.date
    text = f_html.contents
    rows = [str(row).replace('<br/>', '').replace('<p>', '').replace('</p>', '')
            for row in text if str(row) not in ['<br/>', '\n']]
    text = '\n'.join(rows)

    return text, date


def translate(text):
    try:
        return translator.translate(src='en', dest='ru', text=text).text
    except Exception as e:
        print('translate:', e)


class DialogueParser(threading.Thread):

    def __init__(self, man_id):
        threading.Thread.__init__(self)
        threads.append(self)
        self.id = man_id

    def run(self):
        man_messages = []
        url_messages_set = set(get_list_url_messages(self.id))
        for msg_url in url_messages_set:
            text, date = get_message_data(msg_url)
            translate_text = translate(text)
            man_messages.append([self.id, date, text, translate_text])

        threadLock.locked()
        messages.append(*man_messages)
        threadLock.release()


def main():
    list_id_of_men = set(get_list_id_of_men())
    for man_id in list_id_of_men:
        t = DialogueParser(man_id)
        t.start()

    for t in threads:
        t.join()

    messages.sort(key=lambda i: i[1])
    messages.sort(key=lambda i: i[0])

    df = pandas.DataFrame({
        'man_id': [m[0] for m in messages],
        'date': [m[1] for m in messages],
        'text': [m[2] for m in messages],
        'translate_text': [m[3] for m in messages]
    })
    df.to_excel('./messages.xlsx', sheet_name='massages', index=False)


if __name__ == '__main__':
    main()
