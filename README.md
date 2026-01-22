# 🏦 Economy Bot Discord - Commands Guide

This document lists all commands of the Economy Bot for Discord and explains their functionality. Commands are split by access level.

---

## 👥 Roles

- **Owner** → Bank owner  
- **Manager** → Can view bank info (added by Owner or Staff)  
- **Staff** → Can create, delete, reset banks, add money, add managers, and buy generators  

---

## 📌 General Commands (Owner, Manager, Staff)

| Command | Description |
|---------|------------|
| `!bank_info <Bank Name>` | Shows bank balance, owner, managers, and generator counts. Accessible by Owner, Managers, or Staff. |
| `!list_generators` | Displays all generator types with prices, production, and max limits. Only Staff can buy them. |
| `!generator_income <Bank Name> [debug]` | Collects generator income for the bank (25% tax applied). `debug` option shows breakdown per generator type. |
| `!check_irs <Bank Name>` | Applies the IRS rule manually if the bank exceeds the balance cap ($3,000,000). |

---

## 🛡️ Staff Only Commands

| Command | Description |
|---------|------------|
| `!open_bank <Bank Name> <Owner ID>` | Creates a new bank for a user. Bank names must start with a capital letter for each word. |
| `!delete_bank <Bank Name>` | Deletes an existing bank and all its generator data. |
| `!reset_bank <Bank Name>` | Resets a bank's balance and generator counts to zero. |
| `!add_money <Bank Name> <amount> <reason>` | Adds money to a bank. `Reason` is required and `amount` must be a decimal number. |
| `!add_manager <Bank Name> <User>` | Adds a Manager to a bank. Only Owner or Staff can add managers. |
| `!buy_generator <Bank Name> <type> <amount>` | Purchases generators for a bank. Only Staff can buy generators. Respects max per type and total generators per bank. |

---

## ⚙️ Generator Rules

- Maximum **7 generators per bank** in total.  
- Maximum **3 generators per type**.  
- Generator types and stats:

| Type | Price | Produces | Max per Type |
|------|-------|----------|--------------|
| Low-Grade | $15,000 | $5,000 | 3 |
| Middle-Grade | $22,500 | $10,000 | 3 |
| High-Grade | $30,000 | $15,000 | 3 |
| Top-Grade | $50,000 | $20,000 | 3 |

- Income from generators is taxed **25%**.  

---

## 💰 IRS Rule

- If a bank's balance exceeds **$3,000,000**, any income above this limit is reduced by **75%**.  
- Applied automatically during income collection or manually via `!check_irs`.  

---

## 🗓️ Weekly Automation

- Generator income is automatically applied **every Monday**.  
- Tax and IRS are processed automatically during this update.  

---

## ⚠️ Notes

- Only Staff can manage generator purchases, bank creation, money addition, or resetting banks.  
- Owners and Managers can view bank info and collect generator income.  
- All data is saved persistently in `data.json`.  
