from datetime import UTC, timedelta
from zoneinfo import ZoneInfo

from markdown import markdown
from telegraph import Telegraph
from telegraph.utils import html_to_nodes
from telethon.tl.functions.messages import GetPeerDialogsRequest


async def get_unread_messages(
        client,
        channels,
        target_tz='Europe/Moscow',
        mark_read=False
    ):
    target_tz = ZoneInfo(target_tz)
    messages = {}
    async with client:
        earliest_unread_dt = await find_earliest_unread_dt(client, channels)
        next_day_dt = get_next_day_dt(earliest_unread_dt, target_tz)
        for channel_name in channels:
            messages[channel_name] = await get_unread_channel_messages(
                client,
                channel_name,
                next_day_dt,
                target_tz,
                mark_read
            )
    return messages


async def find_earliest_unread_dt(client, channels):
    """Find the date-time of the earliest unread message across a list of channels"""
    earliest_unread_dt = None
    for channel_name in channels:
        # print(channel_name)
        channel = await client.get_entity(channel_name)
        dialogs = await client(GetPeerDialogsRequest(peers=[channel]))
        dialog = dialogs.dialogs[0]

        if dialog.unread_count == 0:
            continue

        # Get first unread message
        messages = await client.get_messages(
            channel,
            min_id=dialog.read_inbox_max_id,
            reverse=True,
            limit=1
        )
        if messages:
            message_dt = messages[0].date
            if earliest_unread_dt is None or message_dt < earliest_unread_dt:
                earliest_unread_dt = message_dt
    return earliest_unread_dt


def get_next_day_dt(dt, target_tz):
    next_day_dt = (
        dt
        .astimezone(target_tz)
        .replace(hour=0, minute=0, second=0)
        + timedelta(days=1)
    ).astimezone(UTC)
    return next_day_dt


async def get_unread_channel_messages(client, channel_name, offset_date, target_tz, mark_read=False):
    channel = await client.get_entity(channel_name)
    dialogs = await client(GetPeerDialogsRequest(peers=[channel]))
    dialog = dialogs.dialogs[0]

    first_id = None
    unread_messages = {}

    async for message in client.iter_messages(
            channel,
            offset_date=offset_date,
            min_id=dialog.read_inbox_max_id,
            limit=1000
        ):
        msg_dt_str = message.date.astimezone(target_tz).strftime(r'%Y-%m-%d %H:%M:%S')
        msg_body = message.message or '[Media]'
        unread_messages[msg_dt_str] = msg_body
        if first_id is None:
            first_id = message.id

    if mark_read and first_id:
        await client.send_read_acknowledge(channel, max_id=first_id)

    unread_messages = dict(reversed(unread_messages.items()))

    return unread_messages


def publish_summary(news_summary_content, access_token, author_name='News Summary Agent'):
    telegraph = Telegraph(access_token=access_token)
    title, _, content = news_summary_content.replace('## ', '### ').lstrip('\n').partition('\n')
    title = title.strip('# ')
    content = content.lstrip('\n')
    nodes = html_to_nodes(markdown(content))
    response = telegraph.create_page(
        title=title,
        content=nodes,
        author_name=author_name,
        return_content=False
    )
    return response


async def fast_forward(client, channels, ff_to_date):
    async with client:
        for channel_name in channels:
            channel = await client.get_entity(channel_name)
            message = await client.get_messages(
                channel,
                offset_date=ff_to_date,
                limit=1
            )
            await client.send_read_acknowledge(channel, max_id=message[0].id)
