from flask import Flask, request, render_template, jsonify
from flask_sqlalchemy import SQLAlchemy
import sqlite3
import os
from datetime import datetime, timedelta
import time
from PIL import Image, ImageDraw, ImageFont
import requests
import base64
import threading

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///reservations.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'

db = SQLAlchemy(app)

class Reservation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(15), nullable=False)
    checkin = db.Column(db.String(10), nullable=False)
    checkout = db.Column(db.String(10), nullable=False)
    slip = db.Column(db.String(100), nullable=False)

class RoomAvailability(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(10), nullable=False, unique=True)
    available_rooms = db.Column(db.Integer, nullable=False)

@app.route('/')
def hotel_information():
    update_thread = threading.Thread(target=update_room_availability)
    update_thread.start()
    return render_template('hotel_information.html')

@app.route('/status_room')
def status_room():
    return render_template('status_room.html')

@app.route('/reservation_form')
def reservation_form():
    return render_template('reservation_form.html')

@app.route('/submit-reservation', methods=['POST'])
def submit_reservation():
    name = request.form['name']
    phone = request.form['phone']
    checkin = request.form['checkin']
    checkout = request.form['checkout']
    slip = request.files['slip']

    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])

    current_time = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    slip_filename = os.path.join(app.config['UPLOAD_FOLDER'], f"{current_time}_{slip.filename}")
    slip.save(slip_filename)
    reservation_details = {
        'name': name,
        'phone': phone,
        'checkin': checkin,
        'checkout': checkout,
    }
    # สร้างภาพที่มีรายละเอียดการจอง
    image_path = create_reservation_image_with_details(reservation_details, slip_filename)

    # ส่งภาพผ่าน LINE
    line_token = 'ca7yuOC9DjF8FNfHZMaPRMtGORlydUUX83VqTwVoMiR'  # เปลี่ยนด้วย token ของคุณ
    send_line_image_2(image_path, line_token)

    # ตรวจสอบความพร้อมของห้อง
    checkin_date = datetime.strptime(checkin, '%Y-%m-%d')
    checkout_date = datetime.strptime(checkout, '%Y-%m-%d')
    date_to_check = checkin_date

    con = sqlite3.connect('instance/reservations.db')
    cur = con.cursor()

    while date_to_check < checkout_date:
        date_str = date_to_check.strftime('%Y-%m-%d')
        cur.execute("SELECT available_rooms FROM room_availability WHERE date = ?", (date_str,))
        row = cur.fetchone()
        if row is None:
            con.close()
            return jsonify({'message': f'No room availability data for {date_str}. Please select another date.'}), 400
        available_rooms = row[0]
        if available_rooms <= 0:
            con.close()
            return jsonify({'message': f'No rooms available on {date_str}. Please select another date.'}), 400
        date_to_check += timedelta(days=1)

    # ถ้าวันที่ที่เลือกมีห้องว่างทั้งหมดก็ทำการบันทึกการจอง
    new_reservation = Reservation(name=name, phone=phone, checkin=checkin, checkout=checkout, slip=slip_filename)
    db.session.add(new_reservation)
    db.session.commit()

    # อัปเดตจำนวนห้องว่างในแต่ละวันหลังจากการจอง
    date_to_update = checkin_date

    while date_to_update < checkout_date:
        date_str = date_to_update.strftime('%Y-%m-%d')
        cur.execute("SELECT available_rooms FROM room_availability WHERE date = ?", (date_str,))
        available_rooms = cur.fetchone()[0]
        available_rooms -= 1
        cur.execute("UPDATE room_availability SET available_rooms = ? WHERE date = ?", (available_rooms, date_str))
        date_to_update += timedelta(days=1)

    con.commit()
    con.close()

    # ดึงข้อมูลการจองทั้งหมดที่เรียงลำดับตามวันที่ check in ก่อนแล้ว
    reservations = Reservation.query.order_by(Reservation.checkin).all()
    # ดึงข้อมูลห้องว่างทั้งหมด
    room_availabilities = get_room_availability()
    # สร้างภาพ
    img = create_reservation_image(reservations, room_availabilities, new_reservation.id)
    save_image(img)

    # ส่งภาพผ่าน LINE
    line_token = 'ca7yuOC9DjF8FNfHZMaPRMtGORlydUUX83VqTwVoMiR'  # เปลี่ยนด้วย token ของคุณ
    send_line_image('reservation_details.jpg', line_token)

    upload_file_to_github(file_path, repo, path_in_repo, commit_message, branch, token)

    return jsonify({'message': 'reservation form was sent (*booking completed when full transaction completed only*)'})

