import { z } from "zod";
import { COOKIE_NAME } from "@shared/const";
import { getSessionCookieOptions } from "./_core/cookies";
import { systemRouter } from "./_core/systemRouter";
import { publicProcedure, router } from "./_core/trpc";
import { getReviewRecord, listReviewRecords, seedReviewRecords, updateReviewDecision } from "./db";
import { OUTCOMES, reviewConfiguration } from "./reviewEngine";

export const appRouter = router({
  system: systemRouter,
  auth: router({
    me: publicProcedure.query(opts => opts.ctx.user),
    logout: publicProcedure.mutation(({ ctx }) => {
      const cookieOptions = getSessionCookieOptions(ctx.req);
      ctx.res.clearCookie(COOKIE_NAME, { ...cookieOptions, maxAge: -1 });
      return { success: true } as const;
    }),
  }),
  review: router({
    config: publicProcedure.query(() => ({ ...reviewConfiguration, outcomes: OUTCOMES })),
    list: publicProcedure.query(() => listReviewRecords()),
    get: publicProcedure.input(z.object({ id: z.string() })).query(({ input }) => getReviewRecord(input.id)),
    seed: publicProcedure.mutation(() => seedReviewRecords()),
    updateDecision: publicProcedure
      .input(z.object({
        id: z.string(),
        decision: z.enum(["CONFIRM", "OVERRIDE", "REMAP", "DEFER", "EXCLUDE"]),
        reason: z.string().trim().min(3),
        initials: z.string().trim().min(1).max(32),
      }))
      .mutation(({ input }) => updateReviewDecision(input)),
  }),
});

export type AppRouter = typeof appRouter;
