# error ของกฎธุรกิจ ไม่ผูกกับ HTTP (กฎจึงเรียกใช้จากที่อื่นนอกจาก endpoint ได้ เช่น CLI หรือเทสต์)
# errors.py เป็นคนแปลงเป็น status code ตอนตอบ request


class AppError(Exception):
    status_code = 400

    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


class NotFound(AppError):
    status_code = 404


class Forbidden(AppError):
    status_code = 403


class Conflict(AppError):
    """ขัดกับข้อมูลที่มีอยู่ เช่น เวลาชน ชื่อซ้ำ"""
    status_code = 409


class RuleViolation(AppError):
    """ข้อมูลถูกรูปแบบแต่ผิดกฎของระบบ เช่น นอกเวลาเปิด คนเกินความจุ"""
    status_code = 422
