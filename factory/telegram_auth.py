from telethon import TelegramClient
from telethon.sessions import StringSession


async def request_code(api_id, api_hash, phone):
    client = TelegramClient(
        StringSession(),
        api_id,
        api_hash,
    )

    await client.connect()

    result = await client.send_code_request(phone)

    session_seed = client.session.save()

    await client.disconnect()

    return session_seed, result.phone_code_hash


async def finish_code(
    api_id,
    api_hash,
    phone,
    code,
    session_seed,
    phone_code_hash,
):
    client = TelegramClient(
        StringSession(session_seed),
        api_id,
        api_hash,
    )

    await client.connect()

    try:
        await client.sign_in(
            phone=phone,
            code=code,
            phone_code_hash=phone_code_hash,
        )
    except Exception:
        raise

    session = client.session.save()

    await client.disconnect()

    return session


async def finish_password(
    api_id,
    api_hash,
    session_seed,
    password,
):
    client = TelegramClient(
        StringSession(session_seed),
        api_id,
        api_hash,
    )

    await client.connect()

    await client.sign_in(password=password)

    session = client.session.save()

    await client.disconnect()

    return session
