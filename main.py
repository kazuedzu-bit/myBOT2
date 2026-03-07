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
        print("✅ 全コマンドの同期が完了しました")

client = MyClient()
game_data = {} 
detail_data = {} 

# --- 役職選択 ＆ 解除ボタン ---
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

        for d in game_data[self.message_id]:
            game_data[self.message_id][d].pop(user_id, None)

        for d in self.selected_days:
            if d in game_data[self.message_id]:
                game_data[self.message_id][d][user_id] = {"name": user_name, "role": role}

        await update_embed(interaction, self.message_id, self.start, self.end)
        await interaction.response.edit_message(content=f"✅ **更新完了！** {', '.join(self.selected_days)}日を【**{role}**】で登録したで。", view=None)

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

    @discord.ui.button(label="登録解除", style=discord.ButtonStyle.gray)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        for d in game_data.get(self.message_id, {}):
            game_data[self.message_id][d].pop(user_id, None)
        await update_embed(interaction, self.message_id, self.start, self.end)
        await interaction.response.edit_message(content="✅ **登録を解除したで！**", view=None)

# --- 詳細表示メニュー（絵文字を整理） ---
class DetailMemberView(discord.ui.View):
    def __init__(self, message_id, start, end):
        super().__init__(timeout=60)
        options = [discord.SelectOption(label=f"{d}日の詳細を確認", value=str(d)) for d in range(start, end + 1)]
        self.select = discord.ui.Select(placeholder="知りたい日を選んでな", options=options)
        self.select.callback = self.callback
        self.add_item(self.select)
        self.message_id = message_id

    async def callback(self, interaction: discord.Interaction):
        day = self.values[0]
        d = detail_data.get(self.message_id, {}).get(day, {})
        users = game_data.get(self.message_id, {}).get(day, {})
        member_list = "\n".join([f"・**{i['name']}** [{i['role']}]" for i in users.values()]) if users else "・(まだ参加者はおらんよ)"
        
        # 指定された絵文字以外を削除
        text = f"**{day}日の交流戦 詳細情報**\n"
        text += f"━━━━━━━━━━━━━━━\n"
        text += f"**日付・時間**: {d.get('time', '未定')}\n"
        text += f"**ルール**: {d.get('rule', '未定')}\n"
        text += f"**ステージ**: {d.get('stage', '未定')}\n"
        text += f"**対戦相手**: {d.get('opponent', '募集中')}\n\n"
        text += f"☀️ **サンズ**: {d.get('suns', '-')}\n" # 残す
        text += f"🌊 **オーシャン**: {d.get('ocean', '-')}\n\n" # 残す
        text += f"🔑 **ルーム作成 ID**: {d.get('room_id', '未定')}\n" # 残す
        text += f"**一言**: {d.get('comment', '特になし')}\n"
        text += f"━━━━━━━━━━━━━━━\n"
        text += f"**参加メンバー ({len(users)}名)**:\n{member_list}"
        
        await interaction.response.edit_message(content=text, view=None)

# --- メインパネルView ---
class RegView(discord.ui.View):
    def __init__(self, message_id, start, end):
        super().__init__(timeout=None)
        self.message_id = message_id
        self.start = start
        self.end = end
        
        options = [discord.SelectOption(label=f"{d}日", value=str(d)) for d in range(start, end + 1)]
        self.select = discord.ui.Select(
            placeholder="参加できる日をまとめて選択（複数OK）",
            min_values=1, max_values=len(options),
            options=options, custom_id=f"sel_{message_id}"
        )
        self.select.callback = self.select_callback
        self.add_item(self.select)

    async def select_callback(self, interaction: discord.Interaction):
        view = RoleButtonView(self.message_id, self.start, self.end, self.select.values)
        await interaction.response.send_message("💡 **希望する役職を選んでな！**", view=view, ephemeral=True)

    @discord.ui.button(label="メンバー/詳細を確認", style=discord.ButtonStyle.secondary, custom_id="btn_detail")
    async def show_detail(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = DetailMemberView(self.message_id, self.start, self.end)
        await interaction.response.send_message("💬 **どの日の詳細・メンバーを確認する？**", view=view, ephemeral=True)

# --- 埋め込み更新（絵文字整理） ---
async def update_embed(interaction, message_id, start, end):
    embed = discord.Embed(title="**交流戦 日程調整パネル**", description="下のメニューから参加日を選んでな！", color=0x00ff00)
    data = game_data.get(message_id, {})
    for d in range(start, end + 1):
        users = data.get(str(d), {})
        count = len(users)
        val = " / ".join([f"**{i['name']}**[{i['role']}]" for i in users.values()]) if count > 0 else "┗ (募集中)"
        embed.add_field(name=f"**{d}日** 【**{count}名**】", value=val, inline=False)
    
    try:
        message = await interaction.channel.fetch_message(message_id)
        await message.edit(embed=embed)
    except: pass

# --- コマンド（絵文字整理） ---
@client.tree.command(name="日程", description="交流戦パネルを作成します")
async def tenko(interaction: discord.Interaction, 開始日: int, 終了日: int):
    await interaction.response.send_message("設置中...", ephemeral=True)
    msg = await interaction.channel.send(embed=discord.Embed(title="読み込み中..."))
    game_data[msg.id] = {str(d): {} for d in range(開始日, 終了日 + 1)}
    await msg.edit(embed=None, view=RegView(msg.id, 開始日, 終了日))
    await update_embed(interaction, msg.id, 開始日, 終了日)

@client.tree.command(name="日程詳細", description="特定の日程に詳しい情報を追加します")
async def set_full_detail(interaction: discord.Interaction, パネルid: str, 日にち: int, 時間: str="", ルール: str="", ステージ: str="", 対戦相手: str="", サンズ: str="", オーシャン: str="", ルームid: str="", 一言: str=""):
    try:
        m_id = int(パネルid)
        if m_id not in detail_data: detail_data[m_id] = {}
        detail_data[m_id][str(日にち)] = {
            "time": 時間, "rule": ルール, "stage": ステージ,
            "opponent": 対戦相手, "suns": サンズ, "ocean": オーシャン,
            "room_id": ルームid, "comment": 一言
        }
        await interaction.response.send_message(f"✅ **{日にち}日の詳細を保存したで！**", ephemeral=True)
    except:
        await interaction.response.send_message("❌ **エラー：パネルIDを正しく入力してな！**", ephemeral=True)

if __name__ == "__main__":
    keep_alive()
    client.run(os.getenv('DISCORD_TOKEN'))
