import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import re
import asyncio
from datetime import datetime, timedelta
import json

load_dotenv()

# --- BOT SETUP ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- CONFIG ---
STAFF_ROLE_ID = 123456789012345678  # <-- Replace with your staff role ID
STAFF_CHANNEL_ID = 987654321098765432  # Optional: channel for weekly notifications
DATA_FILE = "data.json"

# --- GENERATOR SETTINGS ---
GENERATOR_TYPES = {
    "low": {"price": 15000.0, "income": 5000.0, "max": 3},
    "middle": {"price": 22500.0, "income": 10000.0, "max": 3},
    "high": {"price": 30000.0, "income": 15000.0, "max": 3},
    "top": {"price": 50000.0, "income": 20000.0, "max": 3}
}
MAX_GENERATORS_TOTAL = 7
GENERATOR_TAX = 0.25  # 25%
IRS_LIMIT = 3_000_000.0
IRS_PENALTY = 0.75

# --- LOAD / SAVE DATA ---
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        economy = json.load(f)
else:
    economy = {"banks": {}, "generators": {}}

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(economy, f, indent=4)

# --- HELPERS ---
def is_valid_bank_name(name: str) -> bool:
    return bool(re.fullmatch(r"(?:[A-Z][a-zA-Z]*)(?: (?:[A-Z][a-zA-Z]*))*", name))

def has_staff_role(member: discord.Member) -> bool:
    return any(role.id == STAFF_ROLE_ID for role in member.roles)

def get_bank(bank_name: str):
    return economy["banks"].get(bank_name)

def can_access_bank(ctx, bank_name: str):
    bank = get_bank(bank_name)
    if not bank:
        return False
    # Owner, manager or staff can access
    return (
        str(ctx.author.id) == bank["owner_id"] or
        str(ctx.author.id) in bank.get("managers", []) or
        has_staff_role(ctx.author)
    )

def apply_irs(bank):
    if bank["balance"] > IRS_LIMIT:
        excess = bank["balance"] - IRS_LIMIT
        penalty = int(excess * IRS_PENALTY)
        bank["balance"] -= penalty
        return True, excess, penalty
    return False, 0, 0

# --- EVENTS ---
@bot.event
async def on_ready():
    print(f"Bot online as {bot.user}")

# --- HELP COMMAND ---
@bot.command()
async def help_commands(ctx):
    msg = (
        "**🏦 Economy Bot Commands**\n\n"
        "**Owner / Manager / Staff Commands:**\n"
        "`!bank_info <Bank Name>` - Show balance, owner, managers and generators\n"
        "`!list_generators` - Show all generators\n"
        "`!generator_income <Bank Name> [debug]` - Collect generator income\n"
        "`!check_irs <Bank Name>` - Apply IRS rule manually\n\n"
        "**Staff Only Commands:**\n"
        "`!open_bank <Bank Name> <Owner ID>` - Create a bank for a user\n"
        "`!delete_bank <Bank Name>` - Delete a bank\n"
        "`!reset_bank <Bank Name>` - Reset a bank's balance and generators\n"
        "`!add_money <Bank Name> <amount> <reason>` - Add money to any bank (reason required)\n"
        "`!add_manager <Bank Name> <User>` - Add a manager to a bank\n"
        "`!buy_generator <Bank Name> <type> <amount>` - Purchase generators (Staff only)"
    )
    await ctx.send(msg)

# --- OPEN BANK ---
@bot.command()
async def open_bank(ctx, bank_name: str = None, owner_id: str = None):
    if not has_staff_role(ctx.author):
        await ctx.send("❌ Only Economy Staff Team members can open a bank.")
        return
    if not bank_name or not owner_id:
        await ctx.send("**Usage:** `!open_bank <Bank Name> <Owner ID>`")
        return
    if not is_valid_bank_name(bank_name):
        await ctx.send("❌ Invalid bank name format. Each word must start with a capital letter.")
        return
    if bank_name in economy["banks"]:
        await ctx.send("❌ A bank with that name already exists.")
        return
    economy["banks"][bank_name] = {
        "owner_id": owner_id,
        "balance": 0.0,
        "managers": []
    }
    economy["generators"][bank_name] = {"low": 0, "middle": 0, "high": 0, "top": 0}
    save_data()
    await ctx.send(f"✅ Bank **{bank_name}** created for user <@{owner_id}>!")

# --- DELETE BANK ---
@bot.command()
async def delete_bank(ctx, *, bank_name: str = None):
    if not has_staff_role(ctx.author):
        await ctx.send("❌ Only Economy Staff Team members can delete a bank.")
        return
    if not bank_name or bank_name not in economy["banks"]:
        await ctx.send("❌ Bank not found.")
        return
    economy["banks"].pop(bank_name)
    economy["generators"].pop(bank_name)
    save_data()
    await ctx.send(f"🗑️ Bank **{bank_name}** has been deleted.")

