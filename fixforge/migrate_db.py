import sqlite3, glob

for db in glob.glob('./**/fixforge.db', recursive=True):
    print('Checking', db)
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    cur.execute('PRAGMA table_info(review_sessions)')
    cols = [r[1] for r in cur.fetchall()]
    print('Existing cols in', db, ':', cols)
    if 'llm_mode' not in cols:
        print('Adding llm_mode...')
        cur.execute("ALTER TABLE review_sessions ADD COLUMN llm_mode VARCHAR(20) DEFAULT 'fallback'")
    if 'docker_mode' not in cols:
        print('Adding docker_mode...')
        cur.execute("ALTER TABLE review_sessions ADD COLUMN docker_mode VARCHAR(20) DEFAULT 'unavailable'")
    conn.commit()
    conn.close()
print("Done migrating existing db files.")
