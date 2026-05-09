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
STAFF_ROLE_ID = 1458659480395976728
STAFF_CHANNEL_ID = 987654321098765432
DATA_FILE = "data.json"

# --- GENERATOR SETTINGS ---
GENERATOR_TYPES = {
    "low": {"price": 15000.0, "income": 5000.0, "max": 3, "emoji": "🔧"},
    "middle": {"price": 22500.0, "income": 10000.0, "max": 3, "emoji": "⚙️"},
    "high": {"price": 30000.0, "income": 15000.0, "max": 3, "emoji": "🏭"},
    "top": {"price": 50000.0, "income": 20000.0, "max": 3, "emoji": "💎"}
}
MAX_GENERATORS_TOTAL = 7
GENERATOR_TAX = 0.25
IRS_LIMIT = 3_000_000.0
IRS_PENALTY = 0.75

# --- COLORS ---
COLOR_SUCCESS = 0x00ff00
COLOR_ERROR = 0xff0000
COLOR_INFO = 0x3498db
COLOR_WARNING = 0xffa500
COLOR_MONEY = 0xffd700

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
    return (
        str(ctx.author.id) == bank["owner_id"] or
        str(ctx.author.id) in bank.get("managers", []) or
        has_staff_role(ctx.author)
    )

def apply_irs(bank):
    if bank["balance"] > IRS_LIMIT:
        excess = bank["balance"] - IRS_LIMIT
        penalty = round(excess * IRS_PENALTY, 2)
        bank["balance"] = round(bank["balance"] - penalty, 2)
        return True, excess, penalty
    return False, 0, 0

def format_money(amount):
    return f"${amount:,.2f}"

# --- EVENTS ---
@bot.event
async def on_ready():
    print(f"Bot online as {bot.user}")
    bot.loop.create_task(weekly_generator_income(hour=18, minute=0))

# --- HELP COMMAND ---
@bot.command()
async def help_commands(ctx):
    embed = discord.Embed(
        title="🏦 Economy Bot - Command List",
        description="Complete guide to all available commands",
        color=COLOR_INFO
    )
    
    embed.add_field(
        name="📊 General Commands",
        value=(
            "`!bank_info <Bank Name>` - View bank details\n"
            "`!list_generators` - Show all generator types\n"
            "`!generator_income <Bank Name> [debug]` - Collect income\n"
            "`!check_irs <Bank Name>` - Check IRS status"
        ),
        inline=False
    )
    
    embed.add_field(
        name="👑 Staff Commands",
        value=(
            "`!open_bank <Bank Name> <Owner ID>` - Create new bank\n"
            "`!delete_bank <Bank Name>` - Delete a bank\n"
            "`!reset_bank <Bank Name>` - Reset bank to zero\n"
            "`!add_money <Bank Name> <amount> <reason>` - Add funds\n"
            "`!add_manager <Bank Name> <User>` - Add manager\n"
            "`!buy_generator <Bank Name> <type> [amount]` - Buy generators"
        ),
        inline=False
    )
    
    embed.set_footer(text="💡 Use quotes for multi-word bank names")
    await ctx.send(embed=embed)

# --- OPEN BANK ---
@bot.command()
async def open_bank(ctx, *args):
    if not has_staff_role(ctx.author):
        embed = discord.Embed(
            title="❌ Access Denied",
            description="Only Economy Staff Team members can open banks.",
            color=COLOR_ERROR
        )
        await ctx.send(embed=embed)
        return
    
    if len(args) < 2:
        embed = discord.Embed(
            title="📋 Usage",
            description="**Command:** `!open_bank <Bank Name> <Owner ID>`",
            color=COLOR_INFO
        )
        await ctx.send(embed=embed)
        return

    owner_id = args[-1]
    bank_name = " ".join(args[:-1])

    if not is_valid_bank_name(bank_name):
        embed = discord.Embed(
            title="❌ Invalid Bank Name",
            description="Each word must start with a capital letter.",
            color=COLOR_ERROR
        )
        await ctx.send(embed=embed)
        return
    
    if bank_name in economy["banks"]:
        embed = discord.Embed(
            title="❌ Bank Already Exists",
            description=f"A bank named **{bank_name}** already exists.",
            color=COLOR_ERROR
        )
        await ctx.send(embed=embed)
        return

    economy["banks"][bank_name] = {
        "owner_id": owner_id,
        "balance": 0.0,
        "managers": []
    }
    economy["generators"][bank_name] = {"low": 0, "middle": 0, "high": 0, "top": 0}
    save_data()
    
    embed = discord.Embed(
        title="✅ Bank Created Successfully",
        description=f"**{bank_name}** is now open for business!",
        color=COLOR_SUCCESS
    )
    embed.add_field(name="👤 Owner", value=f"<@{owner_id}>", inline=True)
    embed.add_field(name="💰 Starting Balance", value=format_money(0), inline=True)
    embed.set_footer(text=f"Created by {ctx.author.name}")
    await ctx.send(embed=embed)

