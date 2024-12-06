import sqlite3


def list_tables():
    con = sqlite3.connect('instance/reservations.db')  # ใช้ path ของฐานข้อมูลที่คุณอัพโหลด
    cur = con.cursor()

    # ดึงรายชื่อของทุกตารางในฐานข้อมูล
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cur.fetchall()

    if tables:
        print("Tables in the database:")
        for table in tables:
            print(table[0])
    else:
        print("No tables found in the database.")

    con.close()


# เรียกฟังก์ชันเพื่อแสดงรายชื่อตารางทั้งหมด
list_tables()
