#
#
# This file contains the main entrypoint
# and contains the logic that calls the API
#
#
import argparse
import base64
import logging
import os
from datetime import datetime
from typing import Tuple

import config
from askfm_api import AskfmApi, AskfmApiError
from askfm_api import requests as r
from askfm_model import AskFM, askFMChat
from database import Database
from processor import Processor

OUTPUT_DIRECTORY = config.output_directory
api = AskfmApi(base64.b64decode(config.key).decode("ascii"))
logger = logging.getLogger(__name__)
processor = Processor()

logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)


def _get_chat_messages(qid: int) -> askFMChat | None:
    try:
        chats = api.request(r.fetch_chats(qid=qid))
    except AskfmApiError as e:
        if str(e) != "data_not_found":
            logger.error(f"error when retrieveing chat for qid={qid}: {e}")
        return None
    else:
        return chats


def _get_profile_answer_count(username: str) -> int:
    profile = api.request(r.fetch_profile(username))
    answer_count = profile["answerCount"]
    return answer_count


def _get_stored_answered_count(username: str) -> int:
    db = Database(config.db_file)
    db.connect()
    count = db.get_answer_count(uid=username)
    db.close()

    return count


def _get_remaining_answer_count(username: str, force: bool) -> int:
    answer_count = _get_profile_answer_count(username)
    stored_count = _get_stored_answered_count(username)
    if force:
        return answer_count
    return abs(answer_count - stored_count)


def _get_newest_answer_time_stamp(username: str) -> int:
    db = Database(config.db_file)
    db.connect()
    timestamp = db.get_newest_answer_time_stamp(uid=username)
    db.close()

    if timestamp is None:
        return -1
    return timestamp


def _get_oldest_answer_time_stamp(username: str) -> int:
    db = Database(config.db_file)
    db.connect()
    timestamp = db.get_oldest_answer_time_stamp(uid=username)
    db.close()

    if timestamp is None:
        return datetime.now().timestamp()
    return timestamp


def extract_answers_and_chats(username: str, force: bool = False, offset=None):
    """
    @username is the username
    @force if true, then extraction will continue until the last answer is reached, otherwise it will
        stop when it reaches the last answer stored in the database.
    @offset the unix timestamp from which extraction begins. If None then starts from the beginning
    """
    if offset is not None:
        logger.debug(f"extracting answers and chats from offset: {offset}")
    else:
        logger.debug("extracting answers and chats")
    profile_stream = api.request_iter(
        r.fetch_profile_stream(username=username, skip="answer_chats", from_ts=offset)
    )
    answers: list[AskFM] = []
    chats: list[askFMChat] = []
    i = 0

    remaining = _get_remaining_answer_count(username, force)
    newest_answer_timestamp = _get_newest_answer_time_stamp(username)
    if offset is not None:
        # reset since it means the process was interrupted
        newest_answer_timestamp = -1

    answers_count = 0
    chats_count = 0
    prev_answer: AskFM = None
    skipped_count = 0
    while True:
        answer: AskFM = next(profile_stream, None)
        if answer is None:
            break

        if answer["type"] == "photopoll":
            skipped_count += 1
            continue

        if (
            not force
            and answer["data"]["answer"]["createdAt"] <= newest_answer_timestamp
        ):
            break

        if answer["type"] == "answer_chat":
            # technically shouldn't be possible since we are skipping `answer_chats`
            # this won't impact the extraction of chats.
            continue

        if answer["type"] != "question":
            logger.warning(
                f'question id: {answer["data"]["qid"]} has an unusual answer type: {answer["type"]}'
            )
            continue

        if (
            prev_answer is not None
            and prev_answer["data"]["qid"] == answer["data"]["qid"]
        ):
            continue

        answers.append(answer)
        answers_count += 1
        if answer["data"].get("chat", None):
            chat = _get_chat_messages(answer["data"]["qid"])
            chats.append(chat)
            chats_count += 1

        if len(answers) % 1000 == 0:
            processor.process(answers)
            processor.process_chat(chats)
            answers.clear()
            chats.clear()

        prev_answer = answer
        i += 1
        print(f"Progress: {i/remaining*100:.1f}% - extraction\033[K", end="\r")

    processor.process(answers)
    processor.process_chat(chats)

    logger.info(
        f"extracted {answers_count} answers and {chats_count} chats, skipped {skipped_count} photo polls"
    )

    return answers, chats


def extract_new_chats(username: str, limit: int = 700):
    logger.debug("extracting new chats for existing answers")
    db = Database(config.db_file)
    db.connect()
    answer_ids = db.get_top_n_answers(uid=username, limit=limit)
    db.close()

    chats: list[askFMChat] = []
    i = 0
    for id in answer_ids:
        chat = _get_chat_messages(qid=id)
        if chat is not None:
            chats.append(chat)
        i += 1
        print(f"Progress: {i/len(answer_ids)*100:.1f}% - new chats\033[K", end="\r")

    print()
    processor.process_chat(chats)
    logger.debug(f"number of new chats extracted: {len(chats)}")


def run(usernames: list[str], force: bool, offset):
    try:
        api.log_in(config.username, config.password)
    except AskfmApiError as e:
        logger.error(f"error logging-in: {e}")

    i = 0
    for username in usernames:
        i += 1
        logger.info(f"starting job {i}/{len(usernames)} for {username}")
        username = username.lower()
        try:
            os.makedirs(os.path.join(OUTPUT_DIRECTORY, username), exist_ok=True)
            if not force:
                extract_new_chats(username=username, limit=100)
            extract_answers_and_chats(username, force, offset=offset)
            oldest_timestamp = _get_oldest_answer_time_stamp(username)
            archived_count = _get_stored_answered_count(username)
            remaining_count = _get_profile_answer_count(username)
            if remaining_count > archived_count:
                logger.info(f"continuing extracting from timestamp: {oldest_timestamp}")
                extract_answers_and_chats(username, offset=oldest_timestamp)

        except AskfmApiError as e:
            logger.error(f"error: {e}")

        print()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="askfm-archiver", description="archive ask.fm profiles"
    )
    parser.add_argument("usernames", nargs="+")
    parser.add_argument(
        "-f",
        "--force",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Specify this option if extraction was interrupted.",
    )
    parser.add_argument(
        "-t",
        "--timestamp",
        default=None,
        type=int,
        help="Specify the timestamp from which parsing should start.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="time=%(asctime)s  origin=%(name)s level=%(levelname)s msg=%(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        filename="extractor.log",
        filemode="a",
    )

    logging.getLogger().addHandler(logging.FileHandler("extractor.log"))
    logging.getLogger().addHandler(logging.StreamHandler())

    run(args.usernames, args.force, args.timestamp)