# --- DELETE BANK ---
@bot.command()
async def delete_bank(ctx, *, bank_name: str = None):
    if not has_staff_role(ctx.author):
        embed = discord.Embed(
            title="❌ Access Denied",
            description="Only Economy Staff Team members can delete banks.",
            color=COLOR_ERROR
        )
        await ctx.send(embed=embed)
        return
    
    if not bank_name or bank_name not in economy["banks"]:
        embed = discord.Embed(
            title="❌ Bank Not Found",
            description="Please provide a valid bank name.",
            color=COLOR_ERROR
        )
        await ctx.send(embed=embed)
        return
    
    economy["banks"].pop(bank_name)
    economy["generators"].pop(bank_name, None)
    save_data()
    
    embed = discord.Embed(
        title="🗑️ Bank Deleted",
        description=f"**{bank_name}** has been permanently removed.",
        color=COLOR_WARNING
    )
    embed.set_footer(text=f"Deleted by {ctx.author.name}")
    await ctx.send(embed=embed)

# --- RESET BANK ---
@bot.command()
async def reset_bank(ctx, *, bank_name: str = None):
    if not has_staff_role(ctx.author):
        embed = discord.Embed(
            title="❌ Access Denied",
            description="Only Economy Staff Team members can reset banks.",
            color=COLOR_ERROR
        )
        await ctx.send(embed=embed)
        return
    
    bank = get_bank(bank_name)
    if not bank:
        embed = discord.Embed(
            title="❌ Bank Not Found",
            description="Please provide a valid bank name.",
            color=COLOR_ERROR
        )
        await ctx.send(embed=embed)
        return
    
    bank["balance"] = 0.0
    economy["generators"][bank_name] = {"low": 0, "middle": 0, "high": 0, "top": 0}
    save_data()
    
    embed = discord.Embed(
        title="♻️ Bank Reset",
        description=f"**{bank_name}** has been reset to starting conditions.",
        color=COLOR_WARNING
    )
    embed.add_field(name="💰 Balance", value=format_money(0), inline=True)
    embed.add_field(name="⚙️ Generators", value="All removed", inline=True)
    embed.set_footer(text=f"Reset by {ctx.author.name}")
    await ctx.send(embed=embed)

# --- ADD MANAGER ---
@bot.command()
async def add_manager(ctx, *args):
    if len(args) < 2:
        embed = discord.Embed(
            title="📋 Usage",
            description="**Command:** `!add_manager <Bank Name> <User>`",
            color=COLOR_INFO
        )
        await ctx.send(embed=embed)
        return
    
    user = args[-1]
    bank_name = " ".join(args[:-1])

    bank = get_bank(bank_name)
    if not bank:
        embed = discord.Embed(
            title="❌ Bank Not Found",
            description="Please provide a valid bank name.",
            color=COLOR_ERROR
        )
        await ctx.send(embed=embed)
        return
    
    if not (has_staff_role(ctx.author) or str(ctx.author.id) == bank["owner_id"]):
        embed = discord.Embed(
            title="❌ Access Denied",
            description="Only the bank owner or staff can add managers.",
            color=COLOR_ERROR
        )
        await ctx.send(embed=embed)
        return

    try:
        user_id = re.sub(r"\D", "", user)
        if not user_id:
            raise ValueError("Invalid user ID")
    except Exception:
        embed = discord.Embed(
            title="❌ Invalid User",
            description="Please use @mention or a valid user ID.",
            color=COLOR_ERROR
        )
        await ctx.send(embed=embed)
        return

    if user_id in bank["managers"]:
        embed = discord.Embed(
            title="❌ Already a Manager",
            description=f"<@{user_id}> is already managing **{bank_name}**.",
            color=COLOR_ERROR
        )
        await ctx.send(embed=embed)
        return
    
    bank["managers"].append(user_id)
    save_data()
    
    embed = discord.Embed(
        title="✅ Manager Added",
        description=f"<@{user_id}> is now a manager of **{bank_name}**!",
        color=COLOR_SUCCESS
    )
    embed.set_footer(text=f"Added by {ctx.author.name}")
    await ctx.send(embed=embed)

