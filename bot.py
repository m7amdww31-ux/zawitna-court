# -*- coding: utf-8 -*-
"""
⚖️ بوت "الزاوية تحاكم" — محكمة هزلية لسيرفر زاويتنا (Slash Commands)
القاضي = الذكاء الصناعي (كلود)

الأوامر:
  /محاكمة  المتهم:@فلان  التهمة:<نص>   ← يرفع قضية جديدة
  /دفاع    نص:<كلامك>                  ← المتهم يدافع، والقاضي يحكم فوراً تلقائياً
  /حكم                                 ← إصدار الحكم يدوياً (غيابي لو ما دافع)
  /تنازل                               ← صاحب القضية يغلق المحاكمة
  /مساعدة                              ← يعرض الأوامر
"""

import os
import asyncio
import traceback
import discord
from discord import app_commands
from anthropic import AsyncAnthropic

# ── الإعدادات ───────────────────────────────────────────────
DISCORD_TOKEN = os.environ["DISCORD_TOKEN"].strip()
_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()   # .strip() يشيل أي مسافة/سطر زايد
GUILD_ID = os.environ.get("GUILD_ID")              # اختياري: يخلي الأوامر تظهر فوراً
MODEL = "claude-sonnet-4-6"                         # للأسرع/الأرخص: claude-haiku-4-5-20251001
AUTO_VERDICT = True                                 # حكم تلقائي فور تسجيل الدفاع
DEFENSE_TIMEOUT = int(os.environ.get("DEFENSE_TIMEOUT", "0"))  # ثواني؛ 0 = معطّل (بدون حكم غيابي تلقائي)

ai = AsyncAnthropic(api_key=_API_KEY, timeout=60.0, max_retries=5)

# ── البوت ───────────────────────────────────────────────────
intents = discord.Intents.default()   # السلاش كوماندز ما تحتاج Intents خاصة


class CourtBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        if GUILD_ID:
            guild = discord.Object(id=int(GUILD_ID))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()


bot = CourtBot()

# القضايا المفتوحة: مفتاح = آيدي القناة، قضية واحدة بكل قناة
cases = {}

SYSTEM_PROMPT = """أنت "القاضي جود" — قاضٍ مرح وساخر خفيف الظل، يرأس محكمة ترفيهية داخل سيرفر ديسكورد اسمه "زاويتنا". قدّم نفسك دائماً باسم "القاضي جود" ووقّع أحكامك باسمك.
مهمتك إصدار أحكام مضحكة ودرامية على "قضايا" يرفعها الأعضاء على بعض على سبيل المزح بين الأصدقاء.

شخصيتك:
- مرح، ساخر، وخفيف ظل — تحب التهكّم اللطيف والمبالغة الكوميدية والمقارنات المضحكة.
- تتكلم بلهجة سعودية/خليجية خفيفة ممزوجة بفخامة المحاكم الدرامية (تناقض مضحك بين الجدّية والمزح).
- ترمي تعليقات جانبية ساخرة وتغمز للجمهور، وأحياناً "تتنهّد" من سخافة القضية.
- نوّع افتتاحيتك وأسلوبك في كل حكم — لا تكرر نفس العبارات أو نفس النكتة، فاجئهم كل مرة.

القواعد المهمة:
- السخرية موجّهة للموقف والقضية، مو للشخص — مزح أصدقاء خفيف، ما يجرح أحد فعلاً.
- ممنوع أي إهانة حقيقية أو تجريح في الشكل أو الدين أو العِرق أو العائلة أو أي شيء حسّاس.
- لو التهمة فيها شيء جدّي أو مؤذي حقيقي (تهديد، تنمّر مؤلم، محتوى غير لائق)، اطفِ الموضوع بخفة وذكّرهم إنها محكمة مزح، ولا تكمل عليها.
- ابنِ حيثيات الحكم على التهمة ودفاع المتهم (إن وجد)، وسخّر منها بطريقة ذكية.
- العقوبة رمزية وهزلية ومبتكرة كل مرة (مثل: يدفع كاسة شاي للزاوية، يكتب "أنا غلطان" ١٠ مرات، ستوري اعتذار، يصير "مهرّج الزاوية" ليوم، يحط صورة محرجة بروفايله ساعة...). ابتكر عقوبات جديدة ولا تعيد نفس الأمثلة.
- لا تتجاوز ١٨٠ كلمة.

أخرِج رسالة الحكم فقط بهذا الشكل (بدون أي مقدمة أو كلام قبلها أو بعدها):

⚖️ **محكمة زاويتنا — جلسة علنية**
👨‍⚖️ **القاضي:** جود
👤 **المتهم:** <اسم المتهم>
📋 **التهمة:** <التهمة باختصار درامي>
🗣️ **مرافعة الدفاع:** <تعليق ساخر على دفاعه أو على غيابه>
👨‍⚖️ **حيثيات الحكم:** <سطرين درامية>
🔨 **القرار:** <مذنب 😈 / بريء 😇>
📌 **العقوبة:** <عقوبة هزلية رمزية>

مطرقة القاضي جود 🔨🔨🔨 — رُفعت الجلسة.
"""