# --- RESET BANK ---
@bot.command()
async def reset_bank(ctx, *, bank_name: str = None):
    if not has_staff_role(ctx.author):
        await ctx.send("❌ Only Economy Staff Team members can reset a bank.")
        return
    bank = get_bank(bank_name)
    if not bank:
        await ctx.send("❌ Bank not found.")
        return
    bank["balance"] = 0.0
    economy["generators"][bank_name] = {"low": 0, "middle": 0, "high": 0, "top": 0}
    save_data()
    await ctx.send(f"♻️ Bank **{bank_name}** has been reset.")

# --- ADD MANAGER ---
@bot.command()
async def add_manager(ctx, bank_name: str = None, user: discord.Member = None):
    if not bank_name or not user:
        await ctx.send("**Usage:** `!add_manager <Bank Name> <User>`")
        return
    bank = get_bank(bank_name)
    if not bank:
        await ctx.send("❌ Bank not found.")
        return
    if not (has_staff_role(ctx.author) or str(ctx.author.id) == bank["owner_id"]):
        await ctx.send("❌ Only Owner or Staff can add a manager.")
        return
    user_id = str(user.id)
    if user_id in bank["managers"]:
        await ctx.send(f"❌ {user.display_name} is already a manager of **{bank_name}**.")
        return
    bank["managers"].append(user_id)
    save_data()
    await ctx.send(f"✅ {user.display_name} has been added as a manager of **{bank_name}**.")

# --- BANK INFO ---
@bot.command()
async def bank_info(ctx, *, bank_name: str = None):
    if not bank_name:
        await ctx.send("**Usage:** `!bank_info <Bank Name>`")
        return
    bank = get_bank(bank_name)
    if not bank:
        await ctx.send("❌ Bank not found.")
        return
    if not can_access_bank(ctx, bank_name):
        await ctx.send("❌ You don't have permission to access this bank.")
        return
    gens = economy["generators"][bank_name]
    managers_list = [f"<@{mid}>" for mid in bank.get("managers", [])]
    await ctx.send(
        f"🏦 **{bank_name}**\n"
        f"👤 Owner: <@{bank['owner_id']}>\n"
        f"🛡️ Managers: {', '.join(managers_list) if managers_list else 'None'}\n"
        f"💰 Balance: ${bank['balance']}\n\n"
        f"⚙️ Generators:\n"
        f"Low: {gens['low']}\nMiddle: {gens['middle']}\nHigh: {gens['high']}\nTop: {gens['top']}"
    )

# --- ADD MONEY ---
@bot.command()
async def add_money(ctx, bank_name: str = None, amount: str = None, *, reason: str = None):
    if not has_staff_role(ctx.author):
        await ctx.send("❌ Only Economy Staff Team members can add money.")
        return
    if not bank_name or not amount or not reason:
        await ctx.send("**Usage:** `!add_money <Bank Name> <amount> <reason>`")
        return
    try:
        amount_val = float(amount)
    except ValueError:
        await ctx.send("❌ Amount must be a decimal number.")
        return
    if amount_val <= 0:
        await ctx.send("❌ Amount must be greater than 0.")
        return
    bank = get_bank(bank_name)
    if not bank:
        await ctx.send("❌ Bank not found.")
        return
    bank["balance"] += amount_val
    irs_applied, excess, penalty = apply_irs(bank)
    save_data()
    msg = f"✅ Added ${amount_val} to **{bank_name}** for reason: {reason}\n💰 New balance: ${bank['balance']}"
    if irs_applied:
        msg += f"\n🚨 IRS ACTIVE! Excess: ${excess}, Penalty: {penalty}"
    await ctx.send(msg)

# --- LIST GENERATORS ---
@bot.command()
async def list_generators(ctx):
    msg = "**⚙️ Available Generators**\n\n"
    for gtype, info in GENERATOR_TYPES.items():
        msg += f"**{gtype.capitalize()}-Grade Generator**\nPrice: ${info['price']}\nProduces: ${info['income']}\nMax per type: {info['max']}\n\n"
    msg += f"📌 Max total generators per bank: {MAX_GENERATORS_TOTAL}\n⚠️ Note: Only Staff can buy generators."
    await ctx.send(msg)

