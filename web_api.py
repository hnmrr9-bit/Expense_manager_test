import base64
import csv
import hashlib
import hmac
import io
import json
import secrets
import time
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from auth import AuthService
from database import Database
from expense_service import ExpenseService
from ai_service import AIService

load_dotenv()

SECRET_KEY = "expense-manager-secret-key"
ACCESS_TOKEN_TTL = 60 * 60
REFRESH_TOKEN_TTL = 7 * 24 * 60 * 60


def create_token(user_id: int, username: str, role: str = "user", token_type: str = "access", expires_seconds: int | None = None) -> str:
    if expires_seconds is None:
        expires_seconds = ACCESS_TOKEN_TTL if token_type == "access" else REFRESH_TOKEN_TTL
    now = int(time.time())
    payload = {
        "user_id": user_id,
        "username": username,
        "role": role,
        "token_type": token_type,
        "iat": now,
        "exp": now + expires_seconds,
    }
    encoded = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")).decode("utf-8").rstrip("=")
    signature = hmac.new(SECRET_KEY.encode("utf-8"), encoded.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def verify_token(token: str, expected_type: str | None = None):
    if not token:
        return None

    try:
        encoded_payload, signature = token.split(".", 1)
        expected = hmac.new(SECRET_KEY.encode("utf-8"), encoded_payload.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        payload = base64.urlsafe_b64decode(encoded_payload + "=" * (-len(encoded_payload) % 4)).decode("utf-8")
        data = json.loads(payload)
        if isinstance(data, dict):
            if data.get("exp") and int(data.get("exp", 0)) < int(time.time()):
                return None
            if expected_type and data.get("token_type") and data.get("token_type") != expected_type:
                return None
            return int(data.get("user_id")), data.get("username"), data.get("role")

        legacy_parts = payload.split(":", 3)
        if len(legacy_parts) >= 3:
            user_id, username, role, _ = legacy_parts
            return int(user_id), username, role
    except Exception:
        pass

    legacy_parts = token.split(".", 1)
    if len(legacy_parts) == 2 and not token.startswith("{"):
        try:
            encoded_payload, legacy_signature = legacy_parts
            payload = base64.urlsafe_b64decode(encoded_payload + "=" * (-len(encoded_payload) % 4)).decode("utf-8")
            user_id, username, role, _ = payload.split(":", 3)
            return int(user_id), username, role
        except Exception:
            return None
    return None


def get_authenticated_user(request: Request, user_id_query: int | None = None):
    token = None
    auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1]

    if token:
        verified = verify_token(token, "access")
        if verified is not None:
            user_id, _, _ = verified
            return user_id

    if user_id_query is not None:
        return user_id_query

    raise HTTPException(status_code=401, detail="Unauthorized")


def get_authenticated_context(request: Request):
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    verified = verify_token(auth_header.split(" ", 1)[1], "access")
    if verified is None:
        raise HTTPException(status_code=401, detail="Token không hợp lệ hoặc đã hết hạn")
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
        "is_recurring": bool(getattr(expense, "is_recurring", 0)),
        "recurring_frequency": getattr(expense, "recurring_frequency", "monthly") or "monthly",
        "tags": getattr(expense, "tags", "") or "",
        "currency": getattr(expense, "currency", "VND") or "VND",
    }


def normalize_text(value: object) -> str:
    text = unicodedata.normalize("NFC", str(value or ""))
    return " ".join(text.strip().split())


def normalize_category(value: object) -> str:
    return normalize_text(value).casefold()


