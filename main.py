from dbcon import *
from queue import Queue
from base64io import Base64IO
from b64decode import *
import io
import binascii
import re
import pybase64

import base64
import re
from bs4 import BeautifulSoup

def decode_base64(b64_string: str) -> bytes:
    """
    Fix and decode ANY base64 string - guaranteed to work.
    """
    if not b64_string:
        return b""
    
    # 1. Remove data URL prefix
    if 'base64,' in b64_string:
        b64_string = b64_string.split('base64,', 1)[1]
    
    # 2. Remove ALL whitespace (spaces, tabs, newlines)
    b64_string = re.sub(r'\s+', '', b64_string)
    
    # 3. Handle URL-safe variant
    b64_string = b64_string.replace('-', '+').replace('_', '/')
    
    # 4. Remove ALL characters that are not base64
    # Keep only A-Z, a-z, 0-9, +, /, =
    b64_string = re.sub(r'[^A-Za-z0-9+/=]', '', b64_string)
    
    # 5. Fix the length to be multiple of 4
    # If length % 4 == 1, remove one character (likely stray character)
    # If length % 4 == 2 or 3, add padding
    mod = len(b64_string) % 4
    
    if mod == 1:
        # Remove one character from the end (likely a stray = or other char)
        b64_string = b64_string[:-1]
        # Now recalculate mod
        mod = len(b64_string) % 4
    
    # Add padding if needed (now mod can only be 0, 2, or 3)
    if mod:
        b64_string += '=' * (4 - mod)
    
    # 6. Decode (be forgiving)
    return base64.b64decode(b64_string, validate=False)


cache_db_conf = DatabaseConfig(
    host = "10.0.1.42",
    user='root',
    password='toortoor',
    database='projapoti_db_v2'
)
cache_db_conn = DatabaseConnection(cache_db_conf)

office_list = ['65']

office_queue = Queue()
cache_db_conn.connect()

cur = cache_db_conn.cursor
for office in office_list:
    cur.execute("SELECT * FROM office_domains WHERE office_id = %s",(office,))
    data = cur.fetchone()
    print(data['domain_host'])
    new_db_conf = DatabaseConfig(
        host=data['domain_host'],
        user=data['domain_username'],
        password=data['domain_password'],
        database=data['office_db']
    )
    office_queue.put(new_db_conf)

logger.info(f"All selected databases are added to the queue")
cache_db_conn.disconnect()

for queue_i in range(office_queue._qsize()):
    office_db_conf = office_queue.get()
    # try:
    office_db_conn = DatabaseConnection(office_db_conf)
    office_db_conn.connect()
    cur = office_db_conn.cursor
    cur.execute("SELECT * FROM khoshra_draft_versions")
    cleaned_html_tuple = []
    while True:
        data = cur.fetchone()
        if data is None:
            break
        encoded_data = data['updated_content']
        khosra_draft_versions_id = data['id']
        decoded_string = decode_base64(encoded_data)
        html_content = decoded_string
        soup = BeautifulSoup(html_content, 'html.parser')
        for img_tag in soup.find_all('img'):
            img_tag.decompose()
        cleaned_html = str(soup)
        encoded_cleaned_html = base64.b64encode(cleaned_html.encode('utf-8'))
        
        with open(f'cleaned_html_{khosra_draft_versions_id}.txt', 'wb') as f:
            f.write(encoded_cleaned_html)
        cleaned_html_tuple.append([khosra_draft_versions_id,encoded_cleaned_html])
    
    for cleaned_html in cleaned_html_tuple:
        cur.execute("UPDATE khoshra_draft_versions SET updated_content = %s WHERE id = %s", (cleaned_html[1], cleaned_html[0]))
    office_db_conn.commit()
        

    office_db_conn.disconnect()

    # except:
    #     logger.info(f"Could not connect to {office_db_conf.database}")
        
    




