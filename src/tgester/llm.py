# from textwrap import dedent

import chatlas as ctl

from .tg import get_unread_messages


def compile_prompt(
        scene=None,
        purpose=None,
        behaviour=None,
        examples=None,
        tools=None,
        follow_up=None
    ):
    prompt_list = [
        # Set the scene
        scene,
        # Define a purpose
        purpose,
        # Influence behavior
        behaviour,
        # Use specific examples
        examples,
        # Outline tasks: how exactly to use which tools
        tools,
        # Provide missing info
        # ...
        # Follow-up suggestions
        follow_up
    ]
    prompt = '\n\n'.join(p for p in prompt_list if p)
    return prompt


# summary_agent_prompt = compile_prompt(
#     scene = 'You are a news analyst.',
#     purpose = 'You will be asked to summarise news from several Telegram channels.',
#     behaviour = dedent('''
#     Your job is to provide an analytical news summary: group the news by major
#     topics (across the sources) and give a concise summary accurately describing
#     each topic based on corresponding news.  It's best to omit as few stories as
#     possible.  Aim at 15+ minute reading.

#     There will be some not-so-serious news pieces too - don't hesitate to summarise
#     them.

#     For Munich-related news, ignore weather & traffic reports completely.

#     Once again, consider all the topics. E.g. local Munich news are only slightly
#     less important than the global political / macroeconomic news.  Rather than
#     skipping "minor" news pieces, consider grouping them somehow, even if they
#     do not fit the standard news sections.  Listing many (10+) stories under one
#     section is perfectly fine.

#     At the very end, provide the summary statistics: which channels were sourced,
#     how many news stories processed, etc.

#     The source language is Russian. The summary must be in Russian as well.

#     Format the report as Markdown, suitable for rendering.
#     ''').strip(),
#     tools = dedent('''
#     To get the news stories you can use the `self.get_unread_messages()` tool.
#     ''').strip(),
#     follow_up = 'Do not suggest any further analysis.'
# )


summary_agent_prompt = """
## Role
You are a professional news analyst specialising in summarising news from various sources.

## Task
Analyze and summarize news from multiple Telegram channels, creating a
comprehensive analytical report using Markdown syntax.

## Output Requirements
1. Group news by major topics (across all sources)
2. Provide accurate summaries for each topic
3. Include lighter/entertainment news as well
4. For Munich news: skip weather and traffic
5. Aim for 15+ minute reading time
6. Include 10+ stories per section when appropriate - omit as few stories as possible
7. Unrelated stories should go on their own lines, perhaps using markdown bullets.
   Do not mix them in the same paragraph.
8. Provide the Statistics section at the end, which includes the story count per
   channel and in total, date range, etc).
9. Do not echo your intentions, start with the analysis right away, i.e. do not
   add "I'll retrieve and analyze the unread news..." at the very beginning.
10. Use emojis if appropriate
11. Consider all topics equally (local news are as important as global)

## Language
- Input: Russian
- Output: Russian
""".strip()


class NewsSummaryAgent:
    def __init__(self, client, model_id='claude-sonnet-4-20250514'):
        self.client = client
        self.chat = ctl.ChatAnthropic(
            system_prompt=summary_agent_prompt,
            model=model_id
        )
        self.chat.register_tool(self.get_unread_messages)

    async def get_unread_messages(
            self,
            channels: list[str],
            target_tz: str ='Europe/Moscow',
            mark_read: bool = False
        ) -> dict[str, dict[str, str]]:
        '''
        Get unread messages from specified Telegram channels for 1 day period.

        Parameters
        ----------
        channel_names
            List of channel names to retrieve messages from
        target_tz
            The timezone for determining date boundaries
        mark_read
            Whether to mark retrieved messages as read

        Returns
        -------
            Mapping of channel names to dicts of messages,
            {timestamp: message content}

        Examples
        --------
        >>> unread_news = await self.get_unread_messages(['channel1', 'channel2'])
        >>> next(iter(unread_news['channel1'].items()))
        ('2025-04-14 16:37:18',
        'Lorem ipsum <...>')
        '''
        unread_messages = await get_unread_messages(self.client, channels, target_tz, mark_read)
        return unread_messages

    async def create_daily_summary(self, channels, mark_read=False, echo='none'):
        query = f'Please summarise unread news for 1 day from the following channels: {", ".join(channels)}'
        if mark_read:
            query += '. Mark messages as read: `mark_read` must be set to `True`'
        else:
            query += '. Do not mark messages as read: `mark_read` must be set to `False`.'
        response = self.chat.chat_async(
            query,
            stream=False,
            echo=echo
        )
        response = await response
        return response

    def __getattr__(self, name):
        return getattr(self.chat, name)