# --- BANK INFO ---
@bot.command()
async def bank_info(ctx, *, bank_name: str = None):
    if not bank_name:
        embed = discord.Embed(
            title="📋 Usage",
            description="**Command:** `!bank_info <Bank Name>`",
            color=COLOR_INFO
        )
        await ctx.send(embed=embed)
        return
    
    bank = get_bank(bank_name)
    if not bank:
        embed = discord.Embed(
            title="❌ Bank Not Found",
            description="Please provide a valid bank name.",
            color=COLOR_ERROR
        )
        await ctx.send(embed=embed)
        return
    
    if not can_access_bank(ctx, bank_name):
        embed = discord.Embed(
            title="❌ Access Denied",
            description="You don't have permission to view this bank.",
            color=COLOR_ERROR
        )
        await ctx.send(embed=embed)
        return
    
    gens = economy["generators"][bank_name]
    managers_list = [f"<@{mid}>" for mid in bank.get("managers", [])]
    
    embed = discord.Embed(
        title=f"🏦 {bank_name}",
        description="Complete bank information",
        color=COLOR_MONEY
    )
    
    embed.add_field(name="👤 Owner", value=f"<@{bank['owner_id']}>", inline=True)
    embed.add_field(
        name="🛡️ Managers", 
        value=", ".join(managers_list) if managers_list else "None", 
        inline=True
    )
    embed.add_field(name="💰 Balance", value=format_money(bank['balance']), inline=False)
    
    gen_info = ""
    total_gens = 0
    for gtype, info in GENERATOR_TYPES.items():
        count = gens[gtype]
        total_gens += count
        gen_info += f"{info['emoji']} **{gtype.capitalize()}**: {count}/{info['max']}\n"
    
    embed.add_field(
        name=f"⚙️ Generators ({total_gens}/{MAX_GENERATORS_TOTAL})",
        value=gen_info if gen_info else "No generators",
        inline=False
    )
    
    if bank['balance'] > IRS_LIMIT:
        embed.add_field(
            name="⚠️ IRS Warning",
            value=f"Balance exceeds {format_money(IRS_LIMIT)} limit!",
            inline=False
        )
    
    await ctx.send(embed=embed)

# --- ADD MONEY ---
@bot.command()
async def add_money(ctx, *args):
    if not has_staff_role(ctx.author):
        embed = discord.Embed(
            title="❌ Access Denied",
            description="Only Economy Staff Team members can add money.",
            color=COLOR_ERROR
        )
        await ctx.send(embed=embed)
        return
    
    if len(args) < 3:
        embed = discord.Embed(
            title="📋 Usage",
            description="**Command:** `!add_money <Bank Name> <amount> <reason>`",
            color=COLOR_INFO
        )
        await ctx.send(embed=embed)
        return
    
    amount_index = -1
    for i, arg in enumerate(args):
        try:
            float(arg)
            amount_index = i
            break
        except ValueError:
            continue
    
    if amount_index == -1:
        embed = discord.Embed(
            title="❌ Invalid Amount",
            description="Please provide a valid numeric amount.",
            color=COLOR_ERROR
        )
        await ctx.send(embed=embed)
        return
    
    bank_name = " ".join(args[:amount_index])
    amount = args[amount_index]
    reason = " ".join(args[amount_index + 1:])
    
    if not bank_name or not reason:
        embed = discord.Embed(
            title="📋 Usage",
            description="**Command:** `!add_money <Bank Name> <amount> <reason>`",
            color=COLOR_INFO
        )
        await ctx.send(embed=embed)
        return
    
    try:
        amount_val = float(amount)
    except ValueError:
        embed = discord.Embed(
            title="❌ Invalid Amount",
            description="Amount must be a decimal number.",
            color=COLOR_ERROR
        )
        await ctx.send(embed=embed)
        return
    
    if amount_val <= 0:
        embed = discord.Embed(
            title="❌ Invalid Amount",
            description="Amount must be greater than 0.",
            color=COLOR_ERROR
        )
        await ctx.send(embed=embed)
        return
    
    bank = get_bank(bank_name)
    if not bank:
        embed = discord.Embed(
            title="❌ Bank Not Found",
            description="Please provide a valid bank name.",
            color=COLOR_ERROR
        )
        await ctx.send(embed=embed)
        return
    
    old_balance = bank["balance"]
    bank["balance"] = round(bank["balance"] + amount_val, 2)
    irs_applied, excess, penalty = apply_irs(bank)
    save_data()
    
    embed = discord.Embed(
        title="✅ Money Added",
        description=f"Successfully added funds to **{bank_name}**",
        color=COLOR_SUCCESS
    )
    embed.add_field(name="💵 Amount Added", value=format_money(amount_val), inline=True)
    embed.add_field(name="💰 New Balance", value=format_money(bank['balance']), inline=True)
    embed.add_field(name="📝 Reason", value=reason, inline=False)
    
    if irs_applied:
        embed.add_field(
            name="🚨 IRS Penalty Applied",
            value=f"Excess: {format_money(excess)}\nPenalty (75%): {format_money(penalty)}",
            inline=False
        )
        embed.color = COLOR_WARNING
    
    embed.set_footer(text=f"Transaction by {ctx.author.name}")
    await ctx.send(embed=embed)

