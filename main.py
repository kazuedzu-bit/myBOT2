import discord
from discord import app_commands
import os

# --- 設定エリア ---
TOKEN = os.getenv("DISCORD_TOKEN")

class MyClient(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()

client = MyClient()

# データの一時保持（Renderの再起動まで維持）
game_data = {} # {message_id: {day: {user_id: {"name": str, "role": str}}}}
detail_data = {} # {message_id: {day: str}}

# --- 参加登録用の入力画面（ポップアップ） ---
class RegistrationModal(discord.ui.Modal, title='交流戦 参加・役職登録'):
    def __init__(self, message_id, start_day, end_day):
        super().__init__()
        self.message_id = message_id
        self.start_day = start_day
        self.end_day = end_day
        
        self.days_input = discord.ui.TextInput(
            label=f'参加日({start_day}〜{end_day})を数字とコンマで',
            placeholder='例: 1,3,5 (不参加なら空欄)',
            required=False
        )
        self.add_item(self.days_input)

        self.role_input = discord.ui.TextInput(
            label='役職(AT / GT / DF / ANY)',
            placeholder='例: AT',
            min_length=2,
            max_length=3,
            required=True
        )
        self.add_item(self.role_input)

    async def on_submit(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        user_name = interaction.user.display_name
        # コンマ区切りの数字をリスト化
        selected_days = [d.strip() for d in self.days_input.value.split(',') if d.strip().isdigit()]
        role = self.role_input.value.upper()

        if role not in ["AT", "GT", "DF", "ANY"]:
            await interaction.response.send_message("役職は AT, GT, DF, ANY のどれかで入力してな！", ephemeral=True)
            return

        # データの初期化と更新
        if self.message_id not in game_data:
            game_data[self.message_id] = {str(d): {} for d in range(self.start_day, self.end_day + 1)}
        
        # 既存のその人の登録を全日削除（上書き用）
        for d in game_data[self.message_id]:
            game_data[self.message_id][d].pop(user_id, None)

        # 選択された日に名前を追加
        for d in selected_days:
            if d in game_data[self.message_id]:
                game_data[self.message_id][d][user_id] = {"name": user_name, "role": role}

        await update_embed(interaction, self.message_id, self.start_day, self.end_day)
        await interaction.response.send_message("登録完了！表を更新したで。", ephemeral=True)

# --- 詳細確認用のセレクトメニュー ---
class DetailSelect(discord.ui.Select):
    def __init__(self, message_id, start, end):
        options = [discord.SelectOption(label=f"{d}日の詳細を見る", value=str(d)) for d in range(start, end + 1)]
        super().__init__(placeholder="【詳細を確認したい日を選択】", options=options, custom_id="detail_select")
        self.message_id = message_id

    async def callback(self, interaction: discord.Interaction):
        day = self.values[0]
        details = detail_data.get(self.message_id, {}).get(day, "まだ詳細は決まってへんで！")
        await interaction.response.send_message(f"📌 **{day}日の交流戦詳細**\n{details}", ephemeral=True)

# --- ボタンとメニューをまとめるView ---
class RegButtonView(discord.ui.View):
    def __init__(self, message_id, start, end):
        super().__init__(timeout=None)
        self.message_id = message_id
        self.start = start
        self.end = end
        # 詳細選択メニューを追加
        self.add_item(DetailSelect(message_id, start, end))

    @discord.ui.button(label="📝 参加・役職を登録", style=discord.ButtonStyle.primary, custom_id="reg_btn")
    async def register(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RegistrationModal(self.message_id, self.start, self.end))

# --- 表の更新処理 ---
async def update_embed(interaction, message_id, start, end):
    embed = discord.Embed(title="⚔️ 交流戦 日程調整パネル ⚔️", color=0x00ff00)
    embed.description = "下のボタンで「参加登録」、メニューで「内容確認」ができるで！"

    data = game_data[message_id]
    for d in range(start, end + 1):
        users = data.get(str(d), {})
        count = len(users)
        
        if count > 0:
            # 横並びで名前と役職を表示
            user_list = " / ".join([f"{info['name']} [{info['role']}]" for info in users.values()])
            val = f"┣ {user_list}"
        else:
            val = "┗ (未定)"
        
        embed.add_field(name=f"📅 {d}日 【参加：{count}名】", value=val, inline=False)

    message = await interaction.channel.fetch_message(message_id)
    await message.edit(embed=embed)

# --- コマンド：パネル作成 ---
@client.tree.command(name="koryusen_tenko", description="交流戦の点呼パネルを作成します")
async def koryusen_tenko(interaction: discord.Interaction, start: int, end: int):
    if start > end:
        await interaction.response.send_message("開始日は終了日より前にしてな！", ephemeral=True)
        return

    embed = discord.Embed(title="⚔️ 交流戦 日程調整パネル ⚔️", color=0x00ff00)
    embed.description = "作成中..."
    
    await interaction.response.send_message("パネルを生成したで！", ephemeral=True)
    msg = await interaction.channel.send(embed=embed)
    
    game_data[msg.id] = {str(d): {} for d in range(start, end + 1)}
    
    view = RegButtonView(msg.id, start, end)
    await update_embed(interaction, msg.id, start, end)
    await msg.edit(view=view)

# --- コマンド：詳細設定 ---
@client.tree.command(name="set_detail", description="特定の日付の詳細内容を設定します（管理者用）")
async def set_detail(interaction: discord.Interaction, message_id: str, day: int, content: str):
    try:
        m_id = int(message_id)
    except:
        await interaction.response.send_message("正しいメッセージIDを入れてな！", ephemeral=True)
        return

    if m_id not in detail_data:
        detail_data[m_id] = {}
    
    detail_data[m_id][str(day)] = content
    await interaction.response.send_message(f"✅ {day}日の詳細を登録したで！\n内容：{content}", ephemeral=True)

client.run(TOKEN)
