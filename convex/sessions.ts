import { query, mutation } from "./_generated/server";
import { v } from "convex/values";

// Get a session by phone number
export const get = query({
  args: { phoneNumber: v.string() },
  handler: async (ctx, args) => {
    const session = await ctx.db
      .query("sessions")
      .withIndex("by_phone", (q) => q.eq("phoneNumber", args.phoneNumber))
      .first();
    
    return session;
  },
});

// Create or update a session
export const upsert = mutation({
  args: {
    phoneNumber: v.string(),
    name: v.optional(v.string()),
    email: v.optional(v.string()),
    callInitiated: v.optional(v.boolean()),
    callCompleted: v.optional(v.boolean()),
    infoProvided: v.optional(v.boolean()),
    lastActivity: v.string(),
    createdAt: v.optional(v.string()),
    callTime: v.optional(v.string()),
    callCompletedTime: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    // Check if session exists
    const existing = await ctx.db
      .query("sessions")
      .withIndex("by_phone", (q) => q.eq("phoneNumber", args.phoneNumber))
      .first();

    if (existing) {
      // Update existing session
      await ctx.db.patch(existing._id, {
        ...args,
        lastActivity: new Date().toISOString(),
      });
      
      // Return updated session
      return await ctx.db.get(existing._id);
    } else {
      // Create new session
      const sessionId = await ctx.db.insert("sessions", {
        ...args,
        createdAt: args.createdAt || new Date().toISOString(),
        lastActivity: new Date().toISOString(),
      });
      
      // Return new session
      return await ctx.db.get(sessionId);
    }
  },
});

// Update only the last activity timestamp
export const updateActivity = mutation({
  args: {
    phoneNumber: v.string(),
    lastActivity: v.string(),
  },
  handler: async (ctx, args) => {
    const session = await ctx.db
      .query("sessions")
      .withIndex("by_phone", (q) => q.eq("phoneNumber", args.phoneNumber))
      .first();

    if (session) {
      await ctx.db.patch(session._id, {
        lastActivity: args.lastActivity,
      });
      return true;
    }
    return false;
  },
});

// Delete a session
export const deleteSession = mutation({
  args: { phoneNumber: v.string() },
  handler: async (ctx, args) => {
    const session = await ctx.db
      .query("sessions")
      .withIndex("by_phone", (q) => q.eq("phoneNumber", args.phoneNumber))
      .first();

    if (session) {
      await ctx.db.delete(session._id);
      return true;
    }
    return false;
  },
});

// Get all sessions (for debugging)
export const getAll = query({
  handler: async (ctx) => {
    const sessions = await ctx.db.query("sessions").collect();
    return sessions;
  },
});

// Clean up expired sessions (older than 24 hours)
export const cleanupExpired = mutation({
  handler: async (ctx) => {
    const now = new Date();
    const twentyFourHoursAgo = new Date(now.getTime() - 24 * 60 * 60 * 1000);
    
    const sessions = await ctx.db.query("sessions").collect();
    
    let deleted = 0;
    for (const session of sessions) {
      const lastActivity = new Date(session.lastActivity);
      if (lastActivity < twentyFourHoursAgo) {
        await ctx.db.delete(session._id);
        deleted++;
      }
    }
    
    return { deleted };
  },
});
