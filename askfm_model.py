from typing import TypedDict


class AskFMThread(TypedDict):
    threadId: int


class AskFMAnswer(TypedDict):
    author: str
    authorName: str
    type: str  # photo, video, text, etc
    body: str
    photoUrl: str
    videoThumbUrl: str
    videoUrl: str
    videoFormat: int
    createdAt: int


class AskFMQuestionPhoto(TypedDict):
    photoUrl: str


class AskFMData(TypedDict):
    type: str  # anon, system, etc
    body: str  # the question text
    qid: int
    author: str | None
    authorName: str | None
    createdAt: int
    chat: bool
    answer: AskFMAnswer
    thread: AskFMThread
    questionPhotoInfo: AskFMQuestionPhoto


class AskFM(TypedDict):
    type: str  # question or something else
    data: AskFMData
    ts: int


class askFMChatMessages(TypedDict):
    id: int
    fullName: str
    uid: str
    avatarUrl: str
    text: str
    createdAt: int
    isOwn: bool


class askFMChatOwner(TypedDict):
    uid: str
    fullName: str


class askFMChat(TypedDict):
    root: AskFMData
    messages: list[askFMChatMessages]
    hasOlder: bool
    owner: askFMChatOwner


class askFMProfilePictures(TypedDict):
    id: str
    url: str


class askFMProfileDetails(TypedDict):
    fullName: str
    uid: str
    answerCount: int
    likeCount: int
    bio: str
    location: str
    webSite: str
    avatarUrl: str
    backgroundUrl: str
    pictures: list[askFMProfilePictures]
