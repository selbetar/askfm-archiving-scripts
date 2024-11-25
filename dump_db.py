import argparse
import logging
import os
import sqlite3
from typing import Tuple, TypedDict

import config
from database import ChatModel, Database, QuestionAnswerView


class ChatDumpModel(TypedDict):
    id: int
    qid: int
    text: str
    author_id: str
    author_name: str
    created_at: int


class AnswerQuestionDumpModel(TypedDict):
    qid: int
    uid: int
    answer: str
    question: str
    author_id: str
    author_name: str
    q_ts: int
    a_ts: int


class DumpDatabase(Database):
    def __init__(self, uid):
        logging.basicConfig(level=logging.DEBUG)
        self.uid = uid.lower()
        self.db_file = os.path.join(config.output_directory, f"{uid}.db")
        self.db = None

        if not os.path.exists(self.db_file):
            self.create_inital()

    def create_inital(self):
        path = "./sqlite/dump/1_inital_setup.sql"
        logging.info("creating initial database")
        with open(path, "r") as sql_file:
            init_script = sql_file.read()

        db = sqlite3.connect(self.db_file)
        cursor = db.cursor()
        cursor.executescript(init_script)
        cursor.close()
        db.commit()
        db.close()

    def get_data(self) -> Tuple[list[QuestionAnswerView], list[ChatModel]]:
        db = Database(config.db_file)
        db.connect()
        answers = db._get_question_answer_view(self.uid)
        chats = db._get_chats(self.uid)
        db.close()
        return answers, chats

    def __add_chats_dump(self, chats: list[ChatModel]):
        table = "chats"
        values = []
        keys = None

        for chat in chats:
            chat.pop("uid")
            values.append(tuple(chat.values()))
            if keys is None:
                keys = chat.keys()
        self.insertmany(table, keys, values)

    def __add_answer_view_dump(self, answer_view: list[QuestionAnswerView]):
        table = "answers_questions"
        values = []
        keys = None
        for answer in answer_view:
            obj = AnswerQuestionDumpModel(
                qid=answer["qid"],
                uid=self.uid,
                answer=answer["answer"],
                question=answer["question"],
                author_id=answer["author_id"],
                author_name=answer["author_name"],
                q_ts=answer["q_ts"],
                a_ts=answer["a_ts"],
                like_count=answer["like_count"],
            )
            values.append(tuple(obj.values()))
            if keys is None:
                keys = obj.keys()
        self.insertmany(table, keys, values)

    def dump(self):
        answer_view, chats = self.get_data()

        self.connect()
        self.__add_answer_view_dump(answer_view)
        self.__add_chats_dump(chats)
        self.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="askfm-Dump", description="generates askfm_view database"
    )
    parser.add_argument("usernames", nargs="+")
    args = parser.parse_args()

    for uid in args.usernames:
        uid = uid.lower()
        db = DumpDatabase(uid)
        db.dump()