# --- BUY GENERATOR (STAFF ONLY) ---
@bot.command()
async def buy_generator(ctx, bank_name: str = None, gen_type: str = None, amount: int = 1):
    if not has_staff_role(ctx.author):
        await ctx.send("❌ Only Economy Staff Team members can buy generators.")
        return
    if not bank_name or not gen_type:
        await ctx.send("**Usage:** `!buy_generator <Bank Name> <type> <amount>`")
        return
    bank = get_bank(bank_name)
    if not bank:
        await ctx.send("❌ Bank not found.")
        return

    gen_type = gen_type.lower()
    if gen_type not in GENERATOR_TYPES:
        await ctx.send("❌ Invalid generator type.")
        return

    current_total = sum(economy["generators"][bank_name].values())
    if current_total + amount > MAX_GENERATORS_TOTAL:
        await ctx.send(f"❌ Cannot exceed {MAX_GENERATORS_TOTAL} generators in total.")
        return
    if economy["generators"][bank_name][gen_type] + amount > GENERATOR_TYPES[gen_type]["max"]:
        await ctx.send(f"❌ Cannot exceed {GENERATOR_TYPES[gen_type]['max']} {gen_type} generators.")
        return

    total_price = GENERATOR_TYPES[gen_type]["price"] * amount
    if bank["balance"] < total_price:
        await ctx.send(f"❌ Not enough balance. Need ${total_price}.")
        return

    bank["balance"] -= total_price
    economy["generators"][bank_name][gen_type] += amount

    irs_applied, excess, penalty = apply_irs(bank)
    save_data()

    msg = f"✅ Purchased {amount} {gen_type.capitalize()} generator(s) for **{bank_name}**.\n💰 New balance: ${bank['balance']}"
    if irs_applied:
        msg += f"\n🚨 IRS ACTIVE! Excess: ${excess}, Penalty: {penalty}"
    await ctx.send(msg)

# --- GENERATOR INCOME ---
@bot.command()
async def generator_income(ctx, bank_name: str = None, debug: str = None):
    if not bank_name:
        await ctx.send("**Usage:** `!generator_income <Bank Name> [debug]`")
        return
    bank = get_bank(bank_name)
    if not bank:
        await ctx.send("❌ Bank not found.")
        return
    if not can_access_bank(ctx, bank_name):
        await ctx.send("❌ You don't have permission to access this bank.")
        return
    total_income = 0
    breakdown = []
    for gtype, info in GENERATOR_TYPES.items():
        count = economy["generators"][bank_name][gtype]
        income = count * info["income"]
        total_income += income
        if debug == "debug":
            breakdown.append(f"{gtype.capitalize()}: {count} × ${info['income']} = ${income}")
    taxed_income = int(total_income * (1 - GENERATOR_TAX))
    bank["balance"] += taxed_income
    irs_applied, excess, penalty = apply_irs(bank)
    save_data()
    msg = f"🏦 **{bank_name}**\n💰 Generator income after 25% tax: ${taxed_income}"
    if debug == "debug":
        msg += "\n\n**Breakdown:**\n" + "\n".join(breakdown)
        msg += f"\nTotal before tax: ${total_income}"
    if irs_applied:
        msg += f"\n🚨 IRS ACTIVE! Excess: ${excess}, Penalty: {penalty}"
    await ctx.send(msg)

# --- WEEKLY GENERATOR INCOME ---
async def weekly_generator_income(hour=18, minute=0):
    await bot.wait_until_ready()
    while True:
        now = datetime.now()
        days_ahead = 0 - now.weekday()  # Monday=0
        if days_ahead <= 0:
            days_ahead += 7
        next_monday = now + timedelta(days=days_ahead)
        target = next_monday.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target < now:
            target += timedelta(days=7)
        await asyncio.sleep((target - now).total_seconds())
        for bank_name, bank in economy["banks"].items():
            total_income = sum(
                economy["generators"][bank_name][gtype] * info["income"]
                for gtype, info in GENERATOR_TYPES.items()
            )
            taxed_income = int(total_income * (1 - GENERATOR_TAX))
            bank["balance"] += taxed_income
            irs_applied, excess, penalty = apply_irs(bank)
            save_data()
            if STAFF_CHANNEL_ID:
                channel = bot.get_channel(STAFF_CHANNEL_ID)
                if channel:
                    msg = f"🏦 **{bank_name}** collected ${taxed_income} in generator income this week!"
                    if irs_applied:
                        msg += f"\n🚨 IRS ACTIVE! Excess: ${excess}, Penalty: {penalty}"
                    await channel.send(msg)
        print("✅ Weekly generator income applied!")

bot.loop.create_task(weekly_generator_income(hour=18, minute=0))

# --- RUN BOT ---
bot.run(os.getenv("TOKEN"))
