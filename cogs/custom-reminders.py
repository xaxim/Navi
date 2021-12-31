# custom-reminders.py

from discord.ext import commands

from database import reminders, users
from resources import emojis, exceptions, functions, strings


class CustomRemindersCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    """Cog that contains custom reminder commands"""
    # --- Commands ---
    # rm
    @commands.group(aliases=('rm','remind',), invoke_without_command=True)
    @commands.bot_has_permissions(send_messages=True)
    async def reminder(self, ctx: commands.Context, *args: str) -> None:
        """Sets custom reminders"""
        prefix = ctx.prefix
        if prefix.lower() == 'rpg ': return
        syntax_add = (
            f'The syntax is `{prefix}rm [time] [text]`\n'
            f'Support time codes: `w`, `d`, `h`, `m`, `s`\n\n'
            f'Example: `{prefix}rm 1h30m Coffee time!`'
        )
        syntax_delete = (
            f'The syntax is `{prefix}rm delete [ID]`\n'
            f'You can find the ID with `{prefix}list`\n\n'
            f'Example: `{prefix}rm delete 3`'
        )
        error_max_time = 'The maximum time is 4w6d23h59m59s.'

        if not args:
            await ctx.reply(
                f'This command lets you manage custom reminders.\n\n'
                f'**Adding reminders**\n'
                f'{syntax_add}\n\n'
                f'**Deleting reminders**\n'
                f'{syntax_delete}',
                mention_author=False
            )
            return
        user: users.User = await users.get_user(ctx.author.id) # To stop if user is not registered
        args = [arg.lower() for arg in args]
        timestring = args[0]
        try:
            timestring = await functions.check_timestring(timestring)
        except Exception as error:
            await ctx.reply(f'{error}\n{syntax_add}', mention_author=False)
            return
        time_left = await functions.parse_timestring_to_timedelta(ctx, timestring)
        reminder_text = ''
        if len(args) > 1:
            args = list(args)
            args.pop(0)
            for arg in args:
                reminder_text = f'{reminder_text} {arg}'
        else:
            reminder_text = 'idk, something?'
        reminder_text = reminder_text.strip()
        reminder_text = strings.DEFAULT_MESSAGE_CUSTOM_REMINDER.replace('%', reminder_text)
        if time_left.total_seconds() > 3_023_999:
            await ctx.reply(error_max_time, mention_author=False)
            return
        reminder: reminders.Reminder = (
            await reminders.insert_user_reminder(ctx.author.id, 'custom', time_left,
                                                    ctx.channel.id, reminder_text)
        )
        if reminder.record_exists:
            await ctx.message.add_reaction(emojis.NAVI)
        else:
            await ctx.reply(strings.MSG_ERROR, mention_author=False)

    @reminder.command(name='delete', aliases=('del','remove'), invoke_without_command=True)
    @commands.bot_has_permissions(send_messages=True)
    async def reminder_delete(self, ctx: commands.Context, *args: str) -> None:
        """Sets custom reminders"""
        prefix = ctx.prefix
        if prefix.lower() == 'rpg ': return
        syntax_delete = (
            f'The syntax is `{prefix}rm delete [ID]`\n'
            f'You can find the ID with `{prefix}list`\n\n'
            f'Example: `{prefix}rm delete 3`'
        )
        error_invalid_message_id = (
            f'Invalid message ID.\n\n'
            f'{syntax_delete}'
        )
        if not args or len(args) > 1:
            await ctx.reply(syntax_delete, mention_author=False)
            return
        try:
            reminder_id = int(args[0])
        except:
            await ctx.reply(error_invalid_message_id, mention_author=False)
            return
        if reminder_id < 1:
            await ctx.reply(error_invalid_message_id, mention_author=False)
            return
        try:
            reminder: reminders.Reminder = await reminders.get_user_reminder(ctx.author.id, 'custom', reminder_id)
        except exceptions.NoDataFoundError:
            await ctx.reply('There is no custom reminder with that ID.', mention_author=False)
            return
        await reminder.delete()
        if not reminder.record_exists:
            await ctx.message.add_reaction(emojis.NAVI)
        else:
            await ctx.reply('There was an error deleting the reminder, RIP.', mention_author=False)


# Initialization
def setup(bot):
    bot.add_cog(CustomRemindersCog(bot))