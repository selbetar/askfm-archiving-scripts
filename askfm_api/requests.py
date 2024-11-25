from __future__ import annotations

import functools
from typing import Optional, Union

import askfm_api

IdType = Union[str, int]


# Note: typechecking this mess seems impossible.
# See https://github.com/python/mypy/issues/3157#issue-221120895, section "Messing with the return type".
def make_req(method, path, **req_kwargs):
    def decorator(func):
        name = func.__name__

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            params = func(*args, **kwargs)
            return askfm_api.Request(method, path, params, name=name, **req_kwargs)

        return wrapper

    return decorator


# === My profile ===


@make_req("GET", "/my/profile", unwrap_key="profile")
def fetch_my_profile():
    return {}


@make_req(
    "GET",
    "/notifications",
    unwrap_key="notifications_ext",
    paginated=True,
    item_id_key="entityId",
)
def fetch_notifs(filter: str = ""):
    return {"type": filter}


@make_req("PUT", "/notifications/mark_read")
def mark_notifs_as_read(filter: str = ""):
    return {"type": filter}


@make_req("POST", "/users/hashtags", unwrap_key="hashtag")
def add_hashtag(hashtag: str):
    return {"hashtag": hashtag}


@make_req("DELETE", "/users/hashtags")
def delete_hashtag(hashtag: str):
    return {"hashtag": hashtag}


# === My Q&A ===


@make_req(
    "GET", "/my/questions", unwrap_key="questions", paginated=True, item_id_key="qid"
)
def fetch_questions(*, skip_shoutouts: bool = False):
    return {"skip_shoutouts": skip_shoutouts}


@make_req("DELETE", "/my/questions")
def delete_question(question_type: str, question_id: IdType):
    return {
        "qid": question_id,
        "type": question_type,
    }


@make_req("POST", "/my/questions/answer")
def post_answer(question_type: str, question_id: IdType, text: str):
    return {
        "qid": question_id,
        "type": question_type,
        "answer": {
            "type": "text",
            "body": text,
        },
    }


@make_req("DELETE", "/my/answers")
def delete_answer(question_id: IdType):
    return {"qid": question_id}


# === Users ===


@make_req(
    "GET",
    "/users/hashtags/search",
    unwrap_key="users",
    paginated=True,
    item_id_key="uid",
)
def search_users_by_hashtag(*hashtags: str):
    return {"hashtags": ",".join(hashtags)}


@make_req("GET", "/users/details", unwrap_key="user")
def fetch_profile(username: str):
    return {"uid": username}


@make_req(
    "GET", "/users/answers", unwrap_key="questions", paginated=True, item_id_key="qid"
)
def fetch_answers(username: str, *, skip: Optional[str] = None):
    return {"uid": username, "skip": skip}


@make_req("POST", "/users/questions")
def send_question(users: list[str], text: str, *, anon: bool = False):
    return {
        "users": users,
        "question": {
            "type": "anonymous" if anon else "user",
            "body": text,
        },
    }


@make_req("GET", "/answers/chats", paginated=False, item_id_key="qid")
def fetch_chats(qid: str, *, limit: Optional[int] = 100):
    return {"qid": qid, "limit": limit}


@make_req(
    "GET",
    "/users/answers",
)
def fetch_answers_2(username: str, *, skip: Optional[str] = None):
    return {"uid": username, "skip": skip}


@make_req("GET", "/users/profile/stream", paginated=True, unwrap_key="items")
def fetch_profile_stream(
    username: str,
    skip: Optional[str] = None,
    limit: Optional[int] = 1000,
    from_ts: Optional[int] = None,  # unix timestamp
):
    return {"uid": username, "limit": limit, "skip": skip, "from": from_ts}


# === Report/block ===


@make_req("POST", "/report/answer")
def report_answer(question_id: IdType, reason: Optional[str] = None):
    return {"qid": question_id, "reason": reason}


@make_req("POST", "/report/question")
def report_question(
    question_id: IdType, reason: Optional[str] = None, *, should_block: bool = False
):
    return {"qid": question_id, "reason": reason, "block": should_block}


@make_req("POST", "/report/user")
def report_user(
    username: str, reason: Optional[str] = None, *, should_block: bool = False
):
    return {"uid": username, "reason": reason, "block": should_block}


# === Util ===


@make_req("GET", "/token", unwrap_key="accessToken")
def get_access_token(device_id: IdType):
    return {"did": device_id}


@make_req("POST", "/authorize")
def log_in(username: str, password: str, device_id: IdType):
    return {
        "uid": username,
        "pass": password,
        "did": device_id,
        "guid": device_id,
    }
