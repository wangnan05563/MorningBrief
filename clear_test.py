import sqlite3
conn = sqlite3.connect('D:/code/otherProjects/20_News/backend/data/news.db')
cursor = conn.cursor()
cursor.execute('DELETE FROM episode WHERE id = 2')
conn.commit()
cursor.execute('SELECT id, date, title, audio_url, status FROM episode')
rows = cursor.fetchall()
for row in rows:
    print(row)
conn.close()
