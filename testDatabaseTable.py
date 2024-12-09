from datetime import datetime, timedelta
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///reservations.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class RoomAvailability(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(10), nullable=False, unique=True)
    available_rooms = db.Column(db.Integer, nullable=False)

# ฟังก์ชันเพื่อเพิ่มข้อมูลลงในฐานข้อมูล
def initialize_room_availability():
    start_date = datetime.now().date()  # วันที่เริ่มต้นเป็นวันปัจจุบัน
    end_date = start_date + timedelta(days=60)  # กำหนดระยะเวลา 60 วันข้างหน้า

    current_date = start_date
    while current_date <= end_date:
        date_str = current_date.strftime('%Y-%m-%d')  # แปลงวันที่เป็น string ในรูปแบบ YYYY-MM-DD
        available_rooms = 3  # จำนวนห้องว่างเริ่มต้น

        # เพิ่มข้อมูลลงในฐานข้อมูล
        room_availability = RoomAvailability(date=date_str, available_rooms=available_rooms)
        db.session.add(room_availability)

        # ขยับวันที่ไปวันถัดไป
        current_date += timedelta(days=1)

    db.session.commit()  # คอมมิทเพื่อบันทึกข้อมูลลงในฐานข้อมูล

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # สร้างตารางในฐานข้อมูลหากยังไม่มี
        initialize_room_availability()  # เรียกฟังก์ชันเพื่อเพิ่มข้อมูล

# git reposition token repo/workflow "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"