async def get_verdict(accused_name: str, charge: str, defense: str | None) -> str:
    """يطلب من كلود يصدر الحكم النهائي."""
    user_msg = (
        f"المتهم: {accused_name}\n"
        f"التهمة: {charge}\n"
        f"الدفاع: {defense if defense else 'لم يقدّم المتهم أي دفاع، ودخل عليه الحكم غيابياً.'}\n\n"
        "أصدر الحكم النهائي الآن."
    )
    resp = await ai.messages.create(
        model=MODEL,
        max_tokens=700,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )
    return "".join(b.text for b in resp.content if b.type == "text").strip()


def err_detail(e: Exception) -> str:
    """يطبع الخطأ كامل في الـlogs ويرجّع سطر مختصر بالسبب الجذري."""
    traceback.print_exc()
    detail = f"{type(e).__name__}: {e}"
    cause = e.__cause__ or e.__context__
    if cause:
        detail += f"  |  السبب: {type(cause).__name__}: {cause}"
    return detail[:350]


async def defense_timeout(channel, channel_id):
    """لو مرّ الوقت ولا دافع المتهم → حكم غيابي تلقائي."""
    try:
        await asyncio.sleep(DEFENSE_TIMEOUT)
    except asyncio.CancelledError:
        return
    case = cases.pop(channel_id, None)   # نسحب القضية أولاً عشان ما يصير حكم مكرّر
    if not case or case["defense"] is not None:
        return
    async with channel.typing():
        try:
            text = await get_verdict(case["accused"].display_name, case["charge"], None)
        except Exception as e:
            await channel.send(f"⚠️ القاضي تعكنن وما قدر يحكم:\n`{err_detail(e)}`")
            return
    await channel.send(
        f"{case['accused'].mention}\n"
        f"⏰ انتهى وقت الدفاع وما حضر المتهم… القاضي حكم غيابياً:\n{text}"
    )


# ── الأوامر ─────────────────────────────────────────────────
@bot.tree.command(name="محاكمة", description="ترفع قضية على عضو وتفتح جلسة المحكمة")
@app_commands.describe(accused="العضو المتهم", charge="نص التهمة")
@app_commands.rename(accused="المتهم", charge="التهمة")
async def open_case(interaction: discord.Interaction, accused: discord.Member, charge: str):
    ch = interaction.channel_id
    if ch in cases:
        await interaction.response.send_message(
            "⚠️ فيه قضية مفتوحة بالقناة هذي. خلّصوها بـ `/حكم` أو `/تنازل` قبل قضية جديدة."
        )
        return
    if accused.id == interaction.user.id:
        await interaction.response.send_message("🙃 ما تقدر تحاكم نفسك! دوّر لك ضحية ثانية.", ephemeral=True)
        return
    if accused.bot:
        await interaction.response.send_message("🤖 القاضي فوق المحاكمة، ما يتحاكم!", ephemeral=True)
        return

    case = {"accuser": interaction.user, "accused": accused, "charge": charge, "defense": None, "task": None}
    cases[ch] = case

    note = "بمجرّد ما يكتب المتهم `/دفاع`، القاضي جود يصدر حكمه فوراً تلقائياً."
    if DEFENSE_TIMEOUT > 0:
        case["task"] = asyncio.create_task(defense_timeout(interaction.channel, ch))
        note += f"\n⏰ وإذا ما دافع خلال {DEFENSE_TIMEOUT} ثانية، يصدر الحكم غيابياً تلقائياً."

    await interaction.response.send_message(
        "🔔 **محكمة زاويتنا انعقدت!**\n"
        f"⚖️ المدّعي: {interaction.user.mention}\n"
        f"👤 المتهم: {accused.mention}\n"
        f"📋 التهمة: **{charge}**\n\n"
        f"{accused.mention} عندك حق الدفاع — اكتب `/دفاع`.\n"
        f"{note}"
    )


