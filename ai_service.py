import base64
import json
import os
import uuid
from datetime import datetime
from pathlib import Path

import requests


class AIService:
    """Provider-neutral LLM/VLM adapter with a human-review fallback."""

    def __init__(self, review_file="data/ai_reviews.json"):
        self.review_file = Path(review_file)
        self.upload_dir = self.review_file.parent / "ai_uploads"
        self.review_file.parent.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        if not self.review_file.exists():
            self.review_file.write_text("[]", encoding="utf-8")

    def _provider_config(self):
        return {
            "name": os.getenv("AI_PROVIDER", "openai-compatible"),
            "base_url": os.getenv("AI_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
            "api_key": os.getenv("AI_API_KEY") or os.getenv("OPENAI_API_KEY", ""),
            "llm_model": os.getenv("AI_LLM_MODEL", "gpt-4o-mini"),
            "vlm_model": os.getenv("AI_VLM_MODEL", "gpt-4o-mini"),
        }

    def provider_status(self):
        config = self._provider_config()
        return {
            "provider": config["name"],
            "configured": bool(config["api_key"]),
            "llm_model": config["llm_model"],
            "vlm_model": config["vlm_model"],
            "review_fallback": True,
        }

    def _call_vlm(self, image_bytes, content_type):
        config = self._provider_config()
        if not config["api_key"]:
            return None, "Chưa cấu hình AI_API_KEY; ảnh đã được đưa vào hàng chờ duyệt."

        image_data = base64.b64encode(image_bytes).decode("ascii")
        payload = {
            "model": config["vlm_model"],
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Đọc hóa đơn và chỉ trả JSON hợp lệ gồm amount (number), category, description, expense_date (YYYY-MM-DD), merchant, tax_amount (number), confidence (number 0 đến 1). Nếu không chắc trường nào, để null. Không tự bịa dữ liệu."},
                    {"type": "image_url", "image_url": {"url": f"data:{content_type};base64,{image_data}"}},
                ],
            }],
        }
        try:
            response = requests.post(
                f"{config['base_url']}/chat/completions",
                headers={"Authorization": f"Bearer {config['api_key']}", "Content-Type": "application/json"},
                json=payload,
                timeout=45,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            suggestion = json.loads(content)
            if not isinstance(suggestion, dict):
                return None, "VLM không trả về dữ liệu hóa đơn dạng JSON."
            if not any(suggestion.get(field) not in (None, "") for field in ("amount", "merchant", "description", "expense_date")):
                return None, "VLM không đọc được thông tin hữu ích từ ảnh hóa đơn."
            confidence = suggestion.get("confidence")
            if confidence is not None:
                try:
                    suggestion["confidence"] = max(0, min(1, float(confidence)))
                except (TypeError, ValueError):
                    suggestion["confidence"] = None
            return suggestion, None
        except (requests.RequestException, KeyError, ValueError, TypeError) as error:
            return None, f"Không thể phân tích ảnh tự động: {error}"

    @staticmethod
    def validate_image(image_bytes, content_type):
        signatures = {
            "image/jpeg": image_bytes[:3] == b"\xff\xd8\xff",
            "image/png": image_bytes[:8] == b"\x89PNG\r\n\x1a\n",
            "image/webp": image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP",
        }
        if content_type not in signatures or not signatures[content_type]:
            return False, "Nội dung file không khớp định dạng ảnh đã khai báo."
        if len(image_bytes) < 32:
            return False, "Ảnh quá nhỏ hoặc bị hỏng."
        return True, None

    def call_llm(self, prompt):
        config = self._provider_config()
        if not config["api_key"]:
            return {"configured": False, "message": "Chưa cấu hình AI_API_KEY."}
        payload = {
            "model": config["llm_model"],
            "temperature": 0.2,
            "messages": [{"role": "user", "content": prompt}],
        }
        try:
            response = requests.post(
                f"{config['base_url']}/chat/completions",
                headers={"Authorization": f"Bearer {config['api_key']}", "Content-Type": "application/json"},
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
            return {"configured": True, "text": response.json()["choices"][0]["message"]["content"]}
        except (requests.RequestException, KeyError, ValueError, TypeError) as error:
            return {"configured": True, "message": f"LLM không phản hồi: {error}"}

    def create_review(self, user_id, filename, image_bytes, content_type):
        suggestion, error = self._call_vlm(image_bytes, content_type)
        review_id = uuid.uuid4().hex
        extension = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}[content_type]
        image_path = self.upload_dir / f"{review_id}{extension}"
        image_path.write_bytes(image_bytes)
        review = {
            "id": review_id,
            "user_id": user_id,
            "filename": filename,
            "content_type": content_type,
            "image_path": str(image_path),
            "created_at": datetime.utcnow().isoformat() + "Z",
            "status": "pending",
            "suggestion": suggestion or {},
            "message": error or "AI đã tạo đề xuất. Vui lòng kiểm tra trước khi thêm.",
        }
        reviews = self.list_reviews()
        reviews.append(review)
        self.review_file.write_text(json.dumps(reviews, ensure_ascii=False, indent=2), encoding="utf-8")
        return review

    def replace_review_image(self, review_id, user_id, filename, image_bytes, content_type):
        reviews = self.list_reviews()
        for review in reviews:
            if review["id"] == review_id and review.get("user_id") == user_id and review.get("status") == "pending":
                old_path = Path(review.get("image_path", ""))
                extension = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}[content_type]
                new_path = self.upload_dir / f"{review_id}{extension}"
                new_path.write_bytes(image_bytes)
                if old_path != new_path and old_path.is_file() and old_path.parent == self.upload_dir:
                    old_path.unlink()
                suggestion, error = self._call_vlm(image_bytes, content_type)
                review.update({"filename": filename, "content_type": content_type, "image_path": str(new_path), "suggestion": suggestion or {}, "message": error or "Đã cập nhật ảnh và tạo đề xuất mới."})
                self.review_file.write_text(json.dumps(reviews, ensure_ascii=False, indent=2), encoding="utf-8")
                return review
        return None

    def list_reviews(self, user_id=None):
        try:
            reviews = json.loads(self.review_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            reviews = []
        if user_id is None:
            return reviews
        return [review for review in reviews if review.get("user_id") == user_id]

    def update_status(self, review_id, user_id, status):
        reviews = self.list_reviews()
        for review in reviews:
            if review["id"] == review_id and review.get("user_id") == user_id:
                review["status"] = status
                self.review_file.write_text(json.dumps(reviews, ensure_ascii=False, indent=2), encoding="utf-8")
                return review
        return None

    def update_suggestion(self, review_id, user_id, suggestion):
        reviews = self.list_reviews()
        for review in reviews:
            if review["id"] == review_id and review.get("user_id") == user_id and review.get("status") == "pending":
                review["suggestion"] = suggestion
                self.review_file.write_text(json.dumps(reviews, ensure_ascii=False, indent=2), encoding="utf-8")
                return review
        return None
