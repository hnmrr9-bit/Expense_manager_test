import json


class FileService:

    def export_expenses(
        self,
        expenses,
        filename
    ):

        data = []

        for expense in expenses:

            data.append(
                expense.to_dict()
            )

        try:

            with open(
                filename,
                "w",
                encoding="utf-8"
            ) as file:

                json.dump(
                    data,
                    file,
                    ensure_ascii=False,
                    indent=4
                )

            print(
                f"Đã export dữ liệu vào: {filename}"
            )

        except OSError as error:

            print(
                f"Lỗi ghi file: {error}"
            )