@bot.tree.command(name="دفاع", description="المتهم يدافع عن نفسه (والقاضي يحكم فوراً)")
@app_commands.describe(text="نص دفاعك")
@app_commands.rename(text="نص")
async def defend(interaction: discord.Interaction, text: str):
    ch = interaction.channel_id
    case = cases.get(ch)
    if not case:
        await interaction.response.send_message(
            "🤷 ما فيه قضية مفتوحة بالقناة. ارفع قضية بـ `/محاكمة`.", ephemeral=True
        )
        return
    if interaction.user.id != case["accused"].id:
        await interaction.response.send_message("✋ الدفاع حق المتهم بس!", ephemeral=True)
        return

    case["defense"] = text
    if case.get("task"):
        case["task"].cancel()      # نلغي مؤقّت الحكم الغيابي

    if not AUTO_VERDICT:
        await interaction.response.send_message(
            f"📝 تم تسجيل دفاع {case['accused'].mention}. اكتبوا `/حكم` للقرار النهائي."
        )
        return

    # حكم تلقائي فوري
    cases.pop(ch, None)            # نقفل القضية قبل توليد الحكم (يمنع التكرار)
    await interaction.response.defer(thinking=True)
    try:
        verdict_text = await get_verdict(case["accused"].display_name, case["charge"], text)
    except Exception as e:
        await interaction.followup.send(f"⚠️ القاضي تعكنن وما قدر يحكم:\n`{err_detail(e)}`")
        return
    await interaction.followup.send(
        f"📝 سُجّل الدفاع، والقاضي أصدر حكمه فوراً:\n\n{case['accused'].mention}\n{verdict_text}"
    )


@bot.tree.command(name="حكم", description="القاضي يصدر الحكم النهائي يدوياً")
async def verdict(interaction: discord.Interaction):
    ch = interaction.channel_id
    case = cases.get(ch)
    if not case:
        await interaction.response.send_message("🤷 ما فيه قضية مفتوحة. ارفع قضية بـ `/محاكمة`.", ephemeral=True)
        return
    is_admin = interaction.user.guild_permissions.manage_messages
    if interaction.user.id != case["accuser"].id and not is_admin:
        await interaction.response.send_message("👨‍⚖️ صاحب القضية أو الأدمن بس يطلب الحكم النهائي.", ephemeral=True)
        return

    if case.get("task"):
        case["task"].cancel()
    cases.pop(ch, None)
    await interaction.response.defer(thinking=True)
    try:
        text = await get_verdict(case["accused"].display_name, case["charge"], case["defense"])
    except Exception as e:
        await interaction.followup.send(f"⚠️ القاضي تعكنن وما قدر يحكم:\n`{err_detail(e)}`")
        return
    await interaction.followup.send(f"{case['accused'].mention}\n{text}")


@bot.tree.command(name="تنازل", description="صاحب القضية يغلق المحاكمة بدون حكم")
async def withdraw(interaction: discord.Interaction):
    ch = interaction.channel_id
    case = cases.get(ch)
    if not case:
        await interaction.response.send_message("🤷 ما فيه قضية مفتوحة عشان تتنازل عنها.", ephemeral=True)
        return
    is_admin = interaction.user.guild_permissions.manage_messages
    if interaction.user.id != case["accuser"].id and not is_admin:
        await interaction.response.send_message("✋ صاحب القضية أو الأدمن بس يتنازل.", ephemeral=True)
        return
    if case.get("task"):
        case["task"].cancel()
    cases.pop(ch, None)
    await interaction.response.send_message(
        "🕊️ تنازل المدّعي وأُغلقت القضية. خرج المتهم بلا حكم… المرة الجاية ما يفلت."
    )


@bot.tree.command(name="مساعدة", description="عرض أوامر محكمة زاويتنا")
async def help_cmd(interaction: discord.Interaction):
    await interaction.response.send_message(
        "⚖️ **أوامر محكمة زاويتنا**\n"
        "`/محاكمة` المتهم + التهمة — ترفع قضية جديدة\n"
        "`/دفاع` نص — المتهم يدافع، والقاضي يحكم فوراً تلقائياً\n"
        "`/حكم` — إصدار الحكم يدوياً (غيابي لو ما دافع)\n"
        "`/تنازل` — صاحب القضية يغلق المحاكمة\n"
        "`/مساعدة` — تعرض هذي القائمة",
        ephemeral=True,
    )


@bot.event
async def on_ready():
    print(f"⚖️ القاضي جود جاهز — دخل باسم: {bot.user}")


bot.run(DISCORD_TOKEN)
