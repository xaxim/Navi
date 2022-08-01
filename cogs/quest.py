# quest.py

from datetime import datetime, timedelta
import re

import discord
from discord.ext import commands

from database import cooldowns, clans, errors, reminders, users
from resources import emojis, exceptions, functions, settings, strings


class QuestCog(commands.Cog):
    """Cog that contains the quest detection commands"""
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Runs when a message is sent in a channel."""
        if message.author.id != settings.EPIC_RPG_ID: return

        if message.embeds:
            embed: discord.Embed = message.embeds[0]
            message_author = message_title = message_description = icon_url = field_value = ''
            if embed.author:
                message_author = str(embed.author.name)
                icon_url = embed.author.icon_url
            if embed.fields:
                field_value = embed.fields[0].value
            if embed.title: message_title = str(embed.title)
            if embed.description: message_description = embed.description

            # Guild quest check
            search_strings_guild_raid = [
                'do a guild raid', #English
                'has un guild raid', #Spanish
                'faça uma guild raid', #Portuguese
            ]
            search_strings_quest = [
                'are you looking for a quest', #English
                'buscando una misión', #Spanish
                'procurando uma missão', #Portuguese
            ]
            if (any(search_string in field_value.lower() for search_string in search_strings_guild_raid)
                and any(search_string in message_description.lower() for search_string in search_strings_quest)):
                user_id = user_name = None
                user = await functions.get_interaction_user(message)
                if user is None:
                    user_id_match = re.search(strings.REGEX_USER_ID_FROM_ICON_URL, icon_url)
                    if user_id_match:
                        user_id = int(user_id_match.group(1))
                    else:
                        user_name_match = re.search(strings.REGEX_USERNAME_FROM_EMBED_AUTHOR, message_author)
                        if user_name_match:
                            user_name = await functions.encode_text(user_name_match.group(1))
                        else:
                            await functions.add_warning_reaction(message)
                            await errors.log_error('User not found in guild quest message.', message)
                            return
                    if user_id is not None:
                        user = await message.guild.fetch_member(user_id)
                    else:
                        user = await functions.get_guild_member_by_name(message.guild, user_name)
                if user is None:
                    await functions.add_warning_reaction(message)
                    await errors.log_error('User not found in guild quest message.', message)
                    return
                try:
                    user_settings: users.User = await users.get_user(user.id)
                except exceptions.FirstTimeUserError:
                    return
                try:
                    clan: clans.Clan = await clans.get_clan_by_clan_name(user_settings.clan_name)
                except exceptions.NoDataFoundError:
                    return
                if not user_settings.bot_enabled or not user_settings.alert_quest.enabled: return
                if not clan.alert_enabled: return
                await user_settings.update(last_quest_command='quest')
                if clan.stealth_current < clan.stealth_threshold and not clan.upgrade_quests_enabled:
                    await message.reply(
                        f'{emojis.ERROR} Guild quest spot not available.\n'
                        f'Your guild doesn\'t allow doing guild quests below the '
                        f'stealth threshold ({clan.stealth_threshold}).'
                    )
                    return
                if clan.quest_user_id is not None:
                    await message.reply(
                        f'{emojis.ERROR} Guild quest spot not available.\n'
                        f'Another guild member is already doing a guild quest.'
                    )
                    return
                await user_settings.update(guild_quest_prompt_active=True)
                await message.reply(
                    f'{emojis.CHECK} Guild quest spot available.\n'
                    f'If you accept this quest, the next guild reminder will ping you solo first. '
                    f'You will have 5 minutes to raid before the other members are pinged.\n'
                    f'Note that you will lose your spot if you don\'t answer in time.'
                )

            # Quest cooldown
            search_strings = [
                'you have already claimed a quest', #English
                'ya reclamaste una misión', #Spanish
                'você já reivindicou uma missão', #Portuguese
            ]
            if any(search_string in message_title.lower() for search_string in search_strings):
                user_id = user_name = user_command = None
                user = await functions.get_interaction_user(message)
                slash_command = True if user is not None else False
                if user is None:
                    user_id_match = re.search(strings.REGEX_USER_ID_FROM_ICON_URL, icon_url)
                    if user_id_match:
                        user_id = int(user_id_match.group(1))
                    else:
                        user_name_match = re.search(strings.REGEX_USERNAME_FROM_EMBED_AUTHOR, message_author)
                        if user_name_match:
                            user_name = await functions.encode_text(user_name_match.group(1))
                        else:
                            await functions.add_warning_reaction(message)
                            await errors.log_error('User not found in quest cooldown message.', message)
                            return
                    if user_id is not None:
                        user = await message.guild.fetch_member(user_id)
                    else:
                        user = await functions.get_guild_member_by_name(message.guild, user_name)
                if user is None:
                    await functions.add_warning_reaction(message)
                    await errors.log_error('User not found in quest cooldown message.', message)
                    return
                try:
                    user_settings: users.User = await users.get_user(user.id)
                except exceptions.FirstTimeUserError:
                    return
                if not user_settings.bot_enabled or not user_settings.alert_quest.enabled: return
                if slash_command:
                    interaction = await functions.get_interaction(message)
                    if interaction.name.startswith('quest'):
                        user_command = strings.SLASH_COMMANDS['quest']
                        last_quest_command = 'quest'
                    else:
                        user_command = strings.SLASH_COMMANDS['epic quest']
                        last_quest_command = 'epic quest'
                else:
                    user_command_message, user_command = (
                        await functions.get_message_from_channel_history(
                            message.channel, r"^rpg\s+(?:epic\b\s+)?quest\b", user
                        )
                    )
                    if user_command_message is None:
                        await functions.add_warning_reaction(message)
                        await errors.log_error('Couldn\'t find a command for the quest cooldown message.', message)
                        return
                    last_quest_command = 'quest' if 'epic' not in user_command else 'epic quest'
                await user_settings.update(last_quest_command=last_quest_command)
                timestring_match = await functions.get_match_from_patterns(strings.PATTERNS_COOLDOWN_TIMESTRING,
                                                                           message_title)
                if not timestring_match:
                    await functions.add_warning_reaction(message)
                    await errors.log_error('Timestring not found in quest cooldown message.', message)
                    return
                timestring = timestring_match.group(1)
                time_left = await functions.calculate_time_left_from_timestring(message, timestring)
                reminder_message = user_settings.alert_quest.message.replace('{command}', user_command)
                reminder: reminders.Reminder = (
                    await reminders.insert_user_reminder(user.id, 'quest', time_left,
                                                         message.channel.id, reminder_message)
                )
                await functions.add_reminder_reaction(message, reminder, user_settings)

            # Quest in void areas
            search_strings = [
                'i don\'t think i can give you any quest here', #English
                'misión aquí', #Spanish
                'missão aqui', #Portuguese, UNCONFIRMED
            ]
            if any(search_string in message_description.lower() for search_string in search_strings):
                user = await functions.get_interaction_user(message)
                user_command = strings.SLASH_COMMANDS['quest'] if user is not None else '`rpg quest`'
                if user is None:
                    user_id_match = re.search(strings.REGEX_USER_ID_FROM_ICON_URL, icon_url)
                    if user_id_match:
                        user_id = int(user_id_match.group(1))
                    else:
                        user_name_match = re.search(strings.REGEX_USERNAME_FROM_EMBED_AUTHOR, message_author)
                        if user_name_match:
                            user_name = await functions.encode_text(user_name_match.group(1))
                        else:
                            await functions.add_warning_reaction(message)
                            await errors.log_error('User not found in void quest message.', message)
                            return
                    if user_id is not None:
                        user = await message.guild.fetch_member(user_id)
                    else:
                        user = await functions.get_guild_member_by_name(message.guild, user_name)
                if user is None:
                    await functions.add_warning_reaction(message)
                    await errors.log_error('User not found in void quest message.', message)
                    return
                try:
                    user_settings: users.User = await users.get_user(user.id)
                except exceptions.FirstTimeUserError:
                    return
                if not user_settings.bot_enabled or not user_settings.alert_quest.enabled: return
                await user_settings.update(last_quest_command='quest')
                time_left = await functions.calculate_time_left_from_cooldown(message, user_settings, 'quest')
                reminder_message = user_settings.alert_quest.message.replace('{command}', user_command)
                reminder: reminders.Reminder = (
                    await reminders.insert_user_reminder(user.id, 'quest', time_left,
                                                         message.channel.id, reminder_message)
                )
                await functions.add_reminder_reaction(message, reminder, user_settings)

            # Epic Quest
            search_strings = [
                '__wave #1__', #English
                '__oleada #1__', #Spanish
                '__onda #1__', #Portuguese
            ]
            if any(search_string in message_description.lower() for search_string in search_strings):
                user_id = user_name = None
                user = await functions.get_interaction_user(message)
                user_command = strings.SLASH_COMMANDS['epic quest'] if user is not None else '`rpg epic quest`'
                if user is None:
                    user_id_match = re.search(strings.REGEX_USER_ID_FROM_ICON_URL, icon_url)
                    if user_id_match:
                        user_id = int(user_id_match.group(1))
                    else:
                        user_name_match = re.search(strings.REGEX_USERNAME_FROM_EMBED_AUTHOR, message_author)
                        if user_name_match:
                            user_name = await functions.encode_text(user_name_match.group(1))
                        else:
                            await functions.add_warning_reaction(message)
                            await errors.log_error('User not found in epic quest message.', message)
                            return
                    if user_id is not None:
                        user = await message.guild.fetch_member(user_id)
                    else:
                        for member in message.guild.members:
                            member_name = await functions.encode_text(member.name)
                            if member_name == user_name:
                                user = member
                                break
                if user is None:
                    await functions.add_warning_reaction(message)
                    await errors.log_error('User not found in epic quest message.', message)
                    return
                try:
                    user_settings: users.User = await users.get_user(user.id)
                except exceptions.FirstTimeUserError:
                    return
                if not user_settings.bot_enabled or not user_settings.alert_quest.enabled: return
                await user_settings.update(last_quest_command='epic quest')
                current_time = datetime.utcnow().replace(microsecond=0)
                bot_answer_time = message.created_at.replace(microsecond=0, tzinfo=None)
                time_elapsed = current_time - bot_answer_time
                cooldown: cooldowns.Cooldown = await cooldowns.get_cooldown('quest')
                user_donor_tier = 3 if user_settings.user_donor_tier > 3 else user_settings.user_donor_tier
                if cooldown.donor_affected:
                    time_left_seconds = (cooldown.actual_cooldown()
                                        * settings.DONOR_COOLDOWNS[user_donor_tier]
                                        - time_elapsed.total_seconds())
                else:
                    time_left_seconds = cooldown.actual_cooldown() - time_elapsed.total_seconds()
                time_left = timedelta(seconds=time_left_seconds)
                reminder_message = user_settings.alert_quest.message.replace('{command}', user_command)
                reminder: reminders.Reminder = (
                    await reminders.insert_user_reminder(user.id, 'quest', time_left,
                                                         message.channel.id, reminder_message)
                )
                if reminder.record_exists:
                    if user_settings.reactions_enabled: await message.add_reaction(emojis.NAVI)
                else:
                    if settings.DEBUG_MODE: await message.channel.send(strings.MSG_ERROR)

        if not message.embeds:
            message_content = message.content
            # Quest
            search_strings = [
                'got a **new quest**!', #English accepted
                'you did not accept the quest', #English declined
                'consiguió una **nueva misión**', #Spanish accepted
                'no aceptaste la misión', #Spanish declined
                'conseguiu uma **nova missão**', #Portuguese accepted
                'você não aceitou a missão', #Portuguese declined
            ]
            if any(search_string in message_content.lower() for search_string in search_strings):
                user_name = None
                user = await functions.get_interaction_user(message)
                user_command = strings.SLASH_COMMANDS['quest'] if user is not None else '`rpg quest`'
                if user is None:
                    if message.mentions:
                        user = message.mentions[0]
                    else:
                        user_name_match = re.search(strings.REGEX_NAME_FROM_MESSAGE_START, message_content)
                        if user_name_match:
                            user_name = await functions.encode_text(user_name_match.group(1))
                        else:
                            await functions.add_warning_reaction(message)
                            await errors.log_error('User not found in quest message.', message)
                            return
                        for member in message.guild.members:
                            member_name = await functions.encode_text(member.name)
                            if member_name == user_name:
                                user = member
                                break
                if user is None:
                    await functions.add_warning_reaction(message)
                    await errors.log_error('User not found in quest message.', message)
                    return
                quest_declined = True if message.mentions else False
                try:
                    user_settings: users.User = await users.get_user(user.id)
                except exceptions.FirstTimeUserError:
                    return
                if not user_settings.bot_enabled or not user_settings.alert_quest.enabled: return
                await user_settings.update(last_quest_command='quest')
                current_time = datetime.utcnow().replace(microsecond=0)
                bot_answer_time = message.created_at.replace(microsecond=0, tzinfo=None)
                time_elapsed = current_time - bot_answer_time
                if quest_declined:
                    time_left = timedelta(hours=1)
                else:
                    cooldown: cooldowns.Cooldown = await cooldowns.get_cooldown('quest')
                    user_donor_tier = 3 if user_settings.user_donor_tier > 3 else user_settings.user_donor_tier
                    if cooldown.donor_affected:
                        time_left_seconds = (cooldown.actual_cooldown()
                                            * settings.DONOR_COOLDOWNS[user_donor_tier]
                                            - time_elapsed.total_seconds())
                    else:
                        time_left_seconds = cooldown.actual_cooldown() - time_elapsed.total_seconds()
                    time_left = timedelta(seconds=time_left_seconds)
                reminder_message = user_settings.alert_quest.message.replace('{command}', user_command)
                reminder: reminders.Reminder = (
                    await reminders.insert_user_reminder(user.id, 'quest', time_left,
                                                         message.channel.id, reminder_message)
                )
                if user_settings.guild_quest_prompt_active:
                    if not quest_declined:
                        try:
                            clan: clans.Clan = await clans.get_clan_by_clan_name(user_settings.clan_name)
                            await clan.update(quest_user_id=user.id)
                        except exceptions.NoDataFoundError:
                            pass
                    await user_settings.update(guild_quest_prompt_active=False)
                if reminder.record_exists:
                    if user_settings.reactions_enabled: await message.add_reaction(emojis.NAVI)
                else:
                    if settings.DEBUG_MODE: await message.channel.send(strings.MSG_ERROR)

            # Aborted guild quest
            search_strings = [
                'you don\'t have a quest anymore', #English
                'ya no tienes una misión', #Spanish
                'você não tem mais uma missão', #Portuguese
            ]
            if any(search_string in message_content.lower() for search_string in search_strings) and message.mentions:
                user = message.mentions[0]
                try:
                    user_settings: users.User = await users.get_user(user.id)
                except exceptions.FirstTimeUserError:
                    return
                try:
                    clan: clans.Clan = await clans.get_clan_by_user_id(user.id)
                except exceptions.NoDataFoundError:
                    return
                if clan.quest_user_id is not None:
                    if clan.quest_user_id == user.id:
                        await clan.update(quest_user_id=None)
                        if user_settings.reactions_enabled: await message.add_reaction(emojis.NAVI)


# Initialization
def setup(bot):
    bot.add_cog(QuestCog(bot))