# --- LIST GENERATORS ---
@bot.command()
async def list_generators(ctx):
    embed = discord.Embed(
        title="⚙️ Generator Marketplace",
        description="Available generator types and specifications",
        color=COLOR_INFO
    )
    
    for gtype, info in GENERATOR_TYPES.items():
        field_value = (
            f"{info['emoji']} **Price:** {format_money(info['price'])}\n"
            f"💵 **Weekly Income:** {format_money(info['income'])}\n"
            f"📊 **Max per Bank:** {info['max']}"
        )
        embed.add_field(
            name=f"{gtype.capitalize()}-Grade Generator",
            value=field_value,
            inline=True
        )
    
    embed.add_field(
        name="📌 Important Information",
        value=(
            f"• Maximum total generators: **{MAX_GENERATORS_TOTAL}**\n"
            f"• Generator tax: **{int(GENERATOR_TAX * 100)}%**\n"
            f"• Only staff can purchase generators"
        ),
        inline=False
    )
    
    await ctx.send(embed=embed)

# --- BUY GENERATOR ---
@bot.command()
async def buy_generator(ctx, *args):
    if not has_staff_role(ctx.author):
        embed = discord.Embed(
            title="❌ Access Denied",
            description="Only Economy Staff Team members can buy generators.",
            color=COLOR_ERROR
        )
        await ctx.send(embed=embed)
        return
    
    if len(args) < 2:
        embed = discord.Embed(
            title="📋 Usage",
            description="**Command:** `!buy_generator <Bank Name> <type> [amount]`",
            color=COLOR_INFO
        )
        await ctx.send(embed=embed)
        return
    
    amount = 1
    if args[-1].isdigit():
        amount = int(args[-1])
        gen_type = args[-2]
        bank_name = " ".join(args[:-2])
    else:
        gen_type = args[-1]
        bank_name = " ".join(args[:-1])
    
    bank = get_bank(bank_name)
    if not bank:
        embed = discord.Embed(
            title="❌ Bank Not Found",
            description="Please provide a valid bank name.",
            color=COLOR_ERROR
        )
        await ctx.send(embed=embed)
        return

    gen_type = gen_type.lower()
    if gen_type not in GENERATOR_TYPES:
        embed = discord.Embed(
            title="❌ Invalid Generator Type",
            description="Available types: **low**, **middle**, **high**, **top**",
            color=COLOR_ERROR
        )
        await ctx.send(embed=embed)
        return

    current_total = sum(economy["generators"][bank_name].values())
    if current_total + amount > MAX_GENERATORS_TOTAL:
        embed = discord.Embed(
            title="❌ Generator Limit Reached",
            description=f"Cannot exceed {MAX_GENERATORS_TOTAL} total generators.",
            color=COLOR_ERROR
        )
        await ctx.send(embed=embed)
        return
    
    if economy["generators"][bank_name][gen_type] + amount > GENERATOR_TYPES[gen_type]["max"]:
        embed = discord.Embed(
            title="❌ Type Limit Reached",
            description=f"Cannot exceed {GENERATOR_TYPES[gen_type]['max']} {gen_type} generators.",
            color=COLOR_ERROR
        )
        await ctx.send(embed=embed)
        return

    total_price = GENERATOR_TYPES[gen_type]["price"] * amount
    if bank["balance"] < total_price:
        embed = discord.Embed(
            title="❌ Insufficient Funds",
            description=f"Need {format_money(total_price)}, have {format_money(bank['balance'])}",
            color=COLOR_ERROR
        )
        await ctx.send(embed=embed)
        return

    bank["balance"] = round(bank["balance"] - total_price, 2)
    economy["generators"][bank_name][gen_type] += amount
    irs_applied, excess, penalty = apply_irs(bank)
    save_data()

    embed = discord.Embed(
        title="✅ Generator Purchase Complete",
        description=f"Successfully purchased for **{bank_name}**",
        color=COLOR_SUCCESS
    )
    
    gen_info = GENERATOR_TYPES[gen_type]
    embed.add_field(
        name=f"{gen_info['emoji']} Generator Details",
        value=f"**Type:** {gen_type.capitalize()}\n**Quantity:** {amount}\n**Total Cost:** {format_money(total_price)}",
        inline=False
    )
    embed.add_field(name="💰 New Balance", value=format_money(bank['balance']), inline=True)
    embed.add_field(
        name="⚙️ Total Generators", 
        value=f"{sum(economy['generators'][bank_name].values())}/{MAX_GENERATORS_TOTAL}",
        inline=True
    )
    
    if irs_applied:
        embed.add_field(
            name="🚨 IRS Penalty Applied",
            value=f"Excess: {format_money(excess)}\nPenalty: {format_money(penalty)}",
            inline=False
        )
        embed.color = COLOR_WARNING
    
    embed.set_footer(text=f"Purchased by {ctx.author.name}")
    await ctx.send(embed=embed)

