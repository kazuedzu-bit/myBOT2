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

# データを一時的に保持（再起動でリセットされますが、Renderなら24時間保持されます）
# 本格的な保存が必要ならDBが必要ですが、まずはこれで爆速運用！
game_data = {} # {message_id: {day: {user_id: {"name": str, "role": str}}}}

class RegistrationModal(discord.ui.Modal, title='交流戦 参加・役職登録'):
    def __init__(self, message_id, start_day, end_day):
        super().__init__()
        self.message_id = message_id
        self.start_day = start_day
        self.end_day = end_day
        
        self.days_input = discord.ui.TextInput(
            label=f'参加できる日（{start_day}〜{end_day}の数字を半角カンマ区切り）',
            placeholder='例: 1,3,5 (行けない場合は空欄)',
            required=False
        )
        self.add_item(self.days_input)

        self.role_input = discord.ui.TextInput(
            label='メイン役職（AT / GT / DF / ANY）',
            placeholder='例: AT',
            min_length=2,
            max_length=3,
            required=True
        )
        self.add_item(self.role_input)

    async def on_submit(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        user_name = interaction.user.display_name
        selected_days = [d.strip() for d in self.days_input.value.split(',') if d.strip().isdigit()]
        role = self.role_input.value.upper()

        if role not in ["AT", "GT", "DF", "ANY"]:
            await interaction.response.send_message("役職は AT, GT, DF, ANY のいずれかで入力してな！", ephemeral=True)
            return

        # 既存データをクリアして更新
        if self.message_id not in game_data:
            game_data[self.message_id] = {str(d): {} for d in range(self.start_day, self.end_day + 1)}
        
        # 一旦そのユーザーの全日程の登録を削除
        for d in game_data[self.message_id]:
            game_data[self.message_id][d].pop(user_id, None)

        # 選択された日に登録
        for d in selected_days:
            if d in game_data[self.message_id]:
                game_data[self.message_id][d][user_id] = {"name": user_name, "role": role}

        await update_embed(interaction, self.message_id, self.start_day, self.end_day)
        await interaction.response.send_message("登録完了したで！", ephemeral=True)

async def update_embed(interaction, message_id, start, end):
    embed = discord.Embed(title="🛡️ 交流戦 参加希望・日程調整 ⚔️", color=0x00ff00)
    embed.description = f"**【募集期間：{start}日 〜 {end}日】**\n下のボタンから「参加日」と「役職」を登録してな！"

    data = game_data[message_id]
    for d in range(start, end + 1):
        day_str = str(d)
        users = data.get(day_str, {})
        count = len(users)
        
        if count > 0:
            user_list = " / ".join([f"{info['name']} [{info['role']}]" for info in users.values()])
            val = f"┣ {user_list}"
        else:
            val = "┗ (まだ誰もいません)"
        
        embed.add_field(name=f"📅 {d}日 【参加：{count}名】", value=val, inline=False)

    message = await interaction.channel.fetch_message(message_id)
    await message.edit(embed=embed)

class RegButton(discord.ui.View):
    def __init__(self, message_id, start, end):
        super().__init__(timeout=None)
        self.message_id = message_id
        self.start = start
        self.end = end

    @discord.ui.button(label="📝 参加・役職を登録", style=discord.ButtonStyle.primary, custom_id="reg_btn")
    async def register(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RegistrationModal(self.message_id, self.start, self.end))

@client.tree.command(name="koryusen_tenko", description="交流戦の日程点呼パネルを作成します")
async def koryusen_tenko(interaction: discord.Interaction, start: int, end: int):
    if start > end:
        await interaction.response.send_message("開始日は終了日より前にしてな！", ephemeral=True)
        return

    embed = discord.Embed(title="🛡️ 交流戦 参加希望・日程調整 ⚔️", color=0x00ff00)
    embed.description = f"**【募集期間：{start}日 〜 {end}日】**\n下のボタンから「参加日」と「役職」を登録してな！"
    
    for d in range(start, end + 1):
        embed.add_field(name=f"📅 {d}日 【参加：0名】", value="┗ (まだ誰もいません)", inline=False)

    await interaction.response.send_message("作成中...", ephemeral=True)
    msg = await interaction.channel.send(embed=embed)
    
    # データを初期化
    game_data[msg.id] = {str(d): {} for d in range(start, end + 1)}
    
    # ボタン付きに更新
    view = RegButton(msg.id, start, end)
    await msg.edit(view=view)

client.run(TOKEN)
