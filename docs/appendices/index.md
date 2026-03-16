---
title: Appendices
description: >-
  Reference material for revisiting asyncio details -- the checkpoint
  contract, a consolidated best-practices checklist, and a deeper debugging
  guide.
icon: lucide/book-marked
---

# Appendices

This chapter is for reference and revisiting. The earlier chapters teach the
core mental model and the safe defaults; these sections help you look up a
detail quickly once you are already writing and debugging async code.

The appendices are not meant to be read linearly. Dip into them when you need
to check [checkpoint behavior](checkpoint-contract.md#always-suspends), scan the
[best practices](best-practices.md), or debug a [blocked loop](debugging.md#diagnosing-a-blocked-loop)
that is not making sense yet.

## Sections

1. [Checkpoint Contract](checkpoint-contract.md) -- guide-level reference for
   which common operations [always suspend](checkpoint-contract.md#always-suspends),
   [conditionally suspend](checkpoint-contract.md#conditionally-suspends), or
   [never suspend](checkpoint-contract.md#never-suspends).

2. [Best Practices, Pitfalls, and Gotchas](best-practices.md) -- the guide's
   consolidated best practices, pitfalls, and gotchas for quick review.

3. [Debugging Guide](debugging.md) -- practical techniques for
   [blocked loops](debugging.md#diagnosing-a-blocked-loop),
   [task leaks](debugging.md#diagnosing-task-leaks),
   [deadlocks](debugging.md#diagnosing-deadlocks), and
   [diagnostic patterns](debugging.md#useful-diagnostic-patterns).
