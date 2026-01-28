# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Standard Workflow
1. First think through the problem, read the codebase for relevant files, and write a plan to tasks/todo.md.
2. The plan should have a list of todo items that you can check off as you complete them
3. Before you begin working, check in with me and I will verify the plan.
4. Then, begin working on the todo items, marking them as complete as you go.
5. Please every step of the way just give me a high level explanation of what changes you made
6. **Make every task and code change as simple as possible**. We want to avoid making any massive or complex changes. Every change should impact as little code as possible. Everything is about simplicity.
7. Finally, add a review section to the todo.md file with a summary of the changes you made and any other relevant information.

## Project Overview

This repository contains algorithmic trading analysis tasks for B3 (Brazilian) and MOEX (Moscow) exchanges. The project focuses on:
- PCAP file parsing for market data (B3 exchange)
- Calendar spread analysis between futures contracts
- Volatility and momentum algorithm development
- Arbitrage strategy analysis between B3 and MOEX gold futures

## Data

- `quotes_202512260854-GOLD.csv`: Gold futures quotes with columns: `ts`, `symbol`, `bid_price`, `bid_qty`, `ask_price`, `ask_qty`
  - Symbols include `GLDG26` (B3) and `GOLD-3.26` (MOEX)
  - Timestamps in nanosecond precision

## Language

Task descriptions are in Russian. Documentation may be created in Google Docs as specified in the task requirements.
