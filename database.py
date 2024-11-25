import logging
import os
import sqlite3
from typing import TypedDict

import config


class QuestionModel(TypedDict):
    qid: int  # primary
    uid: str
    tid: int | None
    type: str | None  # anon, system, shoutout
    text: str | None
    author_id: str | None
    author_name: str | None
    visual_id: str | None
    created_at: int


class AnswerModel(TypedDict):
    qid: int  # primary
    uid: str
    text: str | None
    visual_id: str | None
    like_count: int
    created_at: int


class ChatModel(TypedDict):
    id: int
    uid: str
    qid: int
    text: str
    author_id: str
    author_name: str
    created_at: int


class VisualModel(TypedDict):
    id: str
    type: str  # gif, photo, video
    directory: str  # relative to visuals directory


class QueueModel(TypedDict):
    id: str
    type: str  # gif, photo, video
    directory: str  # relative to visuals directory
    url: str


class ThreadModel(TypedDict):
    id: int  # tid, usually 1st answer
    uid: str
    qid: int
    external: bool  # true if manually linked


class UserModel(TypedDict):
    id: str
    name: str
    blob: str


class SchemaVersion(TypedDict):
    version: int


class QuestionAnswerView(TypedDict):
    tid: int
    qid: int
    answer: str
    a_vid: str  # answer_visualid
    a_ts: int  # a.created_at
    author_id: str
    author_name: str
    q_vid: str  # question_visualid
    question: str
    q_ts: str  # q.created_at
    like_count: int


