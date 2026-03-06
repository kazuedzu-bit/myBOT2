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
        print("✅ コマンド同期完了")

client = MyClient()
game_data = {} 

# --- 役職選択ボタン ---
class RoleButtonView(discord.ui.View):
    def __init__(self, message_id, start, end, selected_days):
        super().__init__(timeout=60)
        self.message_id = message_id
        self.start = start
        self.end = end
        self.selected_days = selected_days

    async def register(self, interaction: discord.Interaction, role: str):
        user_id = interaction.user.id
        user_name = interaction.user.display_name
        
        if self.message_id not in game_data:
            game_data[self.message_id] = {str(d): {} for d in range(self.start, self.end + 1)}

        # 一旦全日程から削除して、選んだ日にだけ追加（上書き）
        for d in game_data[self.message_id]:
            game_data[self.message_id][d].pop(user_id, None)

        for d in self.selected_days:
            if d in game_data[self.message_id]:
                game_data[self.message_id][d][user_id] = {"name": user_name, "role": role}

        await update_embed(interaction, self.message_id, self.start, self.end)
        await interaction.response.edit_message(content=f"✅ {', '.join(self.selected_days)}日に【{role}】で登録したで！", view=None)

    @discord.ui.button(label="AT", style=discord.ButtonStyle.danger)
    async def at(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.register(interaction, "AT")

    @discord.ui.button(label="GT", style=discord.ButtonStyle.primary)
    async def gt(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.register(interaction, "GT")

    @discord.ui.button(label="DF", style=discord.ButtonStyle.success)
    async def df(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.register(interaction, "DF")

    @discord.ui.button(label="ANY", style=discord.ButtonStyle.secondary)
    async def any(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.register(interaction, "ANY")

# --- 日程選択セレクトメニュー ---
class DaySelect(discord.ui.Select):
    def __init__(self, message_id, start, end):
        options = [discord.SelectOption(label=f"{d}日", value=str(d)) for d in range(start, end + 1)]
        super().__init__(
            placeholder="📅 参加できる日をすべて選んでな！（複数OK）",
            min_values=1,
            max_values=len(options),
            options=options,
            custom_id="day_select"
        )
        self.message_id = message_id
        self.start = start
        self.end = end

    async def callback(self, interaction: discord.Interaction):
        # 役職選択ボタンを出す
        view = RoleButtonView(self.message_id, self.start, self.end, self.values)
        await interaction.response.send_message("次は希望する役職を選んでな！", view=view, ephemeral=True)

class RegView(discord.ui.View):
    def __init__(self, message_id, start, end):
        super().__init__(timeout=None)
        self.add_item(DaySelect(message_id, start, end))

async def update_embed(interaction, message_id, start, end):
    embed = discord.Embed(title="⚔️ 交流戦 日程調整パネル ⚔️", description="メニューから参加日を選んでな！", color=0x00ff00)
    data = game_data.get(message_id, {})
    for d in range(start, end + 1):
        users = data.get(str(d), {})
        count = len(users)
        val = " / ".join([f"{info['name']} [{info['role']}]" for info in users.values()]) if count > 0 else "┗ (募集中)"
        embed.add_field(name=f"📅 {d}日 【{count}名】", value=val, inline=False)
    
    # チャンネルからメッセージを取得して編集
    try:
        message = await interaction.channel.fetch_message(message_id)
        await message.edit(embed=embed)
    except:
        pass

@client.tree.command(name="日程", description="パネル作成")
async def tenko(interaction: discord.Interaction, 開始日: int, 終了日: int):
    await interaction.response.send_message("パネルを設置するで！", ephemeral=True)
    embed = discord.Embed(title="⚔️ 交流戦 日程調整パネル ⚔️", description="読み込み中...", color=0x00ff00)
    msg = await interaction.channel.send(embed=embed)
    game_data[msg.id] = {str(d): {} for d in range(開始日, 終了日 + 1)}
    view = RegView(msg.id, 開始日, 終了日)
    await msg.edit(embed=embed, view=view)
    await update_embed(interaction, msg.id, 開始日, 終了日)

if __name__ == "__main__":
    keep_alive()
    TOKEN = os.getenv('DISCORD_TOKEN')
    if TOKEN:
        client.run(TOKEN)
