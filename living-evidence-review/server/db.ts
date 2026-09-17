import { eq } from "drizzle-orm";
import { drizzle } from "drizzle-orm/mysql2";
import { InsertUser, ReviewRecordRow, InsertReviewRecord, reviewRecords, users } from "../drizzle/schema";
import { ENV } from "./_core/env";
import { computeRecord, type ComputedRecord, type ReviewDecision } from "./reviewEngine";
import { recordSeeds } from "./reviewData";

let _db: ReturnType<typeof drizzle> | null = null;

export async function getDb() {
  if (!_db && process.env.DATABASE_URL) {
    try {
      _db = drizzle(process.env.DATABASE_URL);
    } catch (error) {
      console.warn("[Database] Failed to connect:", error);
      _db = null;
    }
  }
  return _db;
}

export async function upsertUser(user: InsertUser): Promise<void> {
  if (!user.openId) throw new Error("User openId is required for upsert");
  const db = await getDb();
  if (!db) return;
  const values: InsertUser = { openId: user.openId };
  const updateSet: Record<string, unknown> = {};
  const textFields = ["name", "email", "loginMethod"] as const;
  for (const field of textFields) {
    if (user[field] !== undefined) {
      values[field] = user[field] ?? null;
      updateSet[field] = user[field] ?? null;
    }
  }
  if (user.lastSignedIn !== undefined) {
    values.lastSignedIn = user.lastSignedIn;
    updateSet.lastSignedIn = user.lastSignedIn;
  }
  if (user.role !== undefined) {
    values.role = user.role;
    updateSet.role = user.role;
  } else if (user.openId === ENV.ownerOpenId) {
    values.role = "admin";
    updateSet.role = "admin";
  }
  values.lastSignedIn ??= new Date();
  updateSet.lastSignedIn ??= new Date();
  await db.insert(users).values(values).onDuplicateKeyUpdate({ set: updateSet });
}

export async function getUserByOpenId(openId: string) {
  const db = await getDb();
  if (!db) return undefined;
  const result = await db.select().from(users).where(eq(users.openId, openId)).limit(1);
  return result[0];
}

function parseRow(row: ReviewRecordRow): ComputedRecord {
  const parsed = JSON.parse(row.payload) as ComputedRecord;
  return {
    ...parsed,
    reviewerDecision: (row.reviewerDecision as ReviewDecision | null) ?? parsed.reviewerDecision,
    reviewerReason: row.reviewerReason ?? parsed.reviewerReason,
    reviewerInitials: row.reviewerInitials ?? parsed.reviewerInitials,
    reviewedAt: row.reviewedAt?.toISOString() ?? parsed.reviewedAt,
  };
}

export async function seedReviewRecords() {
  const db = await getDb();
  if (!db) return { persisted: false, count: recordSeeds.length };
  for (const seed of recordSeeds) {
    const computed = computeRecord(seed);
    const values: InsertReviewRecord = { id: seed.id, payload: JSON.stringify(computed) };
    await db.insert(reviewRecords).values(values).onDuplicateKeyUpdate({
      set: { payload: JSON.stringify(computed), updatedAt: new Date() },
    });
  }
  return { persisted: true, count: recordSeeds.length };
}

export async function listReviewRecords(): Promise<ComputedRecord[]> {
  const db = await getDb();
  if (!db) return recordSeeds.map(computeRecord);
  const rows = await db.select().from(reviewRecords);
  if (!rows.length) {
    await seedReviewRecords();
    return recordSeeds.map(computeRecord);
  }
  if (rows.some(row => !row.payload.includes('"rubricSignal"'))) {
    await seedReviewRecords();
  }
  const refreshedRows = rows.some(row => !row.payload.includes('"rubricSignal"'))
    ? await db.select().from(reviewRecords)
    : rows;
  return refreshedRows.map(parseRow).sort((a, b) => a.id.localeCompare(b.id, undefined, { numeric: true }));
}

export async function getReviewRecord(id: string) {
  const records = await listReviewRecords();
  return records.find(record => record.id === id);
}

export async function updateReviewDecision(input: {
  id: string;
  decision: ReviewDecision;
  reason: string;
  initials: string;
}) {
  const records = await listReviewRecords();
  const current = records.find(record => record.id === input.id);
  if (!current) throw new Error("Record not found");
  const reviewedAt = new Date();
  const updated: ComputedRecord = {
    ...current,
    reviewerDecision: input.decision,
    reviewerReason: input.reason,
    reviewerInitials: input.initials,
    reviewedAt: reviewedAt.toISOString(),
  };
  const db = await getDb();
  if (db) {
    await db.update(reviewRecords).set({
      payload: JSON.stringify(updated),
      reviewerDecision: input.decision,
      reviewerReason: input.reason,
      reviewerInitials: input.initials,
      reviewedAt,
      updatedAt: reviewedAt,
    }).where(eq(reviewRecords.id, input.id));
  }
  return updated;
}
