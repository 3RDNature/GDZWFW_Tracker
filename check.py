import json
import os
import time
import httpx
import random
import ddddocr


class CaptchaError(Exception):
    ...


class DDDDocr:
    def __init__(self):
        self.ocr = ddddocr.DdddOcr()

    def discriminate(self, binary: bytes) -> str:
        return self.ocr.classification(binary)


class Checker:
    def __init__(self, name: str, sblsh: int):
        """

        :param name: 姓名
        :param sblsh: 流水号
        """
        self.name = name
        self.sblsh = sblsh
        self.client = httpx.Client(headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                                                          'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 '
                                                          'Safari/537.36'})

    def get_captcha(self):
        """
        请求验证码
        :return: 返回验证码
        """
        self.client.get("https://www.gdzwfw.gov.cn/portal/v2/progress-query-detail")
        result = self.client.get(
            f'https://www.gdzwfw.gov.cn/portal/api/v2/qyzx/getVerifyCode?type=BJJD&v={random.random()}')
        return result.content

    def get_info(self, captcha):
        resp = self.client.post(
            "https://www.gdzwfw.gov.cn/portal/api/v2/has-progress",
            json={
                "sqrmc": self.name,
                "sblsh": self.sblsh,
                "captcha": captcha,
                "captcha_type": "BJJD"
            }
        )

        if resp.status_code != 200:
            raise Warning(resp.json())
        elif resp.json()['code'] == '25034':  # 验证码错误
            raise CaptchaError()
        elif resp.json()['code'] != '200':
            raise Warning(resp.json())
        return resp.json()['data']['bjjd']


class User:
    def __init__(self, name: str, sblsh: int, pushdeer_token: str, captcha_solver):
        self.pushdeer_token = pushdeer_token
        self.captcha_solver = captcha_solver
        self.name = name
        self.sblsh = sblsh
        self.client = Checker(name, sblsh)

    def notify(self, content: str):
        self.client.client.get(f"https://api2.pushdeer.com/message/push?pushkey={self.pushdeer_token}&text={content}")

    def do_check(self, tries=3):
        if tries == 0:
            raise Warning("已经重复执行3次，执行失败...")
        print(f"{self.name} Checking.....")
        print(f"{self.name} Getting captcha...")
        captcha = self.client.get_captcha()
        print(f"{self.name} Solving captcha...")
        # 调用打码平台
        solve = self.captcha_solver.discriminate(captcha)
        print(f"{self.name} Solved captcha {solve}, requesting further infomation...")
        try:
            data = self.client.get_info(solve)
            print(f"{self.name} Info: {data}")
            # 比对是否和上次一致
            filename = f"./data/{self.sblsh}.txt"
            if not os.path.exists(filename):
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False)
            else:
                with open(filename, "r", encoding="utf-8") as f:
                    json_data = json.load(f)
                    if json_data != data:
                        print(f"{self.name} 有变动, 变动正在通知 ({data[0]})")
                        self.notify(str(data[0]))
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False)
        except CaptchaError:
            print("疑似验证码错误，重新执行....")
            return self.do_check(tries=tries - 1)
        except Exception as e:
            print(e)


config = json.load(open("./db.json", "r", encoding="utf-8"))
Solver2 = DDDDocr()
users = []

for user in config["users"]:
    users.append(User(user["name"], user["sblsh"], user["pushdeer"], Solver2))

print(f"Append {len(users)} users")

for user in users:
    user.do_check()
    time.sleep(5)
