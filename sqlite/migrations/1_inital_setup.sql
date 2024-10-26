CREATE TABLE `users` (
    `id` varchar(255) not null primary key,
    `name` varchar(255)
);

CREATE TABLE `visuals` (
    `id` varchar(255) not null primary key,
    `type` varchar(5) not null,
    `directory` varchar(255) not null
);

CREATE TABLE `questions` (
    `qid` integer not null primary key,
    `uid` varchar(255) not null,
    `tid` integer,
    `type` varchar(255),
    `text` text,
    `author_id` varchar(255),
    `author_name` varchar(255),
    `visual_id` varchar(255),
    `created_at` datetime not null,
    foreign key(`uid`) references `users`(`id`),
    foreign key(`visual_id`) references `visuals`(`id`)
);

CREATE TABLE `answers` (
    `qid` integer not null primary key,
    `uid` varchar(255) not null,
    `text` text,
    `visual_id` varchar(255),
    `created_at` datetime not null,
    foreign key(`uid`) references `users`(`id`),
    foreign key(`qid`) references `questions`(`qid`),
    foreign key(`visual_id`) references `visuals`(`id`)
);

CREATE TABLE `chats` (
    `id` integer not null primary key,
    `uid` varchar(255) not null,
    `qid` integer not null,
    `text` text not null,
    `author_id` varchar(255),
    `author_name` varchar(255),
    `created_at` datetime not null,
    foreign key(`qid`) references `questions`(`qid`),
    foreign key(`uid`) references `users`(`id`)
);

CREATE TABLE `threads` (
    `id` integer not null,
    `uid` varchar(255) not null,
    `qid` integer not null,
    `external` boolean not null,
    primary key(`id`, `qid`),
    foreign key(`qid`) references `questions`(`qid`),
    foreign key(`uid`) references `users`(`id`)
);

CREATE TABLE `download_queue` (
    `id` varchar(255) not null primary key,
    `type` varchar(5) not null,
    `directory` varchar(255) not null,
    `url` text not null
);

CREATE TABLE `schema` (`version` integer);

CREATE UNIQUE INDEX `index_users_id` on `users` (`id`);

CREATE UNIQUE INDEX `index_visuals_id` on `visuals` (`id`);

CREATE UNIQUE INDEX `index_questions_id` on `questions` (`qid`);

CREATE UNIQUE INDEX `index_answers_id` on `answers` (`qid`);

CREATE INDEX `index_chats_id` on `chats` (`qid`);

CREATE INDEX `index_threads_id` on `threads` (`id`);