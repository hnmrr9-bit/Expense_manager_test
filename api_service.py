import requests


class CurrencyAPI:

    BASE_URL = "https://api.frankfurter.dev"

    def get_rate(
        self,
        base_currency,
        target_currency
    ):

        url = (
            f"{self.BASE_URL}/v2/rate/"
            f"{base_currency.lower()}/"
            f"{target_currency.lower()}"
        )

        try:

            response = requests.get(
                url,
                timeout=5
            )

            response.raise_for_status()

            data = response.json()

            return data["rate"]

        except requests.exceptions.Timeout:

            print("API phản hồi quá lâu.")

        except requests.exceptions.ConnectionError:

            print("Không thể kết nối API.")

        except requests.exceptions.HTTPError:

            print("API trả về lỗi HTTP.")

        except (KeyError, ValueError):

            print("Dữ liệu API không hợp lệ.")

        except Exception as error:

            print(f"Lỗi API: {error}")

        return None

    def convert(
        self,
        amount,
        base_currency,
        target_currency
    ):

        rate = self.get_rate(
            base_currency,
            target_currency
        )

        if rate is None:

            return None

        return amount * rate
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI()    
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI()

response = client.responses.create(
    model="gpt-5.5",
    input="Xin chào, hãy trả lời tôi bằng tiếng Việt."
)

print(response.output_text)
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI()


def ask_ai(question):
    response = client.responses.create(
        model="gpt-5.5",
        input=question
    )

    return response.output_text