@app.route('/get-room-status')
def get_room_status():
    reservations = RoomAvailability.query.all()
    events = []
    for reservation in reservations:
        if reservation.available_rooms > 0:
            events.append({
                'title': f'{reservation.available_rooms} rooms available',
                'start': reservation.date,
                'end': reservation.date,
                'overlap': False,
                'display': 'background',
                'color': '#d4edda'
            })
    return jsonify(events)

def get_reservation_data():
    con = sqlite3.connect('instance/reservations.db')
    cur = con.cursor()
    cur.execute("SELECT * FROM reservation")
    reservations = cur.fetchall()
    con.close()
    return reservations

def get_room_availability():
    con = sqlite3.connect('instance/reservations.db')
    cur = con.cursor()
    cur.execute("SELECT * FROM room_availability")
    room_availabilities = cur.fetchall()
    con.close()
    return room_availabilities

def create_reservation_image_with_details(reservation_details, slip_path):
    # สร้างภาพพื้นหลัง (white background)
    img_width, img_height = 800, 1000  # ขนาดภาพ
    img = Image.new('RGB', (img_width, img_height), color='white')
    draw = ImageDraw.Draw(img)

    try:
        # ฟอนต์
        font = ImageFont.truetype("arial.ttf", 40)
        bold_font = ImageFont.truetype("arialbd.ttf", 40)
    except IOError:
        font = ImageFont.load_default()
        bold_font = ImageFont.load_default()

    y_offset = 20
    margin_left = 20

    # ข้อมูลสำหรับแสดงในรูปภาพ
    draw.text((margin_left, y_offset), f"Name: {reservation_details['name']}", font=bold_font, fill='black')
    y_offset += 30
    draw.text((margin_left, y_offset), f"Phone: {reservation_details['phone']}", font=font, fill='black')
    y_offset += 30
    draw.text((margin_left, y_offset), f"Check-in: {reservation_details['checkin']}", font=font, fill='black')
    y_offset += 30
    draw.text((margin_left, y_offset), f"Check-out: {reservation_details['checkout']}", font=font, fill='black')
    y_offset += 30

    # แสดงสลิป
    slip_image = Image.open(slip_path)
    slip_image = slip_image.resize((660, 490))  # ปรับขนาดของสลิป
    img.paste(slip_image, (margin_left, y_offset))  # วางสลิปในภาพ
    y_offset += 310  # ขยับตำแหน่งหลังจากสลิป

    # บันทึกภาพ
    img.save('reservation_details_with_slip.jpg')
    return 'reservation_details_with_slip.jpg'

def create_reservation_image(reservations, room_availabilities, latest_reservation_id):
    img = Image.new('RGB', (800, 1000), color='white')
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("arial.ttf", 20)
        bold_font = ImageFont.truetype("arialbd.ttf", 20)
    except IOError:
        font = ImageFont.load_default()
        bold_font = ImageFont.load_default()

    y_offset = 10
    draw.text((10, y_offset), "Reservations:", font=font, fill='black')
    y_offset += 30

    for reservation in reservations:
        idd = reservation.id
        name = reservation.name
        phone = reservation.phone
        checkin = reservation.checkin
        checkout = reservation.checkout
        line = f"ID: {idd}, Name: {name}, Phone: {phone}, Check-in: {checkin}, Check-out: {checkout}"
        if idd == latest_reservation_id:
            draw.text((10, y_offset), line, font=bold_font, fill='red')
        else:
            draw.text((10, y_offset), line, font=font, fill='black')
        y_offset += 20

    y_offset += 20
    draw.text((10, y_offset), "Room Availability:", font=font, fill='black')
    y_offset += 30

    for room in room_availabilities:
        date = room[1]
        available_rooms = room[2]
        line = f"Date: {date}, Available Rooms: {available_rooms}"
        draw.text((10, y_offset), line, font=font, fill='black')
        y_offset += 20

    return img