# --- GENERATOR INCOME ---
@bot.command()
async def generator_income(ctx, *args):
    if not args:
        embed = discord.Embed(
            title="📋 Usage",
            description="**Command:** `!generator_income <Bank Name> [debug]`",
            color=COLOR_INFO
        )
        await ctx.send(embed=embed)
        return
    
    debug = "debug" in args
    bank_name = " ".join([arg for arg in args if arg != "debug"])
    
    bank = get_bank(bank_name)
    if not bank:
        embed = discord.Embed(
            title="❌ Bank Not Found",
            description="Please provide a valid bank name.",
            color=COLOR_ERROR
        )
        await ctx.send(embed=embed)
        return
    
    if not can_access_bank(ctx, bank_name):
        embed = discord.Embed(
            title="❌ Access Denied",
            description="You don't have permission to access this bank.",
            color=COLOR_ERROR
        )
        await ctx.send(embed=embed)
        return
    
    total_income = 0
    breakdown = []
    
    for gtype, info in GENERATOR_TYPES.items():
        count = economy["generators"][bank_name][gtype]
        income = count * info["income"]
        total_income += income
        if debug and count > 0:
            breakdown.append(
                f"{info['emoji']} **{gtype.capitalize()}**: {count} × {format_money(info['income'])} = {format_money(income)}"
            )
    
    taxed_income = round(total_income * (1 - GENERATOR_TAX), 2)
    old_balance = bank["balance"]
    bank["balance"] = round(bank["balance"] + taxed_income, 2)
    irs_applied, excess, penalty = apply_irs(bank)
    save_data()
    
    embed = discord.Embed(
        title=f"💰 Generator Income Collected",
        description=f"**{bank_name}**",
        color=COLOR_MONEY
    )
    
    if debug and breakdown:
        embed.add_field(
            name="📊 Income Breakdown",
            value="\n".join(breakdown) + f"\n\n**Subtotal:** {format_money(total_income)}",
            inline=False
        )
    
    embed.add_field(
        name="💵 Gross Income",
        value=format_money(total_income),
        inline=True
    )
    embed.add_field(
        name=f"🏛️ Tax ({int(GENERATOR_TAX * 100)}%)",
        value=format_money(total_income * GENERATOR_TAX),
        inline=True
    )
    embed.add_field(
        name="✅ Net Income",
        value=format_money(taxed_income),
        inline=True
    )
    embed.add_field(
        name="💼 New Balance",
        value=format_money(bank['balance']),
        inline=False
    )
    
    if irs_applied:
        embed.add_field(
            name="🚨 IRS Penalty Applied",
            value=f"Excess over {format_money(IRS_LIMIT)}: {format_money(excess)}\nPenalty (75%): {format_money(penalty)}",
            inline=False
        )
        embed.color = COLOR_WARNING
    
    embed.set_footer(text=f"Collected by {ctx.author.name}")
    await ctx.send(embed=embed)