class Database:
    def __init__(self, db_file):
        self.db = None
        self.db_file = db_file
        if not os.path.exists(self.db_file):
            self.create_inital()

    def create_inital(self):
        path = "./sqlite/migrations/1_inital_setup.sql"
        logging.info("creating initial database file")
        with open(path, "r") as sql_file:
            init_script = sql_file.read()

        db = sqlite3.connect(self.db_file)
        cursor = db.cursor()
        cursor.executescript(init_script)
        cursor.close()
        db.commit()
        db.close()

    def _dict_factory(self, cursor, row):
        fields = [column[0] for column in cursor.description]
        return {key: value for key, value in zip(fields, row)}

    def connect(self):
        if self.db is not None:
            self.close()
        self.db = sqlite3.connect(self.db_file)
        self.db.row_factory = self._dict_factory

    def close(self):
        if self.db is None:
            return
        self.db.commit()
        self.db.close()
        self.db = None

    def ready(self) -> bool:
        return self.db is not None

    def insert(self, table: str, obj: dict):
        if not self.ready():
            raise Exception("database not ready")

        placeholders = ",".join(["?"] * len(obj))
        columns = ", ".join(obj.keys())
        sql = "INSERT OR IGNORE INTO %s ( %s ) VALUES ( %s )" % (
            table,
            columns,
            placeholders,
        )
        try:
            cursor = self.db.cursor()
            cursor.execute(sql, list(obj.values()))
            self.db.commit()
        except sqlite3.Error as e:
            logging.error(f"sqlite3 exception: {e}")

    def insertmany(self, table: str, keys, values: list[tuple]):
        if not self.ready():
            raise Exception("database not ready")
        if len(values) == 0:
            return

        placeholders = ",".join(["?"] * len(keys))
        columns = ", ".join(keys)
        sql = "INSERT OR IGNORE INTO %s ( %s ) VALUES ( %s )" % (
            table,
            columns,
            placeholders,
        )
        try:
            cursor = self.db.cursor()
            cursor.executemany(sql, values)
            self.db.commit()
        except sqlite3.Error as e:
            logging.error(f"sqlite3 exception: {e}")

    def update_user_blob(self, id: str, blob: str):
        if not self.ready():
            raise Exception("database not ready")

        sql = "UPDATE users SET blob=? WHERE id=?"
        try:
            cursor = self.db.cursor()
            cursor.execute(sql, (blob, id))
            self.db.commit()
        except sqlite3.Error as e:
            logging.error(f"sqlite3 exception update_user_blob: {e}")

    def upsert_answers(self, keys, values):
        if not self.ready():
            raise Exception("database not ready")

        placeholders = ",".join(["?"] * len(keys))
        columns = ", ".join(keys)
        sql = (
            "INSERT INTO answers ( %s ) VALUES ( %s ) ON CONFLICT(qid) DO UPDATE SET like_count=(?)"
            % (
                columns,
                placeholders,
            )
        )
        try:
            cursor = self.db.cursor()
            cursor.executemany(sql, values)
            self.db.commit()
        except sqlite3.Error as e:
            logging.error(f"sqlite3 exception upsert_answers: {e}")

    def add_user(self, user: UserModel):
        table = "users"
        user["id"] = user["id"].lower()
        self.insert(table, user)

    def add_answers(self, keys, values):
        self.upsert_answers(keys, values)

    def add_chat(self, chat: ChatModel):
        table = "chats"
        if chat["author_id"] is not None:
            chat["author_id"] = chat["author_id"].lower()
        chat["uid"] = chat["uid"].lower()
        self.insert(table, chat)

    def add_questions(self, keys, values: list[tuple[QuestionModel]]):
        table = "questions"
        self.insertmany(table, keys, values)

    def add_threads(self, keys, values: list[tuple[ThreadModel]]):
        table = "threads"
        self.insertmany(table, keys, values)

    def add_visual(self, visual: VisualModel):
        table = "visuals"
        self.insert(table, visual)

    def add_download_queue(self, visual: QueueModel):
        table = "download_queue"
        self.insert(table, visual)

    def fetch_all(self, sql: str, args):
        if not self.ready():
            raise Exception("database not ready")
        try:
            cursor = self.db.cursor()
            cursor.execute(sql, args)
            return cursor.fetchall()
        except Exception as e:
            logging.error(f"sqlite3 exception: {e}")

    def _get_question_answer_view(self, uid) -> dict[int, QuestionAnswerView]:
        sql = """
SELECT 
    q.tid,
    a.qid,
    a.text as answer,
    a.visual_id as a_vid,
    a.created_at as a_ts,
    a.like_count,
    q.author_id,
    q.author_name,
    q.visual_id as q_vid,
    q.text as question,
    q.created_at as q_ts
FROM 
    questions q, 
    answers a
WHERE
    q.uid = a.uid AND
    q.qid = a.qid AND
    q.uid = ?
ORDER BY q.qid DESC;
        """

        records = self.fetch_all(sql, (uid,))

        return records

    def get_question_answer_view(self, uid) -> dict[int, QuestionAnswerView]:
        records = self._get_question_answer_view(uid)
        map = {}
        for record in records:
            qid = record["qid"]
            map[qid] = record
        return map

    def get_threads(self, uid) -> dict[int, list[int]]:
        """
        returns dict[int, list[int]]
        key: thread_id
        value: list of questions in the thread
        """
        sql = """
SELECT id, qid
FROM 
    threads
Where
    uid = ?
ORDER BY id ASC;
        """
        records = self.fetch_all(sql, (uid,))
        result: dict[int, list[int]] = {}
        for record in records:
            if record["id"] not in result:
                result[record["id"]] = []
            result[record["id"]].append(record["qid"])
        return result

    def _get_chats(self, uid: str) -> list[ChatModel]:
        sql = """
SELECT c.* 
FROM 
    chats c
WHERE 
    c.uid=?
ORDER BY 
    c.created_at ASC;
        """
        records = self.fetch_all(sql, (uid,))
        return records

    def get_chats(self, uid: str) -> dict[int, list[ChatModel]]:
        records = self._get_chats(uid)
        result: dict[int, list[ChatModel]] = {}
        for record in records:
            if record["qid"] not in result:
                result[record["qid"]] = []
            result[record["qid"]].append(record)
        return result

    def get_user(self, uid: str) -> UserModel:
        sql = "Select * FROM users where id = ?"
        records = self.fetch_all(sql, (uid.lower(),))
        return records[0]

    def get_answer_count(self, uid: str) -> int:
        sql = "select count(*) as count from answers where uid = ?"
        records = self.fetch_all(sql, (uid.lower(),))
        return records[0]["count"]

    def get_chat_count(self, uid: str) -> int:
        sql = "select count(*) as count from chats where uid = ?"
        records = self.fetch_all(sql, (uid.lower(),))
        return records[0]["count"]

    def get_oldest_answer_time_stamp(self, uid: str) -> int:
        sql = "select MIN(created_at) as created_at from answers where uid = ?"
        records = self.fetch_all(sql, (uid.lower(),))
        return records[0]["created_at"]

    def get_newest_answer_time_stamp(self, uid: str) -> int:
        sql = "select MAX(created_at) as created_at from answers where uid = ?"
        records = self.fetch_all(sql, (uid.lower(),))
        return records[0]["created_at"]

    def get_top_n_answers(self, uid: str, limit: int = 500) -> list[QuestionModel]:
        sql = "select qid from answers where uid = ? order by created_at DESC limit ?"
        records = self.fetch_all(sql, (uid.lower(), limit))
        result = []
        for r in records:
            result.append(r["qid"])
        return result

    def __delete__(self):
        self.close()
