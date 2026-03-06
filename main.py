import discord
from discord import app_commands
import os
from flask import Flask
from threading import Thread
import datetime

# --- サーバー維持用 ---
app = Flask('')
@app.route('/')
def home(): 
    return f"交流戦ボット稼働中！ {datetime.datetime.now()}"

def run(): 
    app.run(host='0.0.0.0', port=10000)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# --- Bot本体 ---
class MyClient(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.all())
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()
        print("✅ 交流戦コマンド（/日程）を同期しました")

client = MyClient()

game_data = {} 
detail_data = {} 

# --- 入力フォーム ---
class RegistrationModal(discord.ui.Modal, title='【参加登録】'):
    def __init__(self, message_id, start_day, end_day):
        super().__init__()
        self.message_id = message_id
        self.start_day = start_day
        self.end_day = end_day
        self.days_input = discord.ui.TextInput(
            label=f'参加できる日（{start_day}〜{end_day}日）', 
            placeholder='例: 1, 3, 5', 
            required=False
        )
        self.role_input = discord.ui.TextInput(
            label='希望する役職（AT / GT / DF / ANY）', 
            placeholder='例: AT', 
            min_length=2, 
            max_length=3, 
            required=True
        )
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
        await interaction.response.send_message("登録したで！", ephemeral=True)

# --- 詳細選択メニュー ---
class DetailSelect(discord.ui.Select):
    def __init__(self, message_id, start, end):
        options = [discord.SelectOption(label=f"{d}日の詳細を見る", value=str(d)) for d in range(start, end + 1)]
        super().__init__(placeholder="👀 各日程の詳細を確認する", options=options, custom_id="detail_select")
        self.message_id = message_id

    async def callback(self, interaction: discord.Interaction):
        day = self.values[0]
        details = detail_data.get(self.message_id, {}).get(day, "まだ詳細は決まってへんで！")
        await interaction.response.send_message(f"📌 **{day}日の詳細情報**\n{details}", ephemeral=True)

class RegButtonView(discord.ui.View):
    def __init__(self, message_id, start, end):
        super().__init__(timeout=None)
        self.message_id = message_id
        self.start = start
        self.end = end
        self.add_item(DetailSelect(message_id, start, end))

    @discord.ui.button(label="📝 参加・役職を登録する", style=discord.ButtonStyle.success, custom_id="reg_btn")
    async def register(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RegistrationModal(self.message_id, self.start, self.end))

async def update_embed(interaction, message_id, start, end):
    embed = discord.Embed(title="⚔️ 交流戦 日程調整パネル ⚔️", description="参加できる日に名前を載せてな！", color=0x00ff00)
    data = game_data.get(message_id, {})
    for d in range(start, end + 1):
        users = data.get(str(d), {})
        count = len(users)
        val = " / ".join([f"{info['name']} [{info['role']}]" for info in users.values()]) if count > 0 else "┗ (募集中)"
        embed.add_field(name=f"📅 {d}日 【現在：{count}名】", value=val, inline=False)
    
    message = await interaction.channel.fetch_message(message_id)
    await message.edit(embed=embed)

# --- 日本語コマンドの設定 ---

@client.tree.command(name="日程", description="交流戦の点呼パネルを作成します")
async def tenko(interaction: discord.Interaction, 開始日: int, 終了日: int):
    embed = discord.Embed(title="⚔️ 交流戦 日程調整パネル ⚔️", description="パネルを作成中...", color=0x00ff00)
    await interaction.response.send_message("パネルを設置するで！", ephemeral=True)
    msg = await interaction.channel.send(embed=embed)
    game_data[msg.id] = {str(d): {} for d in range(開始日, 終了日 + 1)}
    view = RegButtonView(msg.id, 開始日, 終了日)
    await update_embed(interaction, msg.id, 開始日, 終了日)
    await msg.edit(view=view)

@client.tree.command(name="詳細設定", description="各日程の詳細を設定します")
async def set_detail(interaction: discord.Interaction, パネルのid: str, 日にち: int, 内容: str):
    try:
        m_id = int(パネルのid)
        if m_id not in detail_data: detail_data[m_id] = {}
        detail_data[m_id][str(日にち)] = 内容
        await interaction.response.send_message(f"✅ {日にち}日の詳細を登録したで！", ephemeral=True)
    except:
        await interaction.response.send_message("エラー：パネルのIDを正しく入力してな！", ephemeral=True)

if __name__ == "__main__":
    keep_alive()
    TOKEN = os.getenv('DISCORD_TOKEN')
    if TOKEN:
        client.run(TOKEN)
