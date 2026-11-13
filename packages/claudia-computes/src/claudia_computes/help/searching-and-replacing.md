---
id: computes.searching-and-replacing
title: How do I find and replace things in my workbook?
apps: computes
language: en
tags: search, find, replace, pattern, builder, match
explains: Search & replace, Replace with, Build a pattern, Left out
---
**Edit ▸ Search & replace…** (Ctrl+F) opens a panel beside the sheet. Type what you are looking for and the cells
that contain it are marked as you type; Enter goes to the next match, Shift+Enter to the previous one. Ctrl+H opens the
same panel with **Replace with** already showing.

## Where it looks

The three switches under **Look in** say what is searched: **Text** (what you typed into a cell), **Formulas** (the
formula as written, with its `=`) and **Values** (what a cell shows, including what a formula computes). Each switch
shows how many matches it has. **This sheet**, **All sheets** and **Selection** say how far to look; **Match case**
and **Whole cell** narrow it further.

## Describing more than a word

**Build a pattern…** turns the field into parts you put together — "a letter, then one or more digits, then the
text `EUR`" — and a sentence under them says back in plain words what is being found, so you can check it is what you
meant. **Only in cells that…** adds a demand on the whole cell, for example "do not contain `draft`". Cells that
match the parts but fail a demand are listed under **Left out**, with the reason, so a missing match is never a mystery.

## Replacing

Switch on **Replace with…** and each match shows what it would become. Untick the ones to keep, then press
**Replace this one** or **Replace all**. All of it is one step in the history, so Undo brings every cell back.
Values cannot be replaced — a value follows from its formula — and a replacement that would break a formula, or that
would make a cell too long, is skipped and says so. A cell a colleague is editing is skipped, naming them.

To reuse part of what was found, press **Keep** on that part in the builder, then click its name in the
replacement: "keep the digits, change the text `EUR` to `USD`".

## Writing the pattern yourself

If you know how to write patterns, **⋯ ▸ Write the pattern yourself…** shows the pattern the builder made, ready to
edit. The syntax is that of Python's `re` module. A mistake is explained in words, with the place it is at. Once you
edit it, the builder can no longer show it; **Back to the builder** returns to what you had.
