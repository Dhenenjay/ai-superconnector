import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";

export default defineSchema({
  sessions: defineTable({
    phoneNumber: v.string(),
    name: v.optional(v.string()),
    email: v.optional(v.string()),
    callInitiated: v.optional(v.boolean()),
    callCompleted: v.optional(v.boolean()),
    infoProvided: v.optional(v.boolean()),
    lastActivity: v.string(),
    createdAt: v.string(),
    callTime: v.optional(v.string()),
    callCompletedTime: v.optional(v.string()),
  })
    .index("by_phone", ["phoneNumber"])
    .index("by_email", ["email"]),
});