def save_image(img):
    img.save('reservation_details.jpg')

def send_line_image(image_path, token):
    url = 'https://notify-api.line.me/api/notify'
    headers = {
        'Authorization': f'Bearer {token}',
    }
    message = {'message': 'รายละเอียดการจองและจำนวนห้องว่าง'}
    files = {'imageFile': open(image_path, 'rb')}
    response = requests.post(url, headers=headers, data=message, files=files)
    files['imageFile'].close()
    return response

def send_line_image_2(image_path, token):
    url = 'https://notify-api.line.me/api/notify'
    headers = {
        'Authorization': f'Bearer {token}',
    }
    message = {'message': 'รายละเอียดการจองและสลิปโอนเงิน'}
    files = {'imageFile': open(image_path, 'rb')}
    response = requests.post(url, headers=headers, data=message, files=files)
    files['imageFile'].close()
    return response

file_path = "instance/reservations.db"
repo = "pungyaen/my-flask-app-1"
path_in_repo = "instance/reservations.db"
commit_message = "Update reservations.db"
branch = "master"  # หรือ master
github_token = os.getenv('GITHUB_TOKEN')
token = github_token

def upload_file_to_github(file_path, repo, path_in_repo, commit_message, branch, token):
    # อ่านไฟล์
    with open(file_path, "rb") as file:
        content = file.read()
        print(content)  # ดูข้อมูลที่อ่านจากไฟล์
        content_b64 = base64.b64encode(content).decode("utf-8")

    # URL สำหรับ API GitHub
    url = f"https://api.github.com/repos/{repo}/contents/{path_in_repo}"

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }

    # ตรวจสอบว่าไฟล์มีอยู่แล้วหรือไม่
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        sha = response.json()["sha"]
    else:
        sha = None

    # ข้อมูลที่จะส่ง
    data = {
        "message": commit_message,
        "content": content_b64,
        "branch": branch
    }

    if sha:
        data["sha"] = sha  # ถ้ามีไฟล์ที่มีอยู่แล้วให้ใส่ sha ของไฟล์นั้น

    # ส่งคำขอ PUT
    response = requests.put(url, json=data, headers=headers)

    if response.status_code in [200, 201]:
        print(f"File '{path_in_repo}' successfully uploaded to GitHub.")
    else:
        print(f"Failed to upload file to GitHub: {response.status_code}")
        print(response.json())

def update_room_availability():
    while True:
        with app.app_context():
            print("Started updating room_availability&reservations")  # เพิ่มการตรวจสอบการทำงานของฟังก์ชัน
            start_date = datetime.now().date()
            current_date = start_date
            # ลบข้อมูลห้องที่เก่ากว่าวันปัจจุบัน
            RoomAvailability.query.filter(RoomAvailability.date < str(start_date)).delete()
            # ลบการจองที่หมดอายุ
            Reservation.query.filter(Reservation.checkout < str(current_date)).delete()
            # เรียงลำดับการจองตามวันที่ checkin
            reservations = Reservation.query.order_by(Reservation.checkin).all()
            for reservation in reservations:
                print(
                    f"Reservation ID: {reservation.id}, Name: {reservation.name}, Check-in: {reservation.checkin}, Check-out: {reservation.checkout}")

            db.session.commit()
            print("room_availability&reservations updated!")

            # ส่ง update ทางไลน์ทุกเช้า 05.00 น.
            reservations = Reservation.query.order_by(Reservation.checkin).all()
            room_availabilities = get_room_availability()
            img = create_reservation_image(reservations, room_availabilities, reservation.id)
            save_image(img)
            line_token = 'ca7yuOC9DjF8FNfHZMaPRMtGORlydUUX83VqTwVoMiR'  # เปลี่ยนด้วย token ของคุณ
            send_line_image('reservation_details.jpg', line_token)

        time.sleep(60)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()

    app.run(debug=True)