import discord
from discord import app_commands
import os
from flask import Flask
from threading import Thread
import datetime

# --- サーバー維持用 (Renderの寝落ち防止) ---
app = Flask('')

@app.route('/')
def home(): 
    return f"Koryusen Bot is active! {datetime.datetime.now()}"

def run(): 
    app.run(host='0.0.0.0', port=10000)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# --- Bot本体の設定 ---
class MyClient(discord.Client):
    def __init__(self):
        # 予約BOTと同じく Intents.all() に設定
        super().__init__(intents=discord.Intents.all())
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        # 起動時にコマンドを同期（予約BOTの sync と同じ役割）
        await self.tree.sync()
        print("✅ 交流戦コマンドを同期しました")

client = MyClient()

# データ保持用（※再起動でリセットされる仕様やで！）
game_data = {} 
detail_data = {} 

# --- 参加登録用ポップアップ ---
class RegistrationModal(discord.ui.Modal, title='交流戦 参加・役職登録'):
    def __init__(self, message_id, start_day, end_day):
        super().__init__()
        self.message_id = message_id
        self.start_day = start_day
        self.end_day = end_day
        self.days_input = discord.ui.TextInput(label=f'参加日({start_day}〜{end_day})を半角コンマで', placeholder='例: 1,3,5', required=False)
        self.role_input = discord.ui.TextInput(label='役職(AT/GT/DF/ANY)', placeholder='AT', min_length=2, max_length=3, required=True)
        self.add_item(self.days_input)
        self.add_item(self.role_input)

    async def on_submit(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        user_name = interaction.user.display_name
        selected_days = [d.strip() for d in self.days_input.value.split(',') if d.strip().isdigit()]
        role = self.role_input.value.upper()
        if role not in ["AT", "GT", "DF", "ANY"]:
            await interaction.response.send_message("役職は AT, GT, DF, ANY で入力してな！", ephemeral=True)
            return
        if self.message_id not in game_data:
            game_data[self.message_id] = {str(d): {} for d in range(self.start_day, self.end_day + 1)}
        for d in game_data[self.message_id]:
            game_data[self.message_id][d].pop(user_id, None)
        for d in selected_days:
            if d in game_data[self.message_id]:
                game_data[self.message_id][d][user_id] = {"name": user_name, "role": role}
        await update_embed(interaction, self.message_id, self.start_day, self.end_day)
        await interaction.response.send_message("登録完了！", ephemeral=True)

# --- 詳細確認メニュー ---
class DetailSelect(discord.ui.Select):
    def __init__(self, message_id, start, end):
        options = [discord.SelectOption(label=f"{d}日の詳細", value=str(d)) for d in range(start, end + 1)]
        super().__init__(placeholder="【詳細を見たい日を選択】", options=options, custom_id="detail_select")
        self.message_id = message_id

    async def callback(self, interaction: discord.Interaction):
        day = self.values[0]
        details = detail_data.get(self.message_id, {}).get(day, "まだ詳細は決まってへんで！")
        await interaction.response.send_message(f"📌 **{day}日の詳細**\n{details}", ephemeral=True)

# --- 共通View ---
class RegButtonView(discord.ui.View):
    def __init__(self, message_id, start, end):
        super().__init__(timeout=None)
        self.message_id = message_id
        self.start = start
        self.end = end
        self.add_item(DetailSelect(message_id, start, end))

    @discord.ui.button(label="📝 参加・役職を登録", style=discord.ButtonStyle.primary, custom_id="reg_btn")
    async def register(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RegistrationModal(self.message_id, self.start, self.end))

# --- 表示更新 ---
async def update_embed(interaction, message_id, start, end):
    embed = discord.Embed(title="⚔️ 交流戦 日程調整パネル ⚔️", color=0x00ff00)
    data = game_data.get(message_id, {})
    for d in range(start, end + 1):
        users = data.get(str(d), {})
        count = len(users)
        val = " / ".join([f"{info['name']} [{info['role']}]" for info in users.values()]) if count > 0 else "┗ (未定)"
        embed.add_field(name=f"📅 {d}日 【参加：{count}名】", value=val, inline=False)
    message = await interaction.channel.fetch_message(message_id)
    await message.edit(embed=embed)

@client.tree.command(name="koryusen_tenko", description="交流戦の点呼パネルを作成します")
async def koryusen_tenko(interaction: discord.Interaction, start: int, end: int):
    embed = discord.Embed(title="⚔️ 交流戦 日程調整パネル ⚔️", description="作成中...", color=0x00ff00)
    await interaction.response.send_message("パネルを作成中...", ephemeral=True)
    msg = await interaction.channel.send(embed=embed)
    game_data[msg.id] = {str(d): {} for d in range(start, end + 1)}
    view = RegButtonView(msg.id, start, end)
    await update_embed(interaction, msg.id, start, end)
    await msg.edit(view=view)

@client.tree.command(name="set_detail", description="詳細内容を設定します")
async def set_detail(interaction: discord.Interaction, message_id: str, day: int, content: str):
    try:
        m_id = int(message_id)
        if m_id not in detail_data: detail_data[m_id] = {}
        detail_data[m_id][str(day)] = content
        await interaction.response.send_message(f"✅ {day}日の詳細を登録したで！", ephemeral=True)
    except:
        await interaction.response.send_message("エラー：正しいメッセージIDを入力してな！", ephemeral=True)

# --- 実行 ---
if __name__ == "__main__":
    keep_alive() # 寝落ち防止起動
    TOKEN = os.getenv('DISCORD_TOKEN')
    if TOKEN:
        client.run(TOKEN)
