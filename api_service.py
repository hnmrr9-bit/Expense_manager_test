import requests


class CurrencyAPI:

    BASE_URL = "https://api.frankfurter.dev"

    def get_rate(self, base_currency, target_currency):
        base_currency = (base_currency or "VND").upper()
        target_currency = (target_currency or "VND").upper()
        if base_currency == target_currency:
            return 1.0

        url = f"{self.BASE_URL}/v1/latest?from={base_currency}&to={target_currency}"
        try:
            response = requests.get(url, timeout=8)
            response.raise_for_status()
            data = response.json()
            rates = data.get("rates") or {}
            rate = rates.get(target_currency)
            if rate is None:
                return None
            return float(rate)
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

    def convert(self, amount, base_currency, target_currency):
        base_currency = (base_currency or "VND").upper()
        target_currency = (target_currency or "VND").upper()
        if amount is None:
            return None
        rate = self.get_rate(base_currency, target_currency)
        if rate is None:
            return None
        return float(amount) * float(rate)