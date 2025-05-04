
from mega import Mega
import os
import uuid
from config import MEGA_EMAIL, MEGA_PASSWORD

mega = Mega()
m = mega.login(MEGA_EMAIL, MEGA_PASSWORD)

FOLDER_NAME = "secure_bot"

def ensure_folder():
    folders = m.get_files()
    for fid in folders:
        f = folders[fid]
        if f['t'] == 1 and f['a']['n'] == FOLDER_NAME:
            return f
    return m.create_folder(FOLDER_NAME)

def upload_file(file_bytes, filename):
    folder = ensure_folder()
    temp_path = f"temp_{uuid.uuid4()}_{filename}"
    with open(temp_path, 'wb') as f:
        f.write(file_bytes)
    m.upload(temp_path, folder[0])
    os.remove(temp_path)

def list_files():
    folder = ensure_folder()
    files = m.get_files()
    result = []
    for fid in files:
        f = files[fid]
        if f['t'] == 0 and f['p'] == folder[0]:
            result.append((f['a']['n'], f['h']))
    return result

def delete_file(file_id):
    m.destroy(file_id)
