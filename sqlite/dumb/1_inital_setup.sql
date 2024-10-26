CREATE TABLE `answers_questions` (
    `qid` integer not null primary key,
    `uid` varchar(255) not null,
    `answer` text,
    `question` text,
    `author_id` varchar(255),
    `author_name` varchar(255),
    `q_ts` datetime not null,
    `a_ts` datetime not null
);


CREATE TABLE `chats` (
    `id` integer not null primary key,
    `qid` integer not null,
    `text` text not null,
    `author_id` varchar(255),
    `author_name` varchar(255),
    `created_at` datetime not null,
    foreign key(`qid`) references `questions`(`qid`)
);

CREATE UNIQUE INDEX `index_questions_id` on `answers_questions` (`qid`);

CREATE INDEX `index_chats_id` on `chats` (`qid`);

