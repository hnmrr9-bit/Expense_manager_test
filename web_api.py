import base64
import csv
import hashlib
import hmac
import io
import json
import time
import unicodedata
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

from auth import AuthService
from database import Database
from expense_service import ExpenseService
from ai_service import AIService

load_dotenv()

SECRET_KEY = "expense-manager-secret-key"


def create_token(user_id: int, username: str, role: str = "user") -> str:
    payload = f"{user_id}:{username}:{role}:{int(time.time())}"
    signature = hmac.new(SECRET_KEY.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{base64.urlsafe_b64encode(payload.encode('utf-8')).decode('utf-8').rstrip('=')}.{signature}"


def verify_token(token: str):
    if not token:
        return None

    try:
        encoded_payload, signature = token.split(".", 1)
        payload = base64.urlsafe_b64decode(encoded_payload + "=" * (-len(encoded_payload) % 4)).decode("utf-8")
        expected = hmac.new(SECRET_KEY.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        user_id, username, role, _ = payload.split(":", 3)
        return int(user_id), username, role
    except Exception:
        return None


def get_authenticated_user(request: Request, user_id_query: int | None = None):
    token = None
    auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1]

    if token:
        verified = verify_token(token)
        if verified is not None:
            user_id, _, _ = verified
            return user_id

    raise HTTPException(status_code=401, detail="Unauthorized")


def get_authenticated_context(request: Request):
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    verified = verify_token(auth_header.split(" ", 1)[1])
    if verified is None:
        raise HTTPException(status_code=401, detail="Token không hợp lệ")
    return verified


def require_admin(request: Request):
    user_id, _, role = get_authenticated_context(request)
    if role != "admin":
        raise HTTPException(status_code=403, detail="Chỉ quản trị viên mới có quyền này")
    return user_id


def serialize_expense(expense):
    return {
        "id": expense.expense_id,
        "user_id": expense.user_id,
        "amount": expense.amount,
        "category": expense.category,
        "description": expense.description,
        "expense_date": expense.expense_date,
    }


def normalize_text(value: object) -> str:
    text = unicodedata.normalize("NFC", str(value or ""))
    return " ".join(text.strip().split())


def normalize_category(value: object) -> str:
    return normalize_text(value).casefold()


def serialize_review(review):
    return {key: value for key, value in review.items() if key != "image_path"}


def validate_expense_payload(payload: dict):
    if payload is None:
        raise HTTPException(status_code=400, detail="Dữ liệu không hợp lệ")

    required_fields = ["amount", "category", "description", "expense_date"]
    missing = [field for field in required_fields if field not in payload]

    if missing:
        raise HTTPException(status_code=400, detail=f"Thiếu dữ liệu: {', '.join(missing)}")

    try:
        amount = round(float(payload["amount"]), 2)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Số tiền không hợp lệ")

    if amount <= 0:
        raise HTTPException(status_code=400, detail="Số tiền phải lớn hơn 0")

    category = normalize_category(payload["category"])
    description = normalize_text(payload["description"])

    if not category:
        raise HTTPException(status_code=400, detail="Danh mục không được để trống")

    if not description:
        raise HTTPException(status_code=400, detail="Mô tả không được để trống")

    try:
        datetime.strptime(str(payload["expense_date"]), "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Ngày không hợp lệ. Định dạng đúng: YYYY-MM-DD")

    return {
        "amount": amount,
        "category": category,
        "description": description,
        "expense_date": str(payload["expense_date"]),
    }


database = Database()
database.create_tables()

for expense_row in database.fetch_all("SELECT id, category, description FROM expenses"):
    database.execute(
        "UPDATE expenses SET category = ?, description = ? WHERE id = ?",
        (normalize_category(expense_row[1]), normalize_text(expense_row[2]), expense_row[0]),
    )

expense_service = ExpenseService(database)
auth_service = AuthService(database)
ai_service = AIService()

try:
    demo_user = auth_service.database.fetch_one(
        "SELECT id FROM users WHERE username = ?",
        ("demo",)
    )
    if demo_user is None:
        auth_service.register("demo", "demo123")
    database.execute("UPDATE users SET role = 'admin' WHERE username = 'demo'")
except Exception:
    pass

app = FastAPI(
    title="Expense Manager API",
    description="API quản lý chi tiêu cá nhân",
    version="1.2.3"
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse(request, "index.html", {"request": request})


@app.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {"request": request})


@app.get("/register")
async def register_page(request: Request):
    return templates.TemplateResponse(request, "register.html", {"request": request})


@app.post("/api/auth/register")
def register_api(payload: dict):
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", "")).strip()

    if not username or not password:
        raise HTTPException(status_code=400, detail="Tên đăng nhập và mật khẩu không được để trống")

    existing = auth_service.database.fetch_one(
        "SELECT id FROM users WHERE username = ?",
        (username,)
    )
    if existing is not None:
        raise HTTPException(status_code=400, detail="Tài khoản đã tồn tại")

    success = auth_service.register(username, password)
    if not success:
        raise HTTPException(status_code=400, detail="Đăng ký thất bại")

    created_user = auth_service.login(username, password)
    if created_user is None:
        raise HTTPException(status_code=400, detail="Không thể tạo tài khoản")

    return {
        "message": "Đăng ký thành công",
        "user_id": created_user.user_id,
        "username": created_user.username,
        "token": create_token(created_user.user_id, created_user.username, created_user.role),
        "role": created_user.role,
    }


@app.post("/api/auth/login")
def login_api(payload: dict):
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", "")).strip()

    if not username or not password:
        raise HTTPException(status_code=400, detail="Tên đăng nhập và mật khẩu không được để trống")

    user = auth_service.login(username, password)
    if user is None:
        raise HTTPException(status_code=401, detail="Tên đăng nhập hoặc mật khẩu không đúng")

    return {
        "message": "Đăng nhập thành công",
        "user_id": user.user_id,
        "username": user.username,
        "token": create_token(user.user_id, user.username, user.role),
        "role": user.role,
    }


@app.get("/hello")
def hello():
    return {
        "message": "Xin chào từ FastAPI!"
    }


@app.get("/api/expenses")
def list_expenses(request: Request, user_id: int = 1, start_date: str | None = None, end_date: str | None = None, category: str | None = None, keyword: str | None = None):
    user_id = get_authenticated_user(request, user_id)
    expenses = expense_service.get_expenses(user_id, start_date, end_date, category, keyword)
    return [serialize_expense(expense) for expense in expenses]


@app.get("/api/expenses/{expense_id}")
def get_expense(request: Request, expense_id: int, user_id: int = 1):
    user_id = get_authenticated_user(request, user_id)
    expenses = expense_service.get_expenses(user_id)
    expense = next((item for item in expenses if item.expense_id == expense_id), None)

    if expense is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy khoản chi tiêu")

    return serialize_expense(expense)


@app.post("/api/expenses")
def create_expense(request: Request, payload: dict):
    user_id = payload.get("user_id")
    if user_id is None:
        raise HTTPException(status_code=400, detail="Thiếu user_id")
    user_id = get_authenticated_user(request, user_id)

    validated = validate_expense_payload(payload)

    success = expense_service.add_expense(
        user_id,
        validated["amount"],
        validated["category"],
        validated["description"],
        validated["expense_date"],
    )

    if not success:
        raise HTTPException(status_code=400, detail="Không thể lưu chi tiêu")

    return {"message": "Thêm chi tiêu thành công"}


@app.put("/api/expenses/{expense_id}")
def update_expense(request: Request, expense_id: int, payload: dict, user_id: int = 1):
    user_id = get_authenticated_user(request, user_id)
    validated = validate_expense_payload(payload)

    success = expense_service.update_expense(
        expense_id,
        user_id,
        validated["amount"],
        validated["category"],
        validated["description"],
        validated["expense_date"],
    )

    if not success:
        raise HTTPException(status_code=404, detail="Không tìm thấy khoản chi tiêu để cập nhật")

    return {"message": "Cập nhật chi tiêu thành công"}


@app.delete("/api/expenses/{expense_id}")
def delete_expense(request: Request, expense_id: int, user_id: int = 1):
    user_id = get_authenticated_user(request, user_id)
    success = expense_service.delete_expense(expense_id, user_id)

    if not success:
        raise HTTPException(status_code=404, detail="Không tìm thấy khoản chi tiêu để xoá")

    return {"message": "Xoá chi tiêu thành công"}


@app.get("/api/summary")
def get_summary(request: Request, user_id: int = 1):
    user_id = get_authenticated_user(request, user_id)
    return {
        "total_expense": expense_service.total_expense(user_id),
        "current_month_total": expense_service.total_by_month(
            user_id,
            datetime.now().strftime("%Y-%m")
        )
    }


@app.get("/api/summary/categories")
def get_summary_by_category(request: Request, user_id: int = 1):
    user_id = get_authenticated_user(request, user_id)
    categories = expense_service.total_by_category(user_id)
    return [
        {"label": key, "value": value}
        for key, value in categories.items()
    ]


@app.get("/api/summary/months")
def get_summary_by_month(request: Request, user_id: int = 1, year: int | None = None):
    user_id = get_authenticated_user(request, user_id)
    return [{"label": key, "value": value} for key, value in expense_service.totals_by_month(user_id, year).items()]


@app.get("/api/summary/years")
def get_summary_by_year(request: Request, user_id: int = 1):
    user_id = get_authenticated_user(request, user_id)
    return [{"label": key, "value": value} for key, value in expense_service.totals_by_year(user_id).items()]


@app.get("/api/summary/report")
def get_report(request: Request, user_id: int = 1):
    user_id = get_authenticated_user(request, user_id)
    return expense_service.report(user_id)


@app.get("/api/ai/providers")
def ai_provider_status(request: Request):
    get_authenticated_user(request)
    return ai_service.provider_status()


@app.post("/api/ai/llm")
def call_llm(request: Request, payload: dict):
    get_authenticated_user(request)
    prompt = str(payload.get("prompt", "")).strip()
    if not prompt or len(prompt) > 4000:
        raise HTTPException(status_code=400, detail="Prompt phải có từ 1 đến 4000 ký tự")
    return ai_service.call_llm(prompt)


@app.post("/api/ai/analyze-image")
async def analyze_image(request: Request, image: UploadFile = File(...)):
    user_id = get_authenticated_user(request)
    allowed_types = {"image/jpeg", "image/png", "image/webp"}
    if image.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Chỉ hỗ trợ ảnh JPG, PNG hoặc WEBP")
    image_bytes = await image.read()
    if not image_bytes or len(image_bytes) > 8 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Ảnh phải có dung lượng từ 1 byte đến 8 MB")
    valid_image, image_error = ai_service.validate_image(image_bytes, image.content_type)
    if not valid_image:
        raise HTTPException(status_code=400, detail=image_error)
    review = ai_service.create_review(user_id, image.filename or "receipt-image", image_bytes, image.content_type)
    return {"message": "Ảnh đã được lưu vào hàng chờ kiểm tra", "review": serialize_review(review)}


@app.get("/api/ai/reviews")
def list_ai_reviews(request: Request):
    user_id = get_authenticated_user(request)
    return [serialize_review(review) for review in ai_service.list_reviews(user_id)]


@app.get("/api/ai/reviews/{review_id}/image")
def get_review_image(request: Request, review_id: str):
    user_id = get_authenticated_user(request)
    review = next((item for item in ai_service.list_reviews(user_id) if item.get("id") == review_id), None)
    if review is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy ảnh hóa đơn")
    image_path = Path(review.get("image_path", ""))
    if not image_path.is_file() or image_path.parent != ai_service.upload_dir:
        raise HTTPException(status_code=404, detail="File ảnh không tồn tại")
    return FileResponse(image_path, media_type=review.get("content_type", "image/jpeg"))


@app.patch("/api/ai/reviews/{review_id}/suggestion")
def update_ai_suggestion(request: Request, review_id: str, payload: dict):
    user_id = get_authenticated_user(request)
    suggestion = payload.get("suggestion")
    if not isinstance(suggestion, dict):
        raise HTTPException(status_code=400, detail="Đề xuất không hợp lệ")
    updated = ai_service.update_suggestion(review_id, user_id, suggestion)
    if updated is None:
        raise HTTPException(status_code=404, detail="Đề xuất không tồn tại hoặc đã được xử lý")
    return serialize_review(updated)


@app.put("/api/ai/reviews/{review_id}/image")
async def replace_ai_image(request: Request, review_id: str, image: UploadFile = File(...)):
    user_id = get_authenticated_user(request)
    allowed_types = {"image/jpeg", "image/png", "image/webp"}
    if image.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Chỉ hỗ trợ ảnh JPG, PNG hoặc WEBP")
    image_bytes = await image.read()
    if not image_bytes or len(image_bytes) > 8 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Ảnh phải có dung lượng từ 1 byte đến 8 MB")
    valid_image, image_error = ai_service.validate_image(image_bytes, image.content_type)
    if not valid_image:
        raise HTTPException(status_code=400, detail=image_error)
    review = ai_service.replace_review_image(user_id=user_id, review_id=review_id, filename=image.filename or "receipt-image", image_bytes=image_bytes, content_type=image.content_type)
    if review is None:
        raise HTTPException(status_code=404, detail="Review không tồn tại hoặc đã được xử lý")
    return {"message": "Đã cập nhật ảnh và phân tích lại", "review": serialize_review(review)}


@app.patch("/api/ai/reviews/{review_id}")
def update_ai_review(request: Request, review_id: str, payload: dict):
    user_id = get_authenticated_user(request)
    status = payload.get("status")
    if status not in {"approved", "rejected"}:
        raise HTTPException(status_code=400, detail="Trạng thái duyệt không hợp lệ")
    review = next((item for item in ai_service.list_reviews(user_id) if item.get("id") == review_id), None)
    if review is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy đề xuất ảnh")
    if review.get("status") != "pending":
        raise HTTPException(status_code=409, detail="Đề xuất này đã được xử lý trước đó")
    if status == "approved":
        try:
            validated = validate_expense_payload(review.get("suggestion", {}))
        except HTTPException:
            raise HTTPException(status_code=422, detail="Đề xuất AI chưa đủ dữ liệu để nhập. Hãy sửa thủ công trước.")
        if not expense_service.add_expense(user_id, validated["amount"], validated["category"], validated["description"], validated["expense_date"]):
            raise HTTPException(status_code=400, detail="Không thể tạo giao dịch từ đề xuất")
    review = ai_service.update_status(review_id, user_id, status)
    if status == "approved":
        review["imported_expense"] = True
    return serialize_review(review)


@app.get("/api/export/csv")
def export_csv(request: Request, user_id: int = 1):
    user_id = get_authenticated_user(request, user_id)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["amount", "category", "description", "expense_date"])
    for expense in expense_service.get_expenses(user_id):
        writer.writerow([expense.amount, expense.category, expense.description, expense.expense_date])
    output.seek(0)
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=expenses.csv"})