# --- CHECK IRS ---
@bot.command()
async def check_irs(ctx, *, bank_name: str = None):
    if not bank_name:
        embed = discord.Embed(
            title="📋 Usage",
            description="**Command:** `!check_irs <Bank Name>`",
            color=COLOR_INFO
        )
        await ctx.send(embed=embed)
        return
    
    bank = get_bank(bank_name)
    if not bank:
        embed = discord.Embed(
            title="❌ Bank Not Found",
            description="Please provide a valid bank name.",
            color=COLOR_ERROR
        )
        await ctx.send(embed=embed)
        return
    
    if not can_access_bank(ctx, bank_name):
        embed = discord.Embed(
            title="❌ Access Denied",
            description="You don't have permission to access this bank.",
            color=COLOR_ERROR
        )
        await ctx.send(embed=embed)
        return
    
    old_balance = bank["balance"]
    irs_applied, excess, penalty = apply_irs(bank)
    
    if irs_applied:
        save_data()
        embed = discord.Embed(
            title="🚨 IRS Penalty Applied",
            description=f"**{bank_name}** exceeded the IRS limit",
            color=COLOR_WARNING
        )
        embed.add_field(name="💼 Previous Balance", value=format_money(old_balance), inline=True)
        embed.add_field(name="⚖️ IRS Limit", value=format_money(IRS_LIMIT), inline=True)
        embed.add_field(name="📈 Excess Amount", value=format_money(excess), inline=True)
        embed.add_field(name="💸 Penalty (75%)", value=format_money(penalty), inline=True)
        embed.add_field(name="💰 New Balance", value=format_money(bank['balance']), inline=True)
    else:
        percentage = (bank['balance'] / IRS_LIMIT) * 100
        embed = discord.Embed(
            title="✅ IRS Status: Compliant",
            description=f"**{bank_name}** is under the IRS limit",
            color=COLOR_SUCCESS
        )
        embed.add_field(name="💰 Current Balance", value=format_money(bank['balance']), inline=True)
        embed.add_field(name="⚖️ IRS Limit", value=format_money(IRS_LIMIT), inline=True)
        embed.add_field(
            name="📊 Utilization",
            value=f"{percentage:.1f}%",
            inline=True
        )
    
    embed.set_footer(text=f"Checked by {ctx.author.name}")
    await ctx.send(embed=embed)

# --- WEEKLY GENERATOR INCOME TASK ---
async def weekly_generator_income(hour=18, minute=0):
    await bot.wait_until_ready()
    while True:
        now = datetime.now()
        days_until_monday = (7 - now.weekday()) % 7
        if days_until_monday == 0:
            next_monday = now
            if now.hour > hour or (now.hour == hour and now.minute >= minute):
                next_monday = now + timedelta(days=7)
        else:
            next_monday = now + timedelta(days=days_until_monday)
        
        target = next_monday.replace(hour=hour, minute=minute, second=0, microsecond=0)
        wait_seconds = (target - now).total_seconds()
        if wait_seconds < 0:
            wait_seconds += 7 * 24 * 3600
        
        print(f"Next generator income at: {target}")
        await asyncio.sleep(wait_seconds)
        
        # Apply generator income to all banks
        for bank_name, bank in economy["banks"].items():
            total_income = sum(
                economy["generators"][bank_name][gtype] * info["income"]
                for gtype, info in GENERATOR_TYPES.items()
            )
            taxed_income = round(total_income * (1 - GENERATOR_TAX), 2)
            old_balance = bank["balance"]
            bank["balance"] = round(bank["balance"] + taxed_income, 2)
            irs_applied, excess, penalty = apply_irs(bank)
            save_data()
            
            if STAFF_CHANNEL_ID:
                channel = bot.get_channel(STAFF_CHANNEL_ID)
                if channel:
                    embed = discord.Embed(
                        title="📅 Weekly Generator Income",
                        description=f"**{bank_name}** collected weekly income!",
                        color=COLOR_MONEY
                    )
                    embed.add_field(
                        name="💵 Income Collected",
                        value=format_money(taxed_income),
                        inline=True
                    )
                    embed.add_field(
                        name="💰 New Balance",
                        value=format_money(bank['balance']),
                        inline=True
                    )
                    
                    if irs_applied:
                        embed.add_field(
                            name="🚨 IRS Penalty",
                            value=f"Excess: {format_money(excess)}\nPenalty: {format_money(penalty)}",
                            inline=False
                        )
                        embed.color = COLOR_WARNING
                    
                    embed.set_footer(text=f"Auto-collected on {datetime.now().strftime('%Y-%m-%d at %H:%M')}")
                    await channel.send(embed=embed)
        
        print("✅ Weekly generator income applied!")

# --- RUN BOT ---
bot.run(os.getenv("TOKEN"))