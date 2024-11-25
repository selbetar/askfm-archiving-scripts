import argparse
import os
import re
from datetime import datetime

from tqdm import tqdm

import config
from database import ChatModel, Database, QuestionAnswerView

OUTPUT_DIRECTORY = config.output_directory

re_arabic = re.compile("[\u0600-\u06FF]")


class HTMLView:
    uid: str
    username: str  # name

    def __init__(self, uid: str):
        self.db = Database(config.db_file)
        self.uid = uid
        self.output_dir = os.path.join(OUTPUT_DIRECTORY, uid, "html")
        os.makedirs(self.output_dir, exist_ok=True)

        self.visual_dir = os.path.join("..", OUTPUT_DIRECTORY, uid)

    def generate(self, user: str):
        user = user.lower()
        self.db.connect()
        user_info = self.db.get_user(user)
        records = self.db.get_question_answer_view(uid=user)
        chats = self.db.get_chats(uid=user)
        threads = self.db.get_threads(uid=user)
        self.db.close()

        self.uid = user_info["id"]
        self.username = user_info["name"]

        seen = set()
        body = ""
        count = 0
        for qid, data in tqdm(records.items()):
            if qid in seen:
                continue

            chat = chats.get(qid, [])
            thread = []
            if data["tid"] is not None:
                thread = threads.get(data["tid"])

            if len(thread) > 0 and len(chat) > 0:
                print(f"question with qid={qid} has both threads and chats!")

            follow_ups: list[QuestionAnswerView] = []
            for t in thread:
                entry = records.get(t)
                follow_ups.append(entry)
                seen.add(t)

            follow_ups = sorted(follow_ups, key=lambda d: d["a_ts"])
            seen.add(qid)
            body += self.format_text(data, chats=chat, threads=follow_ups)
            count += 1
            if count % 2500 == 0:
                file = os.path.join(self.output_dir, f"{self.uid}_{count}.html")
                with open(file, mode="w") as f:
                    body = self.body(body)
                    f.write(f"{body}")
                body = ""

        if len(body) > 0:
            body = self.body(body)
            file = os.path.join(self.output_dir, f"{self.uid}_{count}.html")
            with open(file, mode="w") as f:
                f.write(f"{body}")

        print(
            f"generated html files for {self.username}. Output directory: {self.output_dir}"
        )

    def format_text(
        self,
        data: QuestionAnswerView,
        chats: list[ChatModel],
        threads: list[QuestionAnswerView],
    ):
        question_html = ""
        answer_html = ""
        if len(threads) == 0:
            question_html = self.question(data)
            answer_html = self.answer(data)

        chats_html = ""
        for chat in chats:
            if chat["author_id"] is not None and chat["author_id"] == self.uid:
                chats_html += self.answer(chat) + "\n"
            else:
                chats_html += self.question(chat) + "\n"

        follow_ups = ""
        for thread in threads:
            q = self.question(thread)
            a = self.answer(thread)
            follow_ups = f"{follow_ups}\n{q}\n{a}"

        template = f"""
    <div class="conversation">
        <div class="question-answer">
            {question_html}
            {answer_html}
            {chats_html}
            {follow_ups}
        </div>
    </div>        
        """
        return template

    def replace_url_to_link(self, value):
        urls = re.compile(
            r"(((https|http)?):((//)|(\\\\))+[\w\d:#@%/;$()~_?\+-=\\\.&]*)",
            re.MULTILINE | re.UNICODE,
        )
        value = urls.sub(r'<a href="\1" target="_blank">\1</a>', value)
        return value

    def question(self, question: QuestionAnswerView | ChatModel):
        epoch = question.get("q_ts", question.get("created_at"))
        timestamp = datetime.fromtimestamp(epoch).strftime("%Y-%m-%d %H:%M")
        visual_id = question.get("q_vid")
        author_name = question["author_name"]
        text = question.get("question", question.get("text"))

        text = self.replace_url_to_link(text)
        text = text.replace("\n", "<br>")
        text = text.strip()

        img = ""
        if visual_id is not None:
            file = os.path.join(self.visual_dir, visual_id)
            img = f"""
<div class="image-container">
    <img src="{file}" alt="Missing Visual File">
</div>
"""

        if author_name is not None and len(author_name) > 0:
            author_name = f"{author_name}   "
        else:
            author_name = ""

        contains_arabic = re_arabic.search(text) is not None
        if contains_arabic:
            template = f"""<p dir="rtl">{text}\n{img}</p>"""
        else:
            template = f"""<p dir="ltr">{text}\n{img}</p>"""

        template = f"{template} <footer>{author_name}{timestamp}</footer>"
        template = f"""
<div class="question">
  {template}
</div>
"""
        return template

    def answer(self, answer: QuestionAnswerView | ChatModel):
        epoch = answer.get("a_ts", answer.get("created_at"))
        timestamp = datetime.fromtimestamp(epoch).strftime("%Y-%m-%d %H:%M")
        visual_id = answer.get("a_vid", None)
        answer_id = answer["qid"]
        text = answer.get("answer", answer.get("text"))
        if text is None:
            text = ""
        text = self.replace_url_to_link(text)
        text = text.replace("\n", "<br>")
        text = text.strip()
        img = ""
        if visual_id is not None:
            if visual_id.endswith(".mp4"):
                img = ""
            else:
                file = os.path.join(self.visual_dir, visual_id)
                img = f"""
<div class="image-container">
    <img src="{file}" alt="Missing Visual File">
</div>
"""

        contains_arabic = re_arabic.search(text) is not None
        if contains_arabic:
            template = f"""<p dir="rtl">{text}\n{img}</p>"""
        else:
            template = f"""<p dir="ltr">{text}\n{img}</p>"""

        template = f"{template} <footer>{answer_id}   {timestamp}</footer>"
        template = f"""
        <div class="answer">
          {template}
        </div>
        """

        return template

    def body(self, body: str):
        return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Question-Answer Conversation</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
{body}
</body>
</html>
"""

    def style_sheet(self):
        return ""

    def info_page(self, uid: str):
        self.db.connect()
        user_info = self.db.get_user(uid=uid)
        first_a_timestamp = self.db.get_oldest_answer_time_stamp(uid)
        last_a_timestamp = self.db.get_newest_answer_time_stamp(uid)
        answer_count = self.db.get_answer_count(uid)
        chat_count = self.db.get_chat_count(uid)
        self.db.close()
        body = f"""
<h1>{user_info["name"]} Archive</h1>
<hr>
<br>
<h2>File Details: </h2>
<h3>First Answer Date: {datetime.fromtimestamp(first_a_timestamp).strftime("%Y-%m-%d %H:%M")}</h3>
<h3>Last Answer Date: {datetime.fromtimestamp(last_a_timestamp).strftime("%Y-%m-%d %H:%M")}</h3>
<h3>Number of Answers: {answer_count}</h3>
<h3>Number of Chats: {chat_count}</h3>
"""
        file = os.path.join(self.output_dir, f"{uid}_info.html")
        with open(file, mode="w") as f:
            f.write(f"{self.body(body)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="askfm-html", description="generates html files for the specified user"
    )
    parser.add_argument("usernames", nargs="+")
    args = parser.parse_args()

    for uid in args.usernames:
        uid = uid.lower()

        m = HTMLView(uid)

        m.info_page(uid)
        m.generate(uid)