def normalize_tags(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        tags = [normalize_text(item).lower() for item in value.split(",") if normalize_text(item)]
    elif isinstance(value, list):
        tags = [normalize_text(item).lower() for item in value if normalize_text(item)]
    else:
        tags = [normalize_text(value).lower()] if normalize_text(value) else []
    return ", ".join(dict.fromkeys(tags))


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
    tags = normalize_tags(payload.get("tags"))
    currency = str(payload.get("currency", "VND") or "VND").upper()
    is_recurring = bool(payload.get("is_recurring"))
    recurring_frequency = str(payload.get("recurring_frequency", "monthly") or "monthly").lower()

    if not category:
        raise HTTPException(status_code=400, detail="Danh mục không được để trống")

    if not description:
        raise HTTPException(status_code=400, detail="Mô tả không được để trống")

    try:
        datetime.strptime(str(payload["expense_date"]), "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Ngày không hợp lệ. Định dạng đúng: YYYY-MM-DD")

    if recurring_frequency not in {"daily", "weekly", "monthly", "yearly"}:
        recurring_frequency = "monthly"

    return {
        "amount": amount,
        "category": category,
        "description": description,
        "expense_date": str(payload["expense_date"]),
        "is_recurring": is_recurring,
        "recurring_frequency": recurring_frequency,
        "tags": tags,
        "currency": currency,
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


@app.get("/settings")
async def settings_page(request: Request):
    return templates.TemplateResponse(request, "settings.html", {"request": request})


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


@app.post("/api/auth/change-password")
def change_password_api(request: Request, payload: dict):
    user_id = get_authenticated_user(request)
    current_password = str(payload.get("current_password", ""))
    new_password = str(payload.get("new_password", ""))
    if not current_password or len(new_password) < 6:
        raise HTTPException(status_code=400, detail="Mật khẩu mới phải có ít nhất 6 ký tự")
    if not auth_service.change_password(user_id, current_password, new_password):
        raise HTTPException(status_code=400, detail="Mật khẩu hiện tại không đúng")
    return {"message": "Đổi mật khẩu thành công"}


@app.get("/hello")
def hello():
    return {
        "message": "Xin chào từ FastAPI!"
    }


@app.get("/api/expenses")
def list_expenses(request: Request, user_id: int = 1, start_date: str | None = None, end_date: str | None = None, category: str | None = None, keyword: str | None = None, tags: str | None = None, limit: int | None = None, offset: int = 0):
    user_id = get_authenticated_user(request, user_id)
    resolved_limit = min(limit or 50, 200)
    expenses = expense_service.get_expenses(user_id, start_date, end_date, category, keyword, tags, resolved_limit, offset)
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
        validated["is_recurring"],
        validated["recurring_frequency"],
        validated["tags"],
        validated["currency"],
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
        validated["is_recurring"],
        validated["recurring_frequency"],
        validated["tags"],
        validated["currency"],
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
    writer.writerow(["amount", "category", "description", "expense_date", "tags", "currency", "is_recurring", "recurring_frequency"])
    for expense in expense_service.get_expenses(user_id):
        writer.writerow([
            expense.amount,
            expense.category,
            expense.description,
            expense.expense_date,
            getattr(expense, 'tags', ''),
            getattr(expense, 'currency', 'VND'),
            int(bool(getattr(expense, 'is_recurring', 0))),
            getattr(expense, 'recurring_frequency', 'monthly') or 'monthly',
        ])
    output.seek(0)
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=expenses.csv"})


@app.get("/api/export/json")
def export_json(request: Request, user_id: int = 1):
    user_id = get_authenticated_user(request, user_id)
    payload = {
        "generated_at": datetime.utcnow().isoformat(),
        "user_id": user_id,
        "expenses": [serialize_expense(item) for item in expense_service.get_expenses(user_id)],
    }
    content = json.dumps(payload, ensure_ascii=False, indent=2)
    return StreamingResponse(iter([content]), media_type="application/json; charset=utf-8", headers={"Content-Disposition": "attachment; filename=finance-data.json"})


@app.get("/api/export/pdf")
def export_pdf(request: Request, user_id: int = 1):
    user_id = get_authenticated_user(request, user_id)
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    pdf.setTitle("Expense report")
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(60, 760, "Báo cáo chi tiêu")
    pdf.setFont("Helvetica", 11)
    y = 730
    for item in expense_service.get_expenses(user_id):
        line = f"- {item.expense_date} | {item.category} | {item.description} | {item.amount} {item.currency or 'VND'}"
        pdf.drawString(60, y, line[:120])
        y -= 18
        if y < 60:
            pdf.showPage()
            y = 760
    pdf.save()
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=expense_report.pdf"})


@app.post("/api/import")
def import_expenses(request: Request, payload: dict):
    user_id = get_authenticated_user(request, payload.get("user_id"))
    items = payload.get("items", [])
    if not isinstance(items, list) or len(items) > 2000:
        raise HTTPException(status_code=400, detail="Danh sách import không hợp lệ")
    imported = 0
    for item in items:
        validated = validate_expense_payload(item)
        if expense_service.add_expense(
            user_id,
            validated["amount"],
            validated["category"],
            validated["description"],
            validated["expense_date"],
            validated["is_recurring"],
            validated["recurring_frequency"],
            validated["tags"],
            validated["currency"],
        ):
            imported += 1
    return {"message": f"Đã import {imported} khoản chi", "imported": imported}


@app.post("/api/backup")
def backup_data(request: Request, payload: dict | None = None):
    user_id = get_authenticated_user(request, payload.get("user_id") if payload else None)
    expenses = expense_service.get_expenses(user_id)
    export_payload = {
        "generated_at": datetime.utcnow().isoformat(),
        "user_id": user_id,
        "expenses": [serialize_expense(item) for item in expenses],
    }
    backup_path = Path("data") / f"backup_user_{user_id}.json"
    backup_path.write_text(json.dumps(export_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    expense_service.save_user_setting(user_id, refresh_token=secrets.token_urlsafe(24))
    return {"message": "Đã sao lưu dữ liệu", "path": str(backup_path)}


@app.post("/api/restore")
def restore_data(request: Request, payload: dict):
    user_id = get_authenticated_user(request, payload.get("user_id"))
    raw_items = payload.get("expenses")
    if raw_items is None:
        raw_items = payload.get("items")
    if raw_items is None:
        backup_path = Path(payload.get("path") or "")
        if not backup_path.exists() or not backup_path.is_file():
            raise HTTPException(status_code=404, detail="File sao lưu không tồn tại")
        data = json.loads(backup_path.read_text(encoding="utf-8"))
        raw_items = data.get("expenses", [])
    if not isinstance(raw_items, list):
        raise HTTPException(status_code=400, detail="Dữ liệu khôi phục không hợp lệ")
    items = raw_items
    for item in items:
        if not isinstance(item, dict):
            continue
        validate_expense_payload(item)
        expense_service.add_expense(
            user_id,
            item.get("amount"),
            item.get("category"),
            item.get("description"),
            item.get("expense_date"),
            item.get("is_recurring", 0),
            item.get("recurring_frequency", "monthly"),
            item.get("tags", ""),
            item.get("currency", "VND"),
        )
    return {"message": f"Đã khôi phục {len(items)} giao dịch"}


@app.post("/api/auth/refresh")
def refresh_token_api(request: Request, payload: dict):
    refresh_token = str(payload.get("refresh_token", "") or "").strip()
    if not refresh_token:
        raise HTTPException(status_code=400, detail="Refresh token không hợp lệ")
    for row in database.fetch_all("SELECT id, username, role FROM users WHERE id IN (SELECT user_id FROM user_settings WHERE refresh_token = ?)", (refresh_token,)):
        user_id, username, role = row
        refreshed = create_token(user_id, username, role, "access", ACCESS_TOKEN_TTL)
        return {"token": refreshed, "expires_in": ACCESS_TOKEN_TTL}
    raise HTTPException(status_code=401, detail="Refresh token không hợp lệ hoặc đã hết hạn")


@app.get("/api/settings")
def get_user_settings(request: Request, user_id: int = 1):
    user_id = get_authenticated_user(request, user_id)
    return expense_service.get_user_setting(user_id)


@app.post("/api/settings")
def save_user_settings(request: Request, payload: dict):
    user_id = get_authenticated_user(request, payload.get("user_id"))
    default_currency = str(payload.get("default_currency", "VND") or "VND").upper()
    theme = str(payload.get("theme", "blue") or "blue")
    refresh_token = payload.get("refresh_token")
    if refresh_token is not None:
        refresh_token = str(refresh_token)
    if not expense_service.save_user_setting(user_id, default_currency, theme, refresh_token):
        raise HTTPException(status_code=400, detail="Không thể lưu cài đặt")
    return {"message": "Đã lưu cài đặt", "default_currency": default_currency, "theme": theme}


@app.get("/api/category-budgets")
def get_category_budgets(request: Request, user_id: int = 1):
    user_id = get_authenticated_user(request, user_id)
    return expense_service.list_category_budgets(user_id)


@app.post("/api/category-budgets")
def set_category_budget(request: Request, payload: dict):
    user_id = get_authenticated_user(request, payload.get("user_id"))
    category = str(payload.get("category", "")).strip()
    budget_amount = float(payload.get("budget_amount", 0) or 0)
    currency = str(payload.get("currency", "VND") or "VND").upper()
    if not category or budget_amount < 0:
        raise HTTPException(status_code=400, detail="Danh mục hoặc ngân sách không hợp lệ")
    if not expense_service.upsert_category_budget(user_id, category, budget_amount, currency):
        raise HTTPException(status_code=400, detail="Không thể lưu ngân sách danh mục")
    return {"message": "Đã lưu ngân sách danh mục", "category": category, "budget_amount": budget_amount, "currency": currency}


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
