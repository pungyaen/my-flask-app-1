from PIL import Image, ImageDraw, ImageFont
import sqlite3
import requests

# 1. ดึงข้อมูลการจองจากฐานข้อมูล
def get_reservation_data():
    con = sqlite3.connect('instance/reservations.db')  # Corrected path to your database
    cur = con.cursor()
    cur.execute("SELECT * FROM reservation")  # Query the reservation table
    reservations = cur.fetchall()
    con.close()
    return reservations

# 2. ดึงข้อมูลห้องว่างจากฐานข้อมูล
def get_room_availability():
    con = sqlite3.connect('instance/reservations.db')  # Corrected path to your database
    cur = con.cursor()
    cur.execute("SELECT * FROM room_availability")  # Query the room availability table
    room_availabilities = cur.fetchall()
    con.close()
    return room_availabilities

# 3. สร้างภาพจากข้อมูลการจองและจำนวนห้องว่าง
def create_reservation_image(reservations, room_availabilities):
    # สร้างภาพพื้นหลัง
    img = Image.new('RGB', (800, 1000), color='white')
    draw = ImageDraw.Draw(img)

    # ใช้ฟอนต์พื้นฐาน
    try:
        font = ImageFont.truetype("arial.ttf", 15)
    except IOError:
        font = ImageFont.load_default()

    # เขียนข้อมูลการจองลงในภาพ
    y_offset = 10  # กำหนดตำแหน่งเริ่มต้นของข้อความ
    draw.text((10, y_offset), "Reservations:", font=font, fill='black')
    y_offset += 30
    for reservation in reservations:
        idd = reservation[0]
        name = reservation[1]
        phone = reservation[2]
        checkin = reservation[3]
        checkout = reservation[4]
        slip = reservation[5]
        line = f"ID: {idd}, Name: {name}, Phone: {phone}, Check-in: {checkin}, Check-out: {checkout}, Slip: {slip}"
        draw.text((10, y_offset), line, font=font, fill='black')
        y_offset += 20  # ขยับตำแหน่งข้อความลงด้านล่าง

    # เขียนข้อมูลห้องว่างลงในภาพ
    y_offset += 20  # เพิ่มระยะห่างระหว่างส่วนการจองและจำนวนห้องว่าง
    draw.text((10, y_offset), "Room Availability:", font=font, fill='black')
    y_offset += 30
    for room in room_availabilities:
        date = room[1]
        available_rooms = room[2]
        line = f"Date: {date}, Available Rooms: {available_rooms}"
        draw.text((10, y_offset), line, font=font, fill='black')
        y_offset += 20  # ขยับตำแหน่งข้อความลงด้านล่าง

    return img

# 4. บันทึกภาพเป็นไฟล์ .jpg
def save_image(img):
    img.save('reservation_details.jpg')  # บันทึกภาพเป็นไฟล์ JPG

# 5. ใช้ Line API เพื่อส่งภาพ
def send_line_image(image_path, token):
    url = 'https://notify-api.line.me/api/notify'
    headers = {
        'Authorization': f'Bearer {token}',
    }
    message = {'message': 'รายละเอียดการจองและจำนวนห้องว่าง'}
    files = {'imageFile': open(image_path, 'rb')}
    response = requests.post(url, headers=headers, data=message, files=files)
    return response

# โค้ดหลัก
if __name__ == "__main__":
    reservations = get_reservation_data()  # ดึงข้อมูลการจองจากฐานข้อมูล
    room_availabilities = get_room_availability()  # ดึงข้อมูลห้องว่างจากฐานข้อมูล
    img = create_reservation_image(reservations, room_availabilities)  # สร้างภาพจากข้อมูลการจองและจำนวนห้องว่าง
    save_image(img)  # บันทึกภาพเป็นไฟล์ JPG

    # ส่งภาพผ่าน Line API
    line_token = 'ca7yuOC9DjF8FNfHZMaPRMtGORlydUUX83VqTwVoMiR'  # เปลี่ยนด้วย token ของคุณ
    response = send_line_image('reservation_details.jpg', line_token)

    # ตรวจสอบสถานะการตอบสนอง
    print(response.status_code, response.text)

