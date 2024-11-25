import json
import logging
import os
from typing import Tuple

import requests

import config
from askfm_model import (
    AskFM,
    AskFMAnswer,
    AskFMData,
    AskFMQuestionPhoto,
    AskFMThread,
    askFMChat,
    askFMChatMessages,
    askFMChatOwner,
    askFMProfileDetails,
    askFMProfilePictures,
)
from database import (
    AnswerModel,
    ChatModel,
    Database,
    QuestionModel,
    QueueModel,
    ThreadModel,
    UserModel,
    VisualModel,
)


class Processor:

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.download_dir = config.output_directory
        self.db = Database(config.db_file)

    def process(self, data: list[AskFM]):
        self.db.connect()
        self.logger.debug("processing started")
        if len(data) == 0:
            return

        i = 0
        questions = []
        q_keys = None
        answers = []
        a_keys = None
        threads = []
        t_keys = None
        for entry in data:
            i += 1
            if entry["type"] != "question":
                continue

            d = entry["data"]
            question = self._process_question(d)
            questions.append(tuple(question.values()))
            if q_keys is None:
                q_keys = question.keys()

            answer = self._process_answer(d)
            # add like_count as an additional value to satisfy query args
            a_values = list(answer.values())
            a_values.append(answer["like_count"])
            answers.append(tuple(a_values))
            if a_keys is None:
                a_keys = answer.keys()

            thread = self._process_thread(d)
            if thread is not None:
                threads.append(tuple(thread.values()))
                if t_keys is None:
                    t_keys = thread.keys()

            print(
                f"Progress: {i/len(data)*100:.1f}% - writing data to disk\033[K",
                end="\r",
            )

        self.db.add_questions(q_keys, questions)
        self.db.add_answers(a_keys, answers)
        self.db.add_threads(t_keys, threads)

        self.logger.debug("processing finished")
        self.db.close()

    def process_profile(self, data: askFMProfileDetails):
        urls = {}
        if data.get("avatarUrl") is not None and len(data["avatarUrl"]) > 0:
            url = data["avatarUrl"]
            filename = url.split("/")[-1]
            filename = filename[: filename.index(".")]
            filename = f"profile_{filename}"
            urls[filename] = url

        if data.get("backgroundUrl") is not None and len(data["backgroundUrl"]) > 0:
            url = data["backgroundUrl"]
            filename = url.split("/")[-1]
            filename = filename[: filename.index(".")]
            filename = f"background_{filename}"
            urls[filename] = url

        for picture in data["pictures"]:
            url = picture["url"]
            filename = url.split("/")[-1]
            filename = filename[: filename.index(".")]
            filename = f"profile_{filename}"
            urls[filename] = url

        uid = data["uid"].lower()
        for filename, url in urls.items():
            path = os.path.join(self.download_dir, uid, filename)
            visual_id, ok = self.download_image(url=url, path=path)

        blob = json.dumps(data)
        user = UserModel(id=uid, name=data["fullName"], blob=blob)

        self.db.connect()
        self.db.add_user(user)
        self.db.update_user_blob(id=uid, blob=blob)
        self.db.close()

    def _process_question(self, data: AskFMData) -> QuestionModel:
        keys = None
        tid = None
        if data.get("thread") is not None:
            tid = data["thread"]["threadId"]

        if data["author"] is not None:
            data["author"] = data["author"].lower()

        question = QuestionModel(
            qid=data["qid"],
            uid=data["answer"]["author"].lower(),
            tid=tid,
            type=data["type"],
            text=data["body"],
            author_id=data["author"],
            author_name=data["authorName"],
            visual_id=self.__process_visual_from_question(data),
            created_at=data["createdAt"],
        )

        return question

    def __process_visual_from_question(self, data: AskFMData) -> str | None:
        if data.get("questionPhotoInfo") is None:
            return None

        visual_id = f"q_{data['qid']}"
        path = os.path.join(
            self.download_dir, data["answer"]["author"].lower(), visual_id
        )
        visual_id, ok = self.download_image(
            url=data["questionPhotoInfo"]["photoUrl"], path=path
        )
        relative = os.path.join("./", data["answer"]["author"].lower(), visual_id)
        if not ok:
            self.logger.info(
                f"failed to downloda visual for {visual_id}, adding to failed queue"
            )
            self.db.add_download_queue(
                visual=QueueModel(
                    id=visual_id,
                    url=data["questionPhotoInfo"]["photoUrl"],
                    directory=relative,
                    type="photo",
                )
            )
        else:
            self.db.add_visual(
                visual=VisualModel(id=visual_id, directory=relative, type="photo")
            )

        return visual_id

    def _process_answer(self, data: AskFMData) -> AnswerModel:
        answer = AnswerModel(
            qid=data["qid"],
            uid=data["answer"]["author"].lower(),
            text=data["answer"].get("body"),
            visual_id=self.__process_visual_from_answer(data),
            like_count=data["answer"].get("likeCount", 0),
            created_at=data["answer"]["createdAt"],
        )

        return answer

    def __process_visual_from_answer(self, data: AskFMData) -> str | None:
        photo = data["answer"].get("photoUrl")
        video = data["answer"].get("videoUrl")
        if photo is None and video is None:
            return None

        visual_url = photo if photo is not None else video
        visual_id = f"a_{data['qid']}"
        path = os.path.join(
            self.download_dir, data["answer"]["author"].lower(), visual_id
        )
        visual_id, ok = self.download_image(url=visual_url, path=path)
        relative = os.path.join("./", data["answer"]["author"].lower(), visual_id)
        if not ok:
            self.logger.info(
                f"failed to downloda visual for {visual_id}, adding to failed queue"
            )
            self.db.add_download_queue(
                visual=QueueModel(
                    id=visual_id,
                    url=visual_url,
                    directory=relative,
                    type=data["answer"]["type"],
                )
            )
        else:
            self.db.add_visual(
                visual=VisualModel(
                    id=visual_id, directory=relative, type=data["answer"]["type"]
                )
            )

        return visual_id

    def _process_thread(self, data: AskFMData) -> ThreadModel | None:
        if data.get("thread") is None:
            return None

        return ThreadModel(
            id=data["thread"]["threadId"],
            uid=data["answer"]["author"].lower(),
            qid=data["qid"],
            external=False,
        )

    def process_chat(self, datas: list[askFMChat]):
        self.logger.debug("processing chats started")
        self.db.connect()
        for data in datas:
            if data.get("messages", None) is None:
                self.logger.debug(f'chat for qid={data["root"]["qid"]} is gone')
                continue
            for message in data["messages"]:
                chat = ChatModel(
                    id=message["id"],
                    uid=data["owner"]["uid"],
                    qid=data["root"]["qid"],
                    text=message["text"],
                    author_id=message.get("uid"),
                    author_name=message.get("fullName"),
                    created_at=message["createdAt"],
                )
                self.db.add_chat(chat)
        self.logger.debug("processing chats ended")
        self.db.close()

    def download_image(self, url: str, path: str) -> Tuple[str, bool]:
        dir = os.path.dirname(path)
        if not os.path.exists(dir):
            self.logger.info(f"output directory doesn't exist, creating it... {dir}")
            os.makedirs(dir)

        filename = os.path.basename(path)
        tokens = url.split(".")
        ext = tokens[-1]
        if ".gif" in ext:
            ext = ext[: ext.index(".gif") + 4]

        # file already exists, we may have downloaded it before using the old
        # extractor, so skip and return true
        if os.path.isfile(f"{path}.{ext}"):
            return f"{filename}.{ext}", True

        response = requests.get(url)
        if response.status_code != 200:
            self.logger.error(f"error download image: {filename}")
            return filename, False

        try:
            path = os.path.join(dir, f"{filename}.{ext}")
            with open(path, "wb") as handler:
                handler.write(response.content)
        except Exception as ex:
            self.logger.error(f"error saving image to {filename}.{ext}: {ex}")
            return filename, False

        return f"{filename}.{ext}", True
