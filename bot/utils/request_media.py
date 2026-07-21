from aiogram import Bot


async def send_request_media(bot: Bot, chat_id: int, request: dict) -> bool:
    media_type = request.get("media_type")
    file_id = request.get("media_file_id")
    if not media_type or not file_id:
        return False

    caption = f"📎 Доказательство к заявке #{request['id']}"
    if media_type == "photo":
        await bot.send_photo(chat_id, file_id, caption=caption)
    elif media_type == "video":
        await bot.send_video(chat_id, file_id, caption=caption)
    else:
        return False

    return True
