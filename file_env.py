import os
from dotenv import load_dotenv

load_dotenv()

key = os.getenv("OPENAI_API_KEY")

if key:
    print("API KEY đã được đọc thành công!")
else:
    print("Không tìm thấy API KEY")