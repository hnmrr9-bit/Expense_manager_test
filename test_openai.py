from dotenv import load_dotenv
from openai import OpenAI

# Đọc file .env
load_dotenv()

# Tạo OpenAI client
client = OpenAI()

# Gửi câu hỏi
response = client.responses.create(
    model="gpt-5.5",
    input="Xin chào! Hãy giới thiệu ngắn gọn về bạn bằng tiếng Việt."
)

# In câu trả lời
print("AI trả lời:")
print(response.output_text)