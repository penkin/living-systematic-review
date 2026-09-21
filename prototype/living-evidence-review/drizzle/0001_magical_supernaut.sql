CREATE TABLE `review_records` (
	`id` varchar(32) NOT NULL,
	`payload` text NOT NULL,
	`reviewerDecision` varchar(32),
	`reviewerReason` text,
	`reviewerInitials` varchar(32),
	`reviewedAt` timestamp,
	`createdAt` timestamp NOT NULL DEFAULT (now()),
	`updatedAt` timestamp NOT NULL DEFAULT (now()) ON UPDATE CURRENT_TIMESTAMP,
	CONSTRAINT `review_records_id` PRIMARY KEY(`id`)
);