@app.post("/api/import")
def import_expenses(request: Request, payload: dict):
    user_id = get_authenticated_user(request, payload.get("user_id"))
    items = payload.get("items", [])
    if not isinstance(items, list) or len(items) > 2000:
        raise HTTPException(status_code=400, detail="Danh sách import không hợp lệ")
    imported = 0
    for item in items:
        validated = validate_expense_payload(item)
        if expense_service.add_expense(user_id, validated["amount"], validated["category"], validated["description"], validated["expense_date"]):
            imported += 1
    return {"message": f"Đã import {imported} khoản chi", "imported": imported}


@app.get("/api/admin/users")
def list_users(request: Request):
    require_admin(request)
    rows = database.fetch_all("SELECT id, username, role FROM users ORDER BY id")
    return [{"id": row[0], "username": row[1], "role": row[2]} for row in rows]


@app.patch("/api/admin/users/{target_user_id}/role")
def update_user_role(request: Request, target_user_id: int, payload: dict):
    require_admin(request)
    role = payload.get("role")
    if role not in {"user", "admin"}:
        raise HTTPException(status_code=400, detail="Vai trò không hợp lệ")
    if not database.execute("UPDATE users SET role = ? WHERE id = ?", (role, target_user_id)):
        raise HTTPException(status_code=404, detail="Không thể cập nhật vai trò")
    return {"message": "Đã cập nhật vai trò